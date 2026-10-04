# -*- coding: utf-8 -*-
"""Branche les trois prototypes sur le banc indépendant de `evaluation/banc.py`.

Ce fichier ne contient AUCUNE logique de récupération. Il n'existe que pour
une raison : chaque candidat a mesuré sur ses propres questions, avec son
propre format de sortie et sa propre convention de rappel. Les comparer
exigeait de les faire tous entrer par la même porte — celle que `banc.py`
expose, `recuperer(question, k) -> [numéro, ...]`.

La règle que ce fichier s'impose : ne RIEN changer au comportement des
prototypes. Les paramètres passés à chaque index sont ceux que son auteur
recommande dans sa note, pas ceux qui donnent le meilleur chiffre ici.
Choisir les paramètres après avoir vu le score du banc indépendant
reviendrait à régler les candidats sur l'arbitrage, ce qui est précisément
le défaut que cet arbitrage est censé corriger.

Les grafts (classes dont le nom commence par `Greffe`) sont, eux, des
constructions de l'arbitre et sont signalées comme telles : leur chiffre ne
doit pas être lu comme celui d'un candidat.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PROTOTYPES = RACINE / "prototypes"
CORPUS_JSON = RACINE / "corpus" / "code-travail.json"

for _dossier in (PROTOTYPES / "lexical", PROTOTYPES / "vectoriel", PROTOTYPES / "hybride"):
    if str(_dossier) not in sys.path:
        sys.path.append(str(_dossier))


# ---------------------------------------------------------------------------
# Candidat 1 — BM25 en Python pur
# ---------------------------------------------------------------------------

class Lexical:
    """BM25 Okapi du prototype `lexical`, aux paramètres de son auteur.

    poids_hierarchie=2, racinisation active, mots vides actifs : ce sont les
    valeurs par défaut de `IndexLexical`, et son auteur écrit explicitement
    que son balayage de treize variantes ne les départage pas à cette taille
    d'échantillon. Les reprendre telles quelles est donc le choix neutre.
    """

    nom = "lexical"

    def __init__(self, articles):
        import bm25
        self._index = bm25.IndexLexical(articles)

    def _verdict(self, question: str, k: int):
        return self._index.chercher(question, k=k)

    def __call__(self, question: str, k: int):
        v = self._verdict(question, k)
        return [(r.numero, r.score) for r in v.resultats]


class LexicalSansHierarchie(Lexical):
    """Le même, intitulés non réinjectés — pour isoler ce que la hiérarchie apporte.

    Le jeu d'évaluation prévient qu'il avantage mécaniquement toute approche
    qui lit les intitulés, puisque son plancher ne cherche que dans `texte`.
    Mesurer les deux permet de chiffrer cet avantage au lieu de le supposer.
    """

    nom = "lexical-sans-hierarchie"

    def __init__(self, articles):
        import bm25
        self._index = bm25.IndexLexical(articles, poids_hierarchie=0)


# ---------------------------------------------------------------------------
# Candidat 2 — plongements vectoriels
# ---------------------------------------------------------------------------

class _Vectoriel:
    """Base commune : un index vectoriel du prototype `vectoriel`.

    Les vecteurs sont relus depuis `.cache_vecteurs/` quand ils y sont. Ce
    n'est pas une optimisation de confort : recalculer les 588 plongements de
    embeddinggemma coûte quinze minutes de processeur, et le banc ne mesure
    pas le temps d'indexation. Le cache ne change pas un seul chiffre de
    rappel, il ne change que l'attente.
    """

    modele = ""
    entete = True
    coupe = None

    def __init__(self, articles):
        import index_vectoriel
        self._index = index_vectoriel.construire_index(
            self.modele, entete=self.entete, coupe=self.coupe, cache=True
        )
        self._chercheur = index_vectoriel.Chercheur(self._index)

    def __call__(self, question: str, k: int):
        return self._chercheur.chercher(question, k=k)


class VectorielGemma(_Vectoriel):
    """La configuration que l'auteur du candidat 2 recommande explicitement."""

    nom = "vectoriel-gemma"
    modele = "google/embeddinggemma-300m"


class VectorielMiniLM(_Vectoriel):
    """La configuration légère du même candidat, 241 Mo contre 1 199 Mo."""

    nom = "vectoriel-minilm"
    modele = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class VectorielE5(_Vectoriel):
    nom = "vectoriel-e5"
    modele = "intfloat/multilingual-e5-large"


