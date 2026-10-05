# -*- coding: utf-8 -*-
"""L'application FastAPI de Mizan. Du câblage, et rien que du câblage.

    uvicorn service.app:app --host 0.0.0.0 --port 7860
    python -m service.app        (équivalent, pour un essai local)

CONVENTION FIXÉE, que le `Dockerfile` suppose : l'application s'appelle `app`,
elle vit dans `service/app.py`, elle écoute le port **7860** (celui que
Hugging Face attend), et l'interface statique est servie depuis
`service/statique/`.

CE QUI N'EST PAS DANS CE FICHIER, ET POURQUOI
--------------------------------------------
La forme du JSON, la limite de longueur, le compteur de débit, la traduction
des pannes et l'état du service sont dans `contrat.py` et `chargement.py`, qui
n'importent pas `fastapi`. Il ne reste ici que les décorateurs, les codes de
statut et le montage des fichiers. Ce n'est pas un rangement : la suite de
tests du projet tourne sur un interpréteur nu, et ce qui vit dans une fonction
de route n'y est pas vérifié.

LE PORT S'OUVRE AVANT QUE LA RECHERCHE SOIT CHARGÉE
---------------------------------------------------
`uvicorn` exécute le cycle de vie AVANT d'écouter : un chargement de plusieurs
secondes dedans retarde le port d'autant, et un contrôle de santé qui arrive
pendant ce temps déclare le Space mort (`DEPLOIEMENT.md` §4 — le même défaut a
déjà coûté une migration sur un autre projet de l'auteur). Le cycle de vie
appelle donc `chargement.demarrer()`, qui rend la main tout de suite et remplit
la recherche dans un fil. Pendant ce temps `/sante` rend 200, `/api/etat` rend
`etape = "chargement"`, et `/api/question` rend 503 avec un `Retry-After`.

TROIS CHOSES QUI NE SONT PAS DES ERREURS, ET SORTENT EN 200
-----------------------------------------------------------
  1. l'abstention de la récupération — le produit se tait et dit pourquoi ;
  2. le REJET par la garde — le modèle a écrit, la garde a refusé. C'est un
     résultat du produit, et sa raison nomme les articles fautifs. Le rendre
     en 500 cacherait la seule chose que ce projet a de remarquable ;
  3. le SIGNALEMENT d'injection — il signale, il ne bloque pas, et la réponse
     est rendue quand même, dans le même objet.

Les erreurs, elles, sont des pannes ou des appels mal formés : question vide
(400), question trop longue (413), débit dépassé (429), chargement en cours,
index ou modèle absent et fournisseur en panne (503). Chacune porte le message
du cœur, qui nomme la commande à lancer quand il y en a une.
"""
from __future__ import annotations

import math
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import noyau
from moteur import llm as module_llm

from . import chargement, contrat

DOSSIER_STATIQUE = Path(__file__).resolve().parent / "statique"


class Demande(BaseModel):
    """Le corps de `POST /api/question`.

    `question` a une valeur par défaut vide, et ce n'est pas du laxisme : sans
    elle, un corps sans la clé `question` produirait le 422 de pydantic, dont
    le message parle de `body -> question` et de `missing`. Avec elle, l'appel
    tombe dans `contrat.valider_question`, qui rend la phrase française du
    projet et montre la forme attendue. Un corps mal formé reste un 422, mais
    normalisé à la forme d'erreur du service.

    Aucune longueur maximale n'est déclarée ici, pour la même raison : la
    limite est une règle du service, elle a son code (`question_trop_longue`),
    son statut (413) et son explication.
    """

    question: str = ""


