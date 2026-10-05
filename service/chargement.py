# -*- coding: utf-8 -*-
"""Le chargement du démarrage, et l'état que le service dit de lui-même.

Bibliothèque standard uniquement, comme `contrat.py` : rien ici n'a besoin de
`fastapi`, donc tout ici se teste sur un interpréteur nu.

LE CHARGEMENT EST FAIT UNE FOIS, AU DÉMARRAGE — ET EN DEUX TEMPS
----------------------------------------------------------------
Ouvrir la session ONNX du modèle de plongement coûte des secondes (2,83 s
mesurées sur un poste tiède, `DEPLOIEMENT.md` §4, davantage sur un conteneur
froid). Le faire à la première question, c'est servir la première personne en
plusieurs secondes et croire qu'on mesure le service. Mais le faire AVANT
d'ouvrir la prise réseau, c'est pire : `uvicorn` exécute le cycle de vie avant
d'écouter, et un contrôle de santé qui arrive pendant ce temps déclare le
Space mort. Le même défaut a déjà coûté une migration sur un autre projet de
l'auteur, avec un contrôle arrivé à 16 s.

D'où deux temps, et la frontière est une décision de produit :

  `charger_socle()`  SYNCHRONE, immédiat — le corpus et le rédacteur. Le
                     corpus donne l'AVERTISSEMENT de consolidation et la
                     rédaction donne le drapeau FACTICE : ce sont les deux
                     choses que l'interface doit pouvoir dire dès la première
                     milliseconde, parce que ce sont celles qui protègent le
                     visiteur. Elles coûtent une lecture de JSON.

  `installer_recherche()`  EN ARRIÈRE-PLAN — l'index et la session ONNX. Tant
                     qu'elle n'a pas fini, `/api/etat` rend
                     `etape = "chargement"` et `/api/question` rend un 503 qui
                     dit de réessayer. L'interface affiche une attente, pas une
                     page blanche.

TROIS PANNES, TROIS DÉCISIONS DIFFÉRENTES, ET C'EST LE CŒUR DE CE FICHIER
-------------------------------------------------------------------------
**Le corpus absent est FATAL.** Sans corpus, il n'y a pas d'avertissement de
consolidation — et le noyau comme le moteur refusent par construction de
produire un objet sans lui. Un service qui démarrerait quand même laisserait
une interface afficher un assistant juridique SANS son bandeau de date, ce qui
est précisément le danger que ce projet existe pour écarter. Mieux vaut un
conteneur qui refuse de démarrer, et dit pourquoi dans son journal.

**L'index ou le modèle absents ne sont PAS fatals.** Ils sont enregistrés, et
les routes le disent : `/api/etat` rend `etape = "panne"` avec la commande à
lancer, `/api/question` rend un 503 qui porte le message du cœur. Le
raisonnement est celui du corpus pris dans l'autre sens : un Space qui tombe
n'affiche rien du tout — ni la raison, ni la commande, et le propriétaire lit
un journal de construction au lieu d'une phrase. Ici l'avertissement reste
affichable, donc le service peut encore être honnête, donc il démarre.

**La clé absente n'est pas une panne du tout.** C'est l'état normal de ce
dépôt : il n'y a aucune clé dedans. Le rédacteur devient alors le modèle
factice déterministe de `moteur.llm`, et `redaction.factice` passe à vrai —
dans `/api/etat` ET dans chaque réponse. Un visiteur ne doit jamais croire
qu'un vrai modèle a rédigé, et cela ne se joue pas dans un journal.
"""
from __future__ import annotations

import os
import threading
import traceback
from dataclasses import dataclass

import noyau
from moteur import llm as module_llm
from moteur.repondre import ARTICLES_PAR_REPONSE, Mizan, Reponse

from . import contrat

# Les trois étapes que le service traverse, et qu'il nomme à l'écran.
ETAPE_CHARGEMENT = "chargement"
ETAPE_PRET = "pret"
ETAPE_PANNE = "panne"


