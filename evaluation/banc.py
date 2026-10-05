#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc de mesure de la RÉCUPÉRATION pour Mizan.

Ce que ce fichier mesure, et pourquoi il ne mesure que cela
===========================================================

La promesse du projet est « des réponses qui citent les articles sur
lesquels elles s'appuient ». Cette promesse se brise en deux moitiés, qui
n'ont pas du tout la même difficulté à vérifier :

  1. retrouver les BONS articles pour une question donnée ;
  2. rédiger une réponse fidèle à ces articles.

Ce banc ne mesure que la première. Ce n'est pas un renoncement, c'est une
condition de reproductibilité : la moitié 1 se mesure sans modèle de
langue, donc sans clé d'API, donc par quiconque clone le dépôt, aujourd'hui
comme dans deux ans. La moitié 2 exigerait un modèle — c'est-à-dire une
clé, un fournisseur, un tarif, et des résultats qui bougent à chaque
changement de version chez le fournisseur. Mesurer les deux ensemble
produirait un chiffre que personne ne pourrait recalculer.

Conséquence à ne pas perdre de vue : un rappel élevé ici ne dit RIEN sur la
fidélité des réponses. Il dit seulement que les bons articles étaient sur
la table. C'est nécessaire, et ce n'est pas suffisant.

Le protocole
============

Une fonction de récupération est passée en paramètre :

    recuperer(question: str, k: int) -> séquence ordonnée, au plus k éléments

Chaque élément est soit un numéro d'article (chaîne, telle qu'elle figure
dans le corpus : « premier », « 231 »), soit un couple (numéro, score). Le
premier élément est le meilleur candidat. Une séquence VIDE vaut
abstention — c'est le seul moyen pour un système de dire « je ne sais pas »,
et c'est mesuré à part.

Les mesures
===========

  rappel@k      Sur les questions qui ont une vérité de référence :
                moyenne, par question, de |retrouvés@k ∩ attendus| / |attendus|.
                Moyenne PAR QUESTION (macro) et non sur l'ensemble des
                couples : sinon les questions à cinq articles attendus
                pèseraient cinq fois celles à un seul, alors qu'un usager
                pose une question, pas un article.

  touche@k      Part des questions dont au moins un article attendu est
                dans les k premiers. Plus indulgent que le rappel ; les
                deux sont donnés parce qu'ils ne disent pas la même chose :
                « touche » dit qu'on est dans le bon chapitre, « rappel »
                dit qu'il ne manque rien.

  abstention    Sur les questions SANS réponse dans le Code : part de
                celles où la récupération n'a rien renvoyé. C'est la seule
                mesure où réussir consiste à se taire.

  bruit@k       Sur ces mêmes questions, nombre moyen d'articles renvoyés.
                Un système qui ne sait pas s'abstenir a ici un bruit égal
                à k, et c'est exactement ce qu'il faut voir.

  dérobade      Part des questions qui ONT une réponse et pour lesquelles
                la récupération s'est abstenue. Mesurée parce qu'un futur
                seuil de confiance trop prudent ferait monter l'abstention
                en ruinant l'utilité : les deux chiffres doivent être lus
                ensemble, jamais l'un sans l'autre.

  déplacement   Sur les couples étiquetés « reformulation » — deux questions
                attendent au moins un article commun, l'une en langue
                d'usager et l'autre en langue du Code, ou l'une nue et
                l'autre portant une consigne injectée : nombre d'articles
                communs aux deux listes retrouvées. Comme la vérité de
                référence se recoupe, l'écart ne peut venir que de la
                formulation. C'est la mesure qui dit si une injection
                déplace la récupération ; elle ne dit rien de ce que la
                génération ferait de la consigne.

Les articles « tolérés » du jeu (sanction pénale correspondante, définition
voisine) ne comptent ni en réussite ni en bruit. Les compter en réussite
gonflerait le rappel ; les compter en bruit punirait une récupération
correcte.

Usage
=====

    python banc.py                              # plancher : récupération par mots
    python banc.py --recuperation idf
    python banc.py --recuperation muet           # témoin : ne renvoie jamais rien
    python banc.py --recuperation mon_module:ma_fonction
    python banc.py --couverture                  # part du Code touchée par le jeu
    python banc.py --seuil-rappel3 0.70 --seuil-abstention 0.80

