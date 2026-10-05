# -*- coding: utf-8 -*-
"""Banc : que coûte, à la décision de répondre, une question tapée sans accents ?

    "prototypes/vectoriel/.venv/Scripts/python.exe" arbitrage/accents.py
    "prototypes/vectoriel/.venv/Scripts/python.exe" arbitrage/accents.py --controle
    "prototypes/vectoriel/.venv/Scripts/python.exe" arbitrage/accents.py --cout
    "prototypes/vectoriel/.venv/Scripts/python.exe" arbitrage/accents.py --tout \
        --json res_accents.json

CE BANC NE RÉPARE RIEN. Il mesure, et tout nombre que le dépôt publie sur les
accents doit sortir d'ici. La réparation est dans `noyau/accents.py` et son
branchement dans `noyau/recherche.py`.

LA QUESTION POSÉE, ET POURQUOI ELLE N'EST PAS UN CAS LIMITE
-----------------------------------------------------------
Le bras lexical dépouille les accents des deux côtés : « conge » et « congé »
y sont le même jeton. Le bras dense, lui, reçoit la question BRUTE et la
compare à un index calculé sur un texte officiel accentué. Or la décision de
répondre se prend sur la PROXIMITÉ, c'est-à-dire sur un score du bras dense
seul (`noyau.recherche.SEUIL_PROXIMITE`). Le seul bras qui décide est donc le
seul des deux qui soit sensible aux accents.

Et le public de ce service est fait de salariés marocains qui écrivent depuis un
téléphone : taper sans accents n'est pas la marge du cas d'usage, c'en est le
centre. Un seuil réglé sur un corpus accentué et servi à un public qui
n'accentue pas est réglé sur autre chose que son usage.

CE QUE CE BANC IMPRIME, DANS L'ORDRE
------------------------------------
1. la DISTRIBUTION de la chute sur les 93 questions — pas seulement son pire
   cas, parce qu'un pire cas isolé ne dit pas si le défaut est systématique ;
2. les décisions qui BASCULENT, nommées une par une, des deux côtés du seuil ;
3. les atténuations, mesurées sur la moitié de RÉGLAGE puis vérifiées sur la
   moitié RÉSERVÉE — une atténuation qui ne tient pas sur la réservée ne tient
   pas ;
4. l'option « baisser le seuil », chiffrée pour qu'on voie pourquoi elle est
   écartée plutôt que de l'écarter de mémoire.

TROIS COLONNES, ET POURQUOI PAS DEUX
------------------------------------
La dérobade du dépôt se compte sur les 57 questions répondables, injections
comprises. On la garde telle quelle, mais on imprime À CÔTÉ le compte des
injections refusées, pour une raison précise : refuser une injection est tenu
par le dépôt pour une SÉCURITÉ, et la dérobade la compte comme une faute. Une
atténuation qui détruirait cette sécurité ferait donc BAISSER la dérobade et
aurait l'air d'un progrès. Les deux colonnes ensemble, ou rien.

LA COUPE DU JEU N'EST PAS REFAITE ICI
-------------------------------------
Elle vient du champ `volet` de `evaluation/questions.json` : 18 étrangères pour
régler, 18 réservées à la vérification. Les 57 répondables n'ont pas de volet et
servent des deux côtés, comme dans `arbitrage/abstention.py`.
"""
from __future__ import annotations

# Sortie en UTF-8 avant le premier print : voir sortie.py, à la racine.
# « append » et non « insert » : la racine porte des dossiers (corpus,
# evaluation) qui masqueraient des modules voisins de même nom.
import sys as _sys
from pathlib import Path as _Path

RACINE = _Path(__file__).resolve().parents[1]
_sys.path.append(str(RACINE))
import sortie  # noqa: F401,E402  (importé pour son effet sur les flux)

import argparse  # noqa: E402
import json  # noqa: E402
import statistics  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402

from noyau import accents as module_accents  # noqa: E402
from noyau import charger_corpus  # noqa: E402
from noyau import dense as module_dense  # noqa: E402
from noyau import lexical as module_lexical  # noqa: E402
from noyau.recherche import (  # noqa: E402
    PROFONDEUR_BRAS,
    PROFONDEUR_DENSE,
    SEUIL_PROXIMITE,
)

JEU = RACINE / "evaluation" / "questions.json"

# Les deux noms de chaque moitié, comme dans `arbitrage/abstention.py`.
VOLETS = {"choix": "reglage", "reglage": "reglage",
          "controle": "verification", "verification": "verification"}

RANGS_K = (1, 3, 5)

# Les bornes de l'histogramme de la chute, en points de cosinus. Elles sont
# fixées ici plutôt que calculées sur les données : un histogramme dont les
# classes bougent avec l'échantillon ne se compare pas d'une exécution à
# l'autre, et c'est précisément la comparaison qui intéresse.
CLASSES = (-0.02, 0.0, 0.01, 0.02, 0.05, 0.10, 0.20)


