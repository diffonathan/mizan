# -*- coding: utf-8 -*-
"""Les mesures de la couche de détection, hors du module qu'elles mesurent.

    python -m moteur.mesurer_injection           # la couche, sans clé ni modèle
    python -m moteur.mesurer_injection --garde   # + la garde (index dense requis)
    python -m moteur.mesurer_injection --cout    # + le coût d'un examiner()

POURQUOI UN FICHIER SÉPARÉ, ET NON `python -m moteur.injection`
---------------------------------------------------------------
Parce que `moteur/__init__.py` importe déjà `.injection`, et que `moteur.llm`
et `moteur.repondre` l'importent aussi. Lancer le module lui-même par `-m` le
charge donc DEUX FOIS — une fois comme `moteur.injection`, une fois comme
`__main__` — et Python le dit :

    RuntimeWarning: 'moteur.injection' found in sys.modules after import of
    package 'moteur', but prior to execution of 'moteur.injection'

Mesuré, le dédoublement est réel et pas seulement annoncé : les deux copies
portent deux classes `Invite` distinctes et deux tables `MOTIFS` distinctes.
Rien ne casse aujourd'hui, parce que les mesures ne comparent que des chaînes ;
un `isinstance` ou une comparaison de dataclasses entre les deux copies
échouerait sans raison lisible. Et un avertissement en tête d'une sortie de
mesure se recopie dans les dossiers.

Retirer `injection` des réexportations du paquet NE SUFFIRAIT PAS, et c'est
pourquoi la correction est ici : `moteur.repondre` importe `examiner`, donc le
module serait dans `sys.modules` de toute façon.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import sortie  # noqa: E402,F401

from moteur.injection import (  # noqa: E402
    _mesurer_couche,
    _mesurer_frontiere,
    _mesurer_garde,
    _questions_du_jeu,
    examiner,
)

# Cinquante passages sur les 64 questions du jeu : assez d'appels pour que la
# médiane ne dépende plus du bruit de l'horloge, assez peu pour que la mesure
# tienne dans une seconde.
PASSAGES = 50


def mesurer_cout() -> None:
    """Le coût d'un `examiner()`, en médiane, imprimé par cette commande.

    Ce nombre a longtemps été publié en étant attribué à une commande qui ne
    l'imprimait pas, et accompagné d'un RAPPORT au temps d'une recherche dense
    — un rapport dont le dénominateur ne se reproduit pas d'une exécution à
    l'autre (toutes les mesures du projet tiennent entre 20 et 26 ms, et aucune
    n'a redonné la même valeur). Le rapport est donc parti ; la milliseconde,
    elle, est stable et reproductible, à condition qu'une commande l'imprime.
    C'est celle-ci.
    """
    questions = [q["question"] for q in _questions_du_jeu()]
    durees: list[float] = []
    for _ in range(PASSAGES):
        for question in questions:
            depart = time.perf_counter()
            examiner(question)
            durees.append((time.perf_counter() - depart) * 1000)

    mediane = statistics.median(durees)
    print("\nCE QUE COÛTE UN EXAMEN")
    print("-" * 72)
    print(f"  {len(durees)} appels ({PASSAGES} passages sur "
          f"{len(questions)} questions)")
    print(f"  médiane : {mediane:.3f} ms".replace(".", ","))
    print("  Le coût n'est pas un argument : trente expressions régulières")
    print("  contre une inférence, l'ordre de grandeur se raisonne sans")
    print("  chiffre. Il est imprimé pour que le chiffre publié ait une")
    print("  commande, pas pour justifier la couche.")


def principal(arguments: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python -m moteur.mesurer_injection",
        description="Les mesures de la couche de détection d'injection.",
    )
    analyseur.add_argument(
        "--garde", action="store_true",
        help="ajoute la mesure de la garde (demande l'index dense)",
    )
    analyseur.add_argument(
        "--cout", action="store_true",
        help="ajoute le coût médian d'un examiner()",
    )
    options = analyseur.parse_args(arguments)

    _mesurer_couche()
    _mesurer_frontiere()
    if options.cout:
        mesurer_cout()
    if options.garde:
        _mesurer_garde()
    else:
        print("\n(la mesure de la garde demande l'index dense : "
              "python -m moteur.mesurer_injection --garde)")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
