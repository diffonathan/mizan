# -*- coding: utf-8 -*-
"""Le moteur de récupération de Mizan, et le contrat que le reste du projet appelle.

    chercher("combien de jours de congé après deux ans ?") -> Resultat

L'architecture appliquée ici est celle qu'un arbitrage mesuré a retenue
(CONCEPTION.md §1) : **dense en tête, lexical en queue, abstention par la
marge**. Elle n'est pas rediscutée dans ce fichier ; ce fichier la met en
production et dit ce qu'elle coûte.

CE QUE CE MODULE GARANTIT, ET CE QU'IL NE PEUT PAS GARANTIR
-----------------------------------------------------------
Il garantit, par construction :

* qu'un `Resultat` porte toujours l'avertissement de consolidation du corpus —
  un `Resultat` sans avertissement ne peut pas être construit, voir
  `Resultat.__post_init__` ;
* qu'on connaît l'ensemble exact des articles récupérés (`Resultat.numeros`).
  C'est la pièce sur laquelle repose tout le projet : une réponse rédigée en
  aval n'a le droit de citer que des articles de cet ensemble, et ce contrôle
  est une inclusion d'ensembles vérifiable en code, pas une consigne adressée à
  un modèle de langue. Une consigne cède à la première injection, et cède aussi
  toute seule.

Il ne garantit pas que l'article attendu soit dans la liste : sur le banc de
64 questions des fondations, un article attendu est au rang 1 dans six cas sur
dix. C'est la raison d'être de `sur` et de `pourquoi`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from . import corpus as module_corpus
from . import dense as module_dense
from . import lexical as module_lexical

# ── Les trois constantes de l'architecture ──────────────────────────────────

# Profondeur dense : le bras dense tient les rangs 1 à 3, le bras lexical
# remplit la suite. Les trois réglages mesurés (2, 3, 4) rendent le MÊME rang 1 ;
# ce que la profondeur arbitre, ce sont les questions-limites. À 3, le banc des
# fondations gagne trois questions (jours fériés, repos hebdomadaire deux fois)
# et en perd une (salaire minimum, dont l'article tombait au rang 4 du bras
# dense et se fait expulser). L'écart avec la profondeur 4 vaut une question sur
# cinquante-sept : il n'est pas départageable, et présenter 3 comme la bonne
# valeur serait surinterpréter le banc.
PROFONDEUR_DENSE = 3

# Profondeur de travail de chaque bras. Elle n'a rien à voir avec le `k` du
# contrat : elle existe pour que la queue lexicale ait de quoi puiser quand les
# premiers articles lexicaux sont déjà rendus par le bras dense.
PROFONDEUR_BRAS = 50

# ── Le seuil d'abstention, et ce qu'il coûte ────────────────────────────────
#
# CE N'EST PAS UN RÉGLAGE, C'EST UN ARBITRAGE, et le lecteur doit le voir.
#
# Mesuré sur les 57 questions répondables du banc des fondations, en nombres
# absolus plutôt qu'en pourcentages, parce que c'est ainsi que l'échange devient
# concret :
#
#   répondre à tout   : 40 bonnes premières réponses, 17 FAUSSES, et les
#                       7 questions dont la réponse n'est pas dans le Code
#                       reçoivent quand même cinq articles ;
#   marge ≥ 0,04      : 32 bonnes premières réponses, 4 fausses, et 6 des
#                       7 questions hors corpus cessent d'être servies.
#
# On échange donc huit bonnes réponses contre treize fausses en moins. Le prix
# est double et il est lourd :
#
#   • 85,7 % d'abstention correcte se paient 26 points de rappel apparent — le
#     banc compte une abstention comme un rappel nul, et la ligne mesurée tombe
#     de 84,5 à 58,8 au rang 3 ;
#   • 37 % de dérobade : le système se tairait sur 21 des 57 questions
#     répondables, dont 8 qu'il aurait traitées correctement. « Un assistant qui
#     répond à une question sur quatre n'est pas un assistant » ; à ce seuil
#     c'est deux questions sur trois, et c'est le chiffre à surveiller le
#     premier si quelqu'un remonte le seuil.
#
# Sur un outil dont la promesse est la citation vérifiable, cet échange se
# prend : une réponse fausse en droit n'est pas une imprécision, et la citation
# est précisément ce qui donne confiance.
#
# DEUX RÉSERVES, sans lesquelles ce seuil serait présenté malhonnêtement.
#   1. Il est lu sur le banc qui sert aussi à juger, sans échantillon de
#      validation. C'est donc un point de fonctionnement mesuré, pas une valeur
#      établie : d'où un paramètre, pas une constante enfouie.
#   2. Aucun seuil ne sépare vraiment. La marge maximale d'une réponse fausse
#      valait 0,110 et la minimale d'une réponse juste 0,006 : les deux
#      populations se chevauchent. 0,04 est un point d'un compromis continu.
SEUIL_MARGE = 0.04


class QuestionVide(ValueError):
    """La question ne contient rien à chercher."""


@dataclass(frozen=True)
class ArticleTrouve:
    """Un article récupéré, avec de quoi le vérifier dans le texte officiel.

    `score` n'est PAS comparable d'un bras à l'autre, et `bras` est là pour
    qu'on ne l'oublie pas : un cosinus vit entre -1 et 1, un score BM25 entre 0
    et quelques dizaines selon la question. Les afficher comme une « confiance »
    commune serait un mensonge chiffré — et le score dense lui-même en est un :
    mesuré sur le banc des fondations, les scores des réponses justes
    (0,472–0,721) et ceux des réponses fausses (0,458–0,641) se recouvrent
    presque entièrement. Le signal qui sépare est la marge, pas le score, et
    c'est elle que porte le `Resultat`.
    """

    numero: str
    texte: str
    position: str
    score: float
    bras: str
    page_pdf: int = 0


@dataclass(frozen=True)
class Resultat:
    """Ce que `chercher` rend. Le contrat du projet.

    `sur` dit si le système estime avoir trouvé ; il ne vide jamais `articles`.
    C'est volontaire et c'est le cœur du registre de doute : sous le seuil,
    l'interface doit montrer les cinq candidats SANS les présenter comme la
    réponse, et dire quels mots de la question le Code ne connaît pas. Un usager
    qui lit « je ne connais pas le mot *bébé* » reformule ; un usager qui reçoit
    l'article sur les libertés syndicales en réponse à une question sur la
    naissance de son enfant ne sait pas qu'il doit se méfier.
    """

    question: str
    articles: tuple[ArticleTrouve, ...]
    sur: bool
    pourquoi: str
    avertissement: str
    marge: float
    seuil_marge: float
    termes_inconnus: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Le garde-fou de consolidation est STRUCTUREL, pas recommandé. Le
        # corpus est arrêté au 26 octobre 2011 ; un assistant qui laisse croire
        # qu'il connaît le droit en vigueur aujourd'hui est dangereux, et une
        # consigne de « ne pas oublier l'avertissement » serait oubliée le jour
        # où quelqu'un écrit un deuxième gabarit d'affichage. Ici, un Resultat
        # sans avertissement n'existe pas.
        if not (self.avertissement or "").strip():
            raise ValueError(
                "Un Resultat sans avertissement de consolidation ne peut pas "
                "être construit : le corpus est arrêté au 26 octobre 2011 et "
                "toute réponse doit le porter."
            )

    @property
    def numeros(self) -> frozenset[str]:
        """L'ensemble des articles récupérés.

        C'est la référence du seul contrôle qui rende ce projet défendable :
        l'ensemble des articles CITÉS par une réponse rédigée doit être inclus
        dans cet ensemble-ci, sans quoi la réponse entière est rejetée.
        """
        return frozenset(a.numero for a in self.articles)


class Moteur:
    """Les deux bras, la composition du classement, et la décision de doute.

    Le bras dense est injecté et non construit ici : c'est ce qui permet de
    tester l'architecture sans 1,2 Go de modèle ONNX, avec un bras factice
    déterministe. Voir `noyau.dense.BrasDense`.
    """

    def __init__(
        self,
        corpus: module_corpus.Corpus,
        bras_dense: module_dense.BrasDense,
        seuil_marge: float = SEUIL_MARGE,
        profondeur_dense: int = PROFONDEUR_DENSE,
    ) -> None:
        self.corpus = corpus
        self.bras_dense = bras_dense
        self.seuil_marge = seuil_marge
        self.profondeur_dense = profondeur_dense
        self.bras_lexical = module_lexical.IndexLexical(corpus)

    # -- la marge -----------------------------------------------------------

    @staticmethod
    def _marge(classement: Sequence[tuple[str, float]]) -> float:
        """Écart relatif entre le premier et le deuxième score dense.

        Relatif et non absolu : les scores d'un plongement n'ont pas la même
        amplitude d'une question à l'autre, et un écart de 0,05 ne veut pas dire
        la même chose sous un premier score de 0,70 et sous un premier score de
        0,46.

        Deux cas dégénérés, tranchés vers le silence. Un seul candidat : il n'y
        a rien dont se détacher, donc rien qui autorise à affirmer. Un premier
        score négatif ou nul : aucun article ne ressemble à la question, et
        « marge » n'a plus de sens. Le prototype d'arbitrage traitait ces deux
        cas comme une confiance maximale ; le cas ne s'est jamais présenté sur
        les 64 questions du banc, donc ce choix-ci ne déplace aucun chiffre
        mesuré — mais il refuse de parier sur un corpus vide.
        """
        if not classement or classement[0][1] <= 0:
            return 0.0
        if len(classement) < 2:
            return 0.0
        premier, second = classement[0][1], classement[1][1]
        return (premier - second) / premier

    # -- la composition du classement ---------------------------------------

    def _composer(
        self,
        dense: Sequence[tuple[str, float]],
        lexical: Sequence[tuple[str, float]],
        k: int,
    ) -> list[ArticleTrouve]:
        """Dense en tête, lexical en queue, sans doublon.

        Les rangs 1 à `profondeur_dense` sont mécaniquement intouchables : le
        rappel@1 et le rappel@3 de l'architecture sont donc, question par
        question, ceux du bras dense seul. La queue ne cherche pas à améliorer
        le rang 1 — elle cherche à ne pas perdre ce que le bras lexical seul
        trouve, c'est-à-dire les questions à terme exact où le Code renvoie à un
        texte réglementaire qu'il ne contient pas.
        """
        choisis: list[ArticleTrouve] = []
        vus: set[str] = set()

        for numero, score in list(dense)[: min(self.profondeur_dense, k)]:
            choisis.append(self._habiller(numero, score, "dense"))
            vus.add(numero)

        for numero, score in lexical:
            if len(choisis) >= k:
                break
            if numero in vus:
                continue
            choisis.append(self._habiller(numero, score, "lexical"))
            vus.add(numero)

        # Le bras lexical ne rend que les articles qui partagent un terme avec
        # la question : sur une question en langue d'usager, il peut n'en rendre
        # aucun. On complète alors avec la suite du classement dense plutôt que
        # de rendre moins de k articles.
        for numero, score in dense:
            if len(choisis) >= k:
                break
            if numero in vus:
                continue
            choisis.append(self._habiller(numero, score, "dense"))
            vus.add(numero)

        return choisis

    def _habiller(self, numero: str, score: float, bras: str) -> ArticleTrouve:
        article = self.corpus.par_numero[numero]
        return ArticleTrouve(
            numero=numero,
            texte=article["texte"],
            position=article["citation"],
            score=round(float(score), 6),
            bras=bras,
            page_pdf=int(article.get("page_pdf") or 0),
        )

    # -- la phrase ----------------------------------------------------------

    def _pourquoi(
        self,
        articles: Sequence[ArticleTrouve],
        marge: float,
        inconnus: Sequence[str],
    ) -> str:
        """Une phrase française qui dit ce qui a décidé. Lisible par un humain.

        Elle est composée ici et non laissée à l'appelant : si chaque interface
        traduisait les chiffres à sa façon, la raison affichée finirait par ne
        plus correspondre à la décision prise.
        """
        marge_pc = f"{marge * 100:.1f} %".replace(".", ",")
        seuil_pc = f"{self.seuil_marge * 100:.1f} %".replace(".", ",")

        if not articles:
            return (
                "Aucun article du Code ne ressort de cette question : il n'y a "
                "pas de candidat à présenter."
            )

        tete = articles[0].numero
        if marge >= self.seuil_marge:
            return (
                f"L'article {tete} se détache du suivant (marge de {marge_pc}, "
                f"pour un seuil de {seuil_pc})."
            )

        phrase = (
            f"Les premiers articles trouvés se valent de trop près (marge de "
            f"{marge_pc}, pour un seuil de {seuil_pc}) : rien ne désigne "
            f"l'article {tete} comme la réponse."
        )
        if inconnus:
            cites = ", ".join(inconnus[:4])
            phrase += f" Le Code ne connaît pas ces mots de la question : {cites}."
        return phrase

    # -- le contrat ---------------------------------------------------------

    def chercher(self, question: str, k: int = 5) -> Resultat:
        if not isinstance(question, str) or not question.strip():
            raise QuestionVide("La question est vide.")
        if not isinstance(k, int) or k < 1:
            raise ValueError(f"k doit être un entier positif, reçu {k!r}.")

        dense = self.bras_dense.classer(question, PROFONDEUR_BRAS)
        lecture = self.bras_lexical.lire(question, PROFONDEUR_BRAS)

        marge = self._marge(dense)
        articles = self._composer(dense, lecture.classement, k)
        sur = bool(articles) and marge >= self.seuil_marge

        return Resultat(
            question=question,
            articles=tuple(articles),
            sur=sur,
            pourquoi=self._pourquoi(articles, marge, lecture.termes_inconnus),
            avertissement=self.corpus.avertissement,
            marge=round(marge, 6),
            seuil_marge=self.seuil_marge,
            termes_inconnus=lecture.termes_inconnus,
        )


# ── Le moteur du processus ──────────────────────────────────────────────────
#
# Un seul moteur par processus, construit au premier appel et gardé. Le corpus
# et les deux index ne changent pas pendant la vie d'un service, et les
# reconstruire à chaque question multiplierait par mille le coût d'une requête.

_moteur: Moteur | None = None


def charger(seuil_marge: float = SEUIL_MARGE) -> Moteur:
    """Construit le moteur de production. Explicite, et c'est voulu.

    Un service appelle cette fonction à son démarrage. Rien ici ne télécharge :
    si le modèle ou l'index manquent, l'erreur dit quoi lancer — elle ne lance
    pas un quart d'heure de calcul à l'insu de celui qui a posé une question.
    """
    global _moteur
    corpus = module_corpus.charger()
    _moteur = Moteur(corpus, module_dense.charger_bras_dense(corpus), seuil_marge)
    return _moteur


def chercher(question: str, k: int = 5) -> Resultat:
    """Le point d'entrée du projet. Charge le moteur au premier appel."""
    if _moteur is None:
        charger()
    assert _moteur is not None
    return _moteur.chercher(question, k=k)
