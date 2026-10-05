#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc de BOUT EN BOUT pour Mizan : ce que l'usager reçoit, pas ce qu'on a trouvé.

    python evaluation/banc_bout_en_bout.py --recuperation idf   # sans clé, sans paquet
    python evaluation/banc_bout_en_bout.py                      # avec l'index dense

Ce que ce banc mesure, et ce que l'autre ne mesurait pas
========================================================
`banc.py` mesure la RÉCUPÉRATION : l'article attendu était-il sur la table ?
C'est nécessaire et ce n'est pas la promesse du produit. La promesse est une
réponse rédigée QUI CITE, et une citation fausse est pire qu'une absence de
réponse — parce que la citation est précisément ce qui donne confiance.

Trois grandeurs, qui ne se confondent jamais :

  1. EXACTITUDE DES CITATIONS  les articles cités sont-ils ceux qu'il fallait ?
     Comparée aux `articles_attendus` de questions.json. Elle est plafonnée par
     la récupération : une citation ne peut être juste que si l'article a été
     récupéré, et ce plafond est imprimé à côté de la mesure pour qu'on ne
     reproche pas à la rédaction ce que la recherche n'a pas fourni.

  2. REJET PAR LA GARDE        combien de réponses ont été refusées parce
     qu'elles citaient un article hors de l'ensemble récupéré. C'est la mesure
     de l'hallucination : elle dit combien de fois le modèle a inventé un
     numéro. Elle ne dit rien de la pertinence de ce qu'il cite quand il
     n'invente pas — un article réel, récupéré et hors sujet traverse la garde
     intact, et c'est la grandeur 1 qui le voit.

  3. ABSTENTION                sur les questions dont la réponse n'est pas dans
     le Code, combien de fois le système se tait-il ? Et sur les questions
     répondables, combien de fois se tait-il à tort — la dérobade ? Les deux ne
     se lisent jamais l'une sans l'autre : un système qui se tait toujours
     obtient 100 % d'abstention correcte et 100 % de dérobade.

LE BANC NE CROIT PAS LE RÉPONDEUR SUR PAROLE
============================================
C'est le principe du projet appliqué au banc lui-même. Le répondeur annonce
`abstenu` et `raison` ; le banc ne s'en contente pas. Il fournit lui-même le
modèle de rédaction, garde le texte brut produit, en extrait les citations de
son côté, et vérifie l'inclusion dans l'ensemble récupéré. Il peut donc
distinguer trois choses que la seule lecture de `Reponse` confond :

    hallucination REJETÉE    le modèle a inventé, la garde a refusé  → attendu
    hallucination RENDUE     le modèle a inventé, la garde a laissé passer
                             → FUITE. Un invariant brisé, pas une mesure.
    rédaction loyale REJETÉE le modèle n'a rien inventé et la garde a refusé
                             → garde trop zélée, du rappel perdu pour rien.

MODE FACTICE, MODE RÉEL — jamais confondus
==========================================
Aucune clé n'est disponible dans cet environnement, et un banc qui ne tourne
que chez son auteur ne mesure rien. Ce banc tourne donc, par défaut, avec un
modèle FACTICE déterministe, et il écrit en tête de sa sortie, ainsi que dans
son JSON (`production: false`), que ses chiffres ne sont pas des chiffres de
production. Un chiffre obtenu avec le factice mesure LA CHAÎNE — la garde,
l'extraction, l'abstention, le comptage — et rien du modèle.

Le factice n'est pas complaisant, et c'est la condition pour que le banc mesure
quelque chose : par défaut il invente, il mélange vrai et faux, et il rédige
sans citer. Les quatre familles sont tirées par un condensé du texte de la
question, donc stables d'une exécution à l'autre et d'une machine à l'autre ;
la composition tirée est imprimée, et le banc CONTRÔLE que le nombre
d'hallucinations qu'il mesure est exactement celui que le factice a fabriqué.
Un banc qui ne sait pas prédire ses propres rejets ne vérifie pas la garde, il
la croit.

Trois modèles factices, qui encadrent la mesure :

    fidele   ne cite que des articles récupérés     → 0 rejet attendu
    menteur  invente à chaque réponse               → 100 % de rejet attendu
    mixte    les quatre familles, par condensé      → le défaut

Pour mesurer un vrai modèle, on en injecte un par `--redacteur module:attribut`.
Ce fichier n'embarque AUCUN client HTTP : écrire un client qu'on ne peut pas
exécuter ici serait du code non testé au cœur d'un banc de mesure. La
convention du projet pour les variables est LLM_PROVIDER / LLM_API_KEY /
LLM_MODEL ; le banc regarde seulement si une clé est configurée, pour étiqueter
le mode, et ne la lit jamais.

LE CONTRAT LU ICI
=================
Le banc accepte tout `repondre(question: str) -> Reponse` où `Reponse` porte
`texte`, `citations`, `articles`, `abstenu`, `raison`, `avertissement`. Il ne
l'importe pas : il lit les attributs. Une réponse non conforme fait sortir le
banc en code 2 sans produire un chiffre, comme `banc.controler_jeu` refuse de
mesurer un jeu incohérent.

Le témoin `RepondeurTemoin` de ce fichier n'est PAS le produit. Il est au banc
de bout en bout ce que les planchers `mots` et `muet` sont à `banc.py` : la
chaîne la plus courte qui respecte le contrat, pour que le banc produise des
chiffres aujourd'hui et pour qu'on puisse vérifier le banc avant de lui faire
confiance. Le jour où le répondeur du produit existe, il se branche par
`--repondeur module:attribut` et aucune ligne d'ici n'est réécrite.

Codes de sortie
===============
    0  mesuré
    1  un invariant du produit est brisé (fuite, avertissement absent) ou un
       seuil passé en option n'est pas tenu
    2  le banc n'a pas pu mesurer : jeu incohérent, ou réponse non conforme
