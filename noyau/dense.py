# -*- coding: utf-8 -*-
"""Bras dense : plongements `embeddinggemma-300m` sur ONNX.

C'est le moteur de l'architecture, et ce qu'il achète est le seul arbitrage non
serré du dossier : 27 points de rappel@1 contre le bras lexical (61,1 contre
34,2) et, sur les questions posées en langue d'usager, 47 points de rappel@3
(82,1 contre 35,2). Un code du travail se consulte dans les mots de celui qui a
un problème, pas dans ceux du législateur.

Le choix du modèle ne tient pas à sa taille mais à son entraînement : les deux
modèles mesurés qui gagnent sont les deux qui reçoivent un préfixe de rôle,
c'est-à-dire les deux entraînés à la récupération ASYMÉTRIQUE question →
document. Les deux modèles de similarité symétrique essayés passent sous le
plancher naïf du banc. Oublier le préfixe dégrade donc le rappel sans rien
signaler : ce n'est pas un détail d'implémentation, c'est le modèle.

TROIS RÈGLES QUE CE MODULE FAIT TENIR AU CODE
---------------------------------------------
1. **Rien ne se télécharge pendant une requête.** Le chargement est explicite
   (`charger_bras_dense`), il se fait hors ligne, et son échec dit quoi faire.
   Un service qui télécharge 1,2 Go à la première question d'un usager n'est
   pas lent, il est en panne.
2. **L'index se calcule une fois.** Les 588 vecteurs sont lus depuis un fichier
   et jamais recalculés à la volée : les plonger coûte un quart d'heure de
   processeur et un pic de mémoire de l'ordre de dix gigaoctets.
3. **L'index est scellé sur le corpus.** Le fichier porte l'empreinte des
   passages qui l'ont produit. Un corpus réextrait et un index périmé
   décaleraient les vecteurs d'un cran sans rien casser visiblement : les
   réponses deviendraient fausses en restant plausibles.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from . import corpus as module_corpus

RACINE = module_corpus.RACINE
DOSSIER_INDEX = RACINE / ".cache_vecteurs"

# Le nom tel que fastembed le connaît. Le dossier de cache qu'il crée porte un
# autre nom (`models--onnx-community--embeddinggemma-300m-ONNX`) : c'est la
# bibliothèque qui fait la correspondance, pas nous.
MODELE = "google/embeddinggemma-300m"

# Les deux préfixes de rôle du modèle. Voir l'en-tête : les intervertir ou les
# omettre dégrade le rappel en silence.
PREFIXE_QUESTION = "task: search result | query: "
PREFIXE_DOCUMENT = "title: none | text: "

# Les modèles sont volumineux et exclus du dépôt. Deux emplacements sont
# acceptés, dans cet ordre : celui du noyau, puis celui que les prototypes
# avaient rempli. Le second n'est pas de la complaisance envers du code
# jetable : il évite de retélécharger 1,2 Go déjà présents sur la machine, et
# la variable d'environnement permet de n'en dépendre jamais.
DOSSIERS_MODELES = (
    RACINE / ".cache_modeles",
    RACINE / "prototypes" / "vectoriel" / ".cache_modeles",
)


class IndexAbsent(RuntimeError):
    """L'index vectoriel n'existe pas, ou ne correspond pas au corpus."""


class ModeleAbsent(RuntimeError):
    """Le modèle de plongement n'est pas dans un cache local."""


class BrasDense(Protocol):
    """Le contrat que le moteur attend d'un bras dense.

    Il existe pour que le moteur soit testable sans 1,2 Go de modèle : les
    tests injectent un bras déterministe, et vérifient l'architecture — la
    profondeur dense, la queue lexicale, le seuil de proximité — sans dépendre de
    ce qui ne tourne que sur une machine où l'index a été construit. Un projet
    dont les tests ne tournent que chez son auteur n'est pas un projet.
    """

    def classer(self, question: str, profondeur: int) -> list[tuple[str, float]]:
        """Rend au plus `profondeur` couples (numéro d'article, score), décroissants."""
        ...


