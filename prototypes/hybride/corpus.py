"""Chargement du corpus et decoupage en passages, partage par les deux bras.

Les deux bras ne consomment pas le meme objet : BM25 marche bien sur un
article entier (l'IDF se moque de la longueur, le facteur b la corrige),
l'encodeur dense est plafonne en nombre de jetons et dilue un article long
dans un seul vecteur. D'ou un decoupage en passages ici, utilise par le bras
dense seulement, et le score d'article pris comme le maximum de ses passages.
"""

import io
import json
from dataclasses import dataclass, field

CHEMIN_CORPUS = "../../corpus/code-travail.json"


@dataclass
class Article:
    numero: str
    rang: int
    texte: str
    citation: str
    page_pdf: int
    abroge: bool
    chemin_titres: str  # intitules des niveaux renseignes, du livre a la sous-section


@dataclass
class Corpus:
    articles: list[Article]
    avertissement: str
    date_consolidation: str
    index_par_numero: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.index_par_numero = {a.numero: i for i, a in enumerate(self.articles)}


def charger(chemin: str = CHEMIN_CORPUS) -> Corpus:
    brut = json.load(io.open(chemin, encoding="utf-8"))
    articles = []
    for a in brut["articles"]:
        pos = a["position"]
        intitules = [
            pos[n]["intitule"]
            for n in ("livre", "titre", "chapitre", "section", "sous_section")
            if pos[n] and pos[n]["intitule"]
        ]
        articles.append(
            Article(
                numero=a["numero"],
                rang=a["rang"],
                texte=a["texte"],
                citation=a["citation"],
                page_pdf=a["page_pdf"],
                abroge=a["abroge"],
                chemin_titres=" > ".join(intitules),
            )
        )
    articles.sort(key=lambda a: a.rang)
    return Corpus(
        articles=articles,
        avertissement=brut["source"]["avertissement"],
        date_consolidation=brut["source"]["date_consolidation"],
    )


def tete(art: Article) -> str:
    """Le chemin de titres recopie en tete d'un passage, separateur final compris.

    Fonction et non expression recopiee : dense.py doit pouvoir RETIRER cette
    tete au caractere pres pour son ablation, et une tete reconstruite de
    travers ne retire pas ce qu'elle annonce.
    """
    return art.chemin_titres + " > article " + art.numero + ". "


def passages(corpus: Corpus, taille_max: int = 600) -> list[tuple[int, str]]:
    """Decoupe chaque article en morceaux, sans jamais couper un alinea.

    Le chemin de titres est recopie en tete de CHAQUE passage : sans lui,
    l'article 205 se reduit a "il doit etre accorde obligatoirement aux
    salaries un repos hebdomadaire d'au moins vingt-quatre heures" et perd le
    seul mot qui le relie a une question sur le dimanche, celui du chapitre.
    Le cout est une redondance qui rapproche artificiellement tous les
    articles d'un meme chapitre : c'est mesure en ablation dans banc.py.
    """
    sortie: list[tuple[int, str]] = []
    for i, art in enumerate(corpus.articles):
        debut = tete(art)
        alineas = [x.strip() for x in art.texte.split("\n") if x.strip()]
        if not alineas:
            # Le seul cas est l'article 256, abroge : on l'indexe quand meme
            # avec ses titres, pour pouvoir repondre "cet article est abroge"
            # plutot que de ne jamais le trouver.
            sortie.append((i, debut.strip()))
            continue
        courant: list[str] = []
        longueur = 0
        for al in alineas:
            if courant and longueur + len(al) > taille_max:
                sortie.append((i, debut + " ".join(courant)))
                courant, longueur = [], 0
            courant.append(al)
            longueur += len(al)
        if courant:
            sortie.append((i, debut + " ".join(courant)))
    return sortie
