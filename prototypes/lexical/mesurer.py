"""
Mesure du prototype lexical : rappel, coût, échecs, capacité à douter.

    python mesurer.py

Tout ce que ce script imprime est produit par l'exécution en cours. Aucun
nombre du compte rendu n'a d'autre origine.
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

import statistics
import sys
import time
import tracemalloc

from bm25 import IndexLexical, charger_corpus
from questions import BANC

sys.stdout.reconfigure(encoding="utf-8")

K_MAX = 5


def rangs(index: IndexLexical) -> list[tuple[str, str, set[str], str, int | None, object]]:
    """Pour chaque question, le rang du premier article attendu (None si absent du top-5)."""
    sortie = []
    for identifiant, question, attendus, registre, _ in BANC:
        verdict = index.chercher(question, k=K_MAX)
        rang = None
        for position, resultat in enumerate(verdict.resultats, 1):
            if resultat.numero in attendus:
                rang = position
                break
        sortie.append((identifiant, question, attendus, registre, rang, verdict))
    return sortie


def rappels(résultats) -> dict[int, float]:
    total = len(résultats)
    return {
        k: sum(1 for *_, rang, _ in résultats if rang is not None and rang <= k) / total
        for k in (1, 3, 5)
    }


def pourcent(x: float) -> str:
    return f"{100 * x:5.1f} %"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Coût : construction de l'index, mémoire, temps par requête
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 78)
print("1. COÛT MESURÉ")
print("=" * 78)

t0 = time.perf_counter()
corpus = charger_corpus()
t_chargement = (time.perf_counter() - t0) * 1000

articles = corpus["articles"]

# Deux constructions distinctes, et c'est voulu : tracemalloc instrumente
# chaque allocation et ralentit le code qu'il observe. Chronométrer et mesurer
# la mémoire dans le même passage donnerait un temps d'indexation faux.
t0 = time.perf_counter()
index = IndexLexical(articles)
t_index = (time.perf_counter() - t0) * 1000

tracemalloc.start()
_mesure_memoire = IndexLexical(articles)
courant, pic = tracemalloc.get_traced_memory()
tracemalloc.stop()
del _mesure_memoire

print(f"articles indexés                : {len(articles)}")
print(f"lecture du JSON                 : {t_chargement:8.1f} ms")
print(f"construction de l'index         : {t_index:8.1f} ms")
print(f"total démarrage à froid         : {t_chargement + t_index:8.1f} ms")
print(f"mémoire de l'index (tracemalloc): {courant / 1024:8.1f} Kio "
      f"(pic {pic / 1024:.1f} Kio)")
print(f"taille du vocabulaire           : {len(index.idf)} racines")
print(f"longueur moyenne d'un article   : {index.longueur_moyenne:.1f} jetons")

# Temps par requête : chaque question du banc, dix passages, pour que la
# dispersion soit visible plutôt que cachée derrière une moyenne.
durées = []
for _ in range(10):
    for _, question, *_ in BANC:
        t0 = time.perf_counter()
        index.chercher(question, k=K_MAX)
        durées.append((time.perf_counter() - t0) * 1000)

print(f"\nrequêtes chronométrées          : {len(durées)} "
      f"({len(BANC)} questions × 10)")
print(f"temps par requête — médiane      : {statistics.median(durées):7.2f} ms")
print(f"temps par requête — moyenne      : {statistics.mean(durées):7.2f} ms")
print(f"temps par requête — min / max    : {min(durées):7.2f} / {max(durées):.2f} ms")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Rappel
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 78)
print("2. RAPPEL SUR LE BANC")
print("=" * 78)

résultats = rangs(index)
rappel_reference = rappels(résultats)
print(f"{len(BANC)} questions")
print(f"rappel@1 : {pourcent(rappel_reference[1])}")
print(f"rappel@3 : {pourcent(rappel_reference[3])}")
print(f"rappel@5 : {pourcent(rappel_reference[5])}")

for registre in ("technique", "ordinaire"):
    sous = [x for x in résultats if x[3] == registre]
    rr = rappels(sous)
    print(
        f"\n  registre « {registre} » ({len(sous)} questions) : "
        f"@1 {pourcent(rr[1])}  @3 {pourcent(rr[3])}  @5 {pourcent(rr[5])}"
    )

print("\nrang de l'article attendu, question par question :")
for identifiant, _, attendus, registre, rang, _ in résultats:
    marque = "—" if rang is None else str(rang)
    print(f"  {marque:>3}  [{registre[:4]}] {identifiant:<26} attendu {sorted(attendus)}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Échecs détaillés
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 78)
print("3. OÙ L'APPROCHE SE TROMPE")
print("=" * 78)

for identifiant, question, attendus, registre, rang, verdict in résultats:
    if rang == 1:
        continue
    rendu = verdict.resultats[0]
    print(f"\n[{registre}] {identifiant}")
    print(f"  question  : {question}")
    print(f"  rendu     : art. {rendu.numero} (score {rendu.score}) — "
          f"{rendu.extrait[:110]}")
    print(f"  attendu   : art. {sorted(attendus)}  "
          f"(rang obtenu : {'hors top-5' if rang is None else rang})")
    print(f"  couverture={verdict.couverture}  marge={verdict.marge}  "
          f"saturation={verdict.saturation}")
    if verdict.termes_inconnus:
        print(f"  termes absents du corpus : {', '.join(verdict.termes_inconnus)}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Ablations — chaque choix de conception doit se justifier par un chiffre
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 78)
print("4. ABLATIONS")
print("=" * 78)

variantes = [
    ("référence (hiérarchie×2, racines, mots vides)", {}),
    ("sans renfort de hiérarchie", {"poids_hierarchie": 0}),
    ("hiérarchie ×1", {"poids_hierarchie": 1}),
    ("hiérarchie ×3", {"poids_hierarchie": 3}),
    ("hiérarchie ×5", {"poids_hierarchie": 5}),
    ("sans rognage des suffixes", {"racine": False}),
    # Pas de légende « défaut payé/payés » sur cette ligne : ce défaut existe,
    # mais il tient à l'absence de règle sur le « e » final et non au plancher,
    # qui ne le corrige à aucune valeur (voir la docstring de bm25.raciner).
    ("plancher de racine à 4", {"racine_min": 4}),
    ("plancher de racine à 2 (rognage agressif)", {"racine_min": 2}),
    ("sans retrait des mots vides", {"mots_vides": False}),
    ("k1=0.9 b=0.4", {"k1": 0.9, "b": 0.4}),
    ("k1=1.5 b=0.75", {"k1": 1.5, "b": 0.75}),
    ("k1=1.2 b=0.0 (longueur ignorée)", {"b": 0.0}),
    ("k1=1.2 b=1.0 (longueur pleine)", {"b": 1.0}),
]

print(f"{'variante':<46} {'@1':>7} {'@3':>7} {'@5':>7}")
for nom, options in variantes:
    variante = IndexLexical(articles, **options)
    rv = rappels(rangs(variante))
    print(f"{nom:<46} {pourcent(rv[1])} {pourcent(rv[3])} {pourcent(rv[5])}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Savoir dire qu'on ne sait pas
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 78)
print("5. CAPACITÉ À DOUTER")
print("=" * 78)
print(
    "Trois signaux disponibles sans modèle : la COUVERTURE (part des termes de\n"
    "la question que le corpus connaît), la SATURATION (score du premier\n"
    "rapporté à la masse IDF interrogeable) et la MARGE (écart relatif entre\n"
    "le premier et le deuxième). On regarde s'ils séparent les réussites des\n"
    "échecs AU RANG 1."
)

juste = [v for *_, rang, v in résultats if rang == 1]
faux = [v for *_, rang, v in résultats if rang != 1]

for nom, clef in (("couverture", "couverture"), ("saturation", "saturation"), ("marge", "marge")):
    a = [getattr(v, clef) for v in juste]
    b = [getattr(v, clef) for v in faux]
    print(
        f"\n{nom:<12} bon au rang 1 (n={len(a)}) : "
        f"min {min(a):.3f}  médiane {statistics.median(a):.3f}  max {max(a):.3f}"
    )
    print(
        f"{'':<12} faux au rang 1 (n={len(b)}) : "
        f"min {min(b):.3f}  médiane {statistics.median(b):.3f}  max {max(b):.3f}"
    )

# Règle d'abstention. Le seuil est AJUSTÉ SUR CES MÊMES 25 QUESTIONS : ce
# tableau montre ce que les signaux PEUVENT faire, il ne mesure pas une
# performance sur des questions inconnues. Avec quinze échecs et dix
# réussites, un seuil qui tomberait pile entre les deux populations est aussi
# probablement un effet du petit nombre qu'une propriété de la méthode.
for nom, clef in (("saturation", "saturation"), ("marge", "marge")):
    print(f"\nrègle « je préfère me taire » — balayage du seuil de {nom} :")
    print(
        f"{'seuil':>6} {'rendues':>9} {'justes':>8} {'fausses':>9} "
        f"{'précision':>11} {'échecs évités':>15}"
    )
    for seuil in (0.0, 0.05, 0.10, 0.15, 0.21, 0.25, 0.30, 0.40, 0.50, 0.80,
                  1.00, 1.20, 1.40):
        rendues = [(rang, v) for *_, rang, v in résultats
                   if getattr(v, clef) >= seuil]
        justes = sum(1 for rang, _ in rendues if rang == 1)
        fausses = len(rendues) - justes
        précision = f"{100 * justes / len(rendues):.0f} %" if rendues else "—"
        évités = len(faux) - fausses
        print(
            f"{seuil:6.2f} {len(rendues):9} {justes:8} {fausses:9} "
            f"{précision:>11} {évités:15}"
        )

# ─────────────────────────────────────────────────────────────────────────────
# 6. Explicabilité — ce que la piste lexicale offre et qu'un vecteur n'offre pas
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 78)
print("6. EXPLICABILITÉ : LE DÉTAIL D'UNE RÉPONSE")
print("=" * 78)
for question in (
    "Quel est le montant de l'indemnité de licenciement par année d'ancienneté ?",
    "Combien de jours de congés payés ai-je après deux ans de travail ?",
):
    verdict = index.chercher(question, k=3)
    print(f"\n« {question} »")
    print(f"  couverture={verdict.couverture} marge={verdict.marge} "
          f"saturation={verdict.saturation}")
    for rang, res in enumerate(verdict.resultats, 1):
        print(f"  {rang}. art. {res.numero} [{res.score:6.2f}] p. {res.page_pdf} — "
              + ", ".join(f"{t}:{v}" for t, v in res.contributions))

print(
    "\nAvertissement reproduit du corpus, à afficher sous toute réponse :\n  "
    + corpus["source"]["avertissement"]
)

# ─────────────────────────────────────────────────────────────────────────────
# 7. Jusqu'où une expansion manuelle de requête pourrait porter la piste
# ─────────────────────────────────────────────────────────────────────────────
#
# ⚠ CE CHIFFRE N'EST PAS UNE MESURE DE PERFORMANCE, et il ne doit pas être
# cité comme telle. La table ci-dessous a été écrite APRÈS avoir lu les
# échecs du banc, pour combler exactement ces échecs. Elle mesure donc le
# PLAFOND qu'une expansion lexicale manuelle atteindrait sur les questions
# qui l'ont inspirée — autrement dit une borne supérieure optimiste. Sur des
# questions qu'elle n'a pas vues, elle n'apporte rien par construction.
#
# Ce qu'elle sert à établir, et c'est le seul usage légitime : l'écart entre
# le rappel brut et ce plafond chiffre ce que coûte le problème de
# vocabulaire — et donc ce qu'une couche sémantique aurait à gagner.

SYNONYMES = {
    "virer": "licenciement rupture",
    "vire": "licenciement rupture",
    "patron": "employeur",
    "fiche": "bulletin",
    "paie": "paye salaire",
    "semaine": "hebdomadaire",
    "papier": "certificat attestation",
    "prouvant": "justifiant",
    "homme": "sexes",
    "pareil": "egale discrimination",
    "bebe": "naissance enfant",
    "mari": "paternite salarie",
    "arret": "maladie absence",
    "elire": "elus election",
    "age": "age admission mineurs",
    "minimum": "moins",
}


def étendre(question: str) -> str:
    """Ajoute les synonymes connus aux mots de la question, sans en retirer.

    Le découpage est celui de l'index, et non un « .split() » sur les blancs :
    ce dernier laissait la ponctuation collée au mot, donc « bebe, » et
    « paie, » tels quels, et deux des seize entrées de SYNONYMES ne servaient
    jamais — le plafond rapporté plus bas était sous-estimé d'autant.
    """
    from bm25 import _SEPARATEURS, dépouiller

    ajouts = [
        SYNONYMES[mot]
        for mot in _SEPARATEURS.split(dépouiller(question))
        if mot in SYNONYMES
    ]
    return question + " " + " ".join(ajouts)


print()
print("=" * 78)
print("7. PLAFOND D'UNE EXPANSION MANUELLE (ajustée sur le banc — à ne pas citer")
print("   comme une performance)")
print("=" * 78)

étendus = []
for identifiant, question, attendus, registre, _ in BANC:
    verdict = index.chercher(étendre(question), k=K_MAX)
    rang = None
    for position, resultat in enumerate(verdict.resultats, 1):
        if resultat.numero in attendus:
            rang = position
            break
    étendus.append((identifiant, question, attendus, registre, rang, verdict))

re_ = rappels(étendus)
print(f"rappel@1 : {pourcent(re_[1])}   (brut : {pourcent(rappel_reference[1])})")
print(f"rappel@3 : {pourcent(re_[3])}   (brut : {pourcent(rappel_reference[3])})")
print(f"rappel@5 : {pourcent(re_[5])}   (brut : {pourcent(rappel_reference[5])})")
for registre in ("technique", "ordinaire"):
    sous = [x for x in étendus if x[3] == registre]
    rr = rappels(sous)
    print(
        f"  registre « {registre} » ({len(sous)}) : @1 {pourcent(rr[1])}  "
        f"@3 {pourcent(rr[3])}  @5 {pourcent(rr[5])}"
    )
print("\nquestions qui résistent même à l'expansion ajustée :")
for identifiant, _, attendus, registre, rang, v in étendus:
    if rang is None:
        print(f"  [{registre}] {identifiant} — rendu art. {v.resultats[0].numero}, "
              f"attendu {sorted(attendus)}")