@dataclass(frozen=True)
class _Index:
    numeros: tuple[str, ...]
    vecteurs: object  # np.ndarray, non annoté pour ne pas imposer l'import ici
    empreinte_corpus: str
    modele: str


def dossier_modeles() -> Path:
    """Où chercher le modèle. `MIZAN_CACHE_MODELES` a le dernier mot."""
    impose = os.environ.get("MIZAN_CACHE_MODELES")
    if impose:
        return Path(impose)
    for candidat in DOSSIERS_MODELES:
        if candidat.is_dir() and any(candidat.glob("models--*")):
            return candidat
    return DOSSIERS_MODELES[0]


def chemin_index(modele: str = MODELE) -> Path:
    impose = os.environ.get("MIZAN_INDEX_DENSE")
    if impose:
        return Path(impose)
    return DOSSIER_INDEX / f"dense-{modele.replace('/', '_')}.npz"


@contextmanager
def _hors_ligne():
    """Interdit tout accès réseau à la bibliothèque de modèles, le temps du chargement.

    Sans cette contrainte, `fastembed` interroge le dépôt distant même quand les
    fichiers sont là : le chargement réussit en ligne et échoue en production
    derrière un pare-feu, ce qui est exactement le genre de défaut qu'on
    découvre le jour du déploiement. Forcer le mode hors ligne fait échouer ici
    et maintenant, avec un message.

    Les traces de la bibliothèque sont coupées pendant cette tentative pour une
    raison de contrat : l'absence de modèle doit produire une erreur qui dit
    quoi faire, et non deux lignes rouges sur un fichier « tar.gz » que
    personne n'a demandé. Elles sont rétablies ensuite, succès ou échec.
    """
    anciennes = {
        cle: os.environ.get(cle)
        for cle in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
    }
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        from loguru import logger  # dépendance de fastembed, pas du noyau
    except ImportError:
        logger = None
    if logger is not None:
        logger.disable("fastembed")
    try:
        yield
    finally:
        if logger is not None:
            logger.enable("fastembed")
        for cle, valeur in anciennes.items():
            if valeur is None:
                os.environ.pop(cle, None)
            else:
                os.environ[cle] = valeur


class BrasDenseOnnx:
    """Le bras dense de production : un index lu, un modèle chargé, rien d'autre.

    Le modèle reste chargé entre deux questions. Ouvrir une session ONNX coûte
    plusieurs centaines de millisecondes, soit dix fois une requête : le
    recharger à chaque appel transformerait un service de vingt millisecondes
    en service de deux secondes, et confondre les deux coûts est l'erreur de
    mesure que les fondations du projet racontent.
    """

    def __init__(self, index: _Index, plongeur) -> None:
        self._index = index
        self._plongeur = plongeur
        self._numeros = index.numeros

    @property
    def empreinte_corpus(self) -> str:
        return self._index.empreinte_corpus

    def classer(self, question: str, profondeur: int) -> list[tuple[str, float]]:
        import numpy as np

        brut = np.asarray(
            next(iter(self._plongeur.query_embed(PREFIXE_QUESTION + question))),
            dtype=np.float32,
        )
        # `fastembed` ne rend pas des vecteurs normés pour tous les modèles : le
        # produit scalaire brut n'est alors pas un cosinus et favorise les
        # textes longs. La normalisation est faite ici et pas déléguée.
        q = brut / max(float(np.linalg.norm(brut)), 1e-12)
        scores = self._index.vecteurs @ q

        # Un article ne donne aujourd'hui qu'un passage, mais la réduction par
        # MAXIMUM est écrite quand même : si un découpage des articles longs
        # revenait, la somme ferait gagner l'article le plus découpé, c'est-à-dire
        # le plus long, ce qui n'a rien à voir avec sa pertinence.
        meilleur: dict[str, float] = {}
        for numero, score in zip(self._numeros, scores):
            valeur = float(score)
            if valeur > meilleur.get(numero, -2.0):
                meilleur[numero] = valeur

        # Départage à score égal par le numéro tel qu'il apparaît dans le
        # corpus, pour que deux appels identiques rendent le même ordre.
        rang = {n: i for i, n in enumerate(self._numeros)}
        ordre = sorted(meilleur.items(), key=lambda kv: (-kv[1], rang[kv[0]]))
        return ordre[:profondeur]