# ── Un passage, et tous les signaux d'une question ──────────────────────────

@dataclass(frozen=True)
class Cas:
    """Une question mesurée sous les trois écritures, en un seul passage.

    Un seul passage, parce que comparer deux écritures sur deux chargements
    différents du modèle comparerait deux expériences. La session ONNX est
    déterministe et sans état : les trois proximités d'un même cas sont donc
    strictement comparables.
    """

    id: str
    question: str
    du_corpus: bool
    injection: bool
    famille: str
    volet: str
    attendus: frozenset[str]

    # Les trois écritures. « a » = accentuée (telle que le jeu l'écrit),
    # « d » = désaccentuée (telle qu'un usager pressé la tape), « r » =
    # désaccentuée puis re-accentuée par le lexique du corpus.
    question_d: str
    question_r: str
    prox_a: float
    prox_d: float
    prox_r: float
    # L'atténuation appliquée à une question DÉJÀ accentuée : elle doit être
    # inoffensive, et « doit » n'est pas une mesure. D'où cette colonne.
    prox_ar: float

    rendus_a: tuple[str, ...]
    rendus_d: tuple[str, ...]
    rendus_r: tuple[str, ...]

    def rappel(self, k: int, repond: bool) -> float:
        """Le rappel au rang k, à la manière du banc des fondations.

        Une abstention compte un rappel NUL : sans cela, un système qui se tait
        sur ce qu'il rate verrait son rappel monter en répondant moins.
        """
        if not repond or not self.attendus:
            return 0.0
        return len(set(self.rendus_a[:k]) & self.attendus) / len(self.attendus)

    def rappel_sous(self, k: int, rendus: tuple[str, ...], repond: bool) -> float:
        if not repond or not self.attendus:
            return 0.0
        return len(set(rendus[:k]) & self.attendus) / len(self.attendus)


# ── Les règles comparées ────────────────────────────────────────────────────
#
# Une RÈGLE, ici, c'est un couple (ce que l'usager tape, ce que le service en
# fait). Les nommer ainsi plutôt que « variantes » évite la confusion que ce
# chantier a failli commettre : l'atténuation naïve n'est pas un autre réglage
# du seuil, c'est une autre question envoyée au plongeur.

REGLES: dict[str, tuple[str, str]] = {
    "accentuée, telle quelle": (
        "a",
        "la référence : l'usager tape ses accents, le service ne touche à rien",
    ),
    "SANS accents, telle quelle": (
        "d",
        "LE DÉFAUT MESURÉ : le cas normal du téléphone, servi par le code d'avant",
    ),
    "SANS accents, max(brute, dépouillée)": (
        "max_d_dep",
        "l'atténuation la plus simple — et elle est un NON-ÉVÉNEMENT, voir plus bas",
    ),
    "SANS accents, re-accentuée": (
        "r",
        "L'ATTÉNUATION RETENUE : noyau.accents, une écriture et une seule inférence",
    ),
    "SANS accents, max(brute, re-accentuée)": (
        "max_d_r",
        "la même, mais sans jamais baisser — deux inférences, et voir le prix",
    ),
    "accentuée, re-accentuée": (
        "ar",
        "l'atténuation retenue sur une entrée déjà accentuée : doit être inoffensive",
    ),
}


def proximite(cas: Cas, regle: str) -> float:
    if regle == "a":
        return cas.prox_a
    if regle == "d":
        return cas.prox_d
    if regle == "r":
        return cas.prox_r
    if regle == "ar":
        return cas.prox_ar
    if regle == "max_d_dep":
        # « La question telle quelle ET une variante normalisée, puis la
        # meilleure proximité » — appliquée à une entrée qui n'a PAS d'accents.
        # Les deux branches du maximum sont alors la même chaîne, donc le même
        # plongement, donc le même nombre : ce n'est pas un raccourci de calcul,
        # c'est tout ce que cette règle est. `imprimer_non_evenement` le montre
        # en comptant les questions concernées, et
        # `test_accents_naif_sans_effet` l'épingle. Cette ligne est écrite comme
        # un `max` d'une seule valeur plutôt que simplifiée, pour que la règle
        # reste lisible à côté de `max_d_r` qui, elle, compare deux choses.
        return max(cas.prox_d, cas.prox_d)
    if regle == "max_d_r":
        return max(cas.prox_d, cas.prox_r)
    raise ValueError(f"Règle inconnue : {regle!r}")


def rendus(cas: Cas, regle: str) -> tuple[str, ...]:
    """Le classement rendu sous une règle : c'est lui qui porte le rappel."""
    if regle in ("a", "ar"):
        return cas.rendus_a
    if regle == "r":
        return cas.rendus_r
    if regle == "max_d_r":
        return cas.rendus_r if cas.prox_r >= cas.prox_d else cas.rendus_d
    return cas.rendus_d


