# -*- coding: utf-8 -*-
"""Compare les questions des bancs de prototype à celles du jeu indépendant.

Le §8 de CONCEPTION.md avance, comme élément à décharge sur la contamination
du candidat 2, qu'aucune des questions de son banc n'est l'une de celles du
jeu. C'était la dernière affirmation chiffrée du dossier qu'aucune commande ne
rendait, et donc la dernière que le lecteur devait croire sur parole.

Ce que ce script mesure n'innocente personne, et il faut le lire comme ça :
une question reformulée à trois mots près ne serait pas comptée ici. Il
constate une absence de recopiage littéral, ce qui est le minimum, pas une
absence de réglage sur le jeu. Le §8 en tire exactement cette conclusion-là et
pas une plus large.
"""
from __future__ import annotations

# Sortie en UTF-8 avant le premier print : voir sortie.py, à la racine.
# « append » et non « insert » : la racine porte des dossiers (corpus,
# evaluation) qui masqueraient des modules voisins de même nom s'ils passaient
# devant.
import sys as _sys
from pathlib import Path as _Path
_sys.path.append(str(_Path(__file__).resolve().parents[1]))
import sortie  # noqa: F401,E402  (importé pour son effet sur les flux)

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PROTOTYPES = RACINE / "prototypes"
sys.path.insert(0, str(RACINE / "evaluation"))


def _normaliser(texte: str) -> str:
    """Casse et espaces écartées : une recopie à la casse près reste une recopie."""
    return " ".join(texte.lower().split())


def questions_du_candidat_2() -> list[str]:
    """Les 34 répondables et les 3 sans réponse de `prototypes/vectoriel/banc.py`.

    Le banc est importé plutôt que relu au format texte : son contenu est la
    seule définition de son propre jeu, et une expression régulière sur le
    fichier se désaccorderait le jour où son auteur reformate ses listes.
    """
    chemin = str(PROTOTYPES / "vectoriel")
    if chemin not in sys.path:
        sys.path.insert(0, chemin)
    import banc as banc_vectoriel

    return [
        d["q"]
        for d in list(banc_vectoriel.QUESTIONS)
        + list(banc_vectoriel.QUESTIONS_SANS_REPONSE)
    ]


def principal() -> int:
    jeu = json.loads(
        (RACINE / "evaluation" / "questions.json").read_text(encoding="utf-8")
    )
    independantes = {_normaliser(q["question"]): q["id"] for q in jeu["questions"]}

    siennes = questions_du_candidat_2()
    communes = [
        (q, independantes[_normaliser(q)])
        for q in siennes
        if _normaliser(q) in independantes
    ]

    print()
    print("  CHEVAUCHEMENT TEXTUEL — banc du candidat 2 contre jeu indépendant")
    print("  " + "-" * 72)
    print(f"  {'questions du banc du candidat 2':50}{len(siennes):>10}")
    print(f"  {'questions du jeu indépendant':50}{len(independantes):>10}")
    print(f"  {'identiques (casse et espaces écartées)':50}{len(communes):>10}")
    for question, ident in communes:
        print(f"    {ident:6} « {question[:60]} »")
    print()
    print("  Zéro identique ne vaut pas zéro contamination : une question")
    print("  reformulée ne serait pas comptée ici. Voir §8 de CONCEPTION.md.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