def creer_application(
    service: chargement.Service | None = None,
    limiteur: contrat.Limiteur | None = None,
) -> FastAPI:
    """Construit l'application. Le service est injectable, et c'est pour les tests.

    Quand `service` est fourni, rien n'est chargé : les tests de route tournent
    alors sans index vectoriel, sans modèle de 1,2 Go et sans clé. Quand il ne
    l'est pas, le cycle de vie appelle `chargement.demarrer()` UNE FOIS, au
    démarrage — jamais à la première question.
    """
    limiteur = limiteur or contrat.Limiteur()

    @asynccontextmanager
    async def cycle(application: FastAPI):
        if application.state.service is None:
            application.state.service, application.state.fil = (
                chargement.demarrer()
            )
        yield

    application = FastAPI(
        title="Mizan",
        description=(
            "Assistant du droit du travail marocain. Chaque réponse cite les "
            "articles sur lesquels elle s'appuie, et toute citation hors des "
            "articles récupérés fait rejeter la réponse entière. Corpus "
            "consolidé au 26 octobre 2011."
        ),
        lifespan=cycle,
    )
    application.state.service = service
    application.state.limiteur = limiteur
    application.state.fil = None

    def courant(requete: Request) -> chargement.Service:
        etabli = requete.app.state.service
        if etabli is None:  # pragma: no cover - le cycle de vie l'a construit
            raise RuntimeError(
                "Le service n'a pas été chargé : l'application a été appelée "
                "sans passer par son cycle de vie."
            )
        return etabli

    # ── Le contrat avec l'hébergeur ─────────────────────────────────────────

    @application.get("/sante")
    def sante(requete: Request) -> JSONResponse:
        """200 dès que le processus vit, MÊME PENDANT LE CHARGEMENT.

        « Le port répond » n'est pas « le moteur est chaud ». Rendre 503
        pendant le préchauffage reconstruirait exactement la panne que le
        chargement en arrière-plan existe pour éviter.
        """
        return JSONResponse(courant(requete).sante())

    # ── Les deux routes du produit ──────────────────────────────────────────

    @application.get("/api/etat")
    def etat(requete: Request) -> JSONResponse:
        """L'index est-il prêt, la rédaction est-elle factice, quelle date.

        Elle n'est pas comptée par le limiteur : elle ne cherche rien, ne
        rédige rien, et c'est la route que l'interface appelle au chargement
        de la page. La faire tomber en 429 priverait un visiteur légitime de
        la seule information qui l'avertit que la rédaction est factice.
        """
        return JSONResponse(courant(requete).etat())

    @application.post("/api/question")
    def question(requete: Request, demande: Demande) -> JSONResponse:
        """La question, les articles, et la réponse rédigée s'il y a une clé.

        Route synchrone, donc exécutée dans le vivier de fils de FastAPI : la
        recherche dense et l'appel au fournisseur bloquent, et les laisser sur
        la boucle d'événements figerait les autres requêtes, y compris
        `/sante`.
        """
        adresse = contrat.adresse_appelante(
            requete.client.host if requete.client else None,
            requete.headers.get("x-forwarded-for"),
        )
        autorise, attente = requete.app.state.limiteur.autoriser(adresse)
        if not autorise:
            secondes = max(1, math.ceil(attente))
            return JSONResponse(
                contrat.erreur_en_json(
                    contrat.CODE_TROP_DE_REQUETES,
                    f"Trop de questions depuis cette adresse : "
                    f"{contrat.REQUETES_PAR_FENETRE} par "
                    f"{int(contrat.FENETRE_SECONDES)} secondes. Réessayez dans "
                    f"{secondes} seconde{'s' if secondes > 1 else ''}.",
                ),
                status_code=429,
                headers={"Retry-After": str(secondes)},
            )
        return JSONResponse(courant(requete).repondre(demande.question))

    # ── Les erreurs, traduites une fois chacune ─────────────────────────────

    def _reponse(
        code: str,
        erreur: Exception,
        statut: int,
        entetes: dict | None = None,
    ) -> JSONResponse:
        """La forme unique, et la commande relevée dans le message du cœur.

        Le message n'est pas réécrit : celui du noyau et du moteur dit déjà
        quoi lancer, parfois sur plusieurs lignes. Le résumer ferait perdre
        l'information et le recopier le ferait dériver.
        """
        message = str(erreur)
        return JSONResponse(
            contrat.erreur_en_json(code, message, contrat.commande_dans(message)),
            status_code=statut,
            headers=entetes,
        )

    @application.exception_handler(noyau.QuestionVide)
    async def _question_vide(requete: Request, erreur: Exception) -> JSONResponse:
        # 400 et non 422 : la forme du corps était correcte, c'est son contenu
        # qui ne contient rien à chercher.
        return _reponse(contrat.CODE_QUESTION_VIDE, erreur, 400)

    @application.exception_handler(contrat.QuestionTropLongue)
    async def _trop_longue(requete: Request, erreur: Exception) -> JSONResponse:
        return _reponse(contrat.CODE_QUESTION_TROP_LONGUE, erreur, 413)

    @application.exception_handler(contrat.ChargementEnCours)
    async def _chargement(requete: Request, erreur: Exception) -> JSONResponse:
        # 503 avec un `Retry-After` : l'interface sait alors qu'il faut
        # attendre et réessayer, et non afficher une panne. C'est la seule des
        # trois indisponibilités qui se résout d'elle-même.
        return _reponse(
            contrat.CODE_CHARGEMENT_EN_COURS,
            erreur,
            503,
            {"Retry-After": str(contrat.ATTENDRE_PENDANT_CHARGEMENT)},
        )

    @application.exception_handler(noyau.IndexAbsent)
    async def _index_absent(requete: Request, erreur: Exception) -> JSONResponse:
        # 503 et non 500 : rien n'est cassé dans le code, il manque un artefact
        # que la commande du message reconstruit. L'index pèse 1,8 Mo et vaut un
        # quart d'heure de calcul, d'où l'intérêt de le dire plutôt que de
        # laisser un 500 muet.
        return _reponse(contrat.CODE_INDEX_ABSENT, erreur, 503)

    @application.exception_handler(noyau.ModeleAbsent)
    async def _modele_absent(requete: Request, erreur: Exception) -> JSONResponse:
        return _reponse(contrat.CODE_MODELE_ABSENT, erreur, 503)

    @application.exception_handler(module_llm.ErreurModele)
    async def _redaction(requete: Request, erreur: Exception) -> JSONResponse:
        # `moteur.repondre` refuse délibérément de transformer une panne du
        # rédacteur en abstention : le système AVAIT trouvé des articles, et
        # afficher « je ne trouve pas » mentirait sur ce qui s'est passé. La
        # traduction en indisponibilité est la tâche de cette couche-ci, et
        # c'est ce que fait cette ligne.
        return _reponse(contrat.CODE_REDACTION_EN_PANNE, erreur, 503)

    @application.exception_handler(RequestValidationError)
    async def _corps(requete: Request, erreur: Exception) -> JSONResponse:
        return JSONResponse(
            contrat.erreur_en_json(
                contrat.CODE_CORPS_ILLISIBLE,
                'Corps de requête illisible. Attendu : un objet JSON {"question": '
                '"…"} avec l\'entête Content-Type: application/json.',
            ),
            status_code=422,
        )

    # ── L'interface ─────────────────────────────────────────────────────────
    #
    # Montée EN DERNIER, et à la racine : Starlette essaie ses routes dans
    # l'ordre de déclaration, donc un montage à « / » placé plus haut
    # avalerait « /api/… » et « /sante ».
    if DOSSIER_STATIQUE.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=str(DOSSIER_STATIQUE), html=True),
            name="statique",
        )

    return application


app = creer_application()


def principal() -> None:  # pragma: no cover - point d'entrée local
    import uvicorn

    # 0.0.0.0 et non 127.0.0.1 : dans un conteneur, une écoute sur la boucle
    # locale n'est joignable que depuis le conteneur lui-même, et le Space
    # répondrait « application indisponible » sans une ligne de journal.
    uvicorn.run(app, host="0.0.0.0", port=chargement.port())


if __name__ == "__main__":  # pragma: no cover
    principal()