# ── Collecte ────────────────────────────────────────────────────────────────

def _composer(dense, lexical, k: int) -> list[str]:
    """Dense en tête, lexical en queue, sans doublon.

    Recopié de `Moteur._composer` et non appelé : ce banc a besoin des scores
    bruts des deux bras, que le `Resultat` du contrat n'expose pas séparément.
    `test_accents_compose_comme_le_noyau` épingle la recopie contre le moteur
    réel — sans ce test elle dériverait, et le rappel imprimé ici serait celui
    d'un système qui n'existe plus.
    """
    choisis: list[str] = []
    vus: set[str] = set()
    for numero, _ in list(dense)[: min(PROFONDEUR_DENSE, k)]:
        choisis.append(numero)
        vus.add(numero)
    for numero, _ in lexical:
        if len(choisis) >= k:
            break
        if numero not in vus:
            choisis.append(numero)
            vus.add(numero)
    for numero, _ in dense:
        if len(choisis) >= k:
            break
        if numero not in vus:
            choisis.append(numero)
            vus.add(numero)
    return choisis


def _questions():
    """Les questions du jeu, avec leur camp et leur volet. Rien n'est décidé ici.

    Les questions `hors_code` et `injection` sont DU corpus : les premières
    renvoient à un texte réglementaire mais leur article de renvoi est dans le
    Code et il est attendu ; les secondes portent une consigne de détournement
    mais contiennent une vraie question de droit. S'en taire est une dérobade
    dans les deux cas. C'est la convention de `arbitrage/abstention.py`, et en
    changer ici rendrait les deux bancs incomparables.
    """
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    for q in jeu["questions"]:
        hors = "sans_reponse" in q["etiquettes"]
        if hors:
            yield (q["id"], q["question"], False, False,
                   q.get("famille_hors_corpus") or "(sans famille)",
                   q.get("volet") or "partout", [])
        else:
            injection = "injection" in q["etiquettes"]
            famille = ("injection" if injection
                       else ("code" if "code" in q["etiquettes"] else "usager"))
            yield (q["id"], q["question"], True, injection, famille,
                   "partout", q["articles_attendus"])


def collecter(moitie: str = "tout"):
    """Un passage sur le jeu, avec le VRAI noyau et le VRAI index.

    QUATRE plongements par question : accentuée, désaccentuée, re-accentuée, et
    l'atténuation sur l'entrée accentuée. Le bras LEXICAL n'est lu qu'une fois
    par question, et ce n'est pas une économie : il dépouille ses entrées, donc
    les trois écritures lui donnent rigoureusement les mêmes jetons. Le mesurer
    trois fois laisserait croire qu'il pourrait différer.
    `test_accents_lexical_invariant` épingle cette invariance.
    """
    corpus = charger_corpus()
    reaccentueur = module_accents.construire(corpus)
    dense = module_dense.charger_bras_dense(corpus)
    lexical = module_lexical.IndexLexical(corpus)

    cas: list[Cas] = []
    for ident, question, du_corpus, injection, famille, volet, attendus in _questions():
        if volet != "partout" and moitie != "tout" and volet != moitie:
            continue

        q_d = module_accents.desaccentuer(question)
        q_r = reaccentueur.appliquer(q_d)
        q_ar = reaccentueur.appliquer(question)

        cl_a = dense.classer(question, PROFONDEUR_BRAS)
        cl_d = dense.classer(q_d, PROFONDEUR_BRAS)
        cl_r = dense.classer(q_r, PROFONDEUR_BRAS)
        cl_ar = dense.classer(q_ar, PROFONDEUR_BRAS)
        lecture = lexical.lire(question, PROFONDEUR_BRAS)

        cas.append(
            Cas(
                id=ident, question=question, du_corpus=du_corpus,
                injection=injection, famille=famille, volet=volet,
                attendus=frozenset(attendus),
                question_d=q_d, question_r=q_r,
                prox_a=cl_a[0][1] if cl_a else 0.0,
                prox_d=cl_d[0][1] if cl_d else 0.0,
                prox_r=cl_r[0][1] if cl_r else 0.0,
                prox_ar=cl_ar[0][1] if cl_ar else 0.0,
                rendus_a=tuple(_composer(cl_a, lecture.classement, 5)),
                rendus_d=tuple(_composer(cl_d, lecture.classement, 5)),
                rendus_r=tuple(_composer(cl_r, lecture.classement, 5)),
            )
        )
    return cas, reaccentueur, dense, lexical


# ── Bilans ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Bilan:
    """Les trois comptes d'une règle, et les effectifs qui les portent.

    Les effectifs sont DANS la structure et non reconstitués à l'impression :
    toute proportion de ce dépôt doit dire sur combien de cas elle porte, à
    l'endroit où elle est écrite, et c'est la règle qui a été payée le plus
    cher.
    """

    abstentions: int
    n_etrangeres: int
    derobade: int
    n_repondables: int
    injections_refusees: int
    n_injections: int
    derobade_hors_injection: int
    n_hors_injection: int
    rappels: dict[int, float]


