"""
Recherche lexicale BM25 sur le Code du travail marocain — PROTOTYPE JETABLE.

Aucune dépendance : bibliothèque standard seule. C'est le premier argument de
cette piste, et il se vérifie en lisant les imports ci-dessous.
"""

from __future__ import annotations

# Sortie en UTF-8 avant le premier print : voir sortie.py, à la racine. Sans
# lui, ce script s'arrête sur UnicodeEncodeError dès qu'il imprime une flèche.
# « append » et non « insert » : la racine porte des dossiers (corpus,
# evaluation) qui masqueraient des modules voisins de même nom s'ils passaient
# devant.
import sys as _sys
from pathlib import Path as _Path
_sys.path.append(str(_Path(__file__).resolve().parents[2]))
import sortie  # noqa: F401,E402  (importé pour son effet sur les flux)

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CHEMIN_CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "code-travail.json"


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation
# ─────────────────────────────────────────────────────────────────────────────

# Tout ce qui n'est ni chiffre ni lettre non accentuée sépare deux jetons.
# Dire quels caractères sont des séparateurs par la NÉGATIVE plutôt que par
# une liste évite d'avoir à énumérer les variantes d'un même signe, et deux
# signes en particulier doivent couper :
#   — l'apostrophe, que le corpus assume de ne pas normaliser (2 808 U+0027
#     contre 6 U+2019) en renvoyant explicitement ce travail à la couche de
#     recherche : « l'employeur » doit produire le jeton « employeur », sinon
#     une question qui écrit « employeur » tout court ne le trouve pas ;
#   — le trait d'union, pour deux raisons mesurables dans ce PDF : la couche
#     texte a laissé passer « non- respect » (donc le trait d'union n'est pas
#     fiable comme marque de composition), et une question écrite « dommages
#     et intérêts » doit atteindre « dommages-intérêts ».
_SEPARATEURS = re.compile(r"[^0-9a-z]+")


def dépouiller(texte: str) -> str:
    """Minuscules sans accents. NFD puis retrait des diacritiques combinantes."""
    décomposé = unicodedata.normalize("NFD", texte)
    sans_accent = "".join(c for c in décomposé if unicodedata.category(c) != "Mn")
    return sans_accent.lower()


# Mots vides. La liste est volontairement courte : BM25 pénalise déjà de
# lui-même ce qui est fréquent, par l'IDF. On ne retire que ce dont la
# présence dans une question fausse le calcul de longueur de requête sans
# jamais rien discriminer.
MOTS_VIDES = frozenset(
    """
    a au aux avec ce ces dans de des du elle en et eux il ils je la le les leur
    lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que
    qui sa se ses son sur ta te tes toi ton tu un une vos votre vous y est sont
    etre ete suis es sommes etes etait etaient soit d l n s c j m t qu
    ai as avons avez ont avait avaient si ne plus moins tout tous toute toutes
    comme quel quelle quels quelles quoi dont lorsque quand combien
    """.split()
)

# Suffixes rognés, du plus long au plus court. Le but n'est pas de faire un
# vrai analyseur morphologique du français : c'est de réunir les quatre ou
# cinq formes sous lesquelles un même terme juridique apparaît.
# « licenciement », « licencier », « licencié », « licenciée » → « licenci ».
# Le gain de cette liste est MESURÉ dans mesurer.py (ablation « sans rognage
# des suffixes ») : elle n'est pas là par principe.
_SUFFIXES = (
    "issements", "issement",
    "ements", "ement",
    "ations", "ation",
    "ateurs", "ateur", "atrices", "atrice",
    "ances", "ance", "ences", "ence",
    "aires", "aire",
    "elles", "elle",
    "eurs", "euse", "euses",
    "ees", "ee", "es", "er", "ir",
    "aux", "als",
    "s", "x",
)

_LONGUEUR_MINIMALE_RACINE = 3