Sans seuil, le banc rend compte et sort en 0 : il informe. Avec un seuil, il
sort en 1 dès qu'une mesure passe dessous, et peut alors servir de garde-fou
en intégration continue. Aucun seuil n'est câblé par défaut, parce qu'un
seuil inventé avant toute mesure n'est pas un garde-fou mais un ornement.
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

import argparse
import importlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Sequence

RACINE = Path(__file__).resolve().parent
CHEMIN_QUESTIONS = RACINE / "questions.json"
CHEMIN_CORPUS = RACINE.parent / "corpus" / "code-travail.json"

RANGS_K = (1, 3, 5)
K_MAX = max(RANGS_K)


# --------------------------------------------------------------------------
# Chargement et contrôle de cohérence du jeu
# --------------------------------------------------------------------------

def charger_corpus(chemin: Path = CHEMIN_CORPUS) -> dict:
    with chemin.open(encoding="utf-8") as f:
        return json.load(f)


def charger_questions(chemin: Path = CHEMIN_QUESTIONS) -> dict:
    with chemin.open(encoding="utf-8") as f:
        return json.load(f)


def controler_jeu(jeu: dict, corpus: dict) -> list[str]:
    """Vérifie que le jeu est utilisable AVANT de mesurer quoi que ce soit.

    Un banc qui tourne sur un jeu incohérent produit un chiffre faux avec
    aplomb — un numéro d'article mal recopié dans la vérité de référence
    fait baisser le rappel de tous les systèmes évalués, et rien ne le
    signale. Ces contrôles coûtent quelques millisecondes et rendent cette
    erreur impossible à manquer : en cas d'anomalie, le banc refuse de
    mesurer.
    """
    anomalies: list[str] = []
    numeros = {a["numero"] for a in corpus["articles"]}
    vus: set[str] = set()

    for q in jeu["questions"]:
        ident = q.get("id", "<sans id>")
        if ident in vus:
            anomalies.append(f"{ident} : identifiant en double")
        vus.add(ident)

        if not q.get("question", "").strip():
            anomalies.append(f"{ident} : question vide")

        attendus = q.get("articles_attendus", [])
        toleres = q.get("articles_toleres", [])
        for num in list(attendus) + list(toleres):
            if not isinstance(num, str):
                anomalies.append(f"{ident} : le numéro {num!r} n'est pas une chaîne")
            elif num not in numeros:
                anomalies.append(f"{ident} : l'article {num!r} n'existe pas dans le corpus")
        if set(attendus) & set(toleres):
            communs = sorted(set(attendus) & set(toleres))
            anomalies.append(f"{ident} : {communs} sont à la fois attendus et tolérés")
        if len(set(attendus)) != len(attendus):
            anomalies.append(f"{ident} : doublon dans articles_attendus")

        sans_reponse = "sans_reponse" in q.get("etiquettes", [])
        if sans_reponse and attendus:
            anomalies.append(f"{ident} : étiquetée sans_reponse mais des articles sont attendus")
        if not sans_reponse and not attendus:
            anomalies.append(f"{ident} : aucun article attendu sans l'étiquette sans_reponse")

    # Les couples sont le cœur du jeu, et ce sont eux qui dérivent le plus
    # vite : une paire déclarée d'un seul côté donne un couple qui n'existe
    # qu'à moitié, et une étiquette posée à la main se désaccorde tôt ou tard
    # de la vérité de référence. « voisine » et « reformulation » ne sont donc
    # pas crues sur parole : elles ont un critère mécanique — les articles
    # attendus des deux questions se recoupent ou non — et il est vérifié ici.
    par_id = {q.get("id"): q for q in jeu["questions"]}
    for q in jeu["questions"]:
        ident = q.get("id", "<sans id>")
        attendus = set(q.get("articles_attendus", []))
        etiquettes = set(q.get("etiquettes", []))
        avec_recoupement = sans_recoupement = False

        for paire in q.get("paire", []):
            if paire not in vus:
                anomalies.append(f"{ident} : la paire {paire!r} ne désigne aucune question")
                continue
            autre = par_id[paire]
            if ident not in (autre.get("paire") or []):
                anomalies.append(
                    f"{ident} : la paire {paire!r} n'est pas déclarée en retour par {paire}"
                )
            if attendus & set(autre.get("articles_attendus", [])):
                avec_recoupement = True
            else:
                sans_recoupement = True

        if sans_recoupement and "voisine" not in etiquettes:
            anomalies.append(f"{ident} : appariée sans article attendu commun, "
                             f"donc à étiqueter voisine")
        if not sans_recoupement and "voisine" in etiquettes:
            anomalies.append(f"{ident} : étiquetée voisine mais aucune paire "
                             f"ne diffère par les articles attendus")
        if avec_recoupement and "reformulation" not in etiquettes:
            anomalies.append(f"{ident} : appariée avec article attendu commun, "
                             f"donc à étiqueter reformulation")
        if not avec_recoupement and "reformulation" in etiquettes:
            anomalies.append(f"{ident} : étiquetée reformulation mais aucune paire "
                             f"ne partage ses articles attendus")

    return anomalies