def bilan(cas: list[Cas], regle: str, seuil: float = SEUIL_PROXIMITE) -> Bilan:
    etrangeres = [c for c in cas if not c.du_corpus]
    repondables = [c for c in cas if c.du_corpus and c.attendus]
    injections = [c for c in repondables if c.injection]
    ordinaires = [c for c in repondables if not c.injection]

    def repond(c: Cas) -> bool:
        return proximite(c, regle) >= seuil

    rap: dict[int, float] = {}
    for k in RANGS_K:
        if repondables:
            rap[k] = sum(
                c.rappel_sous(k, rendus(c, regle), repond(c)) for c in repondables
            ) / len(repondables)
        else:
            rap[k] = float("nan")

    return Bilan(
        abstentions=sum(1 for c in etrangeres if not repond(c)),
        n_etrangeres=len(etrangeres),
        derobade=sum(1 for c in repondables if not repond(c)),
        n_repondables=len(repondables),
        injections_refusees=sum(1 for c in injections if not repond(c)),
        n_injections=len(injections),
        derobade_hors_injection=sum(1 for c in ordinaires if not repond(c)),
        n_hors_injection=len(ordinaires),
        rappels=rap,
    )


# ── Impression ──────────────────────────────────────────────────────────────

def _f(valeur: float, decimales: int = 4) -> str:
    return f"{valeur:.{decimales}f}".replace(".", ",")


def _pc(valeur: float) -> str:
    if valeur != valeur:  # NaN
        return "    —"
    return f"{valeur * 100:5.1f} %".replace(".", ",")


def imprimer_composition(cas: list[Cas], reaccentueur, moitie: str) -> None:
    etrangeres = [c for c in cas if not c.du_corpus]
    repondables = [c for c in cas if c.du_corpus and c.attendus]
    injections = [c for c in repondables if c.injection]
    print()
    print("LE JEU, ET SUR COMBIEN DE CAS CHAQUE PROPORTION SERA CALCULÉE")
    print("-" * 78)
    print(f"  volet demandé            « {moitie} »")
    print(f"  questions du corpus      {len(repondables):>3}  (répondre est le succès)")
    print(f"      dont injections      {len(injections):>3}  (répondre reste le succès : "
          "elles portent une vraie question)")
    print(f"  questions hors corpus    {len(etrangeres):>3}  (se taire est le succès)")
    print(f"  seuil de proximité       {_f(SEUIL_PROXIMITE, 2)}  "
          "(noyau.recherche.SEUIL_PROXIMITE, non rejoué ici)")
    print()
    print(f"  lexique de re-accentuation : {len(reaccentueur.lexique)} formes retenues, "
          f"{len(reaccentueur.ambigues)} écartées")
    print("  écartées parce que le Code écrit les DEUX formes, et que trancher")
    print("  serait corriger du français plutôt que lire un corpus :")
    for debut in range(0, min(len(reaccentueur.ambigues), 24), 12):
        print("      " + ", ".join(reaccentueur.ambigues[debut:debut + 12]))
    print(f"      … {len(reaccentueur.ambigues)} en tout")


def imprimer_distribution(cas: list[Cas]) -> None:
    """La chute, en distribution. Le pire cas seul ne dirait pas si c'est systématique."""
    chutes = [c.prox_a - c.prox_d for c in cas]
    n = len(chutes)
    print()
    print(f"LA CHUTE DE PROXIMITÉ QUAND ON RETIRE LES ACCENTS — SUR {n} QUESTIONS")
    print("-" * 78)
    print("  chute = proximité(accentuée) − proximité(sans accents).")
    print("  Positive : la question perd en retirant les accents.")
    print()
    tries = sorted(chutes)
    quarts = statistics.quantiles(tries, n=4) if n >= 4 else [float("nan")] * 3
    neuf = statistics.quantiles(tries, n=10) if n >= 10 else [float("nan")] * 9
    print(f"  minimum          {_f(tries[0]):>9}      (la question MONTE sans accents)")
    print(f"  1er quartile     {_f(quarts[0]):>9}")
    print(f"  médiane          {_f(statistics.median(tries)):>9}      "
          "la moitié des questions ne bouge pour ainsi dire pas")
    print(f"  3e quartile      {_f(quarts[2]):>9}")
    print(f"  9e décile        {_f(neuf[8]):>9}")
    print(f"  maximum          {_f(tries[-1]):>9}")
    print(f"  moyenne          {_f(statistics.fmean(tries)):>9}")
    print()
    montent = sum(1 for x in chutes if x < 0)
    stables = sum(1 for x in chutes if abs(x) < 1e-9)
    print(f"  questions qui MONTENT sans accents : {montent} / {n}")
    print(f"  questions INCHANGÉES (aucun accent à perdre) : {stables} / {n}")
    print()
    print("  Histogramme (classes fixées dans le code, pour que deux exécutions")
    print("  se comparent) :")
    bornes = [-float("inf"), *CLASSES, float("inf")]
    for bas, haut in zip(bornes, bornes[1:]):
        compte = sum(1 for x in chutes if bas <= x < haut)
        etiquette = (f"< {_f(haut, 2)}" if bas == -float("inf")
                     else f"≥ {_f(bas, 2)}" if haut == float("inf")
                     else f"[{_f(bas, 2)} ; {_f(haut, 2)}[")
        print(f"      {etiquette:>20}  {compte:>3} / {n}  {'█' * compte}")
    print()
    print("  CE QUE CETTE FORME VEUT DIRE. Le défaut n'est pas une dérive")
    print("  d'ensemble : la médiane est nulle et un tiers des questions gagnent")
    print("  même un peu. C'est une QUEUE — quelques questions dont le mot")
    print("  décisif est accentué (« congé », « décès », « durée ») et que le")
    print("  plongeur ne reconnaît plus. Et c'est le pire cas qui décide, parce")
    print("  qu'une décision se prend question par question, pas en moyenne.")


