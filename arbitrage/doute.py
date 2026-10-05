# -*- coding: utf-8 -*-
"""Mesure ce que vaut chaque mécanisme d'abstention sur le banc indépendant.

Pourquoi un fichier à part de `comparer.py` : le banc rend l'abstention et la
dérobade, et c'est exactement ce qu'il doit faire. Mais il ne rend pas le
chiffre qui décide ici — l'EXACTITUDE QUAND LE SYSTÈME PARLE. Un assistant
juridique se juge sur deux nombres indissociables : la part des questions où
il accepte de répondre, et la part de ces réponses qui sont justes. Une
approche qui répond à tout avec 61 % de bon article au rang 1 et une
approche qui répond à la moitié avec 90 % de bon article ne se comparent pas
sur le rappel. (Ces deux-là sont une illustration de la forme du problème, pas
une mesure : les seuls chiffres qui engagent ce fichier sont ceux qu'il
imprime.)

Les trois signaux balayés ici ont tous été proposés par un candidat, aucun
n'est inventé par l'arbitre :
  - MARGE entre le premier et le deuxième score (candidats 1 et 2, qui l'ont
    mesurée séparément comme le seul signal séparateur) ;
  - ACCORD entre le bras lexical et le bras dense (candidat 3, qui en a fait
    le seul résultat dont il soit content) ;
  - COUVERTURE lexicale de la question (candidats 1 et 3, qui la donnent
    tous deux pour non séparatrice — on le revérifie plutôt que de les croire).

Aucun seuil n'est retenu à la fin de ce fichier. Il imprime des courbes
entières, pour une raison qui est le cœur du dossier : choisir un seuil sur
les questions du banc indépendant referait, à l'étage de l'arbitrage,
exactement la faute que les trois candidats ont confessée à l'étage du
prototype.

AUCUN EFFECTIF N'EST ÉCRIT DANS CE FICHIER, ni dans cette prose ni dans les
légendes qu'il imprime. Il en portait trois — « 64 questions », « 57 questions
répondables », « / 7 » — et les trois sont devenus faux le jour où le jeu hors
corpus est passé de 7 à 36 questions, sans que rien ne le signale. Une sortie
de mesure qui annonce le mauvais effectif ne se contente pas d'être fausse :
c'est contre elle qu'on vérifie les documents, et elle y confirme alors
l'erreur. Les effectifs sont donc comptés sur le jeu à chaque exécution.
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

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "evaluation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import banc  # noqa: E402
import adaptateurs  # noqa: E402


def collecter(modele_dense="google/embeddinggemma-300m"):
    """Pour chaque question : les signaux de doute et ce que valait la réponse.

    Un seul passage sur le banc, qui enregistre tout. Les règles d'abstention
    sont ensuite appliquées sur ces enregistrements : cela garantit qu'elles
    sont comparées sur EXACTEMENT les mêmes classements, et qu'un écart entre
    deux règles ne peut pas venir d'une variation de la récupération.
    """
    corpus = banc.charger_corpus()
    jeu = banc.charger_questions()
    anomalies = banc.controler_jeu(jeu, corpus)
    if anomalies:
        raise SystemExit(f"jeu incohérent : {anomalies}")

    greffe = adaptateurs.greffe_fusion(modele_dense, "scores")(corpus["articles"])

    lignes = []
    for q in jeu["questions"]:
        lex, den, verdict_lex = greffe._bras(q["question"])
        fusion = greffe._fusionner(lex, den)
        attendus = set(q.get("articles_attendus", []))

        def marge(liste):
            if len(liste) < 2 or liste[0][1] <= 0:
                return 1.0
            return (liste[0][1] - liste[1][1]) / liste[0][1]

        # La marge dense est prise sur les scores bruts du cosinus, celle de
        # la fusion sur la somme des deux remises à l'échelle [0, 1]. Les deux
        # sont gardées séparées, mais PAS pour la raison qu'écrivait une
        # version précédente de ce commentaire : « la somme vaut toujours 2,0
        # au premier rang » est faux. Dans _echelle, le 1,0 va au seul article
        # qui est le maximum de son bras ; la somme n'atteint 2,0 que si les
        # deux bras ont le MÊME article en tête, ce qui est l'exception.
        # Mesuré sur la même formule, côté prototype hybride (BM25 + MiniLM,
        # fusion.fusionner_par_scores sur ses 25 questions) : 4 fois sur 25,
        # le premier rang est à 2,0 ; sinon entre 1,000 et 2,000, médiane
        # 1,728.
        #
        # La vraie raison de ne pas balayer marge_fusion est là : sa valeur
        # mélange deux choses que ce fichier veut séparer — l'accord des deux
        # bras au sommet, que `accord` mesure déjà pour lui-même, et l'avance
        # du premier sur le deuxième. Elle est enregistrée pour rester
        # inspectable, et aucune règle ci-dessous ne s'en sert.
        lignes.append({
            "id": q["id"],
            "question": q["question"],
            "etiquettes": q.get("etiquettes", []),
            "attendus": attendus,
            "dense": [n for n, _ in den[:5]],
            "fusion": [n for n, _ in fusion[:5]],
            "lexical": [n for n, _ in lex[:5]],
            "marge_dense": marge(den),
            "marge_fusion": marge(fusion),
            "score_dense": den[0][1] if den else 0.0,
            "accord": greffe._accord(lex, den),
            "couverture": verdict_lex.couverture,
        })
    return lignes


def evaluer(lignes, classement: str, accepte) -> dict:
    """Applique une règle d'acceptation et rend les quatre nombres qui comptent."""
    repondables = [l for l in lignes if l["attendus"]]
    sans = [l for l in lignes if not l["attendus"]]

    parle = [l for l in repondables if accepte(l)]
    juste1 = [l for l in parle if l[classement][:1] and set(l[classement][:1]) & l["attendus"]]
    juste3 = [l for l in parle if set(l[classement][:3]) & l["attendus"]]

    return {
        "service": len(parle) / len(repondables),
        "exactitude1": (len(juste1) / len(parle)) if parle else None,
        "exactitude3": (len(juste3) / len(parle)) if parle else None,
        "utiles1": len(juste1),
        "utiles3": len(juste3),
        "parle": len(parle),
        "abstention": sum(1 for l in sans if not accepte(l)) / len(sans),
        "refuses_hors_corpus": sum(1 for l in sans if not accepte(l)),
    }


