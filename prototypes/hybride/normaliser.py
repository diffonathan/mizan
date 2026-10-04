"""Normalisation du francais juridique, commune aux deux bras du prototype.

Le corpus ne normalise volontairement pas les apostrophes (2 808 U+0027 contre
6 U+2019) : c'est donc ici qu'il faut le faire, et au meme endroit pour les
documents et pour les questions, sinon les deux vocabulaires divergent sans
qu'aucun test ne le signale.
"""

import unicodedata
import re

# Mots que le Code du travail emploie a chaque article ("present", "loi",
# "dispositions") : les garder ne nuit pas a BM25, qui les penalise par l'IDF.
# Ne sont retires que les mots de fonction, qui faussent la mesure de
# couverture lexicale servant a l'abstention.
MOTS_VIDES = {
    "a", "au", "aux", "avec", "ce", "ces", "cet", "cette", "dans", "de", "des",
    "du", "elle", "en", "est", "et", "eux", "il", "ils", "je", "la", "le",
    "les", "leur", "lui", "ma", "mais", "me", "mes", "mon", "ne", "nos",
    "notre", "nous", "on", "ou", "par", "pas", "pour", "qu", "que", "qui",
    "sa", "se", "ses", "son", "sur", "ta", "te", "tes", "toi", "ton", "tu",
    "un", "une", "vos", "votre", "vous", "y", "d", "l", "n", "s", "c", "j",
    "m", "t", "si", "sont", "ete", "etre", "avoir", "ai", "as", "ont", "suis",
    "quel", "quelle", "quels", "quelles", "combien", "quand", "comment",
    "est-ce", "il-y-a", "plus", "moins", "tout", "tous", "toute", "toutes",
    "peut", "peux", "puis", "dois", "doit", "faut", "fait", "faire", "y-a-t-il",
}

_SEPARATEURS = re.compile(r"[^0-9a-z]+")


def sans_accents(texte: str) -> str:
    """Rabat les diacritiques : une question tapee sans accents doit trouver
    "conge" comme "congé"."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def mots(texte: str) -> list[str]:
    """Decoupe en mots en coupant les elisions.

    "l'employeur" doit donner ["l", "employeur"] et non ["lemployeur"], sinon
    le meme mot porte deux formes selon qu'il suit un article elide ou non.
    Le remplacement de l'apostrophe par un separateur suffit : les deux
    apostrophes Unicode tombent dans la meme classe [^0-9a-z].
    """
    brut = sans_accents(texte.lower())
    return [m for m in _SEPARATEURS.split(brut) if m]


def _radical_secours(mot: str) -> str:
    """Troncature de repli quand le stemmer Snowball n'est pas installable.

    Volontairement timide : elle ne traite que le pluriel et le feminin, les
    seules variations qui separent systematiquement la question du salarie
    ("mes conges") du texte de loi ("le conge annuel"). Un suffixe verbal mal
    coupe ferait plus de degats qu'il n'en reparerait.
    """
    if len(mot) > 4 and mot.endswith("aux"):
        return mot[:-3] + "al"
    if len(mot) > 4 and mot.endswith("es"):
        return mot[:-2]
    if len(mot) > 3 and mot.endswith("s"):
        return mot[:-1]
    if len(mot) > 4 and mot.endswith("e"):
        return mot[:-1]
    return mot


class Radicaliseur:
    """Enveloppe le stemmer francais de py-rust-stemmers, avec repli.

    Le repli existe parce que le bras lexical doit rester utilisable seul :
    c'est l'argument de secours si le bras dense est abandonne, et il serait
    absurde qu'il herite d'une dependance du bras qu'on a supprime.
    """

    def __init__(self) -> None:
        self._moteur = None
        self.nom = "troncature de repli (aucun paquet)"
        try:
            from py_rust_stemmers import SnowballStemmer

            self._moteur = SnowballStemmer("french").stem_word
            self.nom = "snowball-fr (py-rust-stemmers)"
        except Exception:
            pass
        self._cache: dict[str, str] = {}

    def __call__(self, mot: str) -> str:
        r = self._cache.get(mot)
        if r is None:
            if self._moteur is not None:
                r = self._moteur(mot)
            else:
                r = _radical_secours(mot)
            self._cache[mot] = r
        return r

    def jetons(self, texte: str, retirer_mots_vides: bool = False) -> list[str]:
        sortie = []
        for m in mots(texte):
            if retirer_mots_vides and m in MOTS_VIDES:
                continue
            sortie.append(self(m))
        return sortie