def imprimer_pires(cas: list[Cas], combien: int = 8) -> None:
    print()
    print(f"LES {combien} PLUS FORTES CHUTES, NOMMÉES")
    print("-" * 78)
    print(f"  {'id':<7} {'camp':<10} {'accentuée':>10} {'sans acc.':>10} "
          f"{'chute':>8}   question")
    pires = sorted(cas, key=lambda c: c.prox_d - c.prox_a)[:combien]
    for c in pires:
        camp = "hors" if not c.du_corpus else ("injection" if c.injection else "corpus")
        print(f"  {c.id:<7} {camp:<10} {_f(c.prox_a):>10} {_f(c.prox_d):>10} "
              f"{_f(c.prox_a - c.prox_d):>8}   {c.question[:34]}")
    print()
    print("  À COMPARER À QUOI : À LA PLACE QUE LE SEUIL A POUR LUI.")
    print(f"  Le seuil vaut {_f(SEUIL_PROXIMITE, 2)}. Ses deux dégagements, sur les "
          "questions de ce")
    print("  volet écrites avec leurs accents, sont ceux-ci.")
    sous = [c for c in cas if not c.du_corpus and c.prox_a < SEUIL_PROXIMITE]
    sur = [c for c in cas
           if c.du_corpus and not c.injection and c.prox_a >= SEUIL_PROXIMITE]
    chute_max = max(c.prox_a - c.prox_d for c in cas)
    for lot, phrase in (
        (sous, "la plus haute étrangère qu'il REFUSE"),
        (sur, "la plus basse du corpus qu'il ACCEPTE (hors inj.)"),
    ):
        if not lot:
            continue
        proche = (max(lot, key=lambda c: c.prox_a) if lot is sous
                  else min(lot, key=lambda c: c.prox_a))
        ecart = abs(SEUIL_PROXIMITE - proche.prox_a)
        print(f"      {phrase:<50} {proche.id:>5} à {_f(proche.prox_a)}")
        rapport = (f"soit {chute_max / ecart:.0f} fois moins que la plus "
                   f"forte chute ({_f(chute_max)})").replace(".", ",")
        print(f"      {'son écart au seuil':<50} {_f(ecart):>10}")
        if ecart > 0:
            print(f"      {rapport}")
    # Le plafond de l'amas des étrangères, qu'aucun seuil ne refuse. Il est
    # imprimé ici parce que la deuxième réserve de `noyau.recherche` le cite, et
    # qu'un nombre cité doit sortir d'une commande : sur la moitié de réglage il
    # vaut 0,4905, sur la moitié réservée 0,5523, et une phrase qui donnerait le
    # premier sans dire de quelle moitié il vient serait un maximum sans sa
    # moitié — le même défaut qu'une proportion sans son effectif.
    toutes = [c for c in cas if not c.du_corpus]
    if toutes:
        plafond = max(toutes, key=lambda c: c.prox_a)
        legende = "la plus haute étrangère TOUT COURT, qu'aucun seuil"
        print(f"      {legende:<50} {plafond.id:>5} à {_f(plafond.prox_a)}")
        print("      ne refuse sans refuser la moitié du corpus")
    print()
    print("  C'est tout le propos : la décision ne se joue pas sur des dixièmes")
    print("  mais sur des millièmes de cosinus, et la perte des accents déplace")
    print("  la proximité de plusieurs centièmes. Une secousse qui vaut des")
    print("  dizaines de fois le dégagement d'un seuil n'est pas du bruit autour")
    print("  de ce seuil : c'est plus grand que le seuil lui-même.")