# --------------------------------------------------------------------------
# Normalisation partagée par les récupérations de plancher
# --------------------------------------------------------------------------

# Mots écartés de la question comme du texte des articles. Cette liste
# appartient aux récupérations de plancher définies plus bas, PAS au banc :
# un autre système branché sur le banc fait ce qu'il veut de ses mots.
MOTS_VIDES = frozenset("""
a ai au aux avec ce ces cet cette c d dans de des du elle elles en encore est
et etre eux il ils j je l la le les leur lui ma mais me mes moi mon n ne nos
notre nous on ou par pas plus pour qu que quel quelle quelles quels qui quoi s
sa sans se ses si son sont sur ta te tes toi ton tu un une vos votre vous y
alors apres aussi autre avoir bien car cela comme comment combien donc donne
droit est-ce etait fait faire ici jamais la-bas meme mon-patron ont peut
peuvent peux pourquoi puis quand sous tout toute toutes tous tres
""".split())


def normaliser(texte: str) -> str:
    """Retire les accents et ramène toute ponctuation à de l'espace.

    Le corpus ne normalise pas les apostrophes (2 808 U+0027 contre 6
    U+2019, mesuré par l'extraction) et c'est assumé là-bas : la
    normalisation pour la recherche appartient à cette couche. Les deux
    apostrophes disparaissent donc ici, au même titre que les accents —
    « l'employeur » et « l’employeur » doivent produire le même jeton
    « employeur ».
    """
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texte)


def jetons(texte: str) -> list[str]:
    return [m for m in normaliser(texte).split() if len(m) > 1 and m not in MOTS_VIDES]


# --------------------------------------------------------------------------
# Récupérations de plancher — sans dépendance, sans modèle
# --------------------------------------------------------------------------

class RecuperationParMots:
    """Plancher nº 1 : compter les mots de la question présents dans l'article.

    Aucune pondération, aucune racinisation, aucun vecteur. L'intérêt n'est
    pas d'être bon, c'est de donner un nombre à battre : toute approche plus
    savante qui ne fait pas mieux que ceci ne sert à rien. La recherche porte
    sur le seul champ `texte` ; l'intitulé du livre, du titre et du chapitre
    est volontairement ignoré, pour que le plancher reste le plancher et non
    une petite ruse déjà optimisée.

    Abstention : seulement quand aucun mot de la question n'apparaît nulle
    part. C'est une règle presque jamais déclenchée, et le taux
    d'abstention mesuré le montrera — c'est l'intérêt de la mesurer.
    """

    nom = "mots"

    def __init__(self, articles: Sequence[dict]):
        self._articles = [
            (a["numero"], a["rang"], frozenset(jetons(a["texte"])))
            for a in articles
        ]

    def _scores(self, question: str) -> list[tuple[float, int, str]]:
        mots = set(jetons(question))
        if not mots:
            return []
        trouves = []
        for numero, rang, sac in self._articles:
            score = len(mots & sac)
            if score:
                # Le rang sert d'arbitre déterministe : à score égal,
                # l'article le plus proche du début du Code passe devant.
                # Arbitraire, mais reproductible — et un banc dont l'ordre
                # dépend de l'ordre d'itération ne mesure rien de stable.
                trouves.append((-float(score), rang, numero))
        trouves.sort()
        return trouves

    def __call__(self, question: str, k: int) -> list[tuple[str, float]]:
        return [(num, -s) for s, _, num in self._scores(question)[:k]]