class VectorielPotion(_Vectoriel):
    nom = "vectoriel-potion"
    modele = "minishlab/potion-multilingual-128M"


# ---------------------------------------------------------------------------
# Candidat 3 — fusion de deux bras
# ---------------------------------------------------------------------------

class _Hybride:
    """Base commune : les deux bras du prototype `hybride` et leur fusion.

    `corpus.charger` reçoit un chemin absolu : son défaut est relatif au
    dossier courant, et le banc s'exécute depuis ailleurs.
    """

    fusion = "rrf"
    k_rrf = 60
    profondeur = 50

    def __init__(self, articles):
        import corpus as corpus_hybride
        import lexical as lexical_hybride
        import dense as dense_hybride
        import fusion as fusion_hybride

        self._f = fusion_hybride
        self._corpus = corpus_hybride.charger(str(CORPUS_JSON))
        self._lex = lexical_hybride.IndexLexical(self._corpus)
        self._den = dense_hybride.IndexDense(self._corpus)

    def _classements(self, question: str):
        lex = self._lex.chercher(question, k=self.profondeur)
        den = self._den.chercher(question, k=self.profondeur)
        return lex, den

    def _fusionner(self, lex, den):
        if self.fusion == "scores":
            return self._f.fusionner_par_scores(lex, den)
        return self._f.fusionner(lex, den, k_rrf=self.k_rrf)

    def __call__(self, question: str, k: int):
        lex, den = self._classements(question)
        ordre = self._fusionner(lex, den)
        return [
            (self._corpus.articles[r.indice].numero, r.score_rrf) for r in ordre[:k]
        ]


class HybrideRRF(_Hybride):
    """RRF k=60 : la configuration que l'auteur a mesurée et présentée."""

    nom = "hybride-rrf60"


class HybrideScores(_Hybride):
    """Somme des scores remis à l'échelle : la variante que ses chiffres préféraient."""

    nom = "hybride-scores"
    fusion = "scores"


class HybrideLexicalSeul(_Hybride):
    nom = "hybride-bras-lexical"

    def __call__(self, question: str, k: int):
        lex = self._lex.chercher(question, k=self.profondeur)
        return [(self._corpus.articles[i].numero, s) for i, s in lex[:k]]


class HybrideDenseSeul(_Hybride):
    nom = "hybride-bras-dense"

    def __call__(self, question: str, k: int):
        den = self._den.chercher(question, k=self.profondeur)
        return [(self._corpus.articles[i].numero, s) for i, s in den[:k]]


class HybrideAbstention(_Hybride):
    """RRF k=60 + la règle de refus de son auteur (couverture < 0,6 OU accord nul).

    Les deux seuils sont ceux écrits dans `fusion.py` avant sa première
    mesure. C'est le seul candidat qui s'abstient sans que l'arbitre ait
    touché à un réglage, et c'est pour cela qu'il est mesuré à part.
    """

    nom = "hybride-rrf60-abstention"

    def __call__(self, question: str, k: int):
        lex, den = self._classements(question)
        ordre = self._fusionner(lex, den)
        couverture, inconnus = self._lex.couverture(question)
        verdict = self._f.juger(ordre, couverture, inconnus)
        if verdict.refus:
            return []
        return [
            (self._corpus.articles[r.indice].numero, r.score_rrf) for r in ordre[:k]
        ]


# ---------------------------------------------------------------------------
# Greffes de l'arbitre — à ne pas confondre avec les candidats
# ---------------------------------------------------------------------------

class GreffeLexicalMarge(Lexical):
    """BM25 qui se tait quand sa marge est faible.

    La marge est le seul signal de doute que les trois candidats ont mesuré
    indépendamment comme séparateur, et c'est le seul qui ne coûte ni modèle
    ni clé. Le seuil n'est PAS repris de la note du candidat 1 (0,21, ajusté
    sur ses propres 25 questions) : il est balayé ici, et la courbe entière
    est publiée, parce qu'un seuil choisi sur le banc d'arbitrage serait
    exactement la faute que cet arbitrage reproche aux candidats.
    """

    nom = "greffe-lexical-marge"
    seuil_marge = 0.0

    def __call__(self, question: str, k: int):
        v = self._verdict(question, k)
        if v.marge < self.seuil_marge:
            return []
        return [(r.numero, r.score) for r in v.resultats]