def _dire(ligne: str) -> None:
    """La seule sortie du module. Le journal du conteneur, pas l'écran.

    Sur un Space, c'est l'onglet « Logs » qui lit ces lignes, et elles sont
    la seule trace d'un démarrage dégradé. Elles passent par une fonction
    plutôt que par des `print` dispersés pour deux raisons : les tests la
    remplacent au lieu de bavarder dans la sortie de la suite, et le
    préfixe reste écrit une fois.

    `flush` explicite : la sortie d'un conteneur n'est pas un terminal, donc
    elle est tamponnée, et une ligne de démarrage qui n'arrive qu'à la mort
    du processus n'aide personne.
    """
    print(f"[mizan] {ligne}", flush=True)

# Le texte que l'interface affiche quand la rédaction est factice. Il est écrit
# ICI, en un seul endroit, et il dit la vérité complète : la récupération est
# réelle et mesurée, c'est la RÉDACTION qui ne l'est pas. Une formule du genre
# « mode démonstration » laisserait croire que rien ne fonctionne, ce qui est
# faux, et c'est l'inverse du service à rendre à celui qui regarde.
POURQUOI_FACTICE = (
    "Aucune clé de modèle de langue n'est posée dans l'environnement "
    f"({module_llm.VARIABLE_CLE}) : la RÉDACTION est produite par un modèle "
    "factice déterministe, qui ne fait que nommer les articles trouvés. Elle "
    "n'a aucune valeur de contenu et aucun vrai modèle ne l'a écrite. La "
    "RECHERCHE des articles, elle, est réelle — c'est elle qui est mesurée "
    "dans MESURES.md."
)

POURQUOI_CHARGEMENT = (
    "La recherche est en cours de chargement : l'index vectoriel est lu et la "
    "session ONNX du modèle de plongement s'ouvre, ce qui prend quelques "
    "secondes au premier démarrage. Les questions sont refusées jusque-là, "
    "avec le délai à attendre."
)


@dataclass(frozen=True)
class Redaction:
    """Qui a écrit, et si c'est un vrai modèle. Jamais la clé elle-même."""

    factice: bool
    fournisseur: str | None
    modele: str | None
    pourquoi: str

    def en_json(self) -> dict:
        # `fournisseur` et `modele` sont des noms publics (« groq »,
        # « openai/gpt-oss-120b ») et non des secrets. La CLÉ n'apparaît dans
        # aucun champ, et `ClientHttp` la garde privée : il n'y a pas de
        # chemin, dans ce fichier, qui puisse la lire pour l'exposer.
        return {
            "factice": self.factice,
            "fournisseur": self.fournisseur,
            "modele": self.modele,
            "pourquoi": self.pourquoi,
        }


def _charger_redacteur() -> tuple[object, Redaction]:
    """Le vrai client s'il y a une clé, sinon le factice. Ne lève jamais.

    La clé est lue par `moteur.llm.ClientHttp` et par personne d'autre : ce
    fichier ne touche jamais `LLM_API_KEY`, il ne regarde que si la
    construction a réussi.
    """
    try:
        client = module_llm.charger_redacteur()
    except module_llm.CleAbsente as erreur:
        # Le message de `CleAbsente` dit déjà quoi poser ; on garde sa première
        # ligne pour que le journal de démarrage soit lisible, et on affiche à
        # l'écran la phrase de produit, qui dit ce qui marche quand même.
        _dire(f"rédaction factice — {str(erreur).splitlines()[0]}")
        factice = module_llm.ModeleFactice("fidele")
        return factice, Redaction(
            factice=True,
            fournisseur=None,
            modele=None,
            pourquoi=POURQUOI_FACTICE,
        )
    return client, Redaction(
        factice=False,
        fournisseur=client.fournisseur,
        modele=client.modele,
        pourquoi=(
            f"Rédigé par « {client.modele} » chez {client.fournisseur}. La "
            "garde vérifie ensuite que chaque article cité fait partie des "
            "articles récupérés, et rejette la réponse entière sinon."
        ),
    )