class RecuperationParIdf(RecuperationParMots):
    """Plancher nº 2 : les mêmes mots, pondérés par leur rareté.

    Deuxième plancher pour une raison précise : un banc qui donne le même
    chiffre à deux systèmes différents ne mesure rien. Comparer « mots » et
    « idf » est le contrôle le moins coûteux que le banc puisse offrir sur
    lui-même. La pondération est l'IDF classique, sans normalisation par la
    longueur de l'article — ce qui favorise mécaniquement les articles
    longs, et fait partie de ce que ce plancher a de rustique.
    """

    nom = "idf"

    def __init__(self, articles: Sequence[dict]):
        super().__init__(articles)
        total = len(self._articles)
        occurrences: Counter[str] = Counter()
        for _, _, sac in self._articles:
            occurrences.update(sac)
        self._idf = {
            mot: math.log(total / (1 + df)) for mot, df in occurrences.items()
        }

    def _scores(self, question: str) -> list[tuple[float, int, str]]:
        mots = set(jetons(question))
        if not mots:
            return []
        trouves = []
        for numero, rang, sac in self._articles:
            score = sum(self._idf.get(mot, 0.0) for mot in mots & sac)
            if score > 0:
                trouves.append((-score, rang, numero))
        trouves.sort()
        return trouves


class RecuperationMuette:
    """Témoin : ne renvoie jamais rien.

    Il n'est pas là pour concourir mais pour empêcher une lecture flatteuse
    de l'abstention. Un système qui se tait toujours obtient 100 %
    d'abstention correcte ; le témoin le montre noir sur blanc, et la
    dérobade imprimée juste en dessous le disqualifie aussitôt. Sans lui,
    « l'abstention ne se lit jamais seule » resterait une affirmation.
    """

    nom = "muet"

    def __init__(self, articles: Sequence[dict]):
        # Signature commune aux planchers pour que le témoin se branche par
        # --recuperation comme les autres ; le corpus ne lui sert à rien.
        self._ignore = articles

    def __call__(self, question: str, k: int) -> list[str]:
        return []


PLANCHERS: dict[str, type] = {
    RecuperationParMots.nom: RecuperationParMots,
    RecuperationParIdf.nom: RecuperationParIdf,
    RecuperationMuette.nom: RecuperationMuette,
}


def construire_recuperation(specification: str, corpus: dict) -> tuple[Callable, str]:
    """Résout `--recuperation` en une fonction appelable.

    Deux formes acceptées : le nom d'un plancher de ce fichier, ou
    « module:attribut » pour brancher un système extérieur. La seconde est
    la raison pour laquelle la récupération est un paramètre : le jour où
    une approche vectorielle existera, elle sera mesurée par CE banc, sans
    qu'une ligne en soit réécrite — un banc retouché pour accueillir la
    solution retenue la flatte sans qu'on s'en aperçoive.
    """
    if specification in PLANCHERS:
        return PLANCHERS[specification](corpus["articles"]), specification
    if ":" not in specification:
        raise SystemExit(
            f"Récupération inconnue : {specification!r}. "
            f"Attendu l'un de {sorted(PLANCHERS)} ou « module:attribut »."
        )
    nom_module, _, nom_attribut = specification.partition(":")
    sys.path.insert(0, str(Path.cwd()))
    module = importlib.import_module(nom_module)
    objet = getattr(module, nom_attribut)
    # Une classe est instanciée avec les articles ; une fonction est prise
    # telle quelle. Cela laisse le choix d'un index construit une fois pour
    # toutes, sans l'imposer.
    if isinstance(objet, type):
        objet = objet(corpus["articles"])
    return objet, specification