def greffe_marge(seuil: float):
    """Fabrique une variante de la greffe à un seuil donné, pour balayer."""

    class _Variante(GreffeLexicalMarge):
        nom = f"greffe-lexical-marge-{seuil:.2f}"
        seuil_marge = seuil

    return _Variante


# ---------------------------------------------------------------------------
# La greffe centrale : BM25 + le bras dense QUI MARCHE
# ---------------------------------------------------------------------------

class _GreffeFusion:
    """Fusionne un bras lexical et un bras dense entraîné à la récupération.

    C'est la mesure manquante du dossier, et son absence n'est pas un oubli
    de l'arbitre : le candidat 3 a fusionné BM25 avec un modèle de
    PARAPHRASE (MiniLM), écrit noir sur blanc que c'était probablement le
    mauvais bras dense, et conclu que la fusion ne valait pas son coût. Le
    candidat 2 a mesuré séparément qu'un modèle de récupération asymétrique
    (préfixes « query: » / « passage: ») fait tout autre chose. Personne n'a
    croisé les deux. Tant que ce croisement n'est pas mesuré, le verdict du
    candidat 3 porte sur son bras dense, pas sur l'idée de fusionner.

    Le bras lexical est celui du candidat 1 : son intérêt n'est pas son
    rappel mais le détail terme par terme qu'il rend avec chaque article, et
    c'est cette sortie-là qu'on veut garder dans l'architecture finale.
    """

    nom = "greffe"
    modele_dense = "google/embeddinggemma-300m"
    fusion = "scores"
    k_rrf = 60
    profondeur = 50
    seuil_marge = 0.0
    exiger_accord = False

    def __init__(self, articles):
        import bm25
        import index_vectoriel

        self._articles = articles
        self._lex = bm25.IndexLexical(articles)
        self._index = index_vectoriel.construire_index(
            self.modele_dense, entete=True, coupe=None, cache=True
        )
        self._chercheur = index_vectoriel.Chercheur(self._index)

    # -- les deux classements ------------------------------------------------

    def _bras(self, question: str):
        verdict = self._lex.chercher(question, k=self.profondeur)
        lex = [(r.numero, r.score) for r in verdict.resultats]
        den = self._chercheur.chercher(question, k=self.profondeur)
        return lex, den, verdict

    @staticmethod
    def _echelle(liste):
        """Remise à l'échelle [0, 1] par requête.

        Un score BM25 vaut entre 0 et 40 selon la question, un cosinus entre
        -1 et 1 selon le modèle : les additionner bruts ferait gagner celui
        dont l'échelle est la plus large, ce qui n'a aucun sens. La remise à
        l'échelle est faite par requête et ne demande donc aucune constante
        à régler sur un jeu de questions.
        """
        if not liste:
            return {}
        valeurs = [s for _, s in liste]
        bas, haut = min(valeurs), max(valeurs)
        if haut - bas <= 0:
            return {n: 1.0 for n, _ in liste}
        return {n: (s - bas) / (haut - bas) for n, s in liste}

    def _fusionner(self, lex, den):
        rang_lex = {n: r for r, (n, _) in enumerate(lex, start=1)}
        scores: dict[str, float] = {}
        if self.fusion == "rrf":
            for liste in (lex, den):
                for r, (n, _) in enumerate(liste, start=1):
                    scores[n] = scores.get(n, 0.0) + 1.0 / (self.k_rrf + r)
        else:
            for table in (self._echelle(lex), self._echelle(den)):
                for n, v in table.items():
                    scores[n] = scores.get(n, 0.0) + v
        return sorted(scores.items(), key=lambda kv: (-kv[1], rang_lex.get(kv[0], 10**6)))

    # -- le doute ------------------------------------------------------------

    def _marge(self, ordre):
        if len(ordre) < 2 or ordre[0][1] <= 0:
            return 1.0
        return (ordre[0][1] - ordre[1][1]) / ordre[0][1]

    @staticmethod
    def _accord(lex, den, profondeur=5):
        return len({n for n, _ in lex[:profondeur]} & {n for n, _ in den[:profondeur]})

    def __call__(self, question: str, k: int):
        lex, den, _ = self._bras(question)
        ordre = self._fusionner(lex, den)
        if self.exiger_accord and self._accord(lex, den) == 0:
            return []
        if self._marge(ordre) < self.seuil_marge:
            return []
        return ordre[:k]


class GreffeGemmaScores(_GreffeFusion):
    nom = "greffe-bm25+gemma-scores"