def _pc(v):
    return "   —" if v is None else f"{v * 100:4.1f}"


def table(titre, lignes, classement, regles):
    repondables = sum(1 for l in lignes if l["attendus"])
    sans = len(lignes) - repondables
    print()
    print(f"  {titre}")
    print("  " + "-" * 96)
    print(f"  {'règle':34} {'service':>8} {'just@1':>7} {'just@3':>7} "
          f"{'bons@1':>7} {'bons@3':>7} {'hors-corpus refusés':>20}")
    print("  " + "-" * 96)
    for nom, regle in regles:
        m = evaluer(lignes, classement, regle)
        # « 4 / 36 » et non « 4 » : une proportion dit toujours sur combien de
        # cas elle porte, à l'endroit où elle est écrite.
        refus = f"{m['refuses_hors_corpus']} / {sans}"
        print(f"  {nom:34} {_pc(m['service']):>8} {_pc(m['exactitude1']):>7} "
              f"{_pc(m['exactitude3']):>7} {m['utiles1']:>7} {m['utiles3']:>7} "
              f"{refus:>20}")
    print("  " + "-" * 96)
    print(f"  service   : part des {repondables} questions répondables où le système")
    print("              accepte de répondre")
    print("  just@1/@3 : parmi CES réponses, part dont un article attendu est au rang 1 / dans les 3")
    print("  bons@1/@3 : nombre absolu de questions correctement servies (le vrai produit rendu)")


def principal() -> int:
    lignes = collecter()

    print()
    print("  SÉPARATION DES SIGNAUX — justes contre faux au rang 1 (bras dense seul)")
    print("  " + "-" * 96)
    repondables = [l for l in lignes if l["attendus"]]
    justes = [l for l in repondables if set(l["dense"][:1]) & l["attendus"]]
    faux = [l for l in repondables if not set(l["dense"][:1]) & l["attendus"]]
    for signal in ("marge_dense", "score_dense", "accord", "couverture"):
        vj = sorted(l[signal] for l in justes)
        vf = sorted(l[signal] for l in faux)
        med = lambda v: v[len(v) // 2]
        print(f"  {signal:16} justes (n={len(justes):2}) min {vj[0]:6.3f} méd {med(vj):6.3f} max {vj[-1]:6.3f}"
              f"   │ faux (n={len(faux):2}) min {vf[0]:6.3f} méd {med(vf):6.3f} max {vf[-1]:6.3f}")
    print()
    print("  Un signal ne sert que si les deux intervalles ne se recouvrent pas trop.")

    table("BRAS DENSE SEUL (gemma) — balayage de la marge",
          lignes, "dense",
          [("tout répondre", lambda l: True)]
          + [(f"marge dense ≥ {s:.3f}", (lambda s: lambda l: l["marge_dense"] >= s)(s))
             for s in (0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10)])

    table("FUSION BM25+gemma — accord des deux bras, et accord + marge",
          lignes, "fusion",
          [("tout répondre", lambda l: True),
           ("accord ≥ 1", lambda l: l["accord"] >= 1),
           ("accord ≥ 2", lambda l: l["accord"] >= 2),
           ("accord ≥ 3", lambda l: l["accord"] >= 3),
           ("couverture ≥ 0,6 (seuil cand. 3)", lambda l: l["couverture"] >= 0.6),
           ("accord ≥ 1 ET couverture ≥ 0,6",
            lambda l: l["accord"] >= 1 and l["couverture"] >= 0.6)])

    table("BRAS DENSE SEUL, mais l'accord avec BM25 sert de garde-fou",
          lignes, "dense",
          [("tout répondre", lambda l: True),
           ("accord ≥ 1", lambda l: l["accord"] >= 1),
           ("accord ≥ 1 OU marge dense ≥ 0,05",
            lambda l: l["accord"] >= 1 or l["marge_dense"] >= 0.05)])

    hors = [l for l in lignes if not l["attendus"]]
    print()
    print(f"  LES {len(hors)} QUESTIONS SANS RÉPONSE, question par question")
    print("  " + "-" * 96)
    for l in lignes:
        if l["attendus"]:
            continue
        print(f"  {l['id']:6} accord {l['accord']}  couv {l['couverture']:.2f}  "
              f"marge {l['marge_dense']:.3f}  score {l['score_dense']:.3f}")
        print(f"         « {l['question'][:84]} »")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