def normaliser_retour(retour: Iterable, k: int) -> list[str]:
    """Accepte les deux formes de retour et coupe à k.

    La coupe est faite ici et non laissée à la confiance : un système qui
    renvoie plus de k articles obtiendrait sinon un rappel@1 calculé sur
    cinq candidats.
    """
    numeros: list[str] = []
    for element in retour or []:
        numero = element[0] if isinstance(element, (tuple, list)) else element
        if not isinstance(numero, str):
            raise TypeError(
                f"La récupération a renvoyé {numero!r} ; attendu le numéro "
                f"d'article sous forme de chaîne (« premier », « 231 »)."
            )
        if numero not in numeros:
            numeros.append(numero)
        if len(numeros) == k:
            break
    return numeros


# --------------------------------------------------------------------------
# Mesure
# --------------------------------------------------------------------------

class Resultats:
    def __init__(self, lignes: list[dict], nom_recuperation: str):
        self.lignes = lignes
        self.nom_recuperation = nom_recuperation

    # -- agrégats ----------------------------------------------------------

    @property
    def repondables(self) -> list[dict]:
        return [l for l in self.lignes if l["attendus"]]

    @property
    def sans_reponse(self) -> list[dict]:
        return [l for l in self.lignes if not l["attendus"]]

    def rappel(self, k: int, lignes: Sequence[dict] | None = None) -> float | None:
        lignes = self.repondables if lignes is None else [l for l in lignes if l["attendus"]]
        if not lignes:
            return None
        return sum(l["rappel"][k] for l in lignes) / len(lignes)

    def touche(self, k: int, lignes: Sequence[dict] | None = None) -> float | None:
        lignes = self.repondables if lignes is None else [l for l in lignes if l["attendus"]]
        if not lignes:
            return None
        return sum(1.0 for l in lignes if l["touche"][k]) / len(lignes)

    def abstention(self) -> float | None:
        lignes = self.sans_reponse
        if not lignes:
            return None
        return sum(1.0 for l in lignes if not l["retrouves"]) / len(lignes)

    def bruit(self) -> float | None:
        lignes = self.sans_reponse
        if not lignes:
            return None
        return sum(len(l["retrouves"]) for l in lignes) / len(lignes)

    def derobade(self) -> float | None:
        lignes = self.repondables
        if not lignes:
            return None
        return sum(1.0 for l in lignes if not l["retrouves"]) / len(lignes)

    def completes(self, k: int) -> int:
        """Questions dont TOUS les articles attendus sont dans les k premiers.

        Le rappel moyen cache la forme de la distribution : 50 % peuvent
        venir de la moitié des articles sur chaque question, ou de toutes les
        questions à moitié. Ce décompte et le suivant disent laquelle des deux.
        """
        return sum(1 for l in self.repondables if l["rappel"][k] == 1.0)

    def nulles(self, k: int) -> int:
        """Questions dont AUCUN article attendu n'est dans les k premiers."""
        return sum(1 for l in self.repondables if not l["touche"][k])

    def couples_reformulation(self) -> list[tuple[dict, dict]]:
        """Couples de questions qui attendent au moins un article commun.

        Ces couples disent la même chose dans deux langues (langue d'usager
        contre langue du Code, ou question nue contre question portant une
        consigne injectée). Comme la vérité de référence se recoupe, l'écart
        entre les deux listes retrouvées ne vient pas du sujet : il vient de
        la formulation seule. C'est la seule façon de mesurer un déplacement
        de la récupération sans changer ce qu'on lui demande.
        """
        par_id = {l["id"]: l for l in self.lignes}
        couples: list[tuple[dict, dict]] = []
        vus: set[frozenset[str]] = set()
        for ligne in self.lignes:
            for autre_id in ligne["paire"]:
                autre = par_id.get(autre_id)
                if autre is None or not (ligne["attendus"] & autre["attendus"]):
                    continue
                cle = frozenset((ligne["id"], autre_id))
                if cle in vus:
                    continue
                vus.add(cle)
                couples.append((ligne, autre))
        return couples


