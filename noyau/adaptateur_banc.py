# -*- coding: utf-8 -*-
"""Branche le noyau sur le banc des fondations, sans toucher au banc.

    python evaluation/banc.py --recuperation noyau.adaptateur_banc:Mesure
    python evaluation/banc.py --recuperation noyau.adaptateur_banc:MesureSansAbstention

Le banc attend `recuperer(question, k) -> [numéro, ...]`. Le noyau rend un
`Resultat`, qui est une autre chose : il porte les candidats même quand il
doute. La traduction se fait ICI, et elle mérite d'être dite explicitement.

**Un `sur` faux devient un silence.** Le banc mesure l'abstention comme une
liste vide, et c'est ainsi que les fondations ont mesuré l'architecture
retenue : comparer le noyau à ces chiffres exige la même convention. Mais c'est
une convention de MESURE, pas le comportement du produit — une interface qui
viderait l'écran sous le seuil contredirait le registre de doute spécifié
(montrer les cinq candidats sans les présenter comme la réponse). Le rappel
mesuré par ce fichier est donc un plancher de ce qu'un usager aura sous les
yeux.

Les deux entrées existent pour que les deux lignes du tableau de décision se
remesurent : avec abstention et sans, puisque l'abstention est comptée comme un
rappel nul et qu'aucune des deux lignes ne se lit sans l'autre.
"""
from __future__ import annotations

from . import corpus as module_corpus
from . import dense as module_dense
from . import recherche as module_recherche


class Mesure:
    """L'architecture retenue, seuil de proximité compris.

    Le banc instancie cette classe avec les articles du corpus qu'il a lui-même
    chargé. Le noyau recharge le corpus par son propre chemin, et c'est
    volontaire : son index vectoriel est scellé sur l'empreinte des passages, et
    accepter une liste d'articles venue d'ailleurs ouvrirait la porte à un index
    mesuré contre un corpus qui n'est pas le sien. Un contrôle de cohérence
    remplace la confiance.
    """

    seuil_proximite = module_recherche.SEUIL_PROXIMITE

    def __init__(self, articles: list[dict] | None = None) -> None:
        corpus = module_corpus.charger()
        if articles is not None and len(articles) != len(corpus.articles):
            raise SystemExit(
                f"Le banc fournit {len(articles)} articles, le corpus du noyau "
                f"en porte {len(corpus.articles)} : ce n'est pas le même corpus."
            )
        self._moteur = module_recherche.Moteur(
            corpus, module_dense.charger_bras_dense(corpus), self.seuil_proximite
        )

    def __call__(self, question: str, k: int):
        resultat = self._moteur.chercher(question, k=k)
        if not resultat.sur:
            return []
        return [(a.numero, a.score) for a in resultat.articles]


class MesureSansAbstention(Mesure):
    """La même architecture, qui répond à tout. Le contrepoids obligatoire.

    Sans cette ligne, l'abstention se lirait seule — et le meilleur système d'un
    banc qui ne regarde que l'abstention est celui qui ne répond à rien.
    """

    # -1,0 et non 0,0, et la différence n'est pas cosmétique : le signal
    # d'abstention est désormais un COSINUS, qui vit entre -1 et 1. Un seuil à
    # zéro ferait encore taire une question dont le meilleur article a un score
    # négatif, et la ligne « répondre à tout » cesserait de répondre à tout —
    # c'est-à-dire que le contrepoids obligatoire mentirait, en silence et dans
    # le sens flatteur. Du temps de la marge, qui est un rapport positif ou nul,
    # zéro suffisait.
    seuil_proximite = -1.0

    def __call__(self, question: str, k: int):
        resultat = self._moteur.chercher(question, k=k)
        return [(a.numero, a.score) for a in resultat.articles]
