# -*- coding: utf-8 -*-
"""Indexation à froid : son temps, sa mémoire, et ce que le cache change vraiment.

C'est le contrôle qui autorise tout le reste du dossier. Toutes les mesures de
rappel relisent les vecteurs depuis `.cache_vecteurs/` au lieu de replonger le
corpus, parce que replonger coûte un quart d'heure par modèle. Cette économie
n'est légitime que si les classements obtenus depuis le cache sont ceux qu'une
indexation neuve produirait.

CE QUE CE SCRIPT A TROUVÉ, et qui est la raison de sa forme actuelle : les
vecteurs replongés ne sont PAS identiques à ceux du cache. Le corpus n'a pas
changé (son empreinte est la même), et pourtant l'écart absolu maximal est de
l'ordre du centième sur des vecteurs normés — c'est-à-dire du même ordre que
la valeur typique d'une composante, donc bien au-delà d'un bruit de virgule
flottante. `onnxruntime` ne garantit pas la reproductibilité au bit près d'une
exécution à l'autre : le découpage en lots, le nombre de fils et le choix des
noyaux fusionnés en dépendent.

Un écart sur les vecteurs n'est pas une erreur de mesure pour autant, et c'est
tout l'objet de la seconde moitié de ce fichier : ce qui compte n'est pas que
les vecteurs soient identiques, c'est que les CLASSEMENTS le soient. Le script
mesure donc les deux — l'écart numérique, puis le rappel du banc calculé deux
fois, une fois sur les vecteurs du cache et une fois sur ceux qu'il vient de
recalculer. Si les rappels coïncident, le cache est légitime ; s'ils diffèrent,
aucun chiffre dense du dossier n'est reproductible et il faut le dire.

Pourquoi un fichier et non la commande d'une ligne qu'il remplace : la version
précédente vivait dans un `python -c "..."` du §10 de CONCEPTION.md, ne
relevait pas la mémoire et ne comparait pas les rappels. Le pic de 7 Go
annoncé dans le dossier venait d'une lecture à la main sur le processus vivant,
donc d'un geste que personne ne peut refaire à l'identique, et la conclusion
« écart nul » ne portait que sur un `max()` dont on ne savait pas ce qu'il
impliquait.

ATTENTION : sans `--relire`, ce script réclame plusieurs gigaoctets de mémoire
résidente et un quart d'heure. C'est le résultat qu'il mesure, pas un défaut :
`fastembed` plonge par lots de 256 par défaut.
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

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE / "prototypes" / "vectoriel"))
sys.path.insert(0, str(RACINE / "evaluation"))
sys.path.insert(0, str(ICI))

MODELE = "google/embeddinggemma-300m"
FICHIER_CACHE = "google_embeddinggemma-300m__entete1__coupe0.npy"
# Les vecteurs recalculés sont gardés ici pour deux raisons : rejouer la
# comparaison des rappels en quelques secondes avec `--relire`, et permettre à
# un lecteur de refaire le calcul d'écart sans replonger le corpus.
FICHIER_FROID = "vecteurs_froid.npy"


def empreinte_corpus() -> str:
    """Numéro + texte + citation de chaque article, dans l'ordre du fichier.

    C'est exactement ce qui entre dans un plongement avec `entete=True`. Une
    empreinte du fichier entier changerait pour une virgule déplacée dans les
    métadonnées et ferait soupçonner le corpus à tort.
    """
    donnees = json.loads(
        (RACINE / "corpus" / "code-travail.json").read_text(encoding="utf-8")
    )
    h = hashlib.sha256()
    for a in donnees["articles"]:
        h.update(a["numero"].encode())
        h.update(b"\x00")
        h.update(a["texte"].encode())
        h.update(b"\x00")
        h.update(a.get("citation", "").encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def principal(argv=None) -> int:
    import numpy as np

    import banc
    import index_vectoriel as iv
    from cout import memoire_mo

    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--relire", action="store_true",
                   help=f"réutiliser {FICHIER_FROID} au lieu de replonger le corpus")
    options = a.parse_args(argv)

    chemin_cache = iv.CACHE_VECTEURS / FICHIER_CACHE
    if not chemin_cache.exists():
        print(f"  cache absent : {chemin_cache}", file=sys.stderr)
        return 2

    index_cache = iv.construire_index(MODELE, entete=True, coupe=None, cache=True)
    vecteurs_cache = index_cache.vecteurs

    chemin_froid = ICI / FICHIER_FROID
    if options.relire:
        if not chemin_froid.exists():
            print(f"  {FICHIER_FROID} absent : relancer sans --relire",
                  file=sys.stderr)
            return 2
        vecteurs_froid = np.load(chemin_froid)
        secondes = None
        pic = None
    else:
        depart = time.perf_counter()
        index_froid = iv.construire_index(MODELE, entete=True, coupe=None,
                                          cache=False)
        secondes = time.perf_counter() - depart
        _, pic = memoire_mo()
        vecteurs_froid = index_froid.vecteurs
        np.save(chemin_froid, vecteurs_froid)

    ecart = float(np.abs(vecteurs_froid - vecteurs_cache).max())
    composante = float(np.abs(vecteurs_cache).mean())

    print()
    print("  INDEXATION À FROID — le corpus replongé, sans cache")
    print("  " + "-" * 76)
    print(f"  {'modèle':54}{MODELE:>22}")
    print(f"  {'empreinte du corpus plongé':54}{empreinte_corpus():>22}")
    print(f"  {'passages':54}{len(index_cache.passages):>22}")
    if secondes is None:
        print(f"  {'temps d indexation':54}{'relu de ' + FICHIER_FROID:>22}")
    else:
        print(f"  {'temps d indexation':54}{secondes:>18.1f} s")
        print(f"  {'pic de mémoire résidente du processus':54}{pic:>17.1f} Mo")

    print()
    print("  ÉCART NUMÉRIQUE AVEC LE CACHE")
    print("  " + "-" * 76)
    print(f"  {'forme comparée':54}"
          f"{f'{vecteurs_cache.shape[0]} × {vecteurs_cache.shape[1]}':>22}")
    print(f"  {'écart absolu maximal':54}{ecart:>22.6f}")
    print(f"  {'valeur absolue moyenne d une composante':54}{composante:>22.6f}")
    print(f"  {'écart maximal rapporté à cette moyenne':54}"
          f"{ecart / composante:>21.1%}")

    # Le seul test qui décide : les deux jeux de vecteurs rendent-ils les mêmes
    # articles ? Un écart numérique sur un vecteur ne devient une erreur de
    # mesure que s'il déplace un classement.
    corpus = banc.charger_corpus()
    jeu = banc.charger_questions()
    anomalies = banc.controler_jeu(jeu, corpus)
    if anomalies:
        for x in anomalies:
            print(f"  jeu incohérent : {x}", file=sys.stderr)
        return 2

    index_froid_relu = iv.Index(
        modele=index_cache.modele, entete=index_cache.entete,
        coupe=index_cache.coupe, passages=index_cache.passages,
        vecteurs=vecteurs_froid, secondes_plongement=0.0,
        articles=index_cache.articles, centre=index_cache.centre,
    )
    rapports = {}
    classements = {}
    for nom, index in (("cache", index_cache), ("froid", index_froid_relu)):
        chercheur = iv.Chercheur(index)
        def recuperer(question, k, _c=chercheur):
            return _c.chercher(question, k=k)
        res = banc.executer(recuperer, jeu, corpus, f"gemma-{nom}")
        rapports[nom] = (res.rappel(1), res.rappel(3), res.rappel(5))
        classements[nom] = {l["id"]: l["retrouves"] for l in res.lignes}

    differentes = sorted(q for q in classements["cache"]
                         if classements["cache"][q] != classements["froid"][q])

    print()
    print("  CE QUE CET ÉCART CHANGE AUX CLASSEMENTS — la seule question qui décide")
    print("  " + "-" * 76)
    for nom in ("cache", "froid"):
        r1, r3, r5 = rapports[nom]
        print(f"  rappel sur les vecteurs « {nom:6} »"
              f"{'':16}{r1 * 100:6.1f} {r3 * 100:6.1f} {r5 * 100:6.1f}")
    print(f"  {'questions dont les 5 articles rendus diffèrent':54}"
          f"{len(differentes):>12} / {len(classements['cache'])}")
    for q in differentes:
        print(f"    {q:6} {','.join(classements['cache'][q])}"
              f"  →  {','.join(classements['froid'][q])}")
    print()
    if rapports["cache"] == rapports["froid"] and not differentes:
        print("  Classements identiques : relire le cache ne change aucun chiffre")
        print("  dense de ce dossier, malgré l écart numérique ci-dessus.")
    elif rapports["cache"] == rapports["froid"]:
        print("  Rappels identiques mais classements déplacés : les chiffres")
        print("  agrégés du dossier tiennent, le détail par question non.")
    else:
        print("  RAPPELS DIFFÉRENTS : les chiffres denses du dossier dépendent du")
        print("  cache, et doivent être donnés avec cette incertitude.")
    print()

    # `--relire` ne mesure ni le temps ni la mémoire : il ne doit donc pas les
    # effacer du rapport. Les écraser par des nuls ferait disparaître du JSON
    # les deux chiffres que le §6 de CONCEPTION.md cite, sans que rien ne le
    # signale — exactement le défaut que ce fichier existe pour corriger.
    rapport = ICI / "res_froid.json"
    precedent = {}
    if rapport.exists():
        try:
            precedent = json.loads(rapport.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            precedent = {}
    if secondes is None:
        secondes_ecrites = precedent.get("secondes_indexation")
        pic_ecrit = precedent.get("pic_memoire_mo")
    else:
        secondes_ecrites = round(secondes, 1)
        pic_ecrit = round(pic, 1)

    rapport.write_text(
        json.dumps({
            "modele": MODELE,
            "empreinte_corpus": empreinte_corpus(),
            "passages": len(index_cache.passages),
            "secondes_indexation": secondes_ecrites,
            "pic_memoire_mo": pic_ecrit,
            "mesures_de_temps_relues": secondes is None,
            "forme": [int(vecteurs_cache.shape[0]), int(vecteurs_cache.shape[1])],
            "ecart_max_avec_cache": ecart,
            "composante_moyenne": composante,
            "rappels": {k: [round(x, 4) for x in v] for k, v in rapports.items()},
            "questions_deplacees": differentes,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