def executer(recuperer: Callable, jeu: dict, corpus: dict,
             nom_recuperation: str = "<anonyme>") -> Resultats:
    """Passe tout le jeu dans une fonction de récupération et calcule les mesures."""
    lignes: list[dict] = []
    for q in jeu["questions"]:
        attendus = set(q.get("articles_attendus", []))
        retrouves = normaliser_retour(recuperer(q["question"], K_MAX), K_MAX)

        rappel: dict[int, float] = {}
        touche: dict[int, bool] = {}
        for k in RANGS_K:
            tete = set(retrouves[:k])
            if attendus:
                rappel[k] = len(tete & attendus) / len(attendus)
                touche[k] = bool(tete & attendus)
            else:
                rappel[k] = 0.0
                touche[k] = False

        lignes.append({
            "id": q["id"],
            "question": q["question"],
            "etiquettes": q.get("etiquettes", []),
            "paire": list(q.get("paire", [])),
            "attendus": attendus,
            "toleres": set(q.get("articles_toleres", [])),
            "retrouves": retrouves,
            "rappel": rappel,
            "touche": touche,
        })
    return Resultats(lignes, nom_recuperation)


# --------------------------------------------------------------------------
# Rendu
# --------------------------------------------------------------------------

ETIQUETTES_RENDUES = ("usager", "code", "multi_articles", "voisine", "reformulation",
                      "hors_code", "injection", "sans_reponse")


def _pc(valeur: float | None) -> str:
    return "     —" if valeur is None else f"{valeur * 100:5.1f} %"


def ecrire_verite_de_reference(jeu: dict, corpus: dict) -> None:
    """Recense la vérité de référence : combien d'articles, cités combien de fois.

    Ces chiffres sont publiés dans METHODE.md § 1. Ils étaient exacts, mais
    aucune commande du dépôt ne les imprimait : un nombre que personne ne peut
    recalculer est un nombre que personne ne peut contredire, ce qui est pire
    qu'un nombre faux — un nombre faux se corrige, celui-là jamais.

    Ce sont des comptages sur questions.json et sur le corpus, pas des durées :
    quiconque clone le dépôt retrouve exactement les mêmes valeurs.

    Deux décomptes sont distingués à dessein. Les OCCURRENCES disent combien de
    fois le jeu exige un article ; les articles DISTINCTS disent quelle part du
    Code il touche. Le second est plus petit parce que plusieurs questions
    appellent le même article — c'est précisément ce que mesurent les
    étiquettes « reformulation ».
    """
    repondables = [q for q in jeu["questions"] if q.get("articles_attendus")]
    occurrences = sum(len(q["articles_attendus"]) for q in repondables)
    attendus = {n for q in repondables for n in q["articles_attendus"]}
    toleres = {n for q in jeu["questions"]
               for n in (q.get("articles_toleres") or [])}
    total = len(corpus["articles"])

    print()
    print("  Vérité de référence du jeu")
    print("  " + "-" * 62)
    print(f"  {'questions répondables':46}{len(repondables):4d}")
    print(f"  {'questions sans réponse dans le Code':46}"
          f"{len(jeu['questions']) - len(repondables):4d}")
    print(f"  {'occurrences d\'article attendu':46}{occurrences:4d}")
    print(f"  {'articles attendus distincts':46}{len(attendus):4d}")
    print(f"  {'articles tolérés distincts':46}{len(toleres):4d}")
    print(f"  {'... dont attendus par aucune question':46}"
          f"{len(toleres - attendus):4d}")
    print(f"  {'union attendus + tolérés':46}"
          f"{len(toleres | attendus):4d} / {total} articles du Code")
    print()


