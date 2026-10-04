"""Banc de mesure du prototype hybride.

Vingt-cinq questions dont la reponse a ete lue dans le corpus AVANT d'ecrire
le moindre code de recherche, et cinq questions dont la reponse n'y est pas.
Elles n'ont pas ete retouchees apres la premiere execution : un banc corrige
pour flatter son auteur ne mesure plus rien. Plusieurs sont volontairement
hostiles au bras lexical (le mot de la question est absent du texte de loi :
"avances", "mort", "papier") et plusieurs lui sont volontairement favorables
(vocabulaire juridique exact : "periode d'essai", "reglement interieur").

Convention de mesure : UN SEUL article attendu par question, celui qu'un
juriste citerait en premier. rappel@k = part des questions dont l'article
attendu figure dans les k premiers. Avec un seul article pertinent, c'est
aussi le taux de reussite@k ; c'est plus severe qu'un ensemble d'articles
acceptables, qui gonflerait les trois chiffres sans rien prouver de plus.

Usage :
  python banc.py            mesure complete (deux bras + fusion + ablations)
  python banc.py --rapide   saute les ablations
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
import ctypes
import json
import sys
import time

import chemin_paquets  # noqa: F401

import corpus as mod_corpus
from fusion import PROFONDEUR, fusionner, fusionner_n, fusionner_par_scores, juger
from lexical import IndexCaracteres, IndexLexical

# (question, article attendu, pourquoi cette question est dans le banc)
QUESTIONS = [
    ("apres deux ans dans la meme entreprise, combien de jours de conge paye j'ai le droit ?", "231", "vocabulaire exact, favorable au lexical"),
    ("est-ce que mon conge augmente quand j'ai de l'anciennete ?", "232", "doit distinguer 232 de 231, tres proches"),
    ("mon employeur doit-il me prevenir avant de me licencier ?", "43", "notion de preavis sans le mot preavis"),
    ("si j'ai commis une faute grave, est-ce que j'ai droit au preavis ?", "61", "doit distinguer 61 de 39 et 43"),
    ("combien de temps dure la periode d'essai d'un cadre ?", "14", "vocabulaire exact, favorable au lexical"),
    ("combien d'heures je dois travailler par semaine ?", "184", "chiffre central du code"),
    ("les heures faites en plus la nuit sont payees combien de plus ?", "201", "paraphrase de heures supplementaires"),
    ("je suis enceinte, combien de temps dure mon conge ?", "152", "enceinte absent du texte, qui dit en etat de grossesse"),
    ("j'allaite mon bebe, ai-je droit a une pause dans la journee ?", "161", "allaiter present mais bebe et pause absents"),
    ("a quel age un jeune peut-il commencer a travailler ?", "143", "jeune absent, le texte dit mineurs"),
    ("en partant de l'entreprise, quel papier mon employeur doit-il me remettre ?", "72", "papier absent, le texte dit certificat de travail"),
    ("combien de jours de repos par semaine au minimum ?", "205", "article tres court, peu de mots a accrocher"),
    ("mon frere est mort, combien de jours d'absence puis-je prendre ?", "274", "mort absent, le texte dit deces"),
    ("ma femme vient d'accoucher, combien de jours le pere peut prendre ?", "269", "doit distinguer le conge du pere du conge de maternite"),
    ("j'ai combien de temps pour aller au tribunal apres un licenciement ?", "65", "delai de 90 jours, concurrence avec 395"),
    ("quel montant d'indemnite apres douze ans d'anciennete quand on est licencie ?", "53", "doit distinguer 53 de 52"),
    ("a partir de combien de salaries faut-il un reglement interieur ?", "138", "concurrence avec 430, meme seuil de dix salaries"),
    ("a partir de combien de salaries faut-il creer un comite d'entreprise ?", "464", "concurrence avec 304 et 336, meme seuil de cinquante"),
    ("a quel age part-on a la retraite ?", "526", "vocabulaire exact"),
    ("mon patron peut-il retenir de l'argent sur mon salaire pour du materiel ?", "385", "patron absent, le texte dit employeur"),
    ("le salaire doit etre verse tous les combien ?", "363", "question mal formee exprimant une periodicite"),
    ("mon chef me fait des avances, que dit la loi ?", "40", "aucun mot commun avec harcelement sexuel"),
    ("je suis malade, dans combien de temps dois-je avertir mon employeur ?", "271", "delai de 48 heures"),
    ("faut-il une autorisation pour embaucher un salarie qui n'est pas marocain ?", "516", "etranger exprime par une negation"),
    ("au bout de combien de temps je ne peux plus reclamer ce qu'on me doit ?", "395", "prescription exprimee sans le mot prescription"),
]

# Questions dont la reponse n'est PAS dans ce corpus. Le systeme ne peut pas
# avoir raison : on mesure seulement s'il sait le dire.
HORS_CORPUS = [
    ("combien je paye d'impot sur mon salaire ?", "fiscalite, hors Code du travail"),
    ("ai-je le droit de teletravailler deux jours par semaine ?", "notion absente d'un texte consolide en 2011"),
    ("quel est le montant du SMIG en dirhams ?", "l'article 356 renvoie a un texte reglementaire, le montant n'y est pas"),
    ("comment je m'inscris a la CNSS pour ma retraite ?", "affiliation sociale, hors Code du travail"),
    ("ai-je droit a un conge parental de trois ans pour elever mon enfant ?", "l'article 156 dit 90 jours ou un an, jamais trois ans"),
]


def memoire_pic_mo() -> float:
    """Pic de memoire du processus, en Mo.

    tracemalloc ne sert a rien ici : l'essentiel de la memoire du bras dense
    est allouee par onnxruntime en code natif, invisible depuis Python.
    """

    class Compteurs(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32")
    psapi = ctypes.WinDLL("psapi")
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(Compteurs),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    c = Compteurs()
    c.cb = ctypes.sizeof(Compteurs)
    if not psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb
    ):
        return float("nan")
    return c.PeakWorkingSetSize / 1024 / 1024


def rappels(rangs) -> dict:
    n = len(rangs)
    return {
        "rappel@%d" % k: sum(1 for r in rangs if r is not None and r <= k) / n
        for k in (1, 3, 5)
    }


def rang_de(attendu, classement, corpus, cle=lambda x: x[0]):
    for r, element in enumerate(classement, start=1):
        if corpus.articles[cle(element)].numero == attendu:
            return r
    return None


def main() -> int:
    rapide = "--rapide" in sys.argv
    corpus = mod_corpus.charger()
    rapport = {
        "corpus": {
            "articles": len(corpus.articles),
            "date_consolidation": corpus.date_consolidation,
        },
        "questions": len(QUESTIONS),
        "hors_corpus": len(HORS_CORPUS),
    }

    t0 = time.perf_counter()
    lex = IndexLexical(corpus, poids_titres=1)
    t_index_lex = time.perf_counter() - t0
    memoire_apres_lexical = memoire_pic_mo()

    from dense import IndexDense

    t0 = time.perf_counter()
    den = IndexDense(corpus, avec_titres=True)
    t_index_den = time.perf_counter() - t0

    rapport["radicaliseur"] = lex.radicaliser.nom
    rapport["vocabulaire_lexical"] = len(lex.vocabulaire)
    rapport["passages_dense"] = len(den.passages)
    rapport["dimension_dense"] = den.dimension
    rapport["indexation_ms"] = {
        "lexical": round(t_index_lex * 1000, 1),
        "dense": round(t_index_den * 1000, 1),
    }
    rapport["memoire_pic_mo"] = {
        "apres_bras_lexical_seul": round(memoire_apres_lexical, 1),
        "les_deux_bras": round(memoire_pic_mo(), 1),
    }

    rangs = {"lexical": [], "dense": [], "fusion": []}
    temps = {"lexical": [], "dense": [], "fusion": []}
    detail = []

    for question, attendu, pourquoi in QUESTIONS:
        t0 = time.perf_counter()
        r_lex = lex.chercher(question, k=PROFONDEUR)
        t_lex = time.perf_counter() - t0
        t0 = time.perf_counter()
        r_den = den.chercher(question, k=PROFONDEUR)
        t_den = time.perf_counter() - t0
        t0 = time.perf_counter()
        fus = fusionner(r_lex, r_den)
        t_fus = time.perf_counter() - t0

        rl = rang_de(attendu, r_lex, corpus)
        rd = rang_de(attendu, r_den, corpus)
        rf = rang_de(attendu, fus, corpus, cle=lambda x: x.indice)
        rangs["lexical"].append(rl)
        rangs["dense"].append(rd)
        rangs["fusion"].append(rf)
        temps["lexical"].append(t_lex * 1000)
        temps["dense"].append(t_den * 1000)
        temps["fusion"].append((t_lex + t_den + t_fus) * 1000)

        couverture, inconnus = lex.couverture(question)
        verdict = juger(fus, couverture, inconnus)
        detail.append(
            {
                "question": question,
                "attendu": attendu,
                "pourquoi": pourquoi,
                "rang_lexical": rl,
                "rang_dense": rd,
                "rang_fusion": rf,
                "rendus_fusion": [corpus.articles[r.indice].numero for r in fus[:5]],
                "rendus_lexical": [corpus.articles[i].numero for i, _ in r_lex[:5]],
                "rendus_dense": [corpus.articles[i].numero for i, _ in r_den[:5]],
                "couverture": round(couverture, 3),
                "mots_inconnus": inconnus,
                "accord": verdict.accord,
                "marge": round(verdict.marge, 4),
                "refus": verdict.refus,
            }
        )

    rapport["resultats"] = {bras: rappels(r) for bras, r in rangs.items()}
    rapport["requete_ms"] = {
        bras: {"median": round(sorted(v)[len(v) // 2], 2), "max": round(max(v), 2)}
        for bras, v in temps.items()
    }
    rapport["detail"] = detail

    # Abstention : combien de bonnes questions refusees a tort, combien de
    # questions hors corpus correctement signalees.
    faux_refus = [d["question"] for d in detail if d["refus"]]
    hors = []
    for question, pourquoi in HORS_CORPUS:
        r_lex = lex.chercher(question, k=PROFONDEUR)
        r_den = den.chercher(question, k=PROFONDEUR)
        fus = fusionner(r_lex, r_den)
        couverture, inconnus = lex.couverture(question)
        verdict = juger(fus, couverture, inconnus)
        hors.append(
            {
                "question": question,
                "pourquoi_hors_corpus": pourquoi,
                "refus": verdict.refus,
                "raison": verdict.raison,
                "couverture": round(couverture, 3),
                "mots_inconnus": inconnus,
                "accord": verdict.accord,
                "premier_rendu": corpus.articles[fus[0].indice].numero if fus else None,
            }
        )
    rapport["abstention"] = {
        "faux_refus_sur_questions_valides": faux_refus,
        "taux_faux_refus": round(len(faux_refus) / len(QUESTIONS), 3),
        "hors_corpus_signales": sum(1 for h in hors if h["refus"]),
        "hors_corpus_total": len(HORS_CORPUS),
        "detail": hors,
    }

    if not rapide:
        ablations = {}
        for poids in (0, 2):
            autre = IndexLexical(corpus, poids_titres=poids)
            r = [rang_de(a, autre.chercher(q, k=PROFONDEUR), corpus) for q, a, _ in QUESTIONS]
            ablations["lexical_poids_titres=%d" % poids] = rappels(r)
        den_sans = IndexDense(corpus, avec_titres=False)
        r = [rang_de(a, den_sans.chercher(q, k=PROFONDEUR), corpus) for q, a, _ in QUESTIONS]
        ablations["dense_sans_chemin_de_titres"] = rappels(r)
        r_fus_sans = []
        for q, a, _ in QUESTIONS:
            fus = fusionner(lex.chercher(q, k=PROFONDEUR), den_sans.chercher(q, k=PROFONDEUR))
            r_fus_sans.append(rang_de(a, fus, corpus, cle=lambda x: x.indice))
        ablations["fusion_avec_dense_sans_titres"] = rappels(r_fus_sans)
        for k_rrf in (1, 2, 5, 10, 20, 120):
            r = []
            for q, a, _ in QUESTIONS:
                fus = fusionner(
                    lex.chercher(q, k=PROFONDEUR), den.chercher(q, k=PROFONDEUR), k_rrf=k_rrf
                )
                r.append(rang_de(a, fus, corpus, cle=lambda x: x.indice))
            ablations["fusion_k_rrf=%d" % k_rrf] = rappels(r)
        # Troisieme bras a cout quasi nul : est-ce que RRF en profite ?
        t0 = time.perf_counter()
        car = IndexCaracteres(corpus)
        t_index_car = time.perf_counter() - t0
        ablations["_indexation_caracteres_ms"] = round(t_index_car * 1000, 1)
        r_car, r_lex_car, r_trois, r_dense_car = [], [], [], []
        for q, a, _ in QUESTIONS:
            cl, cd, cc = (
                lex.chercher(q, k=PROFONDEUR),
                den.chercher(q, k=PROFONDEUR),
                car.chercher(q, k=PROFONDEUR),
            )
            r_car.append(rang_de(a, cc, corpus))
            r_lex_car.append(rang_de(a, fusionner_n([cl, cc]), corpus, cle=lambda x: x.indice))
            r_dense_car.append(rang_de(a, fusionner_n([cd, cc]), corpus, cle=lambda x: x.indice))
            r_trois.append(rang_de(a, fusionner_n([cl, cd, cc]), corpus, cle=lambda x: x.indice))
        ablations["bras_caracteres_seul"] = rappels(r_car)
        ablations["fusion_lexical+caracteres (sans modele)"] = rappels(r_lex_car)
        ablations["fusion_dense+caracteres"] = rappels(r_dense_car)
        ablations["fusion_trois_bras"] = rappels(r_trois)

        r_scores = []
        for q, a, _ in QUESTIONS:
            fus = fusionner_par_scores(
                lex.chercher(q, k=PROFONDEUR), den.chercher(q, k=PROFONDEUR)
            )
            r_scores.append(rang_de(a, fus, corpus, cle=lambda x: x.indice))
        ablations["fusion_par_scores_min_max"] = rappels(r_scores)
        # Plafond : ce que donnerait un oracle qui saurait, pour chaque
        # question, lequel des deux bras consulter. C'est la borne haute de ce
        # que TOUTE fusion des deux memes bras peut atteindre.
        r_oracle = []
        for d in detail:
            candidats = [x for x in (d["rang_lexical"], d["rang_dense"]) if x is not None]
            r_oracle.append(min(candidats) if candidats else None)
        ablations["plafond_oracle_choix_du_bras"] = rappels(r_oracle)
        for profondeur in (10, 20):
            r = []
            for q, a, _ in QUESTIONS:
                fus = fusionner(lex.chercher(q, k=profondeur), den.chercher(q, k=profondeur))
                r.append(rang_de(a, fus, corpus, cle=lambda x: x.indice))
            ablations["fusion_profondeur=%d" % profondeur] = rappels(r)
        rapport["ablations"] = ablations

    rapport["memoire_pic_mo"]["fin"] = round(memoire_pic_mo(), 1)

    with open("resultats_banc.json", "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)

    print("corpus : %d articles, consolides au %s" % (len(corpus.articles), corpus.date_consolidation))
    print("radicaliseur : %s" % lex.radicaliser.nom)
    print("indexation : lexical %.0f ms, dense %.0f ms" % (t_index_lex * 1000, t_index_den * 1000))
    print("%d questions valides, %d hors corpus\n" % (len(QUESTIONS), len(HORS_CORPUS)))
    print("%-10s%8s%8s%8s%14s" % ("bras", "@1", "@3", "@5", "ms/req (med)"))
    for bras in ("lexical", "dense", "fusion"):
        r = rapport["resultats"][bras]
        print(
            "%-10s%8.2f%8.2f%8.2f%14.2f"
            % (
                bras,
                r["rappel@1"],
                r["rappel@3"],
                r["rappel@5"],
                rapport["requete_ms"][bras]["median"],
            )
        )
    print("\nechecs de la fusion (rang > 5) :")
    for d in detail:
        if d["rang_fusion"] is None or d["rang_fusion"] > 5:
            print("  attendu %4s | rendus %s | %s" % (d["attendu"], d["rendus_fusion"], d["question"]))
    print("\nbonne reponse presente mais pas premiere (rangs 2 a 5) :")
    for d in detail:
        if d["rang_fusion"] and 2 <= d["rang_fusion"] <= 5:
            print("  attendu %4s rang %d | rendus %s" % (d["attendu"], d["rang_fusion"], d["rendus_fusion"]))
    print("\nce que la fusion a gagne ou perdu par rapport a chaque bras :")
    for d in detail:
        meilleur_bras = min(
            [x for x in (d["rang_lexical"], d["rang_dense"]) if x is not None] or [10 ** 6]
        )
        rf = d["rang_fusion"] or 10 ** 6
        if rf < meilleur_bras:
            print("  + art %s : fusion %d, meilleur bras seul %d" % (d["attendu"], rf, meilleur_bras))
        elif rf > meilleur_bras:
            print("  - art %s : fusion %d, meilleur bras seul %d" % (d["attendu"], rf, meilleur_bras))
    a = rapport["abstention"]
    print(
        "\nabstention : %d/%d hors-corpus signales, %d/%d refus a tort"
        % (
            a["hors_corpus_signales"],
            a["hors_corpus_total"],
            len(a["faux_refus_sur_questions_valides"]),
            len(QUESTIONS),
        )
    )
    if "ablations" in rapport:
        print("\nablations :")
        for nom, r in rapport["ablations"].items():
            # Les cles prefixees d'un « _ » portent une mesure simple (un
            # temps) et non le triplet de rappels que cette ligne met en
            # colonnes : elles vont au JSON, pas au tableau.
            if nom.startswith("_"):
                continue
            print("  %-36s@1=%.2f @3=%.2f @5=%.2f" % (nom, r["rappel@1"], r["rappel@3"], r["rappel@5"]))
        # Imprimee a part, pour que la note n'ait pas a ouvrir le JSON pour
        # citer le cout du troisieme bras.
        print(
            "  %-36s%.1f ms"
            % ("indexation du bras caracteres", rapport["ablations"]["_indexation_caracteres_ms"])
        )
    print("\nmemoire pic du processus : %s" % rapport["memoire_pic_mo"])
    print("rapport complet : resultats_banc.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