def lire_index(corpus: module_corpus.Corpus, modele: str = MODELE) -> _Index:
    """Lit l'index vectoriel et refuse de servir s'il ne colle pas au corpus."""
    import numpy as np

    chemin = chemin_index(modele)
    if not chemin.exists():
        raise IndexAbsent(
            f"Index vectoriel absent : {chemin}\n"
            "Construisez-le une fois, depuis la racine du projet :\n"
            "    python -m noyau.indexer\n"
            "Comptez un quart d'heure de processeur et quelques gigaoctets de "
            "mémoire ; le résultat est relu ensuite en quelques dizaines de "
            "millisecondes."
        )

    with np.load(chemin, allow_pickle=False) as paquet:
        vecteurs = paquet["vecteurs"].astype(np.float32)
        numeros = tuple(str(n) for n in paquet["numeros"])
        meta = json.loads(str(paquet["meta"].item()))

    attendue = corpus.empreinte()
    if meta.get("empreinte_corpus") != attendue:
        raise IndexAbsent(
            f"L'index {chemin.name} a été calculé sur un autre corpus "
            f"(empreinte {str(meta.get('empreinte_corpus'))[:16]}… contre "
            f"{attendue[:16]}… aujourd'hui).\n"
            "Un index périmé ne casse rien de visible : il décale les vecteurs "
            "et rend des réponses fausses mais plausibles. Reconstruisez-le :\n"
            "    python -m noyau.indexer --forcer"
        )
    if len(numeros) != vecteurs.shape[0]:
        raise IndexAbsent(
            f"Index {chemin.name} incohérent : {len(numeros)} numéros pour "
            f"{vecteurs.shape[0]} vecteurs."
        )

    return _Index(
        numeros=numeros,
        vecteurs=vecteurs,
        empreinte_corpus=attendue,
        modele=meta.get("modele", modele),
    )


def charger_plongeur(modele: str = MODELE):
    """Ouvre la session ONNX, hors ligne, et dit quoi faire si le modèle manque."""
    dossier = dossier_modeles()
    try:
        from fastembed import TextEmbedding
    except ImportError as erreur:
        raise ModeleAbsent(
            "Le bras dense a besoin de `fastembed` et `onnxruntime`, absents de "
            "cet interpréteur.\n"
            "    pip install -r requirements.txt\n"
            f"(détail : {erreur})"
        ) from None

    try:
        with _hors_ligne():
            return TextEmbedding(modele, cache_dir=str(dossier))
    except Exception as erreur:  # fastembed lève des types variés selon la cause
        raise ModeleAbsent(
            f"Modèle « {modele} » introuvable hors ligne dans {dossier}.\n"
            "Deux façons d'y remédier :\n"
            "  • pointer un cache existant : "
            "MIZAN_CACHE_MODELES=/chemin/vers/.cache_modeles\n"
            "  • autoriser un téléchargement unique de 1,2 Go, hors service :\n"
            "        python -m noyau.indexer --telecharger\n"
            f"(détail : {type(erreur).__name__}: {erreur})"
        ) from None


def charger_bras_dense(corpus: module_corpus.Corpus,
                       modele: str = MODELE) -> BrasDenseOnnx:
    """Le chargement explicite exigé par le contrat : index d'abord, modèle ensuite.

    L'index est lu avant d'ouvrir la session ONNX parce qu'il coûte mille fois
    moins cher : échouer sur un index absent doit être instantané, pas payé au
    prix d'un chargement de modèle qui sera jeté.
    """
    index = lire_index(corpus, modele)
    return BrasDenseOnnx(index, charger_plongeur(modele))
