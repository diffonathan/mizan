# -*- coding: utf-8 -*-
"""Relit les JSON écrits par `comparer.py` et répond à trois questions précises.

Elles ne sont pas dans la table de `comparer.py` parce qu'elles ne concernent
que la décision finale, et qu'une table qui répond à tout ne se lit plus :
  1. le rappel@5 par catégorie — la table n'imprime que le @3, et c'est au
     rang 5 que se voit l'apport du bras lexical en queue de classement ;
  2. quelles questions l'approche retenue rate encore, nommément ;
  3. où les deux approches comparées diffèrent, question par question — un
     écart de rappel de trois points vaut deux questions, et il faut pouvoir
     les lire plutôt que de commenter une moyenne.
"""
from __future__ import annotations

# Sortie en UTF-8 avant le premier print : voir sortie.py, à la racine. Sans
# lui, ce script s'arrête sur UnicodeEncodeError dès qu'il imprime une flèche.
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

ICI = Path(__file__).resolve().parent
CATEGORIES = ("usager", "code", "multi_articles", "voisine", "reformulation",
              "hors_code", "injection", "sans_reponse")

# Les fichiers que ce script relit sont EXACTEMENT ceux que les commandes du
# §10 de CONCEPTION.md écrivent, un par commande. L'ancienne liste nommait des
# fichiers qu'aucune commande publiée ne produisait : on pouvait donc lire ici
# le résultat d'une exécution dont personne ne connaissait plus les options.
FICHIERS = ("res_candidats.json", "res_greffes.json", "res_marge.json",
            "res_lexical.json")


def charger(*noms):
    detail = {}
    manquants = []
    for nom in noms:
        chemin = ICI / nom
        if not chemin.exists():
            manquants.append(nom)
            continue
        detail.update(json.loads(chemin.read_text(encoding="utf-8"))["detail"])
    if manquants:
        print(f"  absents, donc non relus : {', '.join(manquants)}", file=sys.stderr)
        print("  (les produire avec les commandes du §10 de CONCEPTION.md)",
              file=sys.stderr)
    return detail


def rappel_a(lignes, k, filtre=None):
    lot = [l for l in lignes if l["attendus"] and (filtre is None or filtre in l["etiquettes"])]
    if not lot:
        return None
    total = 0.0
    for l in lot:
        tete = set(l["retrouves"][:k])
        total += len(tete & set(l["attendus"])) / len(l["attendus"])
    return total / len(lot)


def _pc(v):
    return "   —" if v is None else f"{v * 100:4.1f}"


def principal() -> int:
    detail = charger(*FICHIERS)
    if not detail:
        return 2
    retenues = [n for n in sys.argv[1:]] or list(detail)
    inconnues = [n for n in retenues if n not in detail]
    if inconnues:
        print(f"  approche non mesurée dans les fichiers relus : "
              f"{', '.join(inconnues)}", file=sys.stderr)
        print(f"  disponibles : {', '.join(detail)}", file=sys.stderr)
        return 2

    print()
    print("  RAPPEL@5 PAR CATÉGORIE — ce que la table @3 ne montre pas")
    print("  " + "-" * 100)
    print(f"  {'approche':34}" + "".join(f"{c[:9]:>10}" for c in CATEGORIES[:-1]))
    print("  " + "-" * 100)
    for nom in retenues:
        if nom not in detail:
            continue
        lignes = detail[nom]
        print(f"  {nom:34}" + "".join(_pc(rappel_a(lignes, 5, c)).rjust(10)
                                      for c in CATEGORIES[:-1]))
    print()

    if len(retenues) >= 2:
        a, b = retenues[0], retenues[1]
        if a in detail and b in detail:
            ia = {l["id"]: l for l in detail[a]}
            ib = {l["id"]: l for l in detail[b]}
            print(f"  OÙ « {a} » ET « {b} » DIFFÈRENT (rang du premier article attendu)")
            print("  " + "-" * 100)
            for qid in ia:
                la, lb = ia[qid], ib[qid]
                if not la["attendus"]:
                    continue

                def rang(l):
                    for i, n in enumerate(l["retrouves"], 1):
                        if n in l["attendus"]:
                            return i
                    return None

                ra, rb = rang(la), rang(lb)
                if ra == rb:
                    continue
                print(f"  {qid:6} {str(ra or '—'):>3} → {str(rb or '—'):<3} "
                      f"[{','.join(la['etiquettes'])[:28]:28}] « {la['question'][:46]} »")
            print()

    for nom in retenues:
        if nom not in detail:
            continue
        rates = [l for l in detail[nom]
                 if l["attendus"] and not (set(l["retrouves"][:5]) & set(l["attendus"]))]
        print(f"  « {nom} » — {len(rates)} questions dont AUCUN article attendu n'est dans les 5")
        print("  " + "-" * 100)
        for l in rates:
            print(f"  {l['id']:6} attendu {','.join(l['attendus']):14} "
                  f"rendu {','.join(l['retrouves'][:3]) or '(silence)':18} "
                  f"[{','.join(l['etiquettes'])[:24]}]")
            print(f"         « {l['question'][:88]} »")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