def _charger_recherche() -> tuple[object | None, str]:
    """Le moteur de récupération, ou la raison de son absence. Ne lève jamais.

    Rend (moteur ou None, message). Le message est celui du cœur, qui nomme
    déjà la commande à lancer ; il n'est pas réécrit ici.
    """
    try:
        return noyau.charger(), ""
    except (noyau.IndexAbsent, noyau.ModeleAbsent) as erreur:
        return None, str(erreur)
    except ImportError as erreur:
        # `lire_index` importe numpy au moment de lire. Sur un interpréteur nu,
        # c'est un ImportError et non un `IndexAbsent` : sans ce cas, la panne
        # la plus banale du projet — « les paquets ne sont pas installés » —
        # remonterait en 500 muet au lieu de nommer la commande.
        return None, (
            "Le bras dense a besoin de `fastembed`, `onnxruntime` et `numpy`, "
            f"absents de cet interpréteur (détail : {erreur}).\n"
            "    pip install -r requirements.txt"
        )
    except Exception:  # noqa: BLE001
        # Attrapé, mais MONTRÉ. Un fil d'arrière-plan qui meurt sur une
        # exception inattendue laisserait le service « vivant » et muet,
        # bloqué en « chargement » pour toujours : c'est l'état le plus coûteux
        # à diagnostiquer, et `DEPLOIEMENT.md` §4 le nomme comme tel. La trace
        # complète va au journal, et la première ligne à l'écran.
        trace = traceback.format_exc()
        _dire(f"chargement de la recherche interrompu\n{trace}")
        return None, (
            "Le chargement de la recherche a échoué pour une raison "
            "inattendue. La trace complète est dans le journal du service.\n"
            f"{trace.strip().splitlines()[-1]}"
        )