def ecrire_couverture(jeu: dict, corpus: dict) -> None:
    """Dit quelle part du Code le jeu touche, livre par livre.

    Un rappel élevé sur un jeu qui ne cite que la relation individuelle de
    travail ne promet rien sur une question de grève ou d'inspection. Ce
    tableau est donc une limite du jeu, pas un résultat : il est imprimé par
    le banc pour que la limite soit recalculable et non seulement déclarée.
    """
    attendus: set[str] = set()
    for q in jeu["questions"]:
        attendus |= set(q.get("articles_attendus", []))

    livres: dict[str, list[int]] = {}
    ordre: list[str] = []
    for article in corpus["articles"]:
        livre = (article["position"].get("livre") or {}).get("reference", "(hors livre)")
        if livre not in livres:
            livres[livre] = [0, 0]
            ordre.append(livre)
        livres[livre][0] += 1
        if article["numero"] in attendus:
            livres[livre][1] += 1

    # Les quatre niveaux sont comptés en contexte et non par intitulé : le
    # Code rouvre un « Chapitre premier » dans presque chaque titre, et les
    # dédupliquer par leur seul nom en perdrait deux.
    niveaux = ("livre", "titre", "chapitre", "section")
    comptes = {}
    for rang, niveau in enumerate(niveaux, start=1):
        chemins = set()
        for article in corpus["articles"]:
            if not article["position"].get(niveau):
                continue
            chemins.add(tuple(
                (article["position"].get(n) or {}).get("reference")
                for n in niveaux[:rang]
            ))
        comptes[niveau] = len(chemins)

    print()
    print("  Couverture du Code par les articles attendus")
    print("  " + "-" * 62)
    print("  hiérarchie du corpus : "
          + ", ".join(f"{comptes[n]} {n}s" for n in niveaux))
    print()
    for livre in ordre:
        total, cites = livres[livre]
        print(f"  {livre:34}{cites:4d} / {total:4d}")
    total = sum(v[0] for v in livres.values())
    cites = sum(v[1] for v in livres.values())
    print(f"  {'ensemble du Code':34}{cites:4d} / {total:4d}")
    print()


def ecrire_rapport(res: Resultats, detail: bool = False) -> None:
    repondables = res.repondables
    sans = res.sans_reponse

    print()
    print(f"  BANC DE RÉCUPÉRATION — MIZAN")
    print(f"  récupération évaluée : {res.nom_recuperation}")
    print(f"  {len(res.lignes)} questions, dont {len(repondables)} avec réponse "
          f"et {len(sans)} sans réponse dans le Code")
    print()

    print("  Sur les questions qui ont une réponse")
    print("  " + "-" * 62)
    print(f"  {'':22}{'@1':>9}{'@3':>9}{'@5':>9}")
    print(f"  {'rappel':22}" + "".join(f"{_pc(res.rappel(k)):>9}" for k in RANGS_K))
    print(f"  {'au moins un article':22}" + "".join(f"{_pc(res.touche(k)):>9}" for k in RANGS_K))
    n = len(repondables)
    print(f"  {'tous les articles @3':22}{f'{res.completes(3)} / {n}':>27}")
    print(f"  {'aucun article @5':22}{f'{res.nulles(5)} / {n}':>27}")
    print()

    print("  Par catégorie (rappel@3 / au moins un @3 / effectif)")
    print("  " + "-" * 62)
    for etiquette in ETIQUETTES_RENDUES:
        lot = [l for l in res.lignes if etiquette in l["etiquettes"]]
        if not lot:
            continue
        if etiquette == "sans_reponse":
            print(f"  {etiquette:22}{'abstention':>12} {_pc(res.abstention())}"
                  f"   n={len(lot)}")
        else:
            print(f"  {etiquette:22}{_pc(res.rappel(3, lot)):>12} "
                  f"{_pc(res.touche(3, lot))}   n={len(lot)}")
    print()

    print("  Sur les questions sans réponse — savoir se taire")
    print("  " + "-" * 62)
    print(f"  {'abstention correcte':34}{_pc(res.abstention())}   (n={len(sans)})")
    bruit = res.bruit()
    print(f"  {'articles renvoyés en moyenne':34}"
          f"{'     —' if bruit is None else f'{bruit:6.2f}'}   (sur {K_MAX} possibles)")
    print()
    print("  Contrepoids à lire avec l'abstention")
    print("  " + "-" * 62)
    print(f"  {'dérobade (silence sur une question répondable)':48}{_pc(res.derobade())}")
    print()

    couples = res.couples_reformulation()
    if couples:
        print("  Déplacement d'une formulation à l'autre — couples « reformulation »")
        print("  " + "-" * 62)
        print("  Même article attendu de part et d'autre : tout écart entre les deux")
        print("  listes retrouvées vient de la formulation, pas du sujet.")
        identiques = comparables = 0
        for a, b in couples:
            tete_a, tete_b = set(a["retrouves"][:3]), set(b["retrouves"][:3])
            cinq = len(set(a["retrouves"]) & set(b["retrouves"]))
            if not tete_a and not tete_b:
                # Deux silences ne sont pas une récupération stable : il n'y a
                # rien à déplacer. Le couple sort du décompte au lieu d'y
                # entrer comme une réussite ou comme un échec.
                qualite = "abstention des deux côtés"
            else:
                comparables += 1
                if tete_a == tete_b:
                    identiques += 1
                qualite = "même tête" if tete_a == tete_b else "déplacé"
            marque = qualite + (", injection" if "injection" in a["etiquettes"]
                                or "injection" in b["etiquettes"] else "")
            print(f"  {a['id']:>7} / {b['id']:<8}"
                  f"communs @3 : {len(tete_a & tete_b)}/3   @5 : {cinq}/5   {marque}")
        print(f"  {'mêmes trois premiers articles':44}"
              f"{identiques} / {comparables} couples comparables")
        print()

    if detail:
        print("  Détail par question")
        print("  " + "-" * 62)
        for l in res.lignes:
            marque = "·"
            if l["attendus"]:
                marque = "ok" if l["rappel"][3] == 1.0 else ("~" if l["touche"][3] else "KO")
            else:
                marque = "ok" if not l["retrouves"] else "KO"
            attendus = ", ".join(sorted(l["attendus"])) or "(aucun)"
            print(f"  {marque:>2} {l['id']:7} attendus [{attendus}]")
            print(f"       retrouvés {l['retrouves'] or '(abstention)'}")
            print(f"       « {l['question'][:88]} »")
        print()


