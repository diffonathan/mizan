"""Est-ce que le vectoriel sait dire « je ne sais pas » ? Mesure, pas opinion.

En droit, rendre le mauvais article n'est pas une imprécision : c'est une réponse
fausse. On veut donc savoir s'il existe un seuil sur le score qui laisse passer les
bonnes réponses et retient les mauvaises. Si les deux populations se chevauchent,
le score de similarité cosinus NE PEUT PAS servir de garde-fou, et il faut le dire
au lieu d'afficher un pourcentage rassurant à côté de la réponse.

Deux signaux candidats sont mesurés :
  - le score absolu du premier résultat ;
  - la MARGE entre le premier et le deuxième. L'intuition est qu'une question bien
    posée sur un corpus bien séparé donne un vainqueur net, alors qu'une question
    hors corpus donne un peloton serré.

Commande :
    .venv/Scripts/python.exe abstention.py [numero_de_configuration]
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

import sys

import numpy as np

from banc import QUESTIONS, QUESTIONS_SANS_REPONSE
from index_vectoriel import Chercheur, construire_index
from mesurer import CONFIGURATIONS


def observer(chercheur: Chercheur) -> tuple[list[dict], list[dict]]:
    repondables = []
    for question in QUESTIONS:
        rangs = chercheur.chercher(question["q"], k=5)
        repondables.append(dict(
            id=question["id"], q=question["q"],
            score=rangs[0][1], marge=rangs[0][1] - rangs[1][1],
            juste=rangs[0][0] in question["attendu"],
            rendu=rangs[0][0], attendu=question["attendu"],
        ))
    hors = []
    for question in QUESTIONS_SANS_REPONSE:
        rangs = chercheur.chercher(question["q"], k=5)
        hors.append(dict(id=question["id"], q=question["q"],
                         score=rangs[0][1], marge=rangs[0][1] - rangs[1][1],
                         rendu=rangs[0][0]))
    return repondables, hors


def separation(valeurs_justes: list[float], valeurs_fausses: list[float]) -> float:
    """Probabilité qu'un cas juste ait un signal plus élevé qu'un cas faux (AUC).

    0,5 signifie que le signal ne distingue rien. On la calcule à la main plutôt
    que d'installer scikit-learn pour une double boucle sur 34 points.
    """
    if not valeurs_justes or not valeurs_fausses:
        return float("nan")
    gagne = sum(
        1.0 if j > f else 0.5 if j == f else 0.0
        for j in valeurs_justes for f in valeurs_fausses
    )
    return gagne / (len(valeurs_justes) * len(valeurs_fausses))


def table_de_seuils(repondables: list[dict], hors: list[dict], champ: str) -> None:
    valeurs = sorted({round(o[champ], 3) for o in repondables + hors})
    print(f"\n  seuil({champ})  répondues  justes/répondues  exactitude  hors-corpus refusées")
    for seuil in valeurs[:: max(1, len(valeurs) // 12)]:
        repondues = [o for o in repondables if o[champ] >= seuil]
        justes = sum(1 for o in repondues if o["juste"])
        refusees = sum(1 for o in hors if o[champ] < seuil)
        exactitude = justes / len(repondues) if repondues else float("nan")
        print(f"  {seuil:>12.3f}  {len(repondues):>9}  {justes:>6}/{len(repondues):<10}"
              f"  {exactitude:>10.2f}  {refusees:>20}/{len(hors)}")


if __name__ == "__main__":
    numero = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    modele, entete, coupe, centrer = CONFIGURATIONS[numero]
    print(f"Configuration {numero} : {modele} entete={entete} coupe={coupe} centrage={centrer}")

    index = construire_index(modele, entete=entete, coupe=coupe, centrer=centrer)
    chercheur = Chercheur(index)
    repondables, hors = observer(chercheur)

    justes = [o for o in repondables if o["juste"]]
    faux = [o for o in repondables if not o["juste"]]
    print(f"\n{len(justes)} rangs 1 justes, {len(faux)} faux, {len(hors)} questions hors corpus")

    for champ in ("score", "marge"):
        sj = [o[champ] for o in justes]
        sf = [o[champ] for o in faux]
        sh = [o[champ] for o in hors]
        print(f"\n=== signal : {champ} ===")
        print(f"  justes      min {min(sj):+.3f}  médiane {np.median(sj):+.3f}  max {max(sj):+.3f}")
        print(f"  faux        min {min(sf):+.3f}  médiane {np.median(sf):+.3f}  max {max(sf):+.3f}")
        print(f"  hors corpus min {min(sh):+.3f}  médiane {np.median(sh):+.3f}  max {max(sh):+.3f}")
        print(f"  séparation juste/faux (AUC) : {separation(sj, sf):.3f}"
              f"   —   juste/hors-corpus : {separation(sj, sh):.3f}")
        recouvrement = sum(1 for f in sf if f >= min(sj))
        print(f"  {recouvrement} des {len(sf)} réponses FAUSSES ont un {champ} supérieur"
              f" au plus faible {champ} d'une réponse JUSTE")
        table_de_seuils(repondables, hors, champ)
