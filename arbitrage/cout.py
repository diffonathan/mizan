# -*- coding: utf-8 -*-
"""Coût de la pile retenue, dans le régime où elle sera servie.

Les deux régimes à ne jamais confondre, et la note du candidat 2 raconte ce
qu'il arrive quand on les confond (un chiffre faux d'un facteur 70) :
  - INDEXATION : une fois, au déploiement. Deux sessions ONNX peuvent y
    vivre en même temps, la mémoire y est au plus haut, et le temps n'a
    aucune importance pour l'usager.
  - SERVICE : un processus neuf qui charge un index déjà calculé et répond.
    C'est le seul régime dont les chiffres intéressent quelqu'un qui héberge.

Ce fichier ne mesure que le second, et il le mesure dans un processus qui
n'a jamais plongé le corpus — c'est la raison pour laquelle il est un
fichier séparé et non une fonction de `comparer.py`.

La mémoire est lue par `GetProcessMemoryInfo` en ctypes plutôt qu'avec
`psutil` : installer un paquet pour trois lignes, dans un projet dont la
question centrale est « combien de dépendances cela vaut-il », serait une
petite incohérence.
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

import ctypes
import ctypes.wintypes as w
import json
import statistics
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "evaluation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


class _Memoire(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


_PSAPI = ctypes.WinDLL("psapi")
_K32 = ctypes.WinDLL("kernel32")
# Les signatures sont déclarées explicitement : sans elles, ctypes passe le
# HANDLE comme un entier 32 bits, l'appel échoue sans rien dire et la mesure
# rend 0,0 Mo — ce qui s'est produit à la première exécution de ce fichier.
_PSAPI.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(_Memoire), w.DWORD]
_PSAPI.GetProcessMemoryInfo.restype = w.BOOL
_K32.GetCurrentProcess.restype = w.HANDLE


def memoire_mo() -> tuple[float, float]:
    info = _Memoire()
    info.cb = ctypes.sizeof(_Memoire)
    if not _PSAPI.GetProcessMemoryInfo(
        _K32.GetCurrentProcess(), ctypes.byref(info), ctypes.sizeof(_Memoire)
    ):
        raise OSError("GetProcessMemoryInfo a échoué ; la mesure serait fausse")
    return info.WorkingSetSize / 2**20, info.PeakWorkingSetSize / 2**20


def poids(chemin: Path) -> float:
    if chemin.is_file():
        return chemin.stat().st_size / 2**20
    return sum(f.stat().st_size for f in chemin.rglob("*") if f.is_file()) / 2**20


def principal() -> int:
    import banc
    import adaptateurs

    jalons = {}
    courant, pic = memoire_mo()
    jalons["processus neuf"] = (courant, pic)

    corpus = banc.charger_corpus()
    jeu = banc.charger_questions()
    # L'effectif du jeu est COMPTÉ, jamais écrit : ce fichier a longtemps
    # imprimé « 64 questions » dans son titre et dans ses deux médianes, bien
    # après l'élargissement du jeu. Une sortie de mesure qui annonce le mauvais
    # effectif est plus nuisible qu'un document qui le fait, parce que c'est
    # elle qui sert de preuve quand on vérifie le document.
    questions = jeu["questions"]
    n = len(questions)
    courant, pic = memoire_mo()
    jalons["corpus et jeu chargés"] = (courant, pic)

    depart = time.perf_counter()
    recuperer = adaptateurs.GreffeDenseTeteLexicalQueue(corpus["articles"])
    secondes_demarrage = time.perf_counter() - depart
    courant, pic = memoire_mo()
    jalons["index prêt (cache relu)"] = (courant, pic)

    # Une question posée deux fois ne coûte pas la même chose la première
    # fois : la session ONNX s'ouvre au premier appel. On la sort donc de la
    # mesure, en la comptant à part — c'est un coût de démarrage, pas un
    # coût par question.
    depart = time.perf_counter()
    recuperer("première question, pour ouvrir la session ONNX", 5)
    ms_premiere = (time.perf_counter() - depart) * 1000

    durees = []
    for q in questions:
        depart = time.perf_counter()
        recuperer(q["question"], 5)
        durees.append((time.perf_counter() - depart) * 1000)
    courant, pic = memoire_mo()
    jalons[f"{n} questions servies"] = (courant, pic)

    # Les millisecondes par question se partagent entre deux termes qui ne
    # vieilliront pas du tout de la même façon : le plongement de la question,
    # qui est constant quelle que soit la taille du corpus, et le produit
    # scalaire contre la matrice entière, qui est LINÉAIRE en nombre
    # d'articles. Savoir lequel des deux domine décide si un index approché
    # est nécessaire quand le corpus grandit, et cette répartition avait été
    # affirmée avant d'être mesurée. Les questions sont donc plongées hors
    # chronomètre, et seul le produit est mesuré.
    # Importés ICI et non en tête de fonction : `numpy` pèse une soixantaine
    # de mégaoctets de mémoire résidente, et les charger plus tôt gonflerait
    # le jalon « processus neuf » ci-dessus, qui doit rester le coût d'un
    # interpréteur nu.
    import numpy as np
    import index_vectoriel

    chercheur = recuperer._chercheur
    matrice = chercheur.index.vecteurs
    vecteurs_questions = [
        index_vectoriel._normaliser(
            np.array(
                list(chercheur.embed.query_embed(
                    chercheur.prefixe_requete + q["question"]))[0]
            ).astype(np.float32)
        )
        for q in questions
    ]
    scalaire = []
    for v in vecteurs_questions:
        depart = time.perf_counter()
        matrice @ v
        scalaire.append((time.perf_counter() - depart) * 1000)

    # Les deux étiquettes qui portent l'effectif sont construites ici, une
    # seule fois : deux f-strings séparées pourraient dériver l'une de l'autre.
    etiquette_mediane = f"par question, médiane sur {n}"
    etiquette_scalaire = f"produit scalaire seul, médiane sur {n}"

    print()
    print(f"  COÛT EN SERVICE — processus neuf, index relu, {n} questions")
    print("  " + "-" * 72)
    print(f"  {'démarrage (chargement du modèle + index)':50}{secondes_demarrage:8.2f} s")
    print(f"  {'première question (ouverture session ONNX comprise)':50}{ms_premiere:8.1f} ms")
    print(f"  {etiquette_mediane:50}{statistics.median(durees):8.2f} ms")
    print(f"  {'par question, 95e centile':50}"
          f"{sorted(durees)[int(0.95 * len(durees))]:8.2f} ms")
    print(f"  {'par question, maximum':50}{max(durees):8.2f} ms")
    print()
    print("  OÙ PARTENT CES MILLISECONDES — les deux termes séparés")
    print("  " + "-" * 72)
    print(f"  {'matrice parcourue à chaque question':50}"
          f"{matrice.shape[0]:5} × {matrice.shape[1]} flottants")
    print(f"  {'soit, en mémoire':50}{matrice.nbytes:10} octets")
    print(f"  {etiquette_scalaire:50}"
          f"{statistics.median(scalaire):8.3f} ms")
    print(f"  {'produit scalaire seul, maximum':50}{max(scalaire):8.3f} ms")
    print(f"  {'part du produit scalaire dans la médiane':50}"
          f"{100 * statistics.median(scalaire) / statistics.median(durees):8.1f} %")
    print()
    print("  MÉMOIRE DU PROCESSUS (Mo)")
    print("  " + "-" * 72)
    for nom, (c, p) in jalons.items():
        print(f"  {nom:50}{c:8.1f}  (pic {p:.1f})")
    print()

    venv = RACINE / "prototypes" / "vectoriel" / ".venv"
    modeles = RACINE / "prototypes" / "vectoriel" / ".cache_modeles"
    print("  POIDS SUR DISQUE (Mo)")
    print("  " + "-" * 72)
    elements = {
        "paquets Python (site-packages du .venv)":
            venv / "Lib" / "site-packages",
        "modèle embeddinggemma-300m (ONNX)":
            modeles / "models--onnx-community--embeddinggemma-300m-ONNX",
        "index vectoriel sérialisé (.npy)":
            RACINE / "prototypes" / "vectoriel" / ".cache_vecteurs"
            / "google_embeddinggemma-300m__entete1__coupe0.npy",
        "corpus JSON":
            RACINE / "corpus" / "code-travail.json",
        "bras lexical (code, zéro dépendance)":
            RACINE / "prototypes" / "lexical" / "bm25.py",
    }
    total = 0.0
    for nom, chemin in elements.items():
        if not chemin.exists():
            print(f"  {nom:50}{'absent':>10}")
            continue
        p = poids(chemin)
        total += p
        print(f"  {nom:50}{p:10.1f}")
    print("  " + "-" * 72)
    print(f"  {'total':50}{total:10.1f}")
    print()

    (Path(__file__).resolve().parent / "res_cout.json").write_text(
        json.dumps({
            "questions_mesurees": n,
            "secondes_demarrage": round(secondes_demarrage, 2),
            "ms_premiere_question": round(ms_premiere, 1),
            "ms_mediane": round(statistics.median(durees), 2),
            "ms_p95": round(sorted(durees)[int(0.95 * len(durees))], 2),
            "ms_max": round(max(durees), 2),
            "ms_produit_scalaire_mediane": round(statistics.median(scalaire), 3),
            "ms_produit_scalaire_max": round(max(scalaire), 3),
            "octets_matrice": int(matrice.nbytes),
            "forme_matrice": [int(matrice.shape[0]), int(matrice.shape[1])],
            "memoire": {k: [round(c, 1), round(p, 1)] for k, (c, p) in jalons.items()},
            "disque_mo": {k: round(poids(v), 1) for k, v in elements.items() if v.exists()},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