def raciner(jeton: str, longueur_minimale: int = _LONGUEUR_MINIMALE_RACINE) -> str:
    """Rogne un suffixe, une seule fois, et seulement si le reste tient debout.

    La prudence vient d'un risque réel : sur-rogner fait collisionner des
    termes que le droit distingue. On n'applique donc qu'une passe, et on
    exige une racine d'une longueur minimale.

    Ce plancher est à 3. Une version précédente de cette docstring prétendait
    que le passer de 4 à 3 faisait se rencontrer « congé annuel payé » (texte
    de l'article 231) et « congés payés » (une question du banc). C'est FAUX,
    et à aucun plancher :

        « congé annuel payé »  →  {conge, annuel, paye}  aux trois planchers
        « congés payés »       →  {cong, pay}    aux planchers 2 et 3
                               →  {cong, payes}  au plancher 4

    Aucun jeton commun, dans aucune des trois combinaisons. La cause n'est pas
    le plancher, c'est que _SUFFIXES n'a aucune règle pour le « e » final
    seul : le singulier « payé » le garde (« paye »), le pluriel « payés » le
    perd en même temps que son « es » (« pay »), et les deux formes d'un même
    mot ne convergent donc jamais. Le plancher ne décide que de la longueur à
    partir de laquelle on renonce à rogner, pas de cet écart-là.

    Ce que la mesure dit du plancher, elle : rien de départageable. Les
    ablations « plancher de racine à 4 » et « plancher de racine à 2 » rendent
    toutes deux 40,0 / 56,0 / 64,0 %, soit exactement la référence
    (`python mesurer.py`, section 4), et la question « conges-deux-ans » reste
    un échec hors top-5 aux trois planchers.
    """
    if jeton.isdigit():
        return jeton
    for suffixe in _SUFFIXES:
        if jeton.endswith(suffixe):
            racine = jeton[: -len(suffixe)]
            if len(racine) >= longueur_minimale:
                return racine
            break
    return jeton


def découper(
    texte: str,
    *,
    mots_vides: bool = True,
    racine: bool = True,
    racine_min: int = _LONGUEUR_MINIMALE_RACINE,
) -> list[str]:
    jetons = [j for j in _SEPARATEURS.split(dépouiller(texte)) if j]
    if mots_vides:
        jetons = [j for j in jetons if j not in MOTS_VIDES]
    if racine:
        jetons = [raciner(j, racine_min) for j in jetons]
    return jetons


# ─────────────────────────────────────────────────────────────────────────────
# Index
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Resultat:
    numero: str
    score: float
    citation: str
    page_pdf: int
    extrait: str
    # Pourquoi cet article est remonté, terme par terme. C'est l'argument
    # principal de la piste lexicale : la réponse est auditable sans modèle.
    contributions: list[tuple[str, float]]


@dataclass(frozen=True)
class Verdict:
    """Ce que la recherche rend, assorti de ce qu'elle sait de sa propre fiabilité."""

    resultats: list[Resultat]
    couverture: float          # part des termes de la question connus du corpus
    termes_inconnus: list[str]
    marge: float               # écart relatif entre le 1er et le 2e score
    saturation: float          # score du 1er rapporté à la masse IDF interrogeable