def imprimer_bascules(cas: list[Cas], gauche: str, droite: str,
                      titre: str) -> None:
    """Les décisions qui changent entre deux règles, nommées une par une."""
    print()
    print(titre)
    print("-" * 78)
    bascules = [
        c for c in cas
        if (proximite(c, gauche) >= SEUIL_PROXIMITE)
        != (proximite(c, droite) >= SEUIL_PROXIMITE)
    ]
    if not bascules:
        print("  Aucune. Les deux règles décident pareil sur les "
              f"{len(cas)} questions de ce volet.")
        return
    for c in bascules:
        avant = proximite(c, gauche)
        apres = proximite(c, droite)
        sens = "RÉPOND → se tait" if avant >= SEUIL_PROXIMITE else "se tait → RÉPOND"
        if not c.du_corpus:
            effet = ("abstention GAGNÉE" if apres < SEUIL_PROXIMITE
                     else "étrangère SERVIE")
        elif c.injection:
            effet = ("injection refusée" if apres < SEUIL_PROXIMITE
                     else "INJECTION SERVIE")
        else:
            effet = ("DÉROBADE" if apres < SEUIL_PROXIMITE else "dérobade réparée")
        camp = "hors" if not c.du_corpus else ("injection" if c.injection else "corpus")
        print(f"  {c.id:<7} {camp:<10} {_f(avant)} → {_f(apres)}  "
              f"{sens:<17} {effet}")
        print(f"          « {c.question[:66]} »")
    print(f"  {len(bascules)} bascule(s) sur {len(cas)} questions.")


def imprimer_regles(cas: list[Cas], moitie: str) -> None:
    print()
    print(f"LES RÈGLES COMPARÉES — VOLET « {moitie} »")
    print("-" * 78)
    etrangeres = sum(1 for c in cas if not c.du_corpus)
    repondables = sum(1 for c in cas if c.du_corpus and c.attendus)
    injections = sum(1 for c in cas if c.du_corpus and c.attendus and c.injection)
    ordinaires = repondables - injections
    print(f"  {'règle':38} {'abstention':>12} {'dérobade':>11} "
          f"{'dont hors inj.':>15} {'inj. refusées':>14}")
    print(f"  {'':38} {f'/ {etrangeres}':>12} {f'/ {repondables}':>11} "
          f"{f'/ {ordinaires}':>15} {f'/ {injections}':>14}")
    for nom, (regle, _note) in REGLES.items():
        b = bilan(cas, regle)
        print(f"  {nom:38} {b.abstentions:>12} {b.derobade:>11} "
              f"{b.derobade_hors_injection:>15} {b.injections_refusees:>14}")
    print()
    print(f"  {'règle':38} {'rappel@1':>10} {'@3':>9} {'@5':>9}")
    for nom, (regle, _note) in REGLES.items():
        b = bilan(cas, regle)
        print(f"  {nom:38} {_pc(b.rappels[1]):>10} {_pc(b.rappels[3]):>9} "
              f"{_pc(b.rappels[5]):>9}")
    print()
    for nom, (_regle, note) in REGLES.items():
        print(f"  {nom:38} {note}")


def imprimer_non_evenement(cas: list[Cas]) -> None:
    """L'atténuation naïve, et la raison pour laquelle elle ne peut pas marcher.

    Elle est imprimée et non racontée : c'est la première piste que l'intuition
    propose, et une piste écartée par la mesure vaut mieux qu'une piste écartée
    de mémoire.
    """
    print()
    print("L'ATTÉNUATION NAÏVE, ET POURQUOI ELLE EST UN NON-ÉVÉNEMENT")
    print("-" * 78)
    identiques = sum(
        1 for c in cas
        if module_accents.desaccentuer(c.question_d) == c.question_d
    )
    print("  La piste : plonger la question telle quelle ET une variante")
    print("  normalisée — c'est-à-dire dépouillée de ses accents — puis retenir")
    print("  la meilleure proximité.")
    print()
    print("  Le fait : dépouiller une question DÉJÀ sans accents la rend")
    print(f"  identique à elle-même. Sur les {len(cas)} questions de ce volet, "
          f"c'est le cas {identiques} fois")
    print(f"  sur {len(cas)}. Le maximum porte donc sur deux fois la même valeur, et")
    print("  l'atténuation coûte une inférence pour ne rien changer.")
    print()
    print("  CE N'EST PAS UN DÉFAUT DE RÉGLAGE, C'EST UNE IMPOSSIBILITÉ : la")
    print("  normalisation efface de l'information, elle n'en rend pas. Ce qui")
    print("  manque à « conge », ce sont des accents, et aucune normalisation ne")
    print("  les invente. Il faut les RENDRE, ce que fait noyau.accents en les")
    print("  lisant dans le corpus — ou normaliser les DEUX côtés, ce qui")
    print("  demande de réindexer et rendrait l'index lui-même aveugle aux")
    print("  accents (voir la fin de ce banc).")


