"""Interrogation du prototype en ligne de commande.

Usage : python chercher.py "combien de jours de conges apres deux ans ?"
"""


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

import chemin_paquets  # noqa: F401

import corpus as mod_corpus
from fusion import fusionner, juger
from lexical import IndexLexical


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    question = " ".join(sys.argv[1:])

    corpus = mod_corpus.charger()
    t0 = time.perf_counter()
    lex = IndexLexical(corpus)
    t_lex = time.perf_counter() - t0

    from dense import IndexDense

    t0 = time.perf_counter()
    den = IndexDense(corpus)
    t_den = time.perf_counter() - t0

    t0 = time.perf_counter()
    r_lex = lex.chercher(question, k=50)
    r_den = den.chercher(question, k=50)
    resultats = fusionner(r_lex, r_den)
    couverture, inconnus = lex.couverture(question)
    verdict = juger(resultats, couverture, inconnus)
    t_req = time.perf_counter() - t0

    print(f"Question : {question}\n")
    if verdict.refus:
        print("!! Reponse a ne pas presenter comme sure : " + verdict.raison + "\n")
    for n, r in enumerate(resultats[:5], start=1):
        art = corpus.articles[r.indice]
        print(
            f"{n}. article {art.numero}  rrf={r.score_rrf:.5f} "
            f"(lexical={r.rang_lexical}, dense={r.rang_dense}, page PDF {art.page_pdf})"
        )
        print("   " + art.citation)
        extrait = art.texte.replace("\n", " ")[:260]
        print("   " + (extrait if extrait else "[article abroge, texte vide]"))
    print(
        f"\ncouverture lexicale {verdict.couverture:.0%} | accord des deux bras "
        f"{verdict.accord}/5 | marge {verdict.marge:.1%}"
    )
    print(
        f"indexation lexicale {t_lex*1000:.0f} ms | indexation dense {t_den*1000:.0f} ms "
        f"| requete {t_req*1000:.1f} ms"
    )
    print("\n" + corpus.avertissement)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
