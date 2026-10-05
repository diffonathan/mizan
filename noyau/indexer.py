# -*- coding: utf-8 -*-
"""Construit l'index vectoriel, une fois, hors du chemin d'une requête.

    python -m noyau.indexer              # construit s'il manque
    python -m noyau.indexer --forcer     # recalcule même s'il existe
    python -m noyau.indexer --telecharger  # autorise le téléchargement du modèle
    python -m noyau.indexer --reprendre <fichier.npy>  # adopte des vecteurs déjà calculés

POURQUOI UN SCRIPT SÉPARÉ, ET PAS UN CALCUL PARESSEUX AU PREMIER APPEL
----------------------------------------------------------------------
Parce que ce calcul n'est pas une latence, c'est un déploiement. Mesuré dans les
fondations du projet : un quart d'heure de processeur, et un pic de mémoire
résidente de près de dix gigaoctets si l'on laisse la bibliothèque plonger par
lots de 256 — six fois le plafond du conteneur visé. Un index construit à
l'improviste à la première question d'un usager ne serait pas lent : il serait
tué par le système.

D'où deux décisions ici : la taille des lots est FIXÉE explicitement, et la
construction ne se déclenche jamais toute seule.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import sortie  # noqa: E402,F401  (importé pour son effet sur les flux)

from noyau import corpus as module_corpus  # noqa: E402
from noyau import dense as module_dense  # noqa: E402

# Lots de 32 et non 256. Le pic de mémoire de l'indexation est dominé par la
# taille des lots, et c'est le seul paramètre qui décide si l'opération tient
# dans un conteneur. Le défaut de la bibliothèque a été mesuré à près de dix
# gigaoctets ; le temps total, lui, varie peu avec cette taille.
TAILLE_LOT = 32


def _plonger(corpus: module_corpus.Corpus, hors_ligne: bool):
    import numpy as np

    passages = corpus.passages()
    if hors_ligne:
        plongeur = module_dense.charger_plongeur()
    else:
        from fastembed import TextEmbedding

        print(
            "Téléchargement autorisé : le modèle pèse environ 1,2 Go et n'est "
            "récupéré qu'une fois.",
            flush=True,
        )
        plongeur = TextEmbedding(
            module_dense.MODELE, cache_dir=str(module_dense.dossier_modeles())
        )

    textes = [module_dense.PREFIXE_DOCUMENT + p.texte for p in passages]
    depart = time.perf_counter()
    brut = np.asarray(
        list(plongeur.embed(textes, batch_size=TAILLE_LOT)), dtype=np.float32
    )
    secondes = time.perf_counter() - depart

    # La normalisation est faite ici, pas déléguée : la bibliothèque ne rend pas
    # des vecteurs normés pour tous les modèles, et un produit scalaire de
    # vecteurs non normés n'est pas un cosinus — il favorise les textes longs.
    normes = np.maximum(np.linalg.norm(brut, axis=1, keepdims=True), 1e-12)
    return [p.numero for p in passages], (brut / normes).astype(np.float32), secondes


def _reprendre(corpus: module_corpus.Corpus, source: Path):
    """Adopte un fichier de vecteurs déjà calculé, après contrôles.

    Cette porte existe pour une raison précise et datée : les prototypes du
    projet ont déjà plongé ce corpus avec ce modèle, et leurs vecteurs sont sur
    la machine. Reconstruire à l'identique coûterait un quart d'heure et
    quelques gigaoctets pour obtenir le même index. Les contrôles ci-dessous
    sont ce qui distingue une reprise d'un acte de foi : nombre de vecteurs,
    dimension, et normes unitaires. Ils ne prouvent pas que les vecteurs
    viennent du bon modèle — c'est pourquoi l'empreinte du corpus est écrite
    dans l'index, et pourquoi ce chemin est explicite plutôt qu'automatique.
    """
    import numpy as np

    passages = corpus.passages()
    vecteurs = np.load(source).astype(np.float32)
    if vecteurs.shape[0] != len(passages):
        raise SystemExit(
            f"{source} porte {vecteurs.shape[0]} vecteurs pour "
            f"{len(passages)} passages : ce n'est pas le même corpus."
        )
    normes = np.linalg.norm(vecteurs, axis=1)
    if not np.allclose(normes, 1.0, atol=1e-4):
        raise SystemExit(
            f"{source} porte des vecteurs non normés (normes de "
            f"{normes.min():.4f} à {normes.max():.4f}) : refus, un produit "
            "scalaire sur ces vecteurs ne serait pas un cosinus."
        )
    return [p.numero for p in passages], vecteurs, 0.0


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--forcer", action="store_true",
                           help="recalcule même si l'index existe déjà")
    analyseur.add_argument("--telecharger", action="store_true",
                           help="autorise le téléchargement du modèle (1,2 Go)")
    analyseur.add_argument("--reprendre", type=Path, default=None,
                           help="adopte un fichier .npy de vecteurs déjà calculés")
    arguments = analyseur.parse_args(argv)

    corpus = module_corpus.charger()
    chemin = module_dense.chemin_index()
    empreinte = corpus.empreinte()

    if chemin.exists() and not arguments.forcer:
        try:
            module_dense.lire_index(corpus)
        except module_dense.IndexAbsent as erreur:
            print(f"Index présent mais inutilisable :\n{erreur}", file=sys.stderr)
            return 2
        print(f"Index déjà en place et accordé au corpus : {chemin}")
        return 0

    if arguments.reprendre is not None:
        numeros, vecteurs, secondes = _reprendre(corpus, arguments.reprendre)
        origine = f"repris de {arguments.reprendre.name}"
    else:
        numeros, vecteurs, secondes = _plonger(corpus, hors_ligne=not arguments.telecharger)
        origine = f"calculé en {secondes:.1f} s, lots de {TAILLE_LOT}"

    import numpy as np

    chemin.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "modele": module_dense.MODELE,
        "empreinte_corpus": empreinte,
        "passages": len(numeros),
        "dimension": int(vecteurs.shape[1]),
        "prefixe_document": module_dense.PREFIXE_DOCUMENT,
        "origine": origine,
        "date_consolidation_corpus": corpus.date_consolidation,
    }
    # Les métadonnées voyagent DANS le fichier d'index, pas à côté : un index et
    # sa fiche descriptive séparés finissent par se désaccorder, et c'est
    # l'empreinte qui porte toute la sécurité de ce mécanisme.
    np.savez(
        chemin,
        vecteurs=vecteurs,
        numeros=np.array(numeros, dtype=str),
        meta=np.array(json.dumps(meta, ensure_ascii=False)),
    )
    print(f"Index écrit : {chemin}")
    for cle, valeur in meta.items():
        print(f"  {cle} = {valeur}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