"""
from __future__ import annotations

# Sortie en UTF-8 avant le premier print, et racine du projet sur le chemin :
# même amorce que `banc.py`, pour la même raison (sans elle, la première flèche
# imprimée arrête le script sur UnicodeEncodeError sous Windows). « append » et
# non « insert » : la racine porte des dossiers (corpus, evaluation) qui
# masqueraient des modules voisins de même nom s'ils passaient devant.
import sys as _sys
from pathlib import Path as _Path
_sys.path.append(str(_Path(__file__).resolve().parents[1]))
_sys.path.append(str(_Path(__file__).resolve().parent))
import sortie  # noqa: F401,E402  (importé pour son effet sur les flux)

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib  # noqa: E402
import inspect  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Callable, Sequence  # noqa: E402

import banc  # noqa: E402  (le banc de récupération : chargement et contrôle du jeu)
# `noyau.dense` s'importe sans `numpy` — il ne l'appelle qu'à l'intérieur de ses
# méthodes — et le banc a besoin de ses deux exceptions pour les traduire en un
# message plutôt qu'en pile d'appels.
from noyau import dense as module_dense  # noqa: E402

K_PAR_DEFAUT = 5


# ===========================================================================
# Le contrat de réponse
# ===========================================================================

@dataclass(frozen=True)
class Reponse:
    """La forme de référence du contrat partagé, telle que le témoin la rend.

    Le banc ne l'impose à personne : il lit les attributs, et toute classe qui
    les porte passe. Elle est écrite ici parce qu'une forme de référence
    exécutable vaut mieux qu'un paragraphe, et parce que le témoin a besoin
    d'une classe.

    Les deux contrôles de `__post_init__` sont STRUCTURELS, au même titre que
    celui du `Resultat` du noyau. L'avertissement de consolidation ne peut pas
    être oublié : il n'y a pas d'autre chemin pour construire une Reponse. Et
    une réponse rendue sans citation ne peut pas exister — sur un assistant
    juridique, c'est la forme la plus dangereuse de sortie, parce qu'elle a
    l'autorité d'une réponse et rien pour la vérifier.
    """

    texte: str | None
    citations: tuple[str, ...]
    articles: tuple
    abstenu: bool
    raison: str
    avertissement: str

    def __post_init__(self) -> None:
        if not (self.avertissement or "").strip():
            raise ValueError(
                "Une Reponse sans avertissement de consolidation ne peut pas "
                "être construite : le corpus est arrêté au 26 octobre 2011."
            )
        if not self.abstenu and not self.citations:
            raise ValueError(
                "Une réponse rendue sans citation ne peut pas être construite : "
                "sans citation vérifiable, la réponse ne vaut rien."
            )


ATTRIBUTS_DE_REPONSE = (
    "texte", "citations", "articles", "abstenu", "raison", "avertissement",
)


def controler_reponse(identifiant: str, reponse: object,
                      numeros_corpus: frozenset[str]) -> list[str]:
    """Vérifie qu'une réponse respecte le contrat partagé. Avant toute mesure.

    Un banc qui mesure une sortie malformée produit un chiffre faux avec
    aplomb : des citations rendues en entiers plutôt qu'en chaînes feraient
    tomber l'exactitude à zéro sans que rien ne le signale, et une abstention
    qui porte quand même un texte ferait compter comme silence une réponse que
    l'usager lit.
    """
    anomalies: list[str] = []
    for attribut in ATTRIBUTS_DE_REPONSE:
        if not hasattr(reponse, attribut):
            anomalies.append(f"{identifiant} : la réponse ne porte pas « {attribut} »")
    if anomalies:
        return anomalies

    if not isinstance(reponse.abstenu, bool):
        anomalies.append(f"{identifiant} : « abstenu » n'est pas un booléen")

    # L'AVERTISSEMENT VIDE N'EST PAS CONTRÔLÉ ICI, et c'est une décision.
    # Toute anomalie rendue par cette fonction fait sortir le banc en code 2
    # (« le banc n'a pas pu mesurer ») avant même d'écrire son rapport. Or un
    # avertissement manquant n'est pas une sortie illisible : c'est un
    # INVARIANT DU PRODUIT brisé, le plus dangereux de tous, puisqu'une réponse
    # sans sa date de consolidation laisse croire qu'elle dit le droit en
    # vigueur. Il est donc lu sur chaque `Ligne` et jugé avec les fuites, en
    # code 1. Tant qu'il était ici, le code 1 annoncé pour lui était
    # inatteignable et la ligne d'invariant du rapport affichait zéro par
    # construction — un compteur structurellement nul se lit comme une
    # garantie vérifiée alors qu'il ne vérifie rien.

    citations = list(reponse.citations or [])
    for numero in citations:
        if not isinstance(numero, str):
            anomalies.append(
                f"{identifiant} : la citation {numero!r} n'est pas une chaîne "
                f"(attendu « premier », « 231 »)"
            )
        elif numero not in numeros_corpus:
            anomalies.append(
                f"{identifiant} : l'article cité {numero!r} n'existe pas dans le corpus"
            )

    if reponse.abstenu:
        if (reponse.texte or "").strip():
            anomalies.append(f"{identifiant} : abstention qui porte quand même un texte")
        if not (reponse.raison or "").strip():
            anomalies.append(f"{identifiant} : abstention sans raison française")
    else:
        if not (reponse.texte or "").strip():
            anomalies.append(f"{identifiant} : réponse rendue sans texte")
        if not citations:
            anomalies.append(f"{identifiant} : réponse rendue sans aucune citation")
    return anomalies


# ===========================================================================
# Extraction des citations d'un texte rédigé
# ===========================================================================

# L'extraction est ancrée sur le mot « article » et jamais sur les nombres
# seuls : « le 1er alinéa de l'article 9 » et « 1er mai 1942 » existent dans le
# Code, et une lecture qui ramasserait les nombres y verrait des citations
# partout. Un seul numéro du Code n'est pas un nombre : l'article « premier ».
#
# TROIS ALIGNEMENTS SUR LA GARDE DU PRODUIT, et ce ne sont pas des copies de
# son code. L'indépendance de ce lecteur porte sur son ÉCRITURE, jamais sur son
# périmètre : deux lecteurs qui ne déclarent pas lire la même chose ne se
# contrôlent pas l'un l'autre, ils se contredisent, et c'est le banc qui perd —
# il accuse le produit d'une fuite qu'il n'a pas commise et sort en code 1.
#
#   • « art » sans point et « n° » sont lus, parce que la garde les lit. Sans
#     cela, une hallucination réellement servie sous la forme « l'art 45 » était
#     comptée zéro et le banc concluait que la garde tient ;
#   • le tiret et le « a » sans accent N'OUVRENT PAS une plage. Ce sont les deux
#     écritures que la garde refuse par décision documentée et testée : le tiret
#     est d'abord une ponctuation (« l'article 5 - 10 jours de congé » n'est pas
#     la plage 5 à 10) et « a » est d'abord le verbe avoir (« l'article 32 a 2
#     alinéas » n'est pas la plage 32 à 2) ;
#   • un nombre de PROSE n'enchaîne pas une citation. « l'article 176, soit 1,5
#     jour par mois » faisait fabriquer l'article 5 par ce seul lecteur.
_PROSE = (
    r"\d+,\d"
    r"|\d+\s+\d"
    r"|\d+\s*%"
    r"|\d+\s*(?:heures?|jours?|mois|ans?|années?|semaines?|alinéas?"
    r"|dirhams?|fois|minutes?)\b"
)
# `(?![\d-])` ferme le numéro : « l'article 65-99 » (une LOI, pas un article) ne
# rend plus 65, et « l'article 1234 » ne rend plus 123. C'est le quatrième
# alignement sur la garde, qui refuse ces deux écritures pour la même raison —
# et le filtre par le corpus ne pouvait pas rattraper le premier, puisque
# l'article 65 existe.
_MOTIF_CITATION = re.compile(
    r"\b(?:articles?|art\.?)[\s:]*(?:n[°o][\s:]*)?"
    r"((?:premier|\d{1,3})(?![\d-])"
    r"(?:\s*(?:,|et|ou|à)\s*(?!(?:" + _PROSE + r"))(?:premier|\d{1,3})(?![\d-]))*)",
    re.IGNORECASE,
)
_MOTIF_PARTIES = re.compile(r"premier|\d{1,3}|à", re.IGNORECASE)

# Une plage plus large que cela n'est pas une citation mais un geste de la main
# (« les articles 1 à 589 ») : la déplier fabriquerait des centaines de
# citations pour le compte du modèle, ce qui est exactement ce dont ce fichier
# se méfie. Ses deux bornes sont alors rendues telles quelles.
PLAGE_MAXIMALE = 50


def extraire_citations(texte: str, numeros_corpus: frozenset[str]) -> tuple[str, ...]:
    """Les numéros d'article cités par un texte, dans l'ordre d'apparition.

    **Cette lecture est celle du banc, et elle est volontairement indépendante
    de celle du produit.** Un banc qui vérifierait la garde avec l'extracteur
    de la garde ne pourrait pas détecter un défaut de cet extracteur : les deux
    se tromperaient ensemble et le banc imprimerait « zéro fuite ». Deux
    lecteurs écrits séparément se contrôlent l'un l'autre, et leur désaccord est
    visible dans deux compteurs du banc — une citation que seul le banc lit
    apparaît en **fuite**, une citation que seul le produit lit apparaît en
    **rejet à tort**.

    L'extraction ne retient que les numéros qui existent dans le corpus. Ce
    n'est PAS un filtre de sûreté et il ne faut pas le lire comme tel : un
    modèle qui cite « l'article 231 » alors que 231 n'a pas été récupéré passe
    ici sans encombre, et c'est la garde d'inclusion qui l'arrête. Écarter les
    numéros hors corpus sert seulement à ne pas compter « la loi 65-99 » comme
    une citation d'article — et ce filtre ne suffisait pas : « l'ARTICLE 65-99 »
    rendait 65, qui existe. C'est la fermeture du numéro, `(?![\\d-])`, qui s'en
    charge, et le filtre par le corpus reste ce qu'il est, un garde-fou de
    comptage.

    Les plages sont dépliées : « les articles 205 à 208 » cite quatre articles,
    et n'en rendre que deux laisserait deux numéros hors du contrôle
    d'inclusion — c'est-à-dire laisserait passer ce que la garde devait arrêter.
    """
    trouves: list[str] = []

    def retenir(numero: str) -> None:
        if numero in numeros_corpus and numero not in trouves:
            trouves.append(numero)

    for groupe in _MOTIF_CITATION.findall(texte or ""):
        parties = [p.lower() for p in _MOTIF_PARTIES.findall(groupe)]
        precedent: str | None = None
        attend_une_plage = False
        for partie in parties:
            if partie == "à":
                attend_une_plage = True
                continue
            if attend_une_plage and precedent is not None:
                for numero in _etendre(precedent, partie):
                    retenir(numero)
            else:
                retenir(partie)
            precedent = partie
            attend_une_plage = False

    return tuple(trouves)


def _etendre(debut: str, fin: str) -> list[str]:
    """Les numéros d'une plage, bornes comprises.

    Une plage dont une borne est « premier », dont les bornes sont à l'envers,
    ou plus large que `PLAGE_MAXIMALE`, n'est pas dépliée : ses deux bornes sont
    rendues telles quelles. Déplier une plage incompréhensible serait inventer
    des citations pour le compte du modèle.
    """
    if not (debut.isdigit() and fin.isdigit()):
        return [debut, fin]
    premier, dernier = int(debut), int(fin)
    if not 0 < dernier - premier <= PLAGE_MAXIMALE:
        return [debut, fin]
    return [str(n) for n in range(premier, dernier + 1)]


# ===========================================================================
# Les modèles de rédaction factices
# ===========================================================================

def _condense(question: str) -> int:
    """Un entier stable tiré du texte de la question.

    `hashlib` et non `hash` : le hachage natif de Python est salé par processus,
    et un banc dont la composition change à chaque lancement ne se compare pas
    à lui-même. Ce condensé-ci sera le même dans deux ans et sur une autre
    machine.
    """
    empreinte = hashlib.blake2b(question.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(empreinte, "big")


FAMILLES = ("fidele", "inventee", "muette", "melangee")

_CE_QUE_DIT_LA_FAMILLE = {
    "fidele": "ne cite que des articles récupérés",
    "inventee": "cite un article réel mais NON récupéré",
    "muette": "rédige sans citer aucun article",
    "melangee": "cite un article récupéré ET un article non récupéré",
}

FAMILLES_HALLUCINANTES = ("inventee", "melangee")


class RedacteurFactice:
    """Le modèle de rédaction factice, déterministe et adverse.

    Il ne cherche pas à être bon : il cherche à fabriquer, en proportions
    connues, les sorties qu'une chaîne honnête doit refuser. Un banc dont le
    faux modèle réussit toujours ne mesure rien — il mesurerait seulement qu'un
    répondeur sait recopier un numéro.

    `familles` restreint le tirage : la passer à ("fidele",) donne le témoin
    loyal, à ("inventee",) le témoin menteur. Les deux encadrent la mesure, et
    c'est à eux qu'on vérifie que la garde ne rejette ni trop peu ni trop.

    L'article « non récupéré » est choisi DANS le corpus et non tiré hors de
    lui : un modèle de langue n'invente pas « l'article 9 000 », il cite de
    mémoire un article réel qui ne répond pas à la question. C'est ce cas-là
    qu'il faut attraper, et il est plus difficile que l'autre.
    """

    nom = "factice"

    def __init__(self, numeros_corpus: Sequence[str],
                 familles: Sequence[str] = FAMILLES) -> None:
        inconnues = sorted(set(familles) - set(FAMILLES))
        if inconnues:
            raise SystemExit(
                f"Familles inconnues : {inconnues} ; attendu {list(FAMILLES)}."
            )
        if not familles:
            raise SystemExit("Il faut au moins une famille de rédaction.")
        self._numeros = tuple(numeros_corpus)
        self._familles = tuple(familles)

    def famille(self, question: str) -> str:
        return self._familles[_condense(question) % len(self._familles)]

    def _article_non_recupere(self, question: str,
                              recuperes: frozenset[str]) -> str | None:
        """Un article du corpus absent de l'ensemble récupéré, choisi sans hasard."""
        depart = _condense(question) % len(self._numeros)
        for decalage in range(len(self._numeros)):
            candidat = self._numeros[(depart + decalage) % len(self._numeros)]
            if candidat not in recuperes:
                return candidat
        return None

    def rediger(self, question: str, articles: Sequence) -> str:
        recuperes = frozenset(a.numero for a in articles)
        famille = self.famille(question)
        tete = articles[0].numero if articles else None
        intrus = self._article_non_recupere(question, recuperes)

        # Deux replis, pour que le factice ne fabrique jamais une sortie qu'il
        # prétendrait d'une autre famille. « fidele » sans article récupéré n'a
        # rien à citer, et « melangee » sans article récupéré n'a rien à
        # mélanger : les deux retombent sur un texte sans citation, et c'est
        # bien ce que le journal enregistrera.
        if tete is None and famille in ("fidele", "melangee"):
            famille = "muette"
        if intrus is None and famille in FAMILLES_HALLUCINANTES:
            famille = "fidele" if tete is not None else "muette"

        if famille == "fidele":
            return (f"D'après l'article {tete} du Code du travail, la réponse à "
                    f"votre question se lit dans ce texte.")
        if famille == "inventee":
            return (f"L'article {intrus} du Code du travail règle ce point, et il "
                    f"est formel sur ce que vous demandez.")
        if famille == "melangee":
            return (f"Les articles {tete} et {intrus} du Code du travail se "
                    f"complètent : le premier pose la règle, le second l'étend.")
        return ("Le Code du travail traite de cette question, et la réponse ne "
                "fait pas de doute dans la pratique.")


