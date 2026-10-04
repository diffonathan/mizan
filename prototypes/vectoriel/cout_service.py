"""Coût d'une requête EN SERVICE, index déjà construit — mesure séparée, et voici pourquoi.

Premier chiffre mesuré pour embeddinggemma : 1 456 ms par requête. Faux. Il venait
d'un processus qui venait d'y plonger 588 articles : deux sessions ONNX vivantes
en même temps (celle de l'indexation, celle des requêtes), chacune réclamant tous
les cœurs, et dix gigaoctets déjà résidents. Dans un processus neuf qui charge un
index tout fait, la même question prend 20 ms.

L'écart est d'un facteur 70. Publier le premier chiffre aurait condamné une
configuration qui tient en réalité dans les plafonds mémoire du VPS de l'auteur.
D'où ce fichier : l'indexation et le service sont deux régimes, et un banc qui les
mélange ne mesure ni l'un ni l'autre.

Commande :
    .venv/Scripts/python.exe cout_service.py <modele>
(l'index doit déjà être en cache, sinon il est construit et le chiffre redevient faux)
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
import time

import numpy as np

from banc import QUESTIONS
from index_vectoriel import Chercheur, construire_index
from mesurer import memoire_mo

if __name__ == "__main__":
    modele = sys.argv[1] if len(sys.argv) > 1 else "google/embeddinggemma-300m"
    depart_mo = memoire_mo()[0]

    index = construire_index(modele)  # cache=True par défaut
    depart = time.perf_counter()
    chercheur = Chercheur(index)
    ouverture = time.perf_counter() - depart
    chercheur.chercher("question de chauffe")

    durees = []
    for question in QUESTIONS:
        t = time.perf_counter()
        chercheur.chercher(question["q"], k=5)
        durees.append((time.perf_counter() - t) * 1000)

    # La similarité seule, sans le plongement de la question : c'est la part qui
    # grandira avec le corpus, et elle est invisible à côté du reste.
    q = chercheur.index.vecteurs[0]
    repetitions = 1000
    t = time.perf_counter()
    for _ in range(repetitions):
        _ = chercheur.index.vecteurs @ q
    cosinus_ms = (time.perf_counter() - t) * 1000 / repetitions

    courante, pic = memoire_mo()
    print(f"{modele}")
    print(f"  passages indexés            {len(index.passages)}  "
          f"({index.vecteurs.nbytes / 1e6:.2f} Mo de vecteurs, dim {index.vecteurs.shape[1]})")
    print(f"  ouverture de la session     {ouverture * 1000:.0f} ms (une fois au démarrage)")
    print(f"  requête médiane             {np.median(durees):.1f} ms")
    print(f"  requête p95                 {np.percentile(durees, 95):.1f} ms")
    print(f"  dont similarité cosinus     {cosinus_ms:.3f} ms")
    print(f"  mémoire au départ / pic     {depart_mo:.0f} / {pic:.0f} Mo")