class GreffeGemmaRRF(_GreffeFusion):
    nom = "greffe-bm25+gemma-rrf60"
    fusion = "rrf"


class GreffeE5Scores(_GreffeFusion):
    nom = "greffe-bm25+e5-scores"
    modele_dense = "intfloat/multilingual-e5-large"


class GreffeE5RRF(_GreffeFusion):
    nom = "greffe-bm25+e5-rrf60"
    modele_dense = "intfloat/multilingual-e5-large"
    fusion = "rrf"


class GreffeGemmaAccord(_GreffeFusion):
    """La seule abstention du dossier qui ne demande aucun seuil numérique.

    Le candidat 3 l'a inventée (« les deux méthodes ne désignent aucun
    article commun ») et mesurée sur son bras dense faible. Ici elle
    s'applique à deux bras dont on sait qu'ils sont tous deux compétents, ce
    qui est la condition pour que leur désaccord veuille dire quelque chose.
    """

    nom = "greffe-bm25+gemma-accord"
    exiger_accord = True


def greffe_fusion(modele: str, mode: str, seuil: float = 0.0, accord: bool = False):
    """Fabrique une variante pour balayer les seuils sans réécrire de classe."""
    nom = (f"greffe-{'gemma' if 'gemma' in modele else 'e5'}-{mode}"
           f"{'-accord' if accord else ''}"
           f"{'' if seuil == 0 else f'-marge{seuil:.2f}'}")
    return type("_V", (_GreffeFusion,), {
        "nom": nom,
        "modele_dense": modele,
        "fusion": mode,
        "seuil_marge": seuil,
        "exiger_accord": accord,
    })


class GreffeDenseTeteLexicalQueue(_GreffeFusion):
    """Le bras dense décide la tête du classement, BM25 complète la queue.

    Mécanisme, et il est antérieur à la mesure : la fusion par somme de
    scores fait payer au bras fort les erreurs du bras faible, parce qu'un
    article médiocre dans les deux listes passe devant un article premier
    dans une seule — le candidat 3 avait identifié ce mécanisme sur RRF, il
    vaut aussi pour la somme. Les questions du banc que BM25 sait traiter et
    que le dense rate (renvois à un texte réglementaire : SMIG, jours fériés,
    préavis) sont des questions à terme exact, exactement ce que le candidat 1
    proposait de confier à son bras.

    Autrement dit : on ne cherche pas à améliorer le rang 1 avec BM25, on
    cherche à ne pas perdre ce que lui seul trouve.

    CE QUE CETTE CLASSE COÛTE, et il ne faut pas l'écrire autrement. Les rangs
    1 à 3 sont intouchables, mesuré : les trois premiers articles rendus sont
    identiques, question par question, à ceux du bras dense seul. Mais les
    rangs 4 et 5 du bras dense sont écrasés, et sur ce banc cela se traduit par
    trois questions gagnées (Q27, Q28, Q61) contre une perdue (Q26, où
    l'art. 356 que le dense plaçait au rang 4 disparaît du top 5). « La queue ne
    coûte rien » serait faux ; ce qui est vrai, c'est qu'elle ne coûte rien
    au-dessus du rang 3.
    """

    nom = "greffe-dense-tete+bm25-queue"
    rangs_denses = 3

    def __call__(self, question: str, k: int):
        lex, den, _ = self._bras(question)
        if self.exiger_accord and self._accord(lex, den) == 0:
            return []
        if self._marge(den) < self.seuil_marge:
            return []
        sortie = [(n, s) for n, s in den[: self.rangs_denses]]
        vus = {n for n, _ in sortie}
        for n, s in lex:
            if len(sortie) >= k:
                break
            if n not in vus:
                sortie.append((n, s))
                vus.add(n)
        return sortie[:k]


class GreffeDenseMarge(_GreffeFusion):
    """Le bras dense seul, qui se tait quand sa marge est faible.

    Le seuil de 0,04 est lu sur la courbe de `doute.py`, donc sur CE banc :
    il est donné comme point de fonctionnement mesuré, jamais comme une
    valeur validée. La courbe entière est publiée pour cette raison.
    """

    nom = "greffe-dense-marge0.04"
    seuil_marge = 0.04

    def __call__(self, question: str, k: int):
        lex, den, _ = self._bras(question)
        if self._marge(den) < self.seuil_marge:
            return []
        return den[:k]


class GreffeDenseQueueMarge(GreffeDenseTeteLexicalQueue):
    nom = "greffe-dense-tete+queue+marge0.04"
    seuil_marge = 0.04