class Service:
    """Ce que les routes appellent. Mince, et volontairement sans décision.

    Elle ne contient ni récupération, ni rédaction, ni garde : trois appels
    publics de `noyau` et `moteur`, deux verrous, et une mise en JSON.
    """

    def __init__(
        self,
        corpus,
        redacteur,
        redaction: Redaction,
        moteur_noyau=None,
        panne_index: str = "",
        commande_index: str | None = None,
        en_chargement: bool = False,
        k: int = ARTICLES_PAR_REPONSE,
    ) -> None:
        self.corpus = corpus
        self.redacteur = redacteur
        self.redaction = redaction
        self.k = k

        # Les trois champs que le fil d'arrière-plan remplace, lus par les
        # routes pendant ce temps : un verrou les garde, et `_recherche()` les
        # lit d'un seul coup. Sans lecture atomique, une route pourrait voir
        # `moteur_noyau` encore nul et `en_chargement` déjà faux, et annoncer
        # une panne qui n'existe pas.
        self._moteur_noyau = moteur_noyau
        self._panne_index = panne_index
        self._commande_index = commande_index
        self._en_chargement = en_chargement
        self._verrou_etat = threading.Lock()

        # Le verrou de récupération n'entoure QUE la recherche, pas la
        # rédaction. La raison est double, et la seconde est la plus
        # importante :
        #   • la session ONNX de `fastembed` n'est pas documentée comme
        #     réentrante, et deux vCPU ne gagnent rien à encoder en parallèle ;
        #   • l'appel au modèle de langue peut durer jusqu'à 90 secondes
        #     (`moteur.llm.DELAI_SECONDES`). Le mettre sous le même verrou
        #     ferait attendre une minute et demie à tout le monde pour la
        #     lenteur d'un seul fournisseur.
        # C'est exactement pourquoi la capture du `Resultat` passe par le
        # chercheur injecté plutôt que par un appel enveloppant `repondre`.
        self._verrou_recuperation = threading.Lock()

    # -- le remplissage d'arrière-plan --------------------------------------

    def installer_recherche(self, moteur_noyau, panne: str = "") -> None:
        """Pose le résultat du chargement d'arrière-plan. Appelée une fois.

        Elle existe parce que la prise réseau doit s'ouvrir avant que l'index
        soit lu : le service naît en « chargement » et cette méthode le fait
        passer en « prêt » ou en « panne ».
        """
        with self._verrou_etat:
            self._moteur_noyau = moteur_noyau
            self._panne_index = panne
            self._commande_index = contrat.commande_dans(panne)
            self._en_chargement = False

    def _recherche(self) -> tuple[object | None, str, str | None, bool]:
        with self._verrou_etat:
            return (
                self._moteur_noyau,
                self._panne_index,
                self._commande_index,
                self._en_chargement,
            )

    # -- l'état -------------------------------------------------------------

    @property
    def etape(self) -> str:
        moteur_noyau, _, _, en_chargement = self._recherche()
        if moteur_noyau is not None:
            return ETAPE_PRET
        return ETAPE_CHARGEMENT if en_chargement else ETAPE_PANNE

    @property
    def pret(self) -> bool:
        return self.etape == ETAPE_PRET

    def etat(self) -> dict:
        """Le corps de `GET /api/etat`.

        C'est cette route qui permet à l'interface de dire la vérité sur la
        rédaction : elle est appelée au chargement de la page, avant toute
        question, et c'est le seul moment où un visiteur peut apprendre que la
        rédaction sera factice AVANT d'en lire une.
        """
        moteur_noyau, panne, commande, en_chargement = self._recherche()
        source = self.corpus.source
        return {
            "etape": self.etape,
            "pret": moteur_noyau is not None,
            "recherche": {
                "pret": moteur_noyau is not None,
                "en_chargement": en_chargement,
                "pourquoi": POURQUOI_CHARGEMENT if en_chargement else panne,
                "commande": commande,
            },
            "redaction": self.redaction.en_json(),
            "corpus": {
                # La date et l'avertissement viennent du corpus et ne sont
                # recopiés nulle part : une réextraction sur une autre version
                # du Code ne doit pas laisser derrière elle une date fausse
                # écrite dans du code. Ils sont disponibles DÈS le démarrage,
                # avant même que la recherche soit chargée — c'est le but du
                # découpage en deux temps.
                "date_consolidation": self.corpus.date_consolidation,
                "avertissement": self.corpus.avertissement,
                "articles": len(self.corpus.articles),
                "intitule": source.get("intitule", ""),
                "portail": source.get("portail", ""),
                "fichier": source.get("fichier", ""),
            },
            "limites": {
                "question_caracteres": contrat.LIMITE_CARACTERES_QUESTION,
                "requetes_par_fenetre": contrat.REQUETES_PAR_FENETRE,
                "fenetre_secondes": contrat.FENETRE_SECONDES,
                "articles_par_reponse": self.k,
            },
        }

    def sante(self) -> dict:
        """Le corps de `GET /sante`. Le contrat avec l'hébergeur, et rien d'autre.

        « Le port répond » n'est pas « le moteur est chaud » : cette route rend
        200 dès que le processus vit, y compris pendant le chargement. Rendre
        503 pendant le préchauffage reconstruirait la panne qu'on évite.
        """
        _, panne, _, en_chargement = self._recherche()
        return {
            "pret": self.pret,
            "etape": self.etape,
            "erreur": (panne.splitlines()[0] if panne else None),
            "redaction_reelle": not self.redaction.factice,
            "en_chargement": en_chargement,
        }

    # -- la question --------------------------------------------------------

    def repondre(self, brut: object) -> dict:
        """Le corps de `POST /api/question`. Lève pour ce que HTTP doit traduire.

        Lève `noyau.QuestionVide`, `contrat.QuestionTropLongue`,
        `contrat.ChargementEnCours`, `noyau.IndexAbsent` et
        `moteur.llm.ErreurModele`. Aucune n'est rattrapée ici : chacune porte
        un message qui dit quoi faire, et les écraser en « une erreur est
        survenue » perdrait exactement ce que le cœur a pris la peine
        d'écrire.

        En revanche une abstention, un rejet de la garde et un signalement
        d'injection ne sont PAS des erreurs : ils sortent en 200, dans le même
        objet que les réponses servies.
        """
        # La question est validée AVANT l'état de la recherche : un appel mal
        # formé est un appel mal formé, et le dire est plus utile que
        # d'annoncer un index manquant à quelqu'un qui n'a rien demandé.
        question = contrat.valider_question(brut)

        moteur_noyau, panne, _, en_chargement = self._recherche()
        if moteur_noyau is None:
            if en_chargement:
                raise contrat.ChargementEnCours(POURQUOI_CHARGEMENT)
            raise noyau.IndexAbsent(panne)

        # La composition est reconstruite à chaque question. C'est gratuit —
        # `Mizan` ne tient que trois références — et c'est ce qui rend la
        # capture du `Resultat` sûre entre fils : un attribut partagé se ferait
        # écraser par la requête voisine, et une interface afficherait la marge
        # d'une autre question sous ses articles.
        capture: list = []

        def chercheur(question_posee: str, k: int = self.k):
            with self._verrou_recuperation:
                resultat = moteur_noyau.chercher(question_posee, k=k)
            capture.append(resultat)
            return resultat

        reponse: Reponse = Mizan(self.redacteur, chercheur, self.k).repondre(
            question
        )
        resultat = capture[-1] if capture else None
        return contrat.question_en_json(reponse, resultat, self.redaction.en_json())