@dataclass(frozen=True)
class Demande:
    """Une question et les articles récupérés pour y répondre.

    Elle existe parce que les deux conventions d'appel d'un rédacteur se
    rencontrent dans ce projet : `rediger(question, articles)` et
    `rediger(demande)`. Le banc traduit entre les deux plutôt que d'imposer la
    sienne — un banc qui impose sa convention au code qu'il mesure demande à ce
    code d'être écrit pour lui.
    """

    question: str
    articles: tuple

    @property
    def numeros(self) -> tuple[str, ...]:
        return tuple(a.numero for a in self.articles)


def _lire_demande(arguments: Sequence) -> tuple[str, tuple]:
    """Reconnaît la forme d'appel reçue : (question, articles) ou (demande,)."""
    if len(arguments) == 2:
        return str(arguments[0]), tuple(arguments[1] or ())
    if len(arguments) == 1:
        demande = arguments[0]
        if hasattr(demande, "question") and hasattr(demande, "articles"):
            return str(demande.question), tuple(demande.articles or ())
    raise TypeError(
        "Le rédacteur du banc s'appelle rediger(question, articles) ou "
        f"rediger(demande) ; reçu {len(arguments)} argument(s) non reconnu(s)."
    )


class RedacteurObserve:
    """Enveloppe le modèle pour que le banc voie ce qu'il a réellement produit.

    C'est la pièce qui permet de distinguer une hallucination rejetée d'une
    hallucination rendue. Sans elle, le banc ne connaîtrait que la `Reponse`
    finale, c'est-à-dire ce que le répondeur accepte de dire de lui-même — et
    tout ce projet consiste à ne pas s'en contenter.

    Elle accepte les deux conventions d'appel dans les deux sens : le répondeur
    mesuré l'appelle comme il veut, et elle appelle le modèle enveloppé comme
    celui-ci veut, d'après le nombre de paramètres de sa signature. Elle expose
    `rediger` et `__call__` pour la même raison.
    """

    def __init__(self, interne, numeros_corpus: frozenset[str]) -> None:
        self._interne = interne
        self._numeros_corpus = numeros_corpus
        self.journal: list[dict] = []

    @property
    def nom(self) -> str:
        return getattr(self._interne, "nom", type(self._interne).__name__)

    def famille(self, question: str) -> str | None:
        methode = getattr(self._interne, "famille", None)
        return methode(question) if callable(methode) else None

    def _appeler(self, question: str, articles: tuple) -> str:
        methode = getattr(self._interne, "rediger", self._interne)
        try:
            nombre = len(inspect.signature(methode).parameters)
        except (TypeError, ValueError):
            nombre = 2
        if nombre >= 2:
            return methode(question, articles)
        return methode(Demande(question=question, articles=articles))

    def rediger(self, *arguments) -> str:
        question, articles = _lire_demande(arguments)
        texte = self._appeler(question, articles)
        self.journal.append({
            "question": question,
            "texte": texte,
            "famille": self.famille(question),
            "recuperes": sorted(a.numero for a in articles),
            "citations": list(extraire_citations(texte, self._numeros_corpus)),
        })
        return texte

    __call__ = rediger

    def derniere(self, question: str) -> dict | None:
        """La dernière rédaction produite pour cette question, s'il y en a une.

        Par la fin et non par le début : un répondeur qui réessaierait une
        rédaction refusée serait jugé sur sa dernière tentative, c'est-à-dire
        sur ce qui a servi à construire la réponse rendue.
        """
        for ligne in reversed(self.journal):
            if ligne["question"] == question:
                return ligne
        return None


