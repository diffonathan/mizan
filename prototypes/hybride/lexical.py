"""Bras lexicaux : BM25 Okapi sur les 589 articles, en Python pur.

Ecrit a la main et non pris dans une bibliotheque pour une raison de cout :
589 articles tiennent dans un index inverse de quelques centaines de
kilo-octets, et le seul paquet consomme ici est le radicaliseur. C'est ce qui
rend la comparaison avec le bras dense honnete : ce qu'on pese, c'est le
surcout du second bras, pas le cout d'un systeme entier.

Deux bras sortent de ce fichier parce qu'ils partagent le meme moteur et ne
diffèrent que par la facon de decouper un texte en jetons : mots radicalises
d'un cote, tranches de quatre caracteres de l'autre. Le second existe pour
repondre a une question precise sur la fusion : RRF gagne-t-il quelque chose
quand on lui ajoute un bras qui ne coute rien ?
"""

import math
from collections import Counter

from corpus import Corpus
from normaliser import Radicaliseur, mots

# Valeurs de reference de BM25. Elles ne sont pas reglees sur le banc : un
# reglage sur vingt-cinq questions ecrites par l'auteur du banc n'est pas un
# reglage, c'est un sur-apprentissage que la revue verrait tout de suite.
K1 = 1.2
B = 0.75


class _MoteurBM25:
    """Index inverse et scoring BM25, independants du decoupage en jetons."""

    def __init__(self, corpus: Corpus, sacs: list[list[str]]) -> None:
        self.corpus = corpus
        self.index: dict[str, list[tuple[int, int]]] = {}
        self.longueurs: list[int] = []
        for i, sac in enumerate(sacs):
            self.longueurs.append(len(sac))
            for terme, n in Counter(sac).items():
                self.index.setdefault(terme, []).append((i, n))
        self.n_docs = len(sacs)
        self.longueur_moyenne = sum(self.longueurs) / max(1, self.n_docs)
        self.idf = {
            t: math.log(1 + (self.n_docs - len(p) + 0.5) / (len(p) + 0.5))
            for t, p in self.index.items()
        }
        self.vocabulaire = set(self.index)

    def _scorer(self, jetons_question: list[str], k: int) -> list[tuple[int, float]]:
        scores: dict[int, float] = {}
        for terme in jetons_question:
            affichages = self.index.get(terme)
            if not affichages:
                continue
            idf = self.idf[terme]
            for i, n in affichages:
                norme = K1 * (1 - B + B * self.longueurs[i] / self.longueur_moyenne)
                scores[i] = scores.get(i, 0.0) + idf * n * (K1 + 1) / (n + norme)
        classement = sorted(
            scores.items(), key=lambda kv: (-kv[1], self.corpus.articles[kv[0]].rang)
        )
        return classement[:k]


class IndexLexical(_MoteurBM25):
    """BM25 sur les mots radicalises."""

    def __init__(self, corpus: Corpus, poids_titres: int = 1) -> None:
        """poids_titres : combien de fois le chemin de titres est ajoute au sac
        de mots de l'article. A 0, l'article 205 ne contient pas le mot
        "hebdomadaire" de son chapitre ; au-dela de 1, les 47 articles d'un
        meme chapitre se mettent a se ressembler. L'effet est mesure."""
        self.radicaliser = Radicaliseur()
        self.poids_titres = poids_titres
        sacs = []
        for art in corpus.articles:
            sac = self.radicaliser.jetons(art.texte)
            sac += self.radicaliser.jetons(art.chemin_titres) * poids_titres
            sacs.append(sac)
        super().__init__(corpus, sacs)

    def chercher(self, question: str, k: int = 10) -> list[tuple[int, float]]:
        return self._scorer(
            self.radicaliser.jetons(question, retirer_mots_vides=True), k
        )

    def couverture(self, question: str) -> tuple[float, list[str]]:
        """Part des mots porteurs de la question qui existent dans le corpus.

        Sert au refus de repondre, pas au classement : une question sur le
        teletravail ou sur l'impot n'a aucun mot-cle dans un texte de 2011, et
        c'est le seul signal disponible sans modele de langue pour dire "ce
        sujet n'est pas dans ce code" au lieu de rendre cinq articles.
        """
        mots_porteurs = self.radicaliser.jetons(question, retirer_mots_vides=True)
        if not mots_porteurs:
            return 0.0, []
        absents = [m for m in mots_porteurs if m not in self.vocabulaire]
        return 1 - len(absents) / len(mots_porteurs), absents


def _tranches(texte: str, taille: int = 4) -> list[str]:
    """Decoupe en tranches de caracteres, avec les frontieres de mots.

    Le soulignement encadrant chaque mot est volontaire : sans lui, "salaire"
    et "salarie" partagent trois tranches sur cinq et deviennent presque le
    meme mot, ce qui est exactement l'erreur qu'on ne peut pas se permettre
    dans un code du travail ou les deux termes designent les deux parties.
    """
    sortie = []
    for mot in mots(texte):
        bourre = "_" + mot + "_"
        if len(bourre) <= taille:
            sortie.append(bourre)
            continue
        sortie.extend(bourre[i : i + taille] for i in range(len(bourre) - taille + 1))
    return sortie


class IndexCaracteres(_MoteurBM25):
    """BM25 sur des tranches de quatre caracteres.

    Troisieme bras a cout quasi nul : aucun paquet, aucun modele, et il
    rattrape ce que le radicaliseur rate (formes verbales eloignees, fautes de
    frappe, mots composes). Il n'est PAS un bras semantique : il ne saura
    jamais que "avances" renvoie a "harcelement sexuel".
    """

    def __init__(self, corpus: Corpus, taille: int = 4) -> None:
        self.taille = taille
        sacs = [
            _tranches(art.texte + " " + art.chemin_titres, taille)
            for art in corpus.articles
        ]
        super().__init__(corpus, sacs)

    def chercher(self, question: str, k: int = 10) -> list[tuple[int, float]]:
        return self._scorer(_tranches(question, self.taille), k)