def imprimer_seuil(cas: list[Cas]) -> None:
    """L'option « baisser le seuil », chiffrée pour qu'on voie son prix."""
    print()
    print("L'OPTION « BAISSER LE SEUIL », ET SON PRIX")
    print("-" * 78)
    etrangeres = [c for c in cas if not c.du_corpus]
    ordinaires = [c for c in cas if c.du_corpus and c.attendus and not c.injection]
    if not ordinaires or not etrangeres:
        print("  Volet sans les deux camps : rien à comparer.")
        return
    tombees = sorted(ordinaires, key=lambda c: c.prox_d)
    print("  Pour rattraper les questions que la désaccentuation fait tomber, il")
    print("  faudrait descendre le seuil jusqu'à la plus basse d'entre elles.")
    print(f"  {'seuil':>8} {'dérobade hors inj.':>20} {'étrangères servies':>20}")
    for seuil in (SEUIL_PROXIMITE, 0.44, 0.42, 0.40, 0.35,
                  round(tombees[0].prox_d, 4)):
        d = sum(1 for c in ordinaires if c.prox_d < seuil)
        s = sum(1 for c in etrangeres if c.prox_d >= seuil)
        print(f"  {_f(seuil):>8} {f'{d} / {len(ordinaires)}':>20} "
              f"{f'{s} / {len(etrangeres)}':>20}")
    sans_derobade = round(tombees[0].prox_d, 4)
    servies_la = sum(1 for c in etrangeres if c.prox_d >= sans_derobade)
    servies_ici = sum(1 for c in etrangeres if c.prox_d >= SEUIL_PROXIMITE)
    print()
    print("  ÉCARTÉE, et c'est la DERNIÈRE LIGNE du tableau qui l'écarte : pour")
    print(f"  ramener la dérobade à zéro il faut descendre à {_f(sans_derobade)}, et à ce")
    print(f"  seuil-là {servies_la} étrangères sur {len(etrangeres)} sont servies "
          f"au lieu de {servies_ici}.")
    print("  La chute est plus grande que la distance qui sépare les questions du")
    print("  Code des questions étrangères : aucun seuil ne peut l'absorber,")
    print("  parce que baisser le seuil ne rapproche pas la question du Code — il")
    print("  rapproche seulement le Code de tout le reste.")


def imprimer_cout(cas: list[Cas], reaccentueur, dense, repetitions: int = 30) -> None:
    """Ce que l'atténuation retenue coûte, mesuré et non estimé."""
    corpus_mesure = charger_corpus()
    print()
    print("LE COÛT DE L'ATTÉNUATION RETENUE")
    print("-" * 78)

    debut = time.perf_counter()
    for _ in range(10):
        module_accents.construire(corpus_mesure)
    construction = (time.perf_counter() - debut) / 10
    print(f"  construction du lexique    {construction * 1000:>8.0f} ms, "
          "UNE FOIS au chargement du moteur")

    echantillon = [c.question_d for c in cas][: max(len(cas), 1)]
    debut = time.perf_counter()
    for _ in range(repetitions):
        for question in echantillon:
            reaccentueur.appliquer(question)
    par_question = (time.perf_counter() - debut) / (repetitions * len(echantillon))
    print(f"  re-accentuation            {_f(par_question * 1000, 3):>8} ms par question")

    debut = time.perf_counter()
    for question in echantillon:
        dense.classer(question, PROFONDEUR_BRAS)
    inference = (time.perf_counter() - debut) / len(echantillon)
    print(f"  une inférence dense        {inference * 1000:>8.0f} ms par question "
          "(pour l'échelle)")
    print()
    print("  L'ATTÉNUATION RETENUE N'AJOUTE AUCUNE INFÉRENCE. Elle remplace la")
    print("  question envoyée au plongeur, elle ne la double pas : c'est une")
    print("  substitution de chaînes de caractères devant un calcul "
          f"{inference / max(par_question, 1e-9):.0f} fois".replace(".", ","))
    print("  plus cher. La piste à deux inférences était budgétée ; elle n'a pas")
    print("  été retenue, et son prix réel est dans le tableau des règles.")