# ===========================================================================
# Le répondeur témoin — la chaîne la plus courte qui respecte le contrat
# ===========================================================================

class RepondeurTemoin:
    """Récupérer, faire rédiger, VÉRIFIER, puis rendre ou se taire.

    Ce n'est pas le produit : il n'y a ici ni mise en forme, ni affichage des
    candidats sous le seuil, ni soin apporté à l'invite. Il est au banc de bout
    en bout ce que le plancher `mots` est au banc de récupération — un nombre à
    battre, et un moyen de vérifier le banc avant de lui faire confiance.

    Ce qu'il fait tenir, et qui n'est pas négociable :

    1. Sous `sur=False`, il se tait. Le `Resultat` du noyau garde pourtant ses
       cinq candidats, et le produit devra les montrer sans les présenter comme
       la réponse (CONCEPTION.md §1, point 4). Le témoin ne les montre pas
       parce qu'il n'a pas d'écran, pas parce que c'est la bonne conduite.
    2. L'ensemble des articles cités doit être INCLUS dans l'ensemble récupéré.
       Toute citation hors de cet ensemble fait rejeter la réponse ENTIÈRE, et
       non la seule citation fautive : une réponse dont on retire un article
       cesse de dire ce que son texte dit.
    3. Une rédaction sans citation est refusée. Sur ce domaine, un texte
       d'apparence juridique sans numéro vérifiable est la sortie la plus
       dangereuse de toutes.
    """

    def __init__(self, moteur, redacteur, numeros_corpus: frozenset[str],
                 k: int = K_PAR_DEFAUT) -> None:
        self._moteur = moteur
        self._redacteur = redacteur
        self._numeros_corpus = numeros_corpus
        self._k = k

    def repondre(self, question: str) -> Reponse:
        resultat = self._moteur.chercher(question, k=self._k)

        if not resultat.sur:
            return Reponse(
                texte=None, citations=(), articles=resultat.articles, abstenu=True,
                raison=resultat.pourquoi, avertissement=resultat.avertissement,
            )

        rediger = getattr(self._redacteur, "rediger", self._redacteur)
        texte = rediger(question, resultat.articles)
        citations = extraire_citations(texte, self._numeros_corpus)

        if not citations:
            return Reponse(
                texte=None, citations=(), articles=resultat.articles, abstenu=True,
                raison="La rédaction ne cite aucun article : sans citation "
                       "vérifiable, la réponse n'est pas rendue.",
                avertissement=resultat.avertissement,
            )

        hors = sorted(set(citations) - resultat.numeros)
        if hors:
            return Reponse(
                texte=None, citations=(), articles=resultat.articles, abstenu=True,
                raison="La rédaction cite des articles qui n'ont pas été récupérés "
                       f"({', '.join(hors)}) : la réponse entière est rejetée.",
                avertissement=resultat.avertissement,
            )

        return Reponse(
            texte=texte, citations=citations, articles=resultat.articles,
            abstenu=False, raison="", avertissement=resultat.avertissement,
        )

    __call__ = repondre


# ===========================================================================
# Les deux récupérations branchables
# ===========================================================================

class BrasDenseIdf:
    """Un bras dense factice : le plancher `idf` de `banc.py`, rien de plus.

    Il existe pour une raison et une seule : faire tourner la chaîne entière
    sans les 1,2 Go de modèle ONNX, sans `numpy` et sans index — donc partout,
    donc en test. Il ne prétend pas imiter le bras dense : ses rangs sont ceux
    d'un plancher lexical, et toute mesure obtenue avec lui porte sur la CHAÎNE
    et jamais sur la qualité de la récupération.

    Les scores IDF sont positifs et sans plafond, et la marge du moteur est
    relative : elle reste donc définie, ce qui suffit pour que le seuil
    d'abstention s'exerce vraiment plutôt que de ne jamais se déclencher.
    """

    nom = "idf"

    def __init__(self, articles: Sequence[dict]) -> None:
        self._plancher = banc.RecuperationParIdf(articles)

    def classer(self, question: str, profondeur: int) -> list[tuple[str, float]]:
        return list(self._plancher(question, profondeur))


def construire_moteur(mode: str, seuil_proximite: float | None):
    """Rend (moteur, étiquette de mode). Deux modes, nommés dans la sortie."""
    from noyau import corpus as module_corpus
    from noyau import recherche as module_recherche

    corpus = module_corpus.charger()
    seuil = (module_recherche.SEUIL_PROXIMITE if seuil_proximite is None
             else seuil_proximite)

    if mode == "idf":
        bras = BrasDenseIdf(corpus.articles)
        return (module_recherche.Moteur(corpus, bras, seuil),
                "bras dense FACTICE (plancher idf) — aucun modèle, aucun index")

    if mode != "reel":
        raise SystemExit(
            f"Récupération inconnue : {mode!r} ; attendu « reel » ou « idf »."
        )

    from noyau import dense as module_dense
    bras = module_dense.charger_bras_dense(corpus)
    return (module_recherche.Moteur(corpus, bras, seuil),
            f"noyau RÉEL (index dense {module_dense.MODELE})")


# ===========================================================================
# Résolution des options module:attribut
# ===========================================================================

def _resoudre(specification: str):
    nom_module, _, nom_attribut = specification.partition(":")
    if not nom_attribut:
        raise SystemExit(f"Attendu « module:attribut », reçu {specification!r}.")
    sys.path.insert(0, str(Path.cwd()))
    return getattr(importlib.import_module(nom_module), nom_attribut)


