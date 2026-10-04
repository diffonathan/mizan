# -*- coding: utf-8 -*-
"""Mesure plusieurs approches sur le banc indépendant et rend UNE table.

Pourquoi ce fichier existe alors que `evaluation/banc.py` suffirait : un
appel de `banc.py` par approche reconstruit l'index à chaque fois. Pour les
bras denses, l'index coûte de quarante secondes à un quart d'heure, et
surtout chaque approche s'imprime dans son propre rapport, ce qui rend la
comparaison dépendante du copier-coller de l'arbitre. Ici les mesures
viennent du MÊME code que `banc.py` — il est importé, pas réécrit — mais
l'index est construit une fois par famille et la table est produite par la
machine.

Le banc n'est jamais modifié ni contourné : `banc.executer` est la seule
fonction qui calcule un chiffre dans ce fichier.
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

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "evaluation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import banc  # noqa: E402  (le chemin doit être posé avant)
import adaptateurs  # noqa: E402


def mesurer(nom_classe: str, corpus: dict, jeu: dict) -> tuple[banc.Resultats, float, float]:
    """Construit l'approche, la passe au banc, rend aussi ses deux coûts.

    Les deux temps sont séparés parce qu'ils ne se paient pas au même
    moment : l'indexation une fois au démarrage du service, la requête à
    chaque question d'usager. Les confondre a déjà produit un chiffre faux
    d'un facteur 70 dans la note du candidat 2.
    """
    objet = getattr(adaptateurs, nom_classe)
    depart = time.perf_counter()
    recuperer = objet(corpus["articles"]) if isinstance(objet, type) else objet
    secondes_index = time.perf_counter() - depart

    nom = getattr(recuperer, "nom", nom_classe)
    depart = time.perf_counter()
    res = banc.executer(recuperer, jeu, corpus, nom)
    secondes_total = time.perf_counter() - depart
    ms_par_question = secondes_total * 1000 / len(jeu["questions"])
    return res, secondes_index, ms_par_question


def ligne(res: banc.Resultats, secondes_index: float, ms: float) -> dict:
    par = {}
    for etiquette in ("usager", "code", "multi_articles", "voisine",
                      "hors_code", "injection"):
        lot = [l for l in res.lignes if etiquette in l["etiquettes"]]
        par[etiquette] = res.rappel(3, lot) if lot else None
    return {
        "approche": res.nom_recuperation,
        "r1": res.rappel(1), "r3": res.rappel(3), "r5": res.rappel(5),
        "t3": res.touche(3), "t5": res.touche(5),
        "abstention": res.abstention(), "derobade": res.derobade(),
        "bruit": res.bruit(),
        "par_categorie": par,
        "secondes_index": round(secondes_index, 2),
        "ms_par_question": round(ms, 2),
    }


def _pc(v) -> str:
    return "   —" if v is None else f"{v * 100:4.1f}"


def imprimer(lignes: list[dict]) -> None:
    print()
    print("  BANC INDÉPENDANT — 64 questions, 57 répondables, 7 sans réponse")
    print("  " + "=" * 108)
    print(f"  {'approche':30} {'@1':>5} {'@3':>5} {'@5':>5} │ "
          f"{'usager':>6} {'code':>5} {'multi':>5} {'voisi':>5} {'hors':>5} {'inject':>6} │ "
          f"{'abst':>5} {'dérob':>5}")
    print("  " + "-" * 108)
    for l in lignes:
        p = l["par_categorie"]
        print(f"  {l['approche']:30} {_pc(l['r1']):>5} {_pc(l['r3']):>5} {_pc(l['r5']):>5} │ "
              f"{_pc(p['usager']):>6} {_pc(p['code']):>5} {_pc(p['multi_articles']):>5} "
              f"{_pc(p['voisine']):>5} {_pc(p['hors_code']):>5} {_pc(p['injection']):>6} │ "
              f"{_pc(l['abstention']):>5} {_pc(l['derobade']):>5}")
    print("  " + "=" * 108)
    print("  Lecture : rappel macro par question, en %. « abst » = abstention correcte")
    print("  sur les 7 questions sans réponse ; « dérob » = silence sur une question")
    print("  répondable. Les deux dernières colonnes se lisent ENSEMBLE.")
    print()
    print(f"  {'approche':30} {'indexation (s)':>16} {'ms / question':>16}")
    print("  " + "-" * 64)
    for l in lignes:
        print(f"  {l['approche']:30} {l['secondes_index']:>16.2f} {l['ms_par_question']:>16.2f}")
    print()


def principal(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("approches", nargs="+", help="noms de classes de adaptateurs.py")
    a.add_argument("--sortie", type=Path, default=None,
                   help="écrit la table et le détail par question en JSON")
    options = a.parse_args(argv)

    corpus = banc.charger_corpus()
    jeu = banc.charger_questions()
    anomalies = banc.controler_jeu(jeu, corpus)
    if anomalies:
        for x in anomalies:
            print(f"  jeu incohérent : {x}", file=sys.stderr)
        return 2

    lignes, details = [], {}
    for nom in options.approches:
        res, si, ms = mesurer(nom, corpus, jeu)
        lignes.append(ligne(res, si, ms))
        details[res.nom_recuperation] = [
            {
                "id": l["id"], "question": l["question"],
                "etiquettes": l["etiquettes"],
                "attendus": sorted(l["attendus"]),
                "retrouves": l["retrouves"],
                "rappel3": l["rappel"][3], "touche3": l["touche"][3],
            }
            for l in res.lignes
        ]

    imprimer(lignes)
    if options.sortie:
        options.sortie.write_text(
            json.dumps({"table": lignes, "detail": details},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  écrit : {options.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