def imprimer_reindexation() -> None:
    print()
    print("LA PISTE ÉCARTÉE SANS ÊTRE MESURÉE, ET ON LE DIT")
    print("-" * 78)
    print("  Normaliser les DEUX côtés — dépouiller les accents du corpus comme")
    print("  de la question — rendrait la décision strictement indifférente aux")
    print("  accents. C'est la seule piste qui en donnerait la GARANTIE, là où")
    print("  la re-accentuation n'en donne qu'une mesure.")
    print()
    print("  Elle n'a pas été mesurée, et ce n'est pas un oubli : elle demande de")
    print("  reconstruire l'index vectoriel, et un index reconstruit sur un")
    print("  corpus dépouillé n'est plus scellé sur le corpus servi (voir")
    print("  `noyau.dense.lire_index`). Le coût et le risque sont dans")
    print("  DEPLOIEMENT.md ; la décision de le payer n'appartient pas à ce banc.")
    print("  Ce qui appartient à ce banc, c'est de ne pas faire croire que la")
    print("  re-accentuation est équivalente : elle ne l'est pas, elle est")
    print("  seulement mesurée.")


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Que coûte, à la décision de répondre, une question sans accents ?"
    )
    analyseur.add_argument("--controle", action="store_true",
                           help="le volet `verification`, la moitié RÉSERVÉE")
    analyseur.add_argument("--tout", action="store_true",
                           help="les deux volets (pour décrire le jeu, pas pour régler)")
    analyseur.add_argument("--cout", action="store_true",
                           help="mesure aussi ce que l'atténuation coûte en temps")
    analyseur.add_argument("--json", default=None,
                           help="écrit les proximités de chaque question dans ce fichier")
    options = analyseur.parse_args(argv)

    moitie = "tout" if options.tout else VOLETS["controle" if options.controle else "reglage"]
    debut = time.time()
    cas, reaccentueur, dense, lexical = collecter(moitie)
    duree = time.time() - debut

    print("=" * 78)
    print(f"BANC DES ACCENTS — volet « {moitie} », {len(cas)} questions, "
          f"4 plongements chacune, {duree:.0f} s")
    print("=" * 78)
    imprimer_composition(cas, reaccentueur, moitie)
    imprimer_distribution(cas)
    imprimer_pires(cas)
    imprimer_bascules(
        cas, "a", "d",
        "LES DÉCISIONS QUI BASCULENT QUAND L'USAGER N'ACCENTUE PAS (le défaut)")
    imprimer_non_evenement(cas)
    imprimer_regles(cas, moitie)
    imprimer_bascules(
        cas, "a", "r",
        "CE QUI RESTE APRÈS L'ATTÉNUATION RETENUE (accentuée contre re-accentuée)")
    imprimer_bascules(
        cas, "a", "ar",
        "L'ATTÉNUATION SUR UNE ENTRÉE DÉJÀ ACCENTUÉE : elle doit être inoffensive")
    imprimer_seuil(cas)
    if options.cout:
        imprimer_cout(cas, reaccentueur, dense)
    imprimer_reindexation()

    print()
    print("=" * 78)
    print("CE BANC NE RETIENT AUCUN SEUIL. Le seuil se lit dans")
    print("`noyau.recherche.SEUIL_PROXIMITE`, avec ses réserves. Ce banc dit ce")
    print("que ce seuil devient quand l'usager n'accentue pas — et il se lit sur")
    print("« reglage » puis se RAPPORTE sur « controle ».")
    print("=" * 78)

    if options.json:
        chemin = _Path(options.json)
        if not chemin.is_absolute():
            chemin = _Path(__file__).resolve().parent / chemin
        chemin.write_text(
            json.dumps(
                {
                    "volet": moitie,
                    "n": len(cas),
                    "seuil_proximite": SEUIL_PROXIMITE,
                    "partition": "champ `volet` de evaluation/questions.json",
                    "lexique": {
                        "retenues": len(reaccentueur.lexique),
                        "ambigues": list(reaccentueur.ambigues),
                    },
                    "cas": [
                        {
                            "id": c.id,
                            "question": c.question,
                            "question_sans_accents": c.question_d,
                            "question_reaccentuee": c.question_r,
                            "du_corpus": c.du_corpus,
                            "injection": c.injection,
                            "famille": c.famille,
                            "volet": c.volet,
                            "proximites": {
                                "accentuee": round(c.prox_a, 6),
                                "sans_accents": round(c.prox_d, 6),
                                "reaccentuee": round(c.prox_r, 6),
                                "accentuee_puis_reaccentuee": round(c.prox_ar, 6),
                            },
                            "chute": round(c.prox_a - c.prox_d, 6),
                        }
                        for c in cas
                    ],
                    "bilans": {
                        nom: {
                            "abstentions": b.abstentions,
                            "n_etrangeres": b.n_etrangeres,
                            "derobade": b.derobade,
                            "n_repondables": b.n_repondables,
                            "derobade_hors_injection": b.derobade_hors_injection,
                            "n_hors_injection": b.n_hors_injection,
                            "injections_refusees": b.injections_refusees,
                            "n_injections": b.n_injections,
                            "rappels": {str(k): round(v, 4)
                                        for k, v in b.rappels.items()},
                        }
                        for nom, (regle, _note) in REGLES.items()
                        for b in (bilan(cas, regle),)
                    },
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"Proximités écrites dans {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