FACTICES = {
    "mixte": FAMILLES,
    "fidele": ("fidele",),
    "menteur": ("inventee",),
}


def construire_redacteur(specification: str, numeros_corpus: frozenset[str]):
    """Le modèle de rédaction, et l'étiquette qui dit s'il est factice."""
    if specification in FACTICES:
        familles = FACTICES[specification]
        interne = RedacteurFactice(
            sorted(numeros_corpus, key=_ordre_numero), familles
        )
        detail = " · ".join(f"{f} ({_CE_QUE_DIT_LA_FAMILLE[f]})" for f in familles)
        return interne, (f"modèle FACTICE « {specification} » — AUCUNE CLÉ ; ces "
                         f"chiffres ne mesurent PAS un modèle de production"), detail

    interne = _resoudre(specification)
    if isinstance(interne, type):
        interne = interne()
    cle = "présente" if (os.environ.get("LLM_API_KEY") or "").strip() else "ABSENTE"
    fournisseur = os.environ.get("LLM_PROVIDER") or "(LLM_PROVIDER non défini)"
    modele = os.environ.get("LLM_MODEL") or "(LLM_MODEL non défini)"
    return interne, (f"modèle INJECTÉ {specification} — LLM_API_KEY {cle}, "
                     f"{fournisseur} / {modele}"), "familles non connues du banc"


# Le répondeur par défaut est LE PRODUIT, et non le témoin de ce fichier. Un
# banc qui mesure par défaut sa propre reconstitution de la chaîne mesure
# quelque chose qui n'est livré à personne : les deux rapports se superposaient
# champ par champ au moment où ils ont été comparés, mais rien n'obligeait le
# produit à rester d'accord. `temoin` reste atteignable, comme borne de
# comparaison, et `tests/test_banc_bout_en_bout.py` vérifie que les deux
# tombent sur la même chose.
PRODUIT = "moteur.repondre:Mizan"


def construire_repondeur(specification: str, moteur, redacteur,
                         numeros_corpus: frozenset[str], k: int):
    """Le répondeur mesuré. `temoin` est celui de ce fichier.

    Un répondeur extérieur reçoit le modèle du banc s'il sait en prendre un :
    sa signature est inspectée pour un paramètre `redacteur`, `modele` ou
    `generateur`. S'il n'en prend pas, le banc le mesure quand même, mais en
    AVEUGLE — il ne verra plus les rédactions brutes, donc ni les fuites ni les
    rejets, et il l'écrit en tête de sa sortie plutôt que de rendre des zéros
    rassurants.
    """
    if specification == "temoin":
        return (RepondeurTemoin(moteur, redacteur, numeros_corpus, k),
                "temoin (témoin de CE fichier, pas le produit)", True, True)

    objet = _resoudre(specification)
    observe = moteur_remis = False

    # Trois formes sont acceptées, et la décision se prend AVANT tout appel.
    # Une classe porte un `repondre` non lié : la prendre pour une instance
    # produit un appelable qui passe tous les contrôles du banc et n'échoue
    # qu'au premier appel, sur un argument manquant. Une classe est donc
    # toujours construite ; une instance qui porte déjà `repondre` est prise
    # telle quelle ; une fonction est une fabrique si sa signature nomme une
    # des pièces du banc, et le `repondre(question)` du contrat sinon.
    a_construire = isinstance(objet, type) or (
        callable(objet) and not hasattr(objet, "repondre"))

    if a_construire:
        parametres: dict[str, object] = {}
        try:
            attendus = inspect.signature(objet).parameters
        except (TypeError, ValueError):
            attendus = {}
        for nom in ("redacteur", "modele", "generateur"):
            if nom in attendus:
                parametres[nom] = redacteur
                observe = True
                break
        # « chercheur » reçoit la MÉTHODE et non le moteur : c'est la forme du
        # contrat du noyau, `chercher(question, k=...) -> Resultat`, et un
        # répondeur qui attend ce nom attend cette forme.
        if "chercheur" in attendus:
            parametres["chercheur"] = moteur.chercher
            moteur_remis = True
        else:
            for nom in ("moteur", "recherche"):
                if nom in attendus:
                    parametres[nom] = moteur
                    moteur_remis = True
                    break
        if "k" in attendus:
            parametres["k"] = k
        if parametres or isinstance(objet, type):
            objet = objet(**parametres)

    appelable = getattr(objet, "repondre", objet)
    if not callable(appelable):
        raise SystemExit(f"{specification} ne fournit pas de « repondre » appelable.")
    return appelable, specification, observe, moteur_remis


def _ordre_numero(numero: str) -> tuple[int, str]:
    """« premier » d'abord, puis l'ordre numérique. Pour un tirage stable."""
    return (0, "") if numero == "premier" else (1, f"{int(numero):04d}")


# ===========================================================================
# Mesure
# ===========================================================================

@dataclass
class Ligne:
    identifiant: str
    question: str
    etiquettes: list[str]
    attendus: set[str]
    toleres: set[str]
    recuperes: set[str]
    abstenu: bool
    citations: tuple[str, ...]
    raison: str
    # Ce que le modèle a produit, quand le banc fournit le modèle. `None`
    # signifie « aucune rédaction observée » : soit le répondeur s'est abstenu
    # avant de rédiger, soit le banc mesure en aveugle.
    rediction: dict | None = None
    anomalies: list[str] = field(default_factory=list)
    # Lu sur la réponse et non déduit des anomalies : c'est un invariant du
    # produit, pas un défaut de forme. Voir `controler_reponse`.
    avertissement_absent: bool = False

    # -- les états d'une réponse -------------------------------------------

    @property
    def rendue(self) -> bool:
        return not self.abstenu

    @property
    def a_redige(self) -> bool:
        return self.rediction is not None

    @property
    def a_hallucine(self) -> bool:
        """Le modèle a cité au moins un article hors de l'ensemble récupéré."""
        if self.rediction is None:
            return False
        return bool(set(self.rediction["citations"]) - self.recuperes)

    @property
    def sans_citation(self) -> bool:
        return self.rediction is not None and not self.rediction["citations"]

    @property
    def loyale(self) -> bool:
        return (self.rediction is not None and bool(self.rediction["citations"])
                and not self.a_hallucine)

    @property
    def hors_recuperes(self) -> set[str]:
        """Les numéros annoncés à l'usager hors de l'ensemble récupéré.

        DEUX SOURCES, et la première est la plus importante : les citations que
        la réponse DÉCLARE elle-même, puis celles que le lecteur du banc lit
        dans le texte rédigé.

        La première ne dépend d'AUCUNE expression régulière. C'est l'invariant
        du projet pris littéralement — l'ensemble des articles cités doit être
        inclus dans l'ensemble des articles récupérés — calculé sur deux champs
        que la réponse porte déjà. Tant qu'elle manquait, un répondeur qui
        servait « l'art 45 » sans contrôle était compté zéro fuite, parce que
        le lecteur du banc ne lisait pas cette forme : le banc restait vert à
        travers une régression de la garde.
        """
        annoncees = set(self.citations)
        if self.rediction is not None:
            annoncees |= set(self.rediction["citations"])
        return annoncees - self.recuperes

    @property
    def fuite(self) -> bool:
        """Hallucination RENDUE. L'invariant du projet, brisé."""
        return self.rendue and bool(self.hors_recuperes)

    @property
    def rejet_a_tort(self) -> bool:
        """Rédaction loyale refusée : du rappel perdu sans rien gagner."""
        return self.abstenu and self.loyale

    # -- exactitude --------------------------------------------------------

    @property
    def citations_justes(self) -> set[str]:
        return set(self.citations) & self.attendus

    @property
    def citations_fautives(self) -> set[str]:
        """Citées, ni attendues, ni tolérées.

        Les tolérés ne comptent ni en réussite ni en faute, exactement comme
        dans `banc.py` : les compter en réussite gonflerait l'exactitude, les
        compter en faute punirait une citation correcte.
        """
        return set(self.citations) - self.attendus - self.toleres

    def precision(self) -> float | None:
        denominateur = len(self.citations_justes) + len(self.citations_fautives)
        if not denominateur:
            return None
        return len(self.citations_justes) / denominateur

    def couverture(self) -> float | None:
        if not self.attendus:
            return None
        return len(self.citations_justes) / len(self.attendus)

    @property
    def plafond(self) -> bool:
        """Un article attendu était-il dans l'ensemble récupéré ?

        C'est la borne de l'exactitude : en dessous, la rédaction ne POUVAIT pas
        citer juste. Le distinguer évite de reprocher à la génération ce que la
        recherche n'a pas fourni.
        """
        return bool(self.attendus & self.recuperes)