# Balayage de l'unique paramètre que l'arbitre a introduit. Il est publié
# parce qu'il n'est pas neutre, et c'est lui qui arbitre entre les quatre
# questions nommées ci-dessus : à profondeur 3, l'article 356 (renvoi au SMIG,
# Q26) que le bras dense plaçait au rang 4 est expulsé du top 5 ; à
# profondeur 4, il y reste mais la queue n'a plus qu'un rang à remplir.
class GreffeQueue2(GreffeDenseTeteLexicalQueue):
    nom = "greffe-tete2+queue"
    rangs_denses = 2


class GreffeQueue4(GreffeDenseTeteLexicalQueue):
    nom = "greffe-tete4+queue"
    rangs_denses = 4


class GreffeE5TeteQueue(GreffeDenseTeteLexicalQueue):
    nom = "greffe-e5-tete3+queue"
    modele_dense = "intfloat/multilingual-e5-large"


# Le bras lexical du candidat 3 obtient 44,7 % au rang 1 contre 34,2 % à
# celui du candidat 1. Deux choses les séparent : le racineur (Snowball
# contre un rogneur de suffixes écrit à la main) et le poids des intitulés
# (×1 contre ×2). Les variantes ci-dessous isolent le second, pour ne pas
# attribuer au racineur un écart qui viendrait du poids.
class LexicalPoids1(Lexical):
    nom = "lexical-poids-hierarchie-1"

    def __init__(self, articles):
        import bm25
        self._index = bm25.IndexLexical(articles, poids_hierarchie=1)


class LexicalPoids3(Lexical):
    nom = "lexical-poids-hierarchie-3"

    def __init__(self, articles):
        import bm25
        self._index = bm25.IndexLexical(articles, poids_hierarchie=3)


class LexicalSansRacine(Lexical):
    nom = "lexical-sans-racinisation"

    def __init__(self, articles):
        import bm25
        self._index = bm25.IndexLexical(articles, racine=False)


class LexicalSnowball(Lexical):
    """Le bras du candidat 1, avec Snowball à la place de son rogneur maison.

    Pourquoi cette variante existe : comparer directement les 34,2 % du bras
    du candidat 1 aux 44,7 % de celui du candidat 3 ne mesure PAS le racineur.
    Les deux bras diffèrent aussi par leur découpage (le candidat 3 retire les
    accents et coupe les élisions), par leur liste de mots vides et par leur
    implémentation de BM25. Attribuer l'écart entier à Snowball serait
    exactement le genre d'affirmation que ce dossier reproche aux notes de
    prototype. Ici une seule chose change à la fois.

    La greffe se fait sur `bm25.raciner` parce que c'est par ce nom-là que
    `bm25.découper` l'appelle, à l'indexation ET à chaque requête : elle doit
    donc couvrir les deux, et être retirée ensuite pour qu'une autre approche
    mesurée dans le même processus ne reçoive pas ce racineur à son insu.
    """

    nom = "lexical-snowball"

    def __init__(self, articles):
        import bm25
        from py_rust_stemmers import SnowballStemmer

        moteur = SnowballStemmer("french")
        cache: dict[str, str] = {}

        def raciner_snowball(jeton, longueur_minimale=0):
            # Le cache n'est pas une optimisation de confort : `découper` passe
            # par ici une fois par mot de chaque article, puis une fois par mot
            # de chaque question.
            r = cache.get(jeton)
            if r is None:
                r = moteur.stem_word(jeton)
                cache[jeton] = r
            return r

        self._bm25 = bm25
        self._origine = bm25.raciner
        self._racineur = raciner_snowball
        with self._greffe():
            self._index = bm25.IndexLexical(articles)

    @contextlib.contextmanager
    def _greffe(self):
        self._bm25.raciner = self._racineur
        try:
            yield
        finally:
            self._bm25.raciner = self._origine

    def _verdict(self, question: str, k: int):
        with self._greffe():
            return self._index.chercher(question, k=k)


def muet(question: str, k: int):
    """Témoin qui se tait toujours.

    Il est mesuré pour une seule raison : il obtient le meilleur taux
    d'abstention possible en ne rendant aucun service. C'est le rappel à
    l'ordre permanent du §4 de CONCEPTION.md — l'abstention ne se lit jamais
    sans la dérobade, sinon le système le mieux noté est celui qui ne répond
    à rien.
    """
    return []
