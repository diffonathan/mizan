# -*- coding: utf-8 -*-
"""Bras lexical : BM25 Okapi, bibliothèque standard seule.

Ce bras ne décide jamais de la tête du classement — c'est le bras dense qui la
tient (CONCEPTION.md §3). Il est ici pour deux choses que lui seul sait faire :

1. **Les questions à terme exact.** Les trois questions du banc où le Code
   renvoie à un texte réglementaire qu'il ne contient pas (SMIG, jours fériés,
   préavis) passent de 66,7 % à 100 % de rappel@5 grâce à lui, là où le bras
   dense ne voit qu'un article « qui parle d'argent ».
2. **Dire quels mots de la question le Code ne connaît pas.** C'est une
   information qu'aucun vecteur ne peut rendre : un plongement trouve toujours
   un voisin, même pour un mot absent. Un usager qui lit « je ne connais pas le
   mot *bébé* » reformule.

PAS DE RACINISATION, et c'est un choix mesuré, pas un oubli. Le rogneur de
suffixes écrit à la main que portait le prototype lexical coûte cinq points de
rappel@1 (34,2 avec, 39,5 sans) : il fait collisionner des termes que le droit
distingue. Snowball ferait mieux au rang 1 (41,2) pour 0,5 Mo de dépendance,
mais moins bien au rang 3 (50,9 contre 56,1) — et ce bras ne sert ici qu'aux
rangs 4 et 5. Le prix de ce refus est chiffré dans CONCEPTION.md §5 : trois
points et demi de rappel@5, soit deux questions sur cinquante-sept.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from . import corpus as module_corpus

# Les séparateurs sont dits par la négative plutôt qu'énumérés, et deux signes
# doivent impérativement couper. L'apostrophe : le corpus assume de ne pas la
# normaliser et renvoie ce travail à la couche de recherche, donc
# « l'employeur » doit produire le jeton « employeur ». Le trait d'union : la
# couche texte du PDF a laissé passer « non- respect », et une question écrite
# « dommages et intérêts » doit atteindre « dommages-intérêts ».
_SEPARATEURS = re.compile(r"[^0-9a-z]+")

# Liste courte, et volontairement : l'IDF de BM25 pénalise déjà ce qui est
# fréquent. On ne retire que ce qui fausse le calcul de longueur de requête
# sans jamais rien discriminer.
MOTS_VIDES = frozenset(
    """
    a au aux avec ce ces dans de des du elle en et eux il ils je la le les leur
    lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que
    qui sa se ses son sur ta te tes toi ton tu un une vos votre vous y est sont
    etre ete suis es sommes etes etait etaient soit d l n s c j m t
    ai as avons avez ont avait avaient si plus moins tout tous toute toutes
    comme quel quelle quels quelles quoi dont lorsque quand combien
    """.split()
)


def depouiller(texte: str) -> str:
    """Minuscules sans accents : NFD, puis retrait des diacritiques combinantes."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").lower()


def decouper(texte: str) -> list[str]:
    jetons = _SEPARATEURS.split(depouiller(texte))
    return [j for j in jetons if j and j not in MOTS_VIDES]


@dataclass(frozen=True)
class Lecture:
    """Ce que le bras lexical sait d'une question, au-delà de son classement."""

    classement: list[tuple[str, float]]
    couverture: float
    termes_inconnus: tuple[str, ...]


class IndexLexical:
    """BM25 Okapi sur les articles, construit en mémoire.

    Les 589 articles tiennent dans moins d'un mégaoctet de texte : il n'y a
    aucune raison d'écrire un index sur disque, et la mesure le confirme —
    l'indexation entière se compte en fractions de seconde.
    """

    # Valeurs usuelles de BM25 Okapi, non réglées sur ce corpus. Le prototype
    # lexical les a balayées et a conclu que ses trois rappels n'en dépendaient
    # pas à cette taille d'échantillon ; les déplacer ici serait régler un
    # paramètre sur un banc de 64 questions.
    K1 = 1.2
    B = 0.75

    # Les intitulés de hiérarchie sont répétés deux fois dans le sac de mots.
    # Le poids ×2 est celui du prototype. Ce que la mesure dit exactement : le
    # poids ne change rien au rang 1 (34,2 à ×1, ×2 et ×3) et vaut quatre à six
    # points au rang 3 contre ×0. Réinjecter est donc justifié ; la valeur
    # exacte ne l'est pas, et ×1 faisait marginalement mieux au rang 3 (55,3
    # contre 53,5). On garde ×2 pour ne pas régler un paramètre sur le banc qui
    # sert à juger.
    POIDS_HIERARCHIE = 2

    def __init__(self, corpus: module_corpus.Corpus) -> None:
        self._corpus = corpus
        self._articles = corpus.articles

        self.frequences: list[Counter[str]] = []
        self.longueurs: list[int] = []
        document_frequence: Counter[str] = Counter()

        for article in self._articles:
            jetons = decouper(article["texte"])
            intitules = corpus.intitules(article)
            if intitules and self.POIDS_HIERARCHIE:
                jetons = jetons + decouper(intitules) * self.POIDS_HIERARCHIE
            self.frequences.append(Counter(jetons))
            self.longueurs.append(len(jetons))
            document_frequence.update(set(jetons))

        self.n = len(self._articles)
        self.longueur_moyenne = sum(self.longueurs) / self.n if self.n else 0.0

        # IDF Robertson-Sparck Jones avec le « 1 + » extérieur, qui garantit un
        # poids positif. Sans lui, un terme présent dans plus de la moitié du
        # corpus aurait un poids négatif et PÉNALISERAIT les articles qui le
        # contiennent : défendable en recherche documentaire générale, absurde
        # sur un code du travail où « salarié » est partout sans être du bruit.
        self.idf = {
            terme: math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))
            for terme, df in document_frequence.items()
        }

    def lire(self, question: str, profondeur: int) -> Lecture:
        jetons = decouper(question)
        distincts = set(jetons)
        connus = [j for j in jetons if j in self.idf]
        inconnus = tuple(sorted(distincts - set(self.idf)))
        couverture = len(distincts & set(self.idf)) / len(distincts) if distincts else 0.0

        scores: list[tuple[float, int]] = []
        for i in range(self.n):
            freq = self.frequences[i]
            longueur = self.longueurs[i]
            total = 0.0
            for terme in connus:
                f = freq.get(terme)
                if not f:
                    continue
                denominateur = f + self.K1 * (
                    1 - self.B + self.B * longueur / self.longueur_moyenne
                )
                total += self.idf[terme] * f * (self.K1 + 1) / denominateur
            if total > 0.0:
                scores.append((total, i))

        # Le départage par rang d'article, à score égal, n'est pas cosmétique :
        # c'est lui qui rend deux appels identiques comparables. Sans clé
        # secondaire, l'ordre de deux ex æquo dépendrait de l'ordre d'insertion
        # et le déterminisme exigé par le contrat ne serait vrai que par hasard.
        scores.sort(key=lambda t: (-t[0], self._articles[t[1]]["rang"]))

        return Lecture(
            classement=[
                (self._articles[i]["numero"], round(score, 6))
                for score, i in scores[:profondeur]
            ],
            couverture=round(couverture, 3),
            termes_inconnus=inconnus,
        )