def _moyenne(valeurs: Sequence[float | None]) -> float | None:
    retenues = [v for v in valeurs if v is not None]
    if not retenues:
        return None
    return sum(retenues) / len(retenues)


class Resultats:
    def __init__(self, lignes: list[Ligne], modes: dict) -> None:
        self.lignes = lignes
        self.modes = modes

    @property
    def repondables(self) -> list[Ligne]:
        return [l for l in self.lignes if l.attendus]

    @property
    def sans_reponse(self) -> list[Ligne]:
        return [l for l in self.lignes if not l.attendus]

    @property
    def rendues(self) -> list[Ligne]:
        return [l for l in self.repondables if l.rendue]

    @property
    def redactions(self) -> list[Ligne]:
        return [l for l in self.lignes if l.a_redige]

    # -- grandeur 1 : exactitude des citations -----------------------------

    def precision(self) -> float | None:
        return _moyenne([l.precision() for l in self.rendues])

    def couverture(self) -> float | None:
        return _moyenne([l.couverture() for l in self.rendues])

    def au_moins_une_juste(self) -> float | None:
        if not self.rendues:
            return None
        return sum(1.0 for l in self.rendues if l.citations_justes) / len(self.rendues)

    def aucune_juste(self) -> list[Ligne]:
        return [l for l in self.rendues if not l.citations_justes]

    def plafond(self) -> float | None:
        if not self.rendues:
            return None
        return sum(1.0 for l in self.rendues if l.plafond) / len(self.rendues)

    def exactitude_sous_plafond(self) -> float | None:
        """Parmi les réponses rendues où un article attendu ÉTAIT récupéré, part
        de celles qui le citent. C'est la part qui appartient à la rédaction."""
        possibles = [l for l in self.rendues if l.plafond]
        if not possibles:
            return None
        return sum(1.0 for l in possibles if l.citations_justes) / len(possibles)

    # -- grandeur 2 : rejet par la garde -----------------------------------

    def hallucinations(self) -> list[Ligne]:
        return [l for l in self.lignes if l.a_hallucine]

    def rejets_hallucination(self) -> list[Ligne]:
        return [l for l in self.lignes if l.a_hallucine and l.abstenu]

    def rejets_sans_citation(self) -> list[Ligne]:
        return [l for l in self.lignes if l.sans_citation and l.abstenu]

    def fuites(self) -> list[Ligne]:
        return [l for l in self.lignes if l.fuite]

    def rejets_a_tort(self) -> list[Ligne]:
        return [l for l in self.lignes if l.rejet_a_tort]

    def taux_rejet(self) -> float | None:
        redactions = self.redactions
        if not redactions:
            return None
        return sum(1.0 for l in redactions if l.abstenu) / len(redactions)

    def taux_hallucination(self) -> float | None:
        redactions = self.redactions
        if not redactions:
            return None
        return len(self.hallucinations()) / len(redactions)

    def composition_factice(self) -> dict[str, int]:
        comptes: dict[str, int] = {}
        for ligne in self.redactions:
            famille = ligne.rediction.get("famille") or "(inconnue)"
            comptes[famille] = comptes.get(famille, 0) + 1
        return comptes

    def hallucinations_attendues(self) -> int | None:
        """Combien le factice en a fabriqué, par construction.

        Le banc prédit ses propres rejets et compare. Un écart ne signale pas un
        mauvais modèle : il signale que la garde, l'extraction ou le comptage ne
        font pas ce qu'ils disent. Rend `None` dès qu'une rédaction vient d'un
        modèle dont le banc ne connaît pas les familles — il n'y a alors rien à
        prédire, et prétendre le contraire serait inventer un contrôle.
        """
        comptes = self.composition_factice()
        if not comptes or "(inconnue)" in comptes:
            return None
        return sum(comptes.get(f, 0) for f in FAMILLES_HALLUCINANTES)

    # -- grandeur 3 : abstention -------------------------------------------

    def abstention_correcte(self) -> float | None:
        lot = self.sans_reponse
        if not lot:
            return None
        return sum(1.0 for l in lot if l.abstenu) / len(lot)

    def derobade(self) -> float | None:
        lot = self.repondables
        if not lot:
            return None
        return sum(1.0 for l in lot if l.abstenu) / len(lot)

    def abstentions_avant_redaction(self) -> list[Ligne]:
        """Le silence vient du doute de la récupération, pas de la garde."""
        return [l for l in self.lignes if l.abstenu and not l.a_redige]

    def abstentions_par_la_garde(self) -> list[Ligne]:
        return [l for l in self.lignes if l.abstenu and l.a_redige]

    # -- invariants --------------------------------------------------------

    def avertissements_absents(self) -> list[str]:
        return [l.identifiant for l in self.lignes if l.avertissement_absent]

    def anomalies(self) -> list[str]:
        return [a for l in self.lignes for a in l.anomalies]


def executer(repondre: Callable, jeu: dict, numeros_corpus: frozenset[str],
             observateur: RedacteurObserve | None, modes: dict) -> Resultats:
    lignes: list[Ligne] = []
    for question in jeu["questions"]:
        texte_question = question["question"]
        reponse = repondre(texte_question)
        anomalies = controler_reponse(question["id"], reponse, numeros_corpus)

        # L'ensemble récupéré est lu sur la réponse elle-même, et non demandé au
        # moteur une seconde fois : c'est l'ensemble contre lequel la garde a
        # réellement statué qui doit servir de référence au banc.
        recuperes: set[str] = set()
        for article in getattr(reponse, "articles", ()) or ():
            numero = getattr(article, "numero", None)
            if isinstance(numero, str):
                recuperes.add(numero)

        rediction = observateur.derniere(texte_question) if observateur else None

        lignes.append(Ligne(
            identifiant=question["id"],
            question=texte_question,
            etiquettes=list(question.get("etiquettes", [])),
            attendus=set(question.get("articles_attendus", [])),
            toleres=set(question.get("articles_toleres", [])),
            recuperes=recuperes,
            abstenu=bool(getattr(reponse, "abstenu", True)),
            citations=tuple(getattr(reponse, "citations", ()) or ()),
            raison=str(getattr(reponse, "raison", "") or ""),
            rediction=rediction,
            anomalies=anomalies,
            avertissement_absent=not (
                getattr(reponse, "avertissement", "") or ""
            ).strip(),
        ))
    return Resultats(lignes, modes)


# ===========================================================================
# Rendu
# ===========================================================================

def _pc(valeur: float | None) -> str:
    if valeur is None:
        return "     —"
    return f"{valeur * 100:5.1f} %".replace(".", ",")


def _virgule(valeur: float, decimales: int = 1) -> str:
    return f"{valeur:.{decimales}f}".replace(".", ",")


