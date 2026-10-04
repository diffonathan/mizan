"""Prototype JETABLE de récupération vectorielle sur le Code du travail marocain.

Rien ici n'est destiné à la production : pas de gestion d'erreur sérieuse, pas de
persistance robuste, un index qui tient en mémoire. Le but est de pouvoir mesurer
ce que le vectoriel sait et ne sait pas faire sur CE corpus.

Deux décisions sont exposées en paramètres parce qu'elles changent les chiffres et
qu'un lecteur doit pouvoir les contester :

- `entete` : faut-il plonger l'article seul, ou précédé de sa place dans la
  hiérarchie (« Du congé annuel payé — De la durée du congé ») ? La hiérarchie
  est une information que le législateur a écrite et que l'article ne répète pas ;
  l'article 231 ne contient jamais le mot « congé annuel » dans sa première phrase.
- `coupe` : les articles longs (listes de sanctions pénales) diluent leur propre
  sujet dans un vecteur moyen. Les découper en passages et ne garder que le
  meilleur passage par article est une parade classique ; elle coûte des vecteurs.

ATTENTION, piège mesuré dans cette session : fastembed ne renvoie PAS des vecteurs
normés pour tous les modèles (normes relevées entre 2,9 et 4,7 avec
paraphrase-multilingual-MiniLM-L12-v2). Le produit scalaire brut n'est donc pas un
cosinus et favoriserait les textes longs. La normalisation est faite ici, pas
déléguée à la bibliothèque.
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
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

RACINE = Path(__file__).resolve().parent
CORPUS = RACINE.parent.parent / "corpus" / "code-travail.json"
CACHE_MODELES = RACINE / ".cache_modeles"
CACHE_VECTEURS = RACINE / ".cache_vecteurs"

# Chaque famille de modèles impose sa propre manière d'annoncer « ceci est une
# question » et « ceci est un document ». Les ignorer dégrade silencieusement le
# rappel de e5 et de embeddinggemma : ce n'est pas un détail d'implémentation.
PREFIXES = {
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
    "google/embeddinggemma-300m": ("task: search result | query: ", "title: none | text: "),
}


@dataclass
class Passage:
    numero: str
    texte: str


@dataclass
class Index:
    modele: str
    entete: bool
    coupe: int | None
    passages: list[Passage]
    vecteurs: np.ndarray
    secondes_plongement: float
    articles: dict = field(repr=False, default_factory=dict)
    centre: np.ndarray | None = None


def _normaliser(v: np.ndarray) -> np.ndarray:
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def charger_articles() -> tuple[dict, list[dict]]:
    donnees = json.loads(CORPUS.read_text(encoding="utf-8"))
    return donnees, donnees["articles"]


def _entete_de(article: dict) -> str:
    """La position d'un article dit souvent son sujet mieux que son texte.

    On ne garde que les intitulés, jamais les « Livre II » / « Chapitre VI » : un
    numéro de chapitre n'a aucun contenu sémantique et ajouterait du bruit
    identique à des centaines d'articles.
    """
    morceaux = []
    for niveau in ("livre", "titre", "chapitre", "section", "sous_section"):
        bloc = article["position"].get(niveau)
        if bloc and bloc.get("intitule"):
            morceaux.append(bloc["intitule"].strip())
    return " — ".join(morceaux)


def _decouper(texte: str, maxi: int) -> list[str]:
    """Regroupe les alinéas en paquets d'au plus `maxi` caractères.

    Le découpage suit les alinéas (le "\\n" du corpus) et jamais le milieu d'une
    phrase : couper « 96 heures de salaire pour les cinq premières années » en deux
    produirait un passage qui ne veut plus rien dire.
    """
    alineas = [a for a in texte.split("\n") if a.strip()]
    paquets, courant = [], ""
    for alinea in alineas:
        if courant and len(courant) + len(alinea) + 1 > maxi:
            paquets.append(courant)
            courant = alinea
        else:
            courant = f"{courant}\n{alinea}" if courant else alinea
    if courant:
        paquets.append(courant)
    return paquets or [texte]


def construire_passages(articles: list[dict], entete: bool, coupe: int | None) -> list[Passage]:
    passages: list[Passage] = []
    for article in articles:
        if not article["texte"].strip():
            # L'unique article abrogé (256) n'a pas de texte. L'indexer serait
            # fabriquer un vecteur sur du vide, donc un faux voisin pour tout.
            continue
        tetes = _entete_de(article) if entete else ""
        corps = _decouper(article["texte"], coupe) if coupe else [article["texte"]]
        for bout in corps:
            texte = f"{tetes}\n{bout}" if tetes else bout
            passages.append(Passage(numero=article["numero"], texte=texte))
    return passages


def construire_index(modele: str, entete: bool = True, coupe: int | None = None,
                     cache: bool = True, centrer: bool = False) -> Index:
    donnees, articles = charger_articles()
    passages = construire_passages(articles, entete, coupe)
    prefixe_doc = PREFIXES.get(modele, ("", ""))[1]

    cle = f"{modele.replace('/', '_')}__entete{int(entete)}__coupe{coupe or 0}.npy"
    chemin = CACHE_VECTEURS / cle
    if cache and chemin.exists():
        vecteurs = np.load(chemin)
        secondes = 0.0
    else:
        embed = TextEmbedding(modele, cache_dir=str(CACHE_MODELES))
        depart = time.perf_counter()
        vecteurs = _normaliser(np.array(list(embed.embed([prefixe_doc + p.texte for p in passages]))))
        secondes = time.perf_counter() - depart
        if cache:
            CACHE_VECTEURS.mkdir(exist_ok=True)
            np.save(chemin, vecteurs)

    centre = None
    if centrer:
        # Remède connu à la « hubness » : dans un espace de plongement, quelques
        # vecteurs se retrouvent proches de tout le monde et sortent en tête de
        # n'importe quelle requête (les art. 500, 502 et 75 l'ont fait ici, cinq
        # fois chacun sur 34 questions). Retirer le vecteur moyen du corpus enlève
        # la composante que tous les articles partagent — celle qui dit « ceci est
        # du droit du travail marocain » et qui n'aide à distinguer personne.
        centre = vecteurs.mean(axis=0)
        vecteurs = _normaliser(vecteurs - centre)

    return Index(modele=modele, entete=entete, coupe=coupe, passages=passages,
                 vecteurs=vecteurs.astype(np.float32), secondes_plongement=secondes,
                 articles={a["numero"]: a for a in articles},
                 centre=None if centre is None else centre.astype(np.float32))


class Chercheur:
    """Garde le modèle chargé entre deux questions : le coût d'ouverture d'une
    session ONNX (mesuré à plusieurs centaines de millisecondes) n'a rien à voir
    avec le coût d'une requête, et les confondre donnerait un chiffre faux."""

    def __init__(self, index: Index):
        self.index = index
        self.embed = TextEmbedding(index.modele, cache_dir=str(CACHE_MODELES))
        self.prefixe_requete = PREFIXES.get(index.modele, ("", ""))[0]

    def chercher(self, question: str, k: int = 5) -> list[tuple[str, float]]:
        q = np.array(list(self.embed.query_embed(
            self.prefixe_requete + question))[0]).astype(np.float32)
        if self.index.centre is not None:
            q = q - self.index.centre
        q = _normaliser(q)
        scores = self.index.vecteurs @ q
        # Un article découpé en trois passages ne doit pas gagner parce qu'il a
        # trois tickets : on retient son MEILLEUR passage, pas leur somme.
        meilleur: dict[str, float] = {}
        for passage, score in zip(self.index.passages, scores):
            s = float(score)
            if s > meilleur.get(passage.numero, -2.0):
                meilleur[passage.numero] = s
        return sorted(meilleur.items(), key=lambda x: -x[1])[:k]


def resume_article(index: Index, numero: str, longueur: int = 160) -> str:
    a = index.articles[numero]
    return f"art. {numero} | {a['texte'][:longueur].replace(chr(10), ' / ')}"


if __name__ == "__main__":
    import sys

    modele = sys.argv[2] if len(sys.argv) > 2 else "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    question = sys.argv[1] if len(sys.argv) > 1 else "combien de jours de congés après deux ans ?"
    idx = construire_index(modele)
    ch = Chercheur(idx)
    depart = time.perf_counter()
    resultats = ch.chercher(question, k=5)
    ms = (time.perf_counter() - depart) * 1000
    print(f"« {question} »  —  {modele}  —  {ms:.0f} ms\n")
    for rang, (numero, score) in enumerate(resultats, 1):
        print(f"{rang}. {score:+.3f}  {resume_article(idx, numero)}")
        print(f"          {idx.articles[numero]['citation']}")
