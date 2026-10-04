"""Témoin lexical (BM25) écrit SANS aucune dépendance, pour juger le vectoriel.

Ce fichier n'est pas ma piste : c'est le contrôle. Annoncer un rappel vectoriel
sans dire ce qu'obtient un BM25 de cinquante lignes sur le même banc ne vaut rien
— si l'écart est nul, les 174 Mo de paquets et les 220 Mo de modèle ne sont pas
défendables, et il faut le dire.

Il est écrit du mieux que je peux, pas bridé pour me donner raison : minuscules,
accents retirés, mots vides français, BM25 Okapi aux paramètres usuels. C'est à peu
près ce qu'un développeur ferait en une heure.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

MOTS_VIDES = {
    "a", "au", "aux", "avec", "ce", "ces", "cet", "cette", "dans", "de", "des", "du",
    "elle", "en", "est", "et", "eux", "il", "ils", "je", "la", "le", "les", "leur",
    "lui", "ma", "mais", "me", "meme", "mes", "moi", "mon", "ne", "nos", "notre",
    "nous", "on", "ou", "par", "pas", "pour", "qu", "que", "qui", "sa", "se", "ses",
    "son", "sur", "ta", "te", "tes", "toi", "ton", "tu", "un", "une", "vos", "votre",
    "vous", "c", "d", "j", "l", "m", "n", "s", "t", "y", "ete", "etre", "avoir",
    "si", "sont", "etait", "aussi", "plus", "tout", "tous", "toute", "toutes",
}


def normaliser(texte: str) -> list[str]:
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", texte.lower())
        if unicodedata.category(c) != "Mn"
    )
    return [m for m in re.findall(r"[a-z0-9]+", sans_accent)
            if len(m) > 1 and m not in MOTS_VIDES]


class BM25:
    def __init__(self, documents: dict[str, str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.cles = list(documents)
        self.sacs = [Counter(normaliser(documents[c])) for c in self.cles]
        self.longueurs = [sum(s.values()) for s in self.sacs]
        self.moyenne = sum(self.longueurs) / max(len(self.longueurs), 1)
        presence: Counter = Counter()
        for sac in self.sacs:
            presence.update(sac.keys())
        n = len(self.sacs)
        self.idf = {
            mot: math.log(1 + (n - df + 0.5) / (df + 0.5))
            for mot, df in presence.items()
        }

    def chercher(self, question: str, k: int = 5) -> list[tuple[str, float]]:
        mots = normaliser(question)
        scores = []
        for cle, sac, longueur in zip(self.cles, self.sacs, self.longueurs):
            total = 0.0
            for mot in mots:
                tf = sac.get(mot, 0)
                if not tf:
                    continue
                total += self.idf[mot] * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * longueur / self.moyenne)
                )
            if total:
                scores.append((cle, total))
        return sorted(scores, key=lambda x: -x[1])[:k]