def ecrire_rapport(res: Resultats, detail: bool = False) -> None:
    modes = res.modes
    repondables, sans = res.repondables, res.sans_reponse

    print()
    print("  BANC DE BOUT EN BOUT — MIZAN")
    print("  " + "=" * 68)
    print(f"  GÉNÉRATION    {modes['generation']}")
    print(f"                familles : {modes['familles']}")
    print(f"  RÉCUPÉRATION  {modes['recuperation']}")
    print(f"  RÉPONDEUR     {modes['repondeur']}")
    if modes.get("moteur_remis", True):
        print("  seuil de proximité "
              f"{_virgule(modes['seuil_proximite'], 2)}, k = {modes['k']}")
    else:
        # Un répondeur qui n'a pas pris le moteur du banc construit le sien :
        # annoncer le seuil du banc serait annoncer un réglage qui ne s'applique
        # pas, c'est-à-dire exactement le genre de chiffre faux que ce fichier
        # refuse d'imprimer.
        print("  seuil d'abstention et k : inconnus du banc — ce répondeur a "
              "construit son propre moteur")
    if not modes["observe"]:
        print("  MESURE EN AVEUGLE : le répondeur ne prend pas le modèle du banc.")
        print("                      Ni les fuites ni les rejets ne sont mesurables.")
    print(f"  {len(res.lignes)} questions, dont {len(repondables)} avec réponse "
          f"et {len(sans)} sans réponse dans le Code")
    print()

    # -- 1 -----------------------------------------------------------------
    rendues = res.rendues
    print("  1. EXACTITUDE DES CITATIONS")
    print("  " + "-" * 68)
    print(f"  Sur les {len(rendues)} réponses RENDUES aux {len(repondables)} "
          f"questions répondables.")
    print(f"  {'précision des citations':48}{_pc(res.precision())}")
    print(f"  {'couverture des articles attendus':48}{_pc(res.couverture())}")
    print(f"  {'au moins une citation attendue':48}{_pc(res.au_moins_une_juste())}")
    print(f"  {'aucune citation attendue (réponse fausse)':48}"
          f"{len(res.aucune_juste()):3d} / {len(rendues)}")
    print()
    print(f"  {'plafond posé par la récupération':48}{_pc(res.plafond())}")
    print(f"  {'exactitude sous ce plafond':48}{_pc(res.exactitude_sous_plafond())}")
    print("  Le plafond dit dans quelle part des réponses rendues un article attendu")
    print("  avait été récupéré : en dessous, la rédaction ne POUVAIT pas citer juste.")
    print("  La ligne suivante est la part qui appartient vraiment à la rédaction.")
    print()

    # -- 2 -----------------------------------------------------------------
    redactions = res.redactions
    print("  2. REJET PAR LA GARDE — combien de fois le modèle a inventé")
    print("  " + "-" * 68)
    if not redactions:
        print("  Aucune rédaction observée : rien à mesurer ici.")
        print()
    else:
        print(f"  {'rédactions observées':48}{len(redactions):3d}")
        print(f"  {'dont citant un article NON récupéré':48}"
              f"{len(res.hallucinations()):3d}   {_pc(res.taux_hallucination())}")
        print(f"  {'dont sans aucune citation':48}"
              f"{sum(1 for l in redactions if l.sans_citation):3d}")
        print(f"  {'dont loyales (citations incluses)':48}"
              f"{sum(1 for l in redactions if l.loyale):3d}")
        print()
        print(f"  {'rejetées pour citation hors ensemble':48}"
              f"{len(res.rejets_hallucination()):3d}")
        print(f"  {'rejetées pour absence de citation':48}"
              f"{len(res.rejets_sans_citation()):3d}")
        print(f"  {'taux de rejet par la garde':48}{_pc(res.taux_rejet())}")
        print()
        composition = res.composition_factice()
        if composition:
            print("  Composition tirée par le modèle, et contrôle du banc sur lui-même")
            for famille in list(FAMILLES) + ["(inconnue)"]:
                if famille in composition:
                    dit = _CE_QUE_DIT_LA_FAMILLE.get(famille,
                                                     "famille non connue du banc")
                    print(f"    {famille:12}{composition[famille]:3d}   {dit}")
            attendues = res.hallucinations_attendues()
            if attendues is None:
                print("    aucune prédiction possible : familles non connues du banc")
            else:
                mesurees = len(res.hallucinations())
                verdict = "CONCORDENT" if attendues == mesurees else "NE CONCORDENT PAS"
                print(f"    hallucinations fabriquées {attendues}, mesurées "
                      f"{mesurees} — {verdict}")
            print()

    # -- 3 -----------------------------------------------------------------
    print("  3. ABSTENTION — savoir se taire, et le prix du silence")
    print("  " + "-" * 68)
    print(f"  {'abstention correcte (hors corpus)':48}"
          f"{_pc(res.abstention_correcte())}   n={len(sans)}")
    print(f"  {'dérobade (silence sur une question répondable)':48}"
          f"{_pc(res.derobade())}   n={len(repondables)}")
    print()
    print(f"  {'silences décidés par la récupération':48}"
          f"{len(res.abstentions_avant_redaction()):3d}")
    print(f"  {'silences décidés par la garde':48}"
          f"{len(res.abstentions_par_la_garde()):3d}")
    print("  Les deux ne se corrigent pas de la même façon : le premier est un seuil")
    print("  d'abstention, le second une rédaction refusée.")
    print()

    # -- par catégorie -----------------------------------------------------
    print("  Par catégorie — réponses rendues, puis citations justes parmi elles")
    print("  " + "-" * 68)
    for etiquette in banc.ETIQUETTES_RENDUES:
        lot = [l for l in res.lignes if etiquette in l.etiquettes]
        if not lot:
            continue
        if etiquette == "sans_reponse":
            tues = sum(1 for l in lot if l.abstenu)
            print(f"  {etiquette:18}{'abstention':>16}{tues:4d} / {len(lot)}")
            continue
        lot_rendues = [l for l in lot if l.rendue and l.attendus]
        justes = sum(1 for l in lot_rendues if l.citations_justes)
        print(f"  {etiquette:18}{f'{len(lot_rendues)} / {len(lot)} rendues':>16}"
              f"{justes:4d} justes")
    print()

    # -- invariants --------------------------------------------------------
    print("  INVARIANTS — une seule violation disqualifie la chaîne")
    print("  " + "-" * 68)
    fuites = res.fuites()
    print(f"  {'fuites : hallucination RENDUE à l usager':48}{len(fuites):3d}")
    for ligne in fuites:
        hors = sorted(ligne.hors_recuperes)
        print(f"      {ligne.identifiant} cite {hors} hors de "
              f"{sorted(ligne.recuperes)}")
    print(f"  {'réponses sans avertissement de consolidation':48}"
          f"{len(res.avertissements_absents()):3d}")
    print(f"  {'rejets à tort : rédaction loyale refusée':48}"
          f"{len(res.rejets_a_tort()):3d}")
    print()

    if detail:
        print("  Détail par question")
        print("  " + "-" * 68)
        for ligne in res.lignes:
            if ligne.attendus:
                if ligne.abstenu:
                    marque = ".."
                elif ligne.citations_justes == ligne.attendus:
                    marque = "ok"
                elif ligne.citations_justes:
                    marque = " ~"
                else:
                    marque = "KO"
            else:
                marque = "ok" if ligne.abstenu else "KO"
            famille = (ligne.rediction or {}).get("famille") or "—"
            print(f"  {marque} {ligne.identifiant:5} famille {famille:9} "
                  f"attendus {sorted(ligne.attendus) or '(aucun)'}")
            print(f"       récupérés {sorted(ligne.recuperes)}")
            print(f"       citées    {list(ligne.citations) or '(aucune)'}")
            if ligne.abstenu:
                print(f"       silence : {ligne.raison[:92]}")
        print()