# ── Les deux formes de chargement ───────────────────────────────────────────


def charger_socle(k: int = ARTICLES_PAR_REPONSE) -> Service:
    """Le corpus et le rédacteur, tout de suite. Le service naît « en chargement ».

    Le rédacteur d'abord, le corpus ensuite, dans l'ordre que
    `moteur.repondre.charger` justifie : l'absence de clé se constate sans
    rien ouvrir. Ici elle ne fait d'ailleurs rien échouer, mais garder l'ordre
    évite d'avoir à se demander pourquoi il a changé.

    `noyau.charger_corpus()` peut lever `FileNotFoundError`, et ce n'est PAS
    rattrapé : voir l'en-tête du fichier. Sans corpus, pas d'avertissement de
    consolidation, donc rien d'honnête à servir.
    """
    redacteur, redaction = _charger_redacteur()
    return Service(
        corpus=noyau.charger_corpus(),
        redacteur=redacteur,
        redaction=redaction,
        en_chargement=True,
        k=k,
    )


def demarrer(k: int = ARTICLES_PAR_REPONSE) -> tuple[Service, threading.Thread]:
    """Le chargement du démarrage : socle immédiat, recherche en arrière-plan.

    C'est la forme que le cycle de vie de l'application appelle. Le fil est
    LANCÉ et jamais attendu : la prise réseau s'ouvre tout de suite, et
    `uvicorn` n'attend pas les secondes de la session ONNX avant d'écouter.
    Un contrôle de santé qui arrive pendant ce temps trouve un port qui
    répond, ce qui est tout ce que l'hébergeur demande.

    Le fil est rendu en plus du service pour que les tests puissent l'attendre.
    Rien dans le service ne l'attend.
    """
    service = charger_socle(k)

    def remplir() -> None:
        moteur_noyau, panne = _charger_recherche()
        service.installer_recherche(moteur_noyau, panne)
        if panne:
            _dire(f"recherche indisponible — {panne.splitlines()[0]}")
        else:
            _dire("recherche prête")

    fil = threading.Thread(target=remplir, name="mizan-chargement", daemon=True)
    fil.start()
    return service, fil


def charger(k: int = ARTICLES_PAR_REPONSE) -> Service:
    """Tout, synchrone, et prêt au retour. Pour un script ou un test.

    Ce n'est PAS la forme employée par l'application : elle appelle `demarrer`,
    parce que bloquer le cycle de vie retarde l'ouverture du port. Celle-ci
    existe pour qui veut un service utilisable en une ligne, sans avoir à
    attendre un fil.
    """
    service = charger_socle(k)
    moteur_noyau, panne = _charger_recherche()
    service.installer_recherche(moteur_noyau, panne)
    if panne:
        _dire(f"recherche indisponible — {panne.splitlines()[0]}")
    return service


def port() -> int:
    """Le port d'écoute. 7860 par défaut, parce que Hugging Face l'attend.

    `PORT` reste lisible dans l'environnement pour un essai local sur un autre
    port, mais la valeur par défaut n'est pas négociable côté Space : c'est le
    port que le SDK Docker expose.
    """
    return int(os.environ.get("PORT") or 7860)
