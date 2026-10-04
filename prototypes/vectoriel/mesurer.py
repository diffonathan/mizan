"""Mesure le rappel@1/@3/@5 des configurations vectorielles sur le banc, et le coût.

Commande :
    .venv/Scripts/python.exe mesurer.py                 # toutes les configurations
    .venv/Scripts/python.exe mesurer.py --rapide        # les deux modèles légers
    .venv/Scripts/python.exe mesurer.py --echecs        # détaille les erreurs

La mémoire est relevée avec GetProcessMemoryInfo via ctypes plutôt qu'avec psutil :
un paquet de plus pour trois lignes de mesure ne se justifie pas, et le chiffre
qu'on veut (le pic de mémoire du processus) est exactement celui que Windows donne.
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

import argparse
import ctypes
import ctypes.wintypes as wt
import gc
import json
import time
from pathlib import Path

import numpy as np

from banc import QUESTIONS, QUESTIONS_SANS_REPONSE
from index_vectoriel import Chercheur, charger_articles, construire_index, _entete_de
from temoin_lexical import BM25

RACINE = Path(__file__).resolve().parent

MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# (modèle, entête hiérarchique, découpage en caractères, centrage anti-hubness)
CONFIGURATIONS = [
    (MINILM, True, None, False),
    (MINILM, False, None, False),
    (MINILM, True, 600, False),
    (MINILM, True, None, True),
    ("minishlab/potion-multilingual-128M", True, None, False),
    ("google/embeddinggemma-300m", True, None, False),
    ("google/embeddinggemma-300m", True, None, True),
    ("intfloat/multilingual-e5-large", True, None, False),
    ("intfloat/multilingual-e5-large", True, None, True),
]


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


# Sans argtypes, ctypes tronque le HANDLE à 32 bits et l'appel échoue en
# silence en rendant 0 : une mesure fausse est pire qu'une mesure absente.
_GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
_GetCurrentProcess.restype = wt.HANDLE
_GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
_GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(_PMC), wt.DWORD]
_GetProcessMemoryInfo.restype = wt.BOOL


def memoire_mo() -> tuple[float, float]:
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(_PMC)
    if not _GetProcessMemoryInfo(_GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        raise OSError(ctypes.GetLastError(), "GetProcessMemoryInfo a echoue")
    return pmc.WorkingSetSize / 1e6, pmc.PeakWorkingSetSize / 1e6


def rappels(resultats: dict[int, list[tuple[str, float]]]) -> dict[str, float]:
    attendus = {q["id"]: set(q["attendu"]) for q in QUESTIONS}
    sortie = {}
    for k in (1, 3, 5):
        touches = sum(
            1 for qid, rangs in resultats.items()
            if attendus[qid] & {n for n, _ in rangs[:k]}
        )
        sortie[f"rappel@{k}"] = touches / len(attendus)
    return sortie


def evaluer_vectoriel(modele: str, entete: bool, coupe: int | None,
                      centrer: bool = False, cache: bool = False) -> dict:
    gc.collect()
    avant, _ = memoire_mo()

    depart = time.perf_counter()
    index = construire_index(modele, entete=entete, coupe=coupe, cache=cache,
                             centrer=centrer)
    secondes_index = time.perf_counter() - depart

    chercheur = Chercheur(index)
    # Une requête à blanc : la première inférence d'une session ONNX paie
    # l'allocation des tampons, et la compter dans la médiane serait trompeur.
    chercheur.chercher("question de chauffe")

    resultats, durees = {}, []
    for question in QUESTIONS:
        t = time.perf_counter()
        resultats[question["id"]] = chercheur.chercher(question["q"], k=5)
        durees.append((time.perf_counter() - t) * 1000)

    sans_reponse = {
        q["id"]: chercheur.chercher(q["q"], k=5) for q in QUESTIONS_SANS_REPONSE
    }

    _, pic = memoire_mo()
    return dict(
        modele=modele, entete=entete, coupe=coupe, centrer=centrer,
        passages=len(index.passages), dimension=int(index.vecteurs.shape[1]),
        secondes_index=round(secondes_index, 2),
        secondes_plongement=round(index.secondes_plongement, 2),
        ms_requete_mediane=round(float(np.median(durees)), 1),
        ms_requete_p95=round(float(np.percentile(durees, 95)), 1),
        memoire_pic_mo=round(pic, 1), memoire_avant_mo=round(avant, 1),
        octets_index=int(index.vecteurs.nbytes),
        **rappels(resultats),
        resultats={str(k): v for k, v in resultats.items()},
        sans_reponse={str(k): v for k, v in sans_reponse.items()},
    )


def evaluer_lexical(entete: bool = True) -> dict:
    _, articles = charger_articles()
    documents = {}
    for a in articles:
        if not a["texte"].strip():
            continue
        tete = _entete_de(a) if entete else ""
        documents[a["numero"]] = f"{tete}\n{a['texte']}" if tete else a["texte"]

    depart = time.perf_counter()
    moteur = BM25(documents)
    secondes_index = time.perf_counter() - depart

    resultats, durees = {}, []
    for question in QUESTIONS:
        t = time.perf_counter()
        resultats[question["id"]] = moteur.chercher(question["q"], k=5)
        durees.append((time.perf_counter() - t) * 1000)

    return dict(
        modele=f"TEMOIN BM25 (entete={int(entete)})", entete=entete, coupe=None, centrer=False,
        passages=len(documents), dimension=0,
        secondes_index=round(secondes_index, 2), secondes_plongement=0.0,
        ms_requete_mediane=round(float(np.median(durees)), 1),
        ms_requete_p95=round(float(np.percentile(durees, 95)), 1),
        memoire_pic_mo=round(memoire_mo()[1], 1), memoire_avant_mo=0.0, octets_index=0,
        **rappels(resultats),
        resultats={str(k): v for k, v in resultats.items()},
        sans_reponse={str(q["id"]): moteur.chercher(q["q"], k=5) for q in QUESTIONS_SANS_REPONSE},
    )


def imprimer_tableau(lignes: list[dict]) -> None:
    print(f"\nBanc : {len(QUESTIONS)} questions, {len(QUESTIONS_SANS_REPONSE)} sans réponse dans le corpus\n")
    entetes = ("modèle / variante", "pass.", "dim", "idx s", "req ms", "mém Mo", "@1", "@3", "@5")
    print(f"{entetes[0]:<58} {entetes[1]:>5} {entetes[2]:>5} {entetes[3]:>6} "
          f"{entetes[4]:>7} {entetes[5]:>7} {entetes[6]:>6} {entetes[7]:>6} {entetes[8]:>6}")
    print("-" * 118)
    for l in lignes:
        nom = l["modele"].split("/")[-1]
        if l["coupe"]:
            nom += f" +coupe{l['coupe']}"
        if not l["entete"] and "BM25" not in l["modele"]:
            nom += " SANS entête"
        if l.get("centrer"):
            nom += " +centrage"
        print(f"{nom:<58} {l['passages']:>5} {l['dimension']:>5} {l['secondes_index']:>6.1f} "
              f"{l['ms_requete_mediane']:>7.1f} {l['memoire_pic_mo']:>7.0f} "
              f"{l['rappel@1']:>6.3f} {l['rappel@3']:>6.3f} {l['rappel@5']:>6.3f}")


def imprimer_echecs(ligne: dict) -> None:
    index_articles = {a["numero"]: a for a in charger_articles()[1]}
    par_id = {q["id"]: q for q in QUESTIONS}
    print(f"\n=== Échecs de {ligne['modele']} (rang 1 faux) ===")
    for qid, rangs in ligne["resultats"].items():
        question = par_id[int(qid)]
        rendu = rangs[0][0]
        if rendu in question["attendu"]:
            continue
        rang_bon = next((i + 1 for i, (n, _) in enumerate(rangs) if n in question["attendu"]), None)
        print(f"\nQ{qid} « {question['q']} »")
        print(f"  attendu  art. {'/'.join(question['attendu'])} — {index_articles[question['attendu'][0]]['texte'][:110]!r}")
        print(f"  rendu 1  art. {rendu} ({rangs[0][1]:+.3f}) — {index_articles[rendu]['texte'][:110]!r}")
        print(f"  le bon article est au rang {rang_bon or '>5 (absent du top 5)'}")
        if question.get("piege"):
            print(f"  piège prévu : art. {question['piege']}"
                  f" {'ATTRAPÉ' if rendu == question['piege'] else '(autre erreur)'}")


def imprimer_sans_reponse(lignes: list[dict]) -> None:
    par_id = {q["id"]: q for q in QUESTIONS_SANS_REPONSE}
    print("\n=== Questions sans réponse dans le corpus : score du 1er résultat ===")
    print("(un score élevé ici est un mensonge que l'approche ne sait pas repérer)")
    for l in lignes:
        print(f"\n{l['modele'].split('/')[-1]}")
        for qid, rangs in l["sans_reponse"].items():
            q = par_id[int(qid)]
            print(f"  Q{qid} « {q['q'][:62]} » -> art. {rangs[0][0]} à {rangs[0][1]:+.3f}")


if __name__ == "__main__":
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--rapide", action="store_true", help="seulement les modèles légers")
    parseur.add_argument("--echecs", action="store_true", help="détailler les erreurs de rang 1")
    parseur.add_argument("--json", type=str, default=None, help="écrire les résultats bruts")
    parseur.add_argument("--cache", action="store_true",
                         help="réutiliser/écrire les vecteurs sur disque : le temps "
                              "d'indexation rapporté devient alors faux, utile seulement "
                              "pour les variantes qui rejouent les mêmes vecteurs")
    parseur.add_argument("--une", type=int, default=None,
                         help="n'évaluer QUE la configuration n° i (processus neuf : "
                              "le pic de mémoire d'un modèle n'est juste que mesuré seul)")
    args = parseur.parse_args()

    if args.une is not None:
        modele, entete, coupe, centrer = CONFIGURATIONS[args.une]
        ligne = evaluer_vectoriel(modele, entete, coupe, centrer, cache=args.cache)
        imprimer_tableau([ligne])
        print()
        print(f"  mémoire avant index : {ligne['memoire_avant_mo']:.0f} Mo"
              f"   pic du processus : {ligne['memoire_pic_mo']:.0f} Mo"
              f"   index seul : {ligne['octets_index'] / 1e6:.2f} Mo")
        print(f"  plongement des {ligne['passages']} passages : {ligne['secondes_plongement']:.1f} s"
              f"   requête médiane {ligne['ms_requete_mediane']:.1f} ms"
              f"   p95 {ligne['ms_requete_p95']:.1f} ms")
        imprimer_sans_reponse([ligne])
        if args.echecs:
            imprimer_echecs(ligne)
        if args.json:
            (RACINE / args.json).write_text(json.dumps([ligne], ensure_ascii=False, indent=1), encoding="utf-8")
        raise SystemExit

    configurations = CONFIGURATIONS[:5] if args.rapide else CONFIGURATIONS
    lignes = [evaluer_lexical(True), evaluer_lexical(False)]
    for modele, entete, coupe, centrer in configurations:
        print(f"... {modele} entete={entete} coupe={coupe} centrer={centrer}", flush=True)
        # cache=args.cache est transmis ici aussi : sans lui, --cache n'avait
        # d'effet que sur le chemin --une, et le passage complet recalculait
        # tous les vecteurs en silence apres les avoir demandes sur disque.
        lignes.append(evaluer_vectoriel(modele, entete, coupe, centrer, cache=args.cache))

    imprimer_tableau(lignes)
    imprimer_sans_reponse(lignes)
    if args.echecs:
        for l in lignes:
            imprimer_echecs(l)
    if args.json:
        (RACINE / args.json).write_text(json.dumps(lignes, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nRésultats bruts : {args.json}")