def rapport_json(res: Resultats) -> dict:
    """Le JSON que relirait un suivi dans le temps. `production` est en tête.

    Le drapeau n'est pas un ornement : un chiffre de ce banc obtenu avec le
    modèle factice ne mesure pas un modèle, et un fichier qui ne le dirait pas
    serait relu dans six mois comme une mesure de production.
    """
    return {
        "production": bool(res.modes["production"]),
        "modes": res.modes,
        "questions": len(res.lignes),
        "repondables": len(res.repondables),
        "sans_reponse": len(res.sans_reponse),
        "exactitude": {
            "rendues": len(res.rendues),
            "precision": res.precision(),
            "couverture_attendus": res.couverture(),
            "au_moins_une_juste": res.au_moins_une_juste(),
            "aucune_juste": len(res.aucune_juste()),
            "plafond_recuperation": res.plafond(),
            "exactitude_sous_plafond": res.exactitude_sous_plafond(),
        },
        "garde": {
            "redactions_observees": len(res.redactions),
            "hallucinations": len(res.hallucinations()),
            "taux_hallucination": res.taux_hallucination(),
            "rejets_hallucination": len(res.rejets_hallucination()),
            "rejets_sans_citation": len(res.rejets_sans_citation()),
            "taux_rejet": res.taux_rejet(),
            "composition_factice": res.composition_factice(),
            "hallucinations_attendues": res.hallucinations_attendues(),
        },
        "abstention": {
            "correcte": res.abstention_correcte(),
            "derobade": res.derobade(),
            "avant_redaction": len(res.abstentions_avant_redaction()),
            "par_la_garde": len(res.abstentions_par_la_garde()),
        },
        "invariants": {
            "fuites": [l.identifiant for l in res.fuites()],
            "avertissements_absents": res.avertissements_absents(),
            "rejets_a_tort": [l.identifiant for l in res.rejets_a_tort()],
        },
    }


# ===========================================================================
# Entrée en ligne de commande
# ===========================================================================

def principal(argv: Sequence[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Mesure la RÉPONSE de bout en bout contre questions.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analyseur.add_argument("--repondeur", default=PRODUIT,
                           help=f"module:attribut | temoin "
                                f"(défaut : {PRODUIT}, le produit)")
    analyseur.add_argument("--redacteur", default="mixte",
                           help="mixte | fidele | menteur | module:attribut "
                                "(défaut : mixte, le seul adverse)")
    analyseur.add_argument("--recuperation", default="reel",
                           help="reel (index dense) | idf (factice, sans paquet) "
                                "(défaut : reel)")
    # Renommée avec le signal : le noyau décide sur la proximité (le score
    # dense absolu du 1er article) depuis `arbitrage/abstention.py`. Garder
    # « --seuil-marge » aurait laissé croire qu'on règle encore un écart entre
    # rangs, et les chiffres de ce banc seraient lus pour autre chose que ce
    # qu'ils mesurent.
    analyseur.add_argument("--seuil-proximite", type=float, default=None,
                           help="remplace le seuil d'abstention du noyau "
                                "(cosinus, défaut noyau.recherche.SEUIL_PROXIMITE)")
    analyseur.add_argument("--k", type=int, default=K_PAR_DEFAUT)
    analyseur.add_argument("--questions", type=Path, default=banc.CHEMIN_QUESTIONS)
    analyseur.add_argument("--corpus", type=Path, default=banc.CHEMIN_CORPUS)
    analyseur.add_argument("--detail", action="store_true")
    analyseur.add_argument("--json", type=Path, default=None,
                           help="écrit le rapport complet dans ce fichier")
    analyseur.add_argument("--seuil-exactitude", type=float, default=None,
                           help="sortie en code 1 si « au moins une citation "
                                "attendue » passe dessous (0 à 1)")
    analyseur.add_argument("--seuil-abstention", type=float, default=None,
                           help="sortie en code 1 si l'abstention correcte passe "
                                "dessous (0 à 1)")
    options = analyseur.parse_args(argv)

    corpus_brut = banc.charger_corpus(options.corpus)
    jeu = banc.charger_questions(options.questions)

    # Le même refus que `banc.py` : mesurer une chaîne contre un jeu incohérent
    # produit un chiffre faux avec aplomb.
    anomalies = banc.controler_jeu(jeu, corpus_brut)
    if anomalies:
        print("  Le jeu d'évaluation est incohérent ; aucune mesure n'a été faite.",
              file=sys.stderr)
        for anomalie in anomalies:
            print(f"    - {anomalie}", file=sys.stderr)
        return 2

    numeros_corpus = frozenset(a["numero"] for a in corpus_brut["articles"])

    # L'index ou le modèle absents ne sont pas une mesure qui échoue, c'est une
    # mesure qui n'a pas lieu : code 2, et le message du noyau, qui porte la
    # commande à lancer. Une pile d'appels à la place ferait chercher la cause
    # dans le banc.
    try:
        moteur, mode_recuperation = construire_moteur(options.recuperation,
                                                      options.seuil_proximite)
    except (module_dense.IndexAbsent, module_dense.ModeleAbsent) as manque:
        print(f"  {manque}", file=sys.stderr)
        return 2
    interne, mode_generation, familles = construire_redacteur(options.redacteur,
                                                              numeros_corpus)
    observateur = RedacteurObserve(interne, numeros_corpus)
    repondre, mode_repondeur, observe, moteur_remis = construire_repondeur(
        options.repondeur, moteur, observateur, numeros_corpus, options.k)

    modes = {
        "generation": mode_generation,
        "familles": familles,
        "recuperation": mode_recuperation,
        "repondeur": mode_repondeur,
        "observe": observe,
        "moteur_remis": moteur_remis,
        # Un chiffre n'est « de production » que si LES DEUX étages le sont. Un
        # vrai modèle branché sur une récupération factice ne mesure pas le
        # produit, et l'inverse non plus.
        "production": (options.redacteur not in FACTICES
                       and options.recuperation == "reel"),
        "seuil_proximite": moteur.seuil_proximite,
        "k": options.k,
    }

    res = executer(repondre, jeu, numeros_corpus,
                   observateur if observe else None, modes)

    anomalies_reponses = res.anomalies()
    if anomalies_reponses:
        print("  Des réponses ne respectent pas le contrat ; la mesure n'a pas "
              "de sens.", file=sys.stderr)
        for anomalie in anomalies_reponses:
            print(f"    - {anomalie}", file=sys.stderr)
        return 2

    ecrire_rapport(res, detail=options.detail)

    if options.json:
        options.json.write_text(
            json.dumps(rapport_json(res), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"  Rapport écrit dans {options.json}")
        print()

    echecs: list[str] = []
    if res.fuites():
        echecs.append(f"{len(res.fuites())} hallucination(s) rendue(s) à l'usager : "
                      f"la garde ne tient pas")
    if res.avertissements_absents():
        echecs.append(f"{len(res.avertissements_absents())} réponse(s) sans "
                      f"avertissement de consolidation")
    if options.seuil_exactitude is not None:
        mesure = res.au_moins_une_juste() or 0.0
        if mesure < options.seuil_exactitude:
            echecs.append(f"citations justes {_virgule(mesure * 100)} % < seuil "
                          f"{_virgule(options.seuil_exactitude * 100)} %")
    if options.seuil_abstention is not None:
        mesure = res.abstention_correcte() or 0.0
        if mesure < options.seuil_abstention:
            echecs.append(f"abstention correcte {_virgule(mesure * 100)} % < seuil "
                          f"{_virgule(options.seuil_abstention * 100)} %")
    if echecs:
        for echec in echecs:
            print(f"  ÉCHEC : {echec}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