# --------------------------------------------------------------------------
# Entrée en ligne de commande
# --------------------------------------------------------------------------

def principal(argv: Sequence[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Mesure une récupération d'articles contre questions.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analyseur.add_argument(
        "--recuperation", default=RecuperationParMots.nom,
        help=f"{' | '.join(sorted(PLANCHERS))} | module:attribut "
             f"(défaut : {RecuperationParMots.nom})",
    )
    analyseur.add_argument("--questions", type=Path, default=CHEMIN_QUESTIONS)
    analyseur.add_argument("--corpus", type=Path, default=CHEMIN_CORPUS)
    analyseur.add_argument("--detail", action="store_true",
                           help="écrit le résultat question par question")
    analyseur.add_argument("--couverture", action="store_true",
                           help="écrit le recensement de la vérité de référence "
                                "et la part du Code couverte, livre par livre")
    analyseur.add_argument("--seuil-rappel3", type=float, default=None,
                           help="sortie en code 1 si le rappel@3 passe dessous (0 à 1)")
    analyseur.add_argument("--seuil-abstention", type=float, default=None,
                           help="sortie en code 1 si l'abstention correcte passe dessous (0 à 1)")
    options = analyseur.parse_args(argv)

    corpus = charger_corpus(options.corpus)
    jeu = charger_questions(options.questions)

    anomalies = controler_jeu(jeu, corpus)
    if anomalies:
        print("  Le jeu d'évaluation est incohérent ; aucune mesure n'a été faite.",
              file=sys.stderr)
        for anomalie in anomalies:
            print(f"    - {anomalie}", file=sys.stderr)
        return 2

    recuperer, nom = construire_recuperation(options.recuperation, corpus)
    res = executer(recuperer, jeu, corpus, nom)
    ecrire_rapport(res, detail=options.detail)
    if options.couverture:
        ecrire_verite_de_reference(jeu, corpus)
        ecrire_couverture(jeu, corpus)

    echecs: list[str] = []
    if options.seuil_rappel3 is not None:
        mesure = res.rappel(3) or 0.0
        if mesure < options.seuil_rappel3:
            echecs.append(f"rappel@3 {mesure * 100:.1f} % < seuil "
                          f"{options.seuil_rappel3 * 100:.1f} %")
    if options.seuil_abstention is not None:
        mesure = res.abstention() or 0.0
        if mesure < options.seuil_abstention:
            echecs.append(f"abstention correcte {mesure * 100:.1f} % < seuil "
                          f"{options.seuil_abstention * 100:.1f} %")
    if echecs:
        for echec in echecs:
            print(f"  SOUS LE SEUIL : {echec}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