class IndexLexical:
    """BM25 Okapi sur les 589 articles, construit en mémoire.

    Le corpus tient dans 280 000 caractères de texte d'articles : il n'y a
    aucune raison de sortir du processus, ni d'écrire un index sur disque.
    """

    # Valeurs usuelles de BM25 Okapi. Elles ne sont pas réglées sur ce corpus :
    # mesurer.py balaie k1 et b pour vérifier que le banc n'en dépend pas, et
    # le rapport dit ce que ce balayage a donné.
    K1 = 1.2
    B = 0.75

    def __init__(
        self,
        articles: list[dict],
        *,
        poids_hierarchie: int = 2,
        mots_vides: bool = True,
        racine: bool = True,
        racine_min: int = _LONGUEUR_MINIMALE_RACINE,
        k1: float | None = None,
        b: float | None = None,
    ) -> None:
        self.articles = articles
        self.k1 = self.K1 if k1 is None else k1
        self.b = self.B if b is None else b
        self._mots_vides = mots_vides
        self._racine = racine
        self._racine_min = racine_min

        self.frequences: list[Counter[str]] = []
        self.longueurs: list[int] = []
        document_frequence: Counter[str] = Counter()

        for article in articles:
            jetons = découper(
                article["texte"],
                mots_vides=mots_vides,
                racine=racine,
                racine_min=racine_min,
            )

            # Les intitulés de la hiérarchie sont répétés `poids_hierarchie`
            # fois. Ce n'est pas un ornement : « Du congé annuel payé » est un
            # intitulé de chapitre, et plusieurs articles qui en relèvent ne
            # contiennent nulle part les mots « congé annuel payé ». Sans ce
            # renfort, une question posée avec les mots du chapitre ne peut
            # atteindre que les articles qui les répètent. Le poids retenu est
            # celui que l'ablation a départagé, pas celui qui paraissait bien.
            if poids_hierarchie:
                intitulés = " ".join(
                    niveau["intitule"]
                    for niveau in article["position"].values()
                    if niveau and niveau.get("intitule")
                )
                jetons += découper(
                    intitulés,
                    mots_vides=mots_vides,
                    racine=racine,
                    racine_min=racine_min,
                ) * poids_hierarchie

            self.frequences.append(Counter(jetons))
            self.longueurs.append(len(jetons))
            document_frequence.update(set(jetons))

        self.n = len(articles)
        self.longueur_moyenne = sum(self.longueurs) / self.n if self.n else 0.0

        # IDF Robertson-Sparck Jones, avec le +1 extérieur qui garantit un
        # poids positif. Sans lui, un terme présent dans plus de la moitié du
        # corpus aurait un poids négatif et PÉNALISERAIT les articles qui le
        # contiennent — comportement défendable en recherche documentaire,
        # absurde ici où « salarié » apparaît partout sans être du bruit.
        self.idf = {
            terme: math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))
            for terme, df in document_frequence.items()
        }

    # ── interrogation ────────────────────────────────────────────────────────

    def chercher(self, question: str, k: int = 5) -> Verdict:
        jetons = découper(
            question,
            mots_vides=self._mots_vides,
            racine=self._racine,
            racine_min=self._racine_min,
        )
        connus = [j for j in jetons if j in self.idf]
        inconnus = sorted({j for j in jetons if j not in self.idf})

        masse_idf = sum(self.idf[j] for j in set(connus))
        couverture = (
            len(set(connus)) / len(set(jetons)) if jetons else 0.0
        )

        scores: list[tuple[float, int, dict[str, float]]] = []
        for i in range(self.n):
            freq = self.frequences[i]
            longueur = self.longueurs[i]
            total = 0.0
            détail: dict[str, float] = {}
            for terme in connus:
                f = freq.get(terme)
                if not f:
                    continue
                dénominateur = f + self.k1 * (
                    1 - self.b + self.b * longueur / self.longueur_moyenne
                )
                apport = self.idf[terme] * f * (self.k1 + 1) / dénominateur
                total += apport
                détail[terme] = détail.get(terme, 0.0) + apport
            if total > 0.0:
                scores.append((total, i, détail))

        scores.sort(key=lambda t: (-t[0], self.articles[t[1]]["rang"]))
        meilleurs = scores[: max(k, 2)]

        premier = meilleurs[0][0] if meilleurs else 0.0
        second = meilleurs[1][0] if len(meilleurs) > 1 else 0.0
        marge = (premier - second) / premier if premier > 0 else 0.0
        saturation = premier / masse_idf if masse_idf > 0 else 0.0

        resultats = [
            Resultat(
                numero=self.articles[i]["numero"],
                score=round(score, 4),
                citation=self.articles[i]["citation"],
                page_pdf=self.articles[i]["page_pdf"],
                extrait=self.articles[i]["texte"].split("\n")[0][:220],
                contributions=sorted(
                    ((t, round(v, 3)) for t, v in détail.items()),
                    key=lambda c: -c[1],
                )[:6],
            )
            for score, i, détail in meilleurs[:k]
        ]

        return Verdict(
            resultats=resultats,
            couverture=round(couverture, 3),
            termes_inconnus=inconnus,
            marge=round(marge, 3),
            saturation=round(saturation, 3),
        )


def charger_corpus(chemin: Path = CHEMIN_CORPUS) -> dict:
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


# ─────────────────────────────────────────────────────────────────────────────
# Usage direct : python bm25.py "ma question"
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    corpus = charger_corpus()
    index = IndexLexical(corpus["articles"])

    question = " ".join(sys.argv[1:]) or "combien de jours de congés après deux ans ?"
    verdict = index.chercher(question, k=5)

    print(f"Question : {question}")
    print(f"⚠ {corpus['source']['avertissement']}")
    print(
        f"\ncouverture={verdict.couverture}  marge={verdict.marge}  "
        f"saturation={verdict.saturation}"
    )
    if verdict.termes_inconnus:
        print(f"termes absents du corpus : {', '.join(verdict.termes_inconnus)}")
    print()
    for rang, r in enumerate(verdict.resultats, 1):
        print(f"{rang}. [{r.score:7.3f}] {r.citation}  (p. {r.page_pdf})")
        print(f"   {r.extrait}")
        print(f"   pourquoi : {', '.join(f'{t}={v}' for t, v in r.contributions)}")
        print()
