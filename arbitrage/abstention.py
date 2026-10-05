# -*- coding: utf-8 -*-
"""Banc : quel signal distingue « le Code contient la réponse » de « il ne la contient pas » ?

CE FICHIER NE RÉPARE RIEN. Il mesure, et son seul produit est une décision
étayée sur le signal d'abstention à retenir. La correction se fait ailleurs,
dans `noyau/recherche.py`, et elle doit pouvoir citer ce banc.

    python arbitrage/abstention.py                 # la moitié « choix » seule
    python arbitrage/abstention.py --controle       # la moitié tenue à l'écart
    python arbitrage/abstention.py --tout --json res_abstention.json

POURQUOI CE BANC EXISTE
-----------------------
La marge — écart relatif entre le premier et le deuxième score dense — était le
signal d'abstention en production quand ce banc a été écrit. Le chantier a été
ouvert sur l'idée qu'elle était INVERSÉE : une question étrangère au corpus
n'aurait aucun bon appariement, donc un article quelconque gagnerait largement
contre d'autres tout aussi étrangers (grande marge), tandis qu'une vraie
question de droit toucherait un faisceau d'articles tous assez bons (petite
marge).

**CE BANC A MESURÉ LE CONTRAIRE DE CE RÉCIT, et c'est son premier résultat.**
L'aire de la marge vaut 0,607 en réglage et 0,596 en vérification, c'est-à-dire
AU-DESSUS de 0,5 : elle porte un peu d'information, et dans le bon sens.
Médianes du réglage : 0,0568 pour les questions du corpus contre 0,0353 pour
les étrangères, l'ordre attendu. Son vrai défaut n'est pas de mesurer le
contraire, c'est de ne mesurer presque rien — les deux populations se recouvrent
au point qu'il faut refuser 55 des 57 questions du corpus pour n'accepter plus
qu'une seule étrangère. Les quatre cas qui ont ouvert le chantier sont des
queues de distribution, pas un changement de signe. Le récit était plus
satisfaisant que la mesure ; c'est la mesure qui est publiée.

Conséquence : la réparation ne retourne pas la marge, elle la REMPLACE par le
score dense absolu du premier article (`score1`, aire 0,978 / 0,937), qui n'a
rien à voir avec un relief entre rangs. C'est fait dans `noyau/recherche.py`
sous le nom de `proximite`.

`--sanite` réimprime les quatre cas qui ont ouvert ce chantier, pour que le
défaut soit constatable et non raconté.

CE BANC MESURE LE SIGNAL, PAS LE PRODUIT, ET LA NUANCE A UNE CONSÉQUENCE
-----------------------------------------------------------------------
Il appelle `dense.classer` directement, là où la production passe désormais par
`noyau.recherche.Moteur`, qui rend au bras dense les accents que le Code n'écrit
jamais autrement (`noyau.accents`). Les deux chemins ne sont donc plus
littéralement le même code, et c'est assumé : les 93 questions du jeu sont
écrites AVEC leurs accents, et `arbitrage/accents.py` a mesuré que la
re-accentuation ne change alors aucune décision et aucun des trois rappels. Ce
banc mesure bien ce que la production fait — pour une question accentuée.

Pour une question tapée SANS accents, il ne la mesure pas, et il ne faut pas lui
demander de le faire : c'est `arbitrage/accents.py` qui porte cette mesure, avec
la même coupe du jeu en deux moitiés.

DEUX CORRECTIONS DE FAIT, PORTÉES ICI PARCE QU'ELLES CHANGENT LES CHIFFRES
--------------------------------------------------------------------------
1. **L'étiquette du hors-corpus est `sans_reponse`, pas `hors_code`.** Le
   chantier a été ouvert sur l'idée que les sept questions hors corpus portaient
   l'étiquette `hors_code`. Elles portent `sans_reponse` (sept questions,
   `articles_attendus` vide). `hors_code` désigne trois questions TOUT AUTRES —
   SMIG, jours fériés, préavis — dont la réponse chiffrée est dans un texte
   réglementaire mais dont l'article de renvoi EST dans le Code et EST attendu.
   Elles comptent donc ici comme questions DU corpus : s'en abstenir est une
   faute, pas un succès. Confondre les deux étiquettes aurait classé trois
   questions répondables du mauvais côté de la frontière mesurée.
2. **Le 85,7 % d'abstention correcte vaut six cas sur sept.** C'est écrit en
   toutes lettres dans `MESURES.md` §A.3, qui dit aussi que le seuil a été lu
   sur le banc qui sert à juger. Ce banc-ci ne corrige pas le chiffre publié :
   il fournit de quoi le remplacer par un chiffre lu sur plus de sept cas, et
   sur une moitié qui n'a pas servi à régler le seuil.

LA MOITIÉ DE RÉGLAGE, ET POURQUOI IL Y EN A UNE
-----------------------------------------------
Le jeu élargi est arrivé pendant l'écriture de ce banc : `questions.json` porte
désormais 93 questions, dont 36 hors corpus réparties par un champ `volet` en
`reglage` (18) et `verification` (18). C'est cette partition-là qui est
employée, et non une partition maison — ce banc avait commencé par construire
la sienne, faute de mieux, et elle a été retirée dès que l'officielle a existé.
« choix » et « reglage » désignent la même moitié ; les deux noms sont acceptés
en ligne de commande.

Les 57 questions répondables n'ont pas de volet : elles servent des deux côtés.
C'est volontaire et sans conséquence sur l'honnêteté du chiffre — ce qui est
tenu à l'écart, c'est ce qui sert à régler le seuil DU HORS-CORPUS, et le coût
en rappel est de toute façon rapporté sur les mêmes 57 questions dans les deux
cas, donc comparable d'une moitié à l'autre.

Le seuil se lit sur `reglage`. Il se RAPPORTE sur `verification`. C'est la seule
protection contre le défaut que ce dépôt vient de passer deux revues à
corriger : un nombre réglé sur le jeu qui le juge n'est pas une mesure, c'est
un ajustement.

LES VINGT-DEUX QUESTIONS ÉTRANGÈRES ÉCRITES ICI, ET CE QU'ELLES AJOUTENT
------------------------------------------------------------------------
Elles ont été écrites AVANT que le jeu élargi n'existe, sans le voir, et elles
sont gardées pour cette raison précise : un seuil qui tient sur deux lots
d'étrangères écrits indépendamment est plus croyable qu'un seuil qui tient sur
un seul. Elles ne servent pas à régler et ne comptent dans aucune proportion
publiée par défaut ; `--mes-etrangeres` les ajoute comme contre-épreuve, et le
tableau dit alors sur combien de cas chaque colonne est calculée.

Chacune a été vérifiée contre le corpus avant d'être inscrite : le terme qui
porte la question est absent des 589 articles. La commande qui le vérifie est
`--verifier-etrangeres`, et elle échoue si une question étrangère touche un
terme que le Code connaît. TROIS candidates ont été écartées par ce contrôle
plutôt que forcées — le statut du stagiaire (les art. 5, 275 et 328 parlent de
stage), l'âge de la retraite (cinq articles la mentionnent) et la courroie de
distribution d'une voiture (l'art. 286 protège les salariés des organes de
transmission). Les classer hors corpus aurait flatté la séparation mesurée.

LE COÛT EN RAPPEL EST IMPRIMÉ À CÔTÉ DE CHAQUE RÉGLAGE, TOUJOURS
----------------------------------------------------------------
Un signal qui refuse tout obtient 100 % d'abstention correcte pour 0 % de
rappel. Ce banc refuse donc d'imprimer une abstention sans le rappel qui la
paie, et il imprime les deux témoins — répondre à tout, se taire toujours — en
tête de chaque tableau, pour que le piège soit visible sur la même page.
"""
from __future__ import annotations

# Sortie en UTF-8 avant le premier print : voir sortie.py, à la racine. Sans
# lui, ce script s'arrête sur UnicodeEncodeError dès qu'il imprime une flèche.
# « append » et non « insert » : la racine porte des dossiers (corpus,
# evaluation) qui masqueraient des modules voisins de même nom.
import sys as _sys
from pathlib import Path as _Path

RACINE = _Path(__file__).resolve().parents[1]
_sys.path.append(str(RACINE))
import sortie  # noqa: F401,E402  (importé pour son effet sur les flux)

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
import unicodedata  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from noyau import charger_corpus  # noqa: E402
from noyau import dense as module_dense  # noqa: E402
from noyau import lexical as module_lexical  # noqa: E402
from noyau.recherche import PROFONDEUR_BRAS, PROFONDEUR_DENSE  # noqa: E402

# Le seuil de marge qui était EN PRODUCTION quand ce banc a été écrit. Il n'est
# plus dans `noyau/recherche.py`, où la décision se prend désormais sur la
# proximité. On le garde ici, en dur et nommé pour ce qu'il est : un banc qui
# suivrait la constante du noyau cesserait d'imprimer le défaut le jour où le
# noyau est réparé — c'est-à-dire exactement le jour où la preuve devient utile.
SEUIL_MARGE_REMPLACE = 0.04

JEU = RACINE / "evaluation" / "questions.json"

# La partition vient du jeu, elle n'est pas refaite ici. Les deux noms de la
# moitié de réglage sont acceptés : le chantier l'a appelée « choix », le jeu
# l'appelle « reglage ».
VOLETS = {"choix": "reglage", "reglage": "reglage",
          "controle": "verification", "verification": "verification"}

# Les rangs auxquels le rappel est rapporté, ceux du banc des fondations.
RANGS_K = (1, 3, 5)

# Profondeur sur laquelle l'accord entre les deux bras est mesuré. Cinq, et pas
# une autre valeur : c'est le nombre d'articles que l'interface montre, donc le
# seul voisinage dont l'usager voie quelque chose.
PROFONDEUR_ACCORD = 5


# ── Les questions étrangères écrites pour ce banc ───────────────────────────
#
# Chaque entrée porte le terme à vérifier dans le corpus. Ce n'est pas une
# décoration : `--verifier-etrangeres` s'en sert pour refuser une question dont
# le sujet serait en réalité traité par le Code, et c'est ce contrôle qui donne
# sa valeur à l'étiquette « hors corpus ».

ETRANGERES = (
    # -- lointaine : étrangère au droit tout entier ---------------------------
    ("X01", "Quelle est la recette du couscous royal ?", "lointaine", "couscous"),
    ("X02", "Qui a gagné la Coupe du monde de football en 2018 ?", "lointaine", "coupe du monde"),
    ("X03", "Quelle est la capitale de l'Australie ?", "lointaine", "australie"),
    ("X04", "Combien de temps faut-il pour cuire un oeuf dur ?", "lointaine", "oeuf"),
    # X05 a d'abord été « changer la courroie de distribution d'une voiture ».
    # `--verifier-etrangeres` l'a REFUSÉE : « courroie » est à l'art. 286, qui
    # protège les salariés des organes de transmission des machines. La question
    # aurait été comptée étrangère alors que le Code en parle, et la séparation
    # mesurée en aurait été flattée. Remplacée, pas forcée.
    ("X05", "Comment apprendre à jouer de la guitare ?", "lointaine", "guitare"),
    # -- autre_droit : droit marocain, autre corps de règles ------------------
    ("X06", "Quel est le taux de l'impôt sur les sociétés au Maroc ?", "autre_droit", None),
    ("X07", "Comment s'inscrire à l'assurance maladie obligatoire (AMO) ?", "autre_droit", "assurance maladie"),
    ("X08", "Combien coûte un avocat spécialisé en droit du travail au Maroc ?", "autre_droit", "avocat"),
    ("X09", "Quel est le délai pour obtenir un permis de conduire professionnel ?", "autre_droit", "permis de conduire"),
    ("X10", "Quelles sont les formalités de création d'une société anonyme au Maroc ?", "autre_droit", "societe anonyme"),
    ("X11", "Quel est le préavis pour résilier un bail commercial ?", "autre_droit", "bail"),
    ("X12", "Comment récupérer la TVA sur un achat professionnel ?", "autre_droit", "tva"),
    ("X13", "Quelles sont les règles de protection des données personnelles d'un salarié ?",
     "autre_droit", "donnees personnelles"),
    # -- hors_2011 : droit du travail, absent du Code de 2011 -----------------
    ("X14", "Le télétravail est-il encadré par le Code du travail marocain ?", "hors_2011", "teletravail"),
    ("X15", "Quelles sont les règles du congé sabbatique ?", "hors_2011", "sabbatique"),
    ("X16", "Le treizième mois est-il obligatoire au Maroc ?", "hors_2011", "treizieme"),
    ("X17", "Un livreur de plateforme numérique est-il salarié ?", "hors_2011", "livreur"),
    ("X18", "Le droit à la déconnexion existe-t-il au Maroc ?", "hors_2011", "deconnexion"),
    ("X19", "Un employeur peut-il imposer la vaccination à ses salariés ?", "hors_2011", "vaccin"),
    ("X20", "Les jours d'absence pour don de sang sont-ils payés ?", "hors_2011", "don de sang"),
    ("X21", "Quelle est la durée du congé parental partagé entre les deux parents ?", "hors_2011", "conge parental"),
    ("X22", "Le salarié a-t-il droit à un titre-restaurant ?", "hors_2011", "titre-restaurant"),
)

# `None` en quatrième position : le terme EST dans le corpus et la question est
# quand même étrangère. Le seul cas est X06 — « impôt » apparaît au Code du
# travail (retenues sur salaire), mais le TAUX de l'impôt sur les sociétés n'y
# est pas. La vérification l'épargne explicitement plutôt que de laisser croire
# que toutes les étrangères sont lexicalement absentes : c'est justement cette
# question-là qui est dangereuse.

# Les familles du jeu élargi. Elles sont lues dans le fichier et non décidées
# ici ; cette liste ne sert qu'à fixer l'ORDRE d'affichage, de la plus facile à
# la plus difficile, parce qu'un signal peut séparer les lointaines sans rien
# séparer des limitrophes et que la moyenne le cacherait.
FAMILLES_JEU = ("etrangere", "autre_branche", "travail_hors_corpus",
                "limitrophe", "mal_posee")

# Les familles de mes propres étrangères, tenues à part de celles du jeu pour
# qu'aucun tableau ne les additionne par accident.
FAMILLES_MIENNES = ("lointaine", "autre_droit", "hors_2011")


# ── Ce qu'une question rend quand on la passe dans les deux bras ────────────

@dataclass(frozen=True)
class Cas:
    """Une question, son camp, et tous les signaux lus en un seul passage.

    Un seul passage, et tous les signaux enregistrés ensemble : c'est ce qui
    garantit qu'un écart entre deux signaux ne vient pas d'une variation de la
    récupération. Les comparer sur deux passages distincts serait comparer deux
    expériences.
    """

    id: str
    question: str
    du_corpus: bool
    famille: str
    moitie: str
    attendus: frozenset[str]
    # les classements, gardés pour recalculer le rappel sous n'importe quelle règle
    dense: tuple[tuple[str, float], ...]
    rendus: tuple[str, ...]
    # les signaux
    signaux: dict[str, float] = field(default_factory=dict)

    def rappel(self, k: int, repond: bool) -> float:
        """Le rappel au rang k, à la manière du banc des fondations.

        Une abstention compte un rappel NUL et non une absence de mesure. Ce
        n'est pas une sévérité gratuite : c'est ce qui empêche de présenter le
        silence comme une amélioration. Un système qui se tait sur les questions
        qu'il rate verrait sinon son rappel monter en ne répondant plus.
        """
        if not repond or not self.attendus:
            return 0.0
        tete = set(self.rendus[:k])
        return len(tete & self.attendus) / len(self.attendus)


def depouiller(texte: str) -> str:
    """Minuscules sans accents. Même convention que le bras lexical."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").lower()


# ── Les signaux éprouvés ────────────────────────────────────────────────────
#
# Chaque signal est orienté de sorte que PLUS HAUT VEUILLE DIRE PLUS CONFIANT,
# et la décision est toujours « répondre si signal >= seuil ». Sans cette
# convention, la moitié des courbes se liraient à l'envers et une comparaison
# entre deux signaux de sens opposés serait un piège de lecture. Les signaux
# dont la grandeur naturelle décroît avec la confiance (le nombre de mots
# inconnus) sont donc NIÉS à la source, et leur nom le dit.

SIGNAUX: dict[str, str] = {
    "marge": "écart relatif entre le 1er et le 2e score dense — REMPLACÉ, gardé comme observation",
    "score1": "score dense absolu du 1er article — RETENU, voir noyau.recherche.SEUIL_PROXIMITE",
    "masse5": "moyenne des 5 premiers scores denses — le niveau du voisinage, pas son relief",
    "masse3": "moyenne des 3 premiers scores denses — même idée, sur la profondeur dense",
    "couverture": "part des mots distincts de la question que le Code connaît",
    "moins_inconnus": "nombre de mots de la question absents du Code, NIÉ (0 mot = 0, le plus confiant)",
    "accord": "part des 5 premiers articles denses que le bras lexical place aussi dans ses 5",
}

# Les combinaisons ne sont pas des signaux de plus : ce sont des règles à deux
# conditions, réglées sur DEUX seuils. Elles sont éprouvées en dernier et avec
# méfiance — deux seuils lus sur quarante questions se règlent sur le bruit.
COMBINAISONS: dict[str, tuple[str, str]] = {
    "masse5+couverture": ("masse5", "couverture"),
    "masse5+accord": ("masse5", "accord"),
}


def collecter(moitie_demandee: str = "tout", mes_etrangeres: bool = False):
    """Un passage sur le jeu entier, avec le VRAI noyau et le VRAI index.

    Rend les cas ET les deux bras : le bloc de sanité en a besoin pour mesurer
    des questions qui n'appartiennent à aucune moitié, et les recharger pour
    quatre questions coûterait le chargement entier du modèle.

    Le bras dense est chargé une fois. Le charger par question multiplierait le
    coût du banc par le nombre de questions sans rien changer aux chiffres : la
    session ONNX est déterministe et n'a pas d'état entre deux appels.
    """
    corpus = charger_corpus()
    dense = module_dense.charger_bras_dense(corpus)
    lexical = module_lexical.IndexLexical(corpus)

    cas: list[Cas] = []
    for ident, question, du_corpus, famille, volet, attendus in _questions(mes_etrangeres):
        # `partout` passe toujours ; `mien` ne passe que si on l'a demandé, et
        # il est alors ajouté À CÔTÉ de la moitié en cours, jamais fondu dedans.
        if volet not in ("partout", "mien") and moitie_demandee != "tout" \
                and volet != moitie_demandee:
            continue

        classement = dense.classer(question, PROFONDEUR_BRAS)
        lecture = lexical.lire(question, PROFONDEUR_BRAS)
        cas.append(
            Cas(
                id=ident,
                question=question,
                du_corpus=du_corpus,
                famille=famille,
                moitie=volet,
                attendus=frozenset(attendus),
                dense=tuple(classement),
                rendus=tuple(_composer(classement, lecture.classement, 5)),
                signaux=_signaux(classement, lecture),
            )
        )
    return cas, dense, lexical


def _composer(dense, lexical, k: int) -> list[str]:
    """Le classement rendu : dense en tête, lexical en queue, sans doublon.

    Recopié de `Moteur._composer` et non appelé : ce banc a besoin des SCORES
    des deux bras, que le `Resultat` du contrat n'expose pas séparément. La
    recopie est bornée à la composition, et `test_abstention_compose_comme_le_noyau`
    l'épingle contre le moteur réel — sans ce test, la recopie dériverait le
    jour où la composition change, et le coût en rappel imprimé ici serait
    celui d'un système qui n'existe plus.
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


def _signaux(classement, lecture) -> dict[str, float]:
    """Tous les signaux d'un coup, depuis les deux classements bruts."""
    scores = [s for _, s in classement]
    premier = scores[0] if scores else 0.0

    if not scores or premier <= 0 or len(scores) < 2:
        # Les deux cas dégénérés du noyau, tranchés de la même façon : marge
        # nulle. Les reproduire ici plutôt que de les ignorer évite que le banc
        # et la production diffèrent sur un corpus réduit.
        marge = 0.0
    else:
        marge = (premier - scores[1]) / premier

    numeros_denses = [n for n, _ in classement[:PROFONDEUR_ACCORD]]
    numeros_lexicaux = {n for n, _ in lecture.classement[:PROFONDEUR_ACCORD]}
    communs = sum(1 for n in numeros_denses if n in numeros_lexicaux)

    return {
        "marge": marge,
        "score1": premier,
        "masse5": sum(scores[:5]) / max(len(scores[:5]), 1),
        "masse3": sum(scores[:3]) / max(len(scores[:3]), 1),
        "couverture": lecture.couverture,
        "moins_inconnus": -float(len(lecture.termes_inconnus)),
        "accord": communs / PROFONDEUR_ACCORD,
    }


def _questions(mes_etrangeres: bool = False):
    """Les deux camps, dans un format commun. Le camp est la vérité mesurée ici.

    Le volet vient du fichier. Les 57 questions répondables n'en portent pas et
    reçoivent `partout` : elles servent des deux côtés, et c'est ce qui rend le
    coût en rappel comparable d'une moitié à l'autre.

    Les questions `hors_code` sont DU corpus : voir l'en-tête, correction nº 1.
    Les questions `injection` le sont aussi — elles portent une consigne de
    détournement mais contiennent une vraie question de droit du travail, et
    s'en taire serait une dérobade. Le détournement se mesure ailleurs, dans
    `moteur/injection.py`.
    """
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    for q in jeu["questions"]:
        if "sans_reponse" in q["etiquettes"]:
            yield (q["id"], q["question"], False,
                   q.get("famille_hors_corpus") or "(sans famille)",
                   q.get("volet") or "partout", [])
        else:
            famille = "code" if "code" in q["etiquettes"] else "usager"
            yield (q["id"], q["question"], True, famille, "partout",
                   q["articles_attendus"])
    if mes_etrangeres:
        for ident, question, famille, _terme in ETRANGERES:
            yield ident, question, False, famille, "mien", []


# ── La séparation, et les deux erreurs ensemble ─────────────────────────────

def frontiere(cas: list[Cas], signal: str) -> list[dict]:
    """La frontière de Pareto du signal : les deux erreurs, seuil par seuil.

    On ne balaie pas une grille de seuils ronds : on balaie les valeurs
    OBSERVÉES, parce qu'un seuil ne change de comportement qu'en traversant une
    valeur du jeu. Une grille ronde raterait le meilleur point ou en inventerait
    un qui ne se distingue pas de son voisin.

    Pour chaque nombre d'étrangères acceptées à tort, on garde le seuil qui
    refuse le moins de questions du corpus. C'est la seule présentation qui
    tienne la consigne « les deux erreurs ensemble » : un signal n'a pas un
    score, il a une courbe, et c'est la courbe qui se compare.
    """
    du_corpus = [c for c in cas if c.du_corpus]
    etrangeres = [c for c in cas if not c.du_corpus]

    valeurs = sorted({c.signaux[signal] for c in cas})
    # Les seuils candidats : juste au-dessus de chaque valeur observée, plus un
    # seuil qui laisse tout passer. Le « juste au-dessus » compte comme refusée
    # la question qui porte exactement cette valeur, ce qui correspond à la
    # décision du noyau (répondre si signal >= seuil).
    candidats = [-math.inf] + [v + 1e-12 for v in valeurs]

    meilleurs: dict[int, dict] = {}
    for seuil in candidats:
        refus_a_tort = sum(1 for c in du_corpus if c.signaux[signal] < seuil)
        acceptees_a_tort = sum(1 for c in etrangeres if c.signaux[signal] >= seuil)
        garde = meilleurs.get(acceptees_a_tort)
        if garde is None or refus_a_tort < garde["refus_a_tort"]:
            meilleurs[acceptees_a_tort] = {
                "seuil": seuil,
                "refus_a_tort": refus_a_tort,
                "acceptees_a_tort": acceptees_a_tort,
                "n_corpus": len(du_corpus),
                "n_etrangeres": len(etrangeres),
            }
    return [meilleurs[k] for k in sorted(meilleurs)]


def aire(cas: list[Cas], signal: str) -> float:
    """Probabilité qu'une question du corpus porte un signal plus haut qu'une étrangère.

    Une mesure SANS SEUIL, et c'est tout son intérêt : elle dit si le signal
    porte de l'information, avant qu'on ait choisi où couper. 0,5 vaut le
    hasard ; au-dessous de 0,5 le signal est inversé, ce qui est exactement ce
    qu'on soupçonne de la marge. Les égalités comptent une demie, sans quoi un
    signal à valeurs entières (le nombre de mots inconnus) serait flatté.
    """
    du_corpus = [c.signaux[signal] for c in cas if c.du_corpus]
    etrangeres = [c.signaux[signal] for c in cas if not c.du_corpus]
    if not du_corpus or not etrangeres:
        return float("nan")
    total = 0.0
    for a in du_corpus:
        for b in etrangeres:
            total += 1.0 if a > b else (0.5 if a == b else 0.0)
    return total / (len(du_corpus) * len(etrangeres))


def correlation(cas: list[Cas], gauche: str, droite: str) -> float:
    """Corrélation de Pearson entre deux signaux, sur toutes les questions.

    Elle sert à une seule vérification, mais décisive : le mécanisme du défaut
    prédit que la masse du voisinage est ANTI-CORRÉLÉE à la marge. Si la
    prédiction tombe, le mécanisme est confirmé et la réparation suit ; si elle
    ne tombe pas, l'explication du défaut est fausse et il faut la réécrire
    avant de toucher à un seuil.
    """
    xs = [c.signaux[gauche] for c in cas]
    ys = [c.signaux[droite] for c in cas]
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def rappels(cas: list[Cas], signal: str | None, seuil: float) -> dict[int, float]:
    """Le rappel aux trois rangs sous une règle d'abstention donnée.

    `signal=None` est le témoin « répondre à tout ». Le témoin « se taire
    toujours » s'obtient avec un seuil infini, et il doit rester lisible : c'est
    lui qui montre qu'une abstention parfaite coûte tout le rappel.
    """
    repondables = [c for c in cas if c.du_corpus and c.attendus]
    if not repondables:
        return {k: float("nan") for k in RANGS_K}
    sortie_: dict[int, float] = {}
    for k in RANGS_K:
        total = 0.0
        for c in repondables:
            repond = True if signal is None else c.signaux[signal] >= seuil
            total += c.rappel(k, repond)
        sortie_[k] = total / len(repondables)
    return sortie_


def frontiere_combinaison(cas: list[Cas], gauche: str, droite: str) -> list[dict]:
    """La même frontière, pour une règle « signal A >= a ET signal B >= b ».

    Deux seuils balayés ensemble sur les valeurs observées. Le résultat est à
    lire avec la méfiance que ce dépôt s'impose : une règle à deux seuils a deux
    fois plus de liberté pour coller au bruit de quarante questions, et elle
    doit donc battre le meilleur signal simple D'UNE MARGE VISIBLE pour être
    préférée, pas d'une question.
    """
    du_corpus = [c for c in cas if c.du_corpus]
    etrangeres = [c for c in cas if not c.du_corpus]
    valeurs_g = [-math.inf] + [v + 1e-12 for v in sorted({c.signaux[gauche] for c in cas})]
    valeurs_d = [-math.inf] + [v + 1e-12 for v in sorted({c.signaux[droite] for c in cas})]

    meilleurs: dict[int, dict] = {}
    for sg in valeurs_g:
        for sd in valeurs_d:
            refus = sum(
                1 for c in du_corpus
                if not (c.signaux[gauche] >= sg and c.signaux[droite] >= sd)
            )
            acceptees = sum(
                1 for c in etrangeres
                if c.signaux[gauche] >= sg and c.signaux[droite] >= sd
            )
            garde = meilleurs.get(acceptees)
            if garde is None or refus < garde["refus_a_tort"]:
                meilleurs[acceptees] = {
                    "seuils": (sg, sd),
                    "refus_a_tort": refus,
                    "acceptees_a_tort": acceptees,
                    "n_corpus": len(du_corpus),
                    "n_etrangeres": len(etrangeres),
                }
    return [meilleurs[k] for k in sorted(meilleurs)]


# ── Impression ─────────────────────────────────────────────────────────────

def _f(valeur: float) -> str:
    if valeur == -math.inf:
        return "(aucun)"
    return f"{valeur:.4f}".replace(".", ",")


def _pc(valeur: float) -> str:
    if valeur != valeur:  # NaN
        return "    —"
    return f"{valeur * 100:5.1f} %".replace(".", ",")


# Les quatre questions qui ont ouvert ce chantier. Elles sont mesurées à part
# et non cherchées dans la moitié en cours : deux d'entre elles n'appartiennent
# à aucune moitié, et un défaut qu'on ne reconstate que dans la moitié où il
# tombe est un défaut raconté.
TEMOINS_DU_DEFAUT = (
    ("Quelle est la recette du couscous ?", "hors corpus"),
    ("Qui a gagné la Coupe du monde 2018 ?", "hors corpus"),
    ("Combien de jours de congé annuel payé ?", "du corpus"),
    ("Quelle est la durée normale de travail ?", "du corpus"),
)


def imprimer_sanite(dense, lexical) -> None:
    """Les quatre cas qui ont ouvert le chantier, reconstatés et non racontés."""
    print()
    print("LE DÉFAUT, RECONSTATÉ (la marge telle qu'elle décidait, seuil "
          f"{_f(SEUIL_MARGE_REMPLACE)})")
    print("-" * 78)
    print(f"  {'question':40} {'camp':12} {'marge':>16} {'score1':>8}")
    for question, camp in TEMOINS_DU_DEFAUT:
        classement = dense.classer(question, PROFONDEUR_BRAS)
        signaux = _signaux(classement, lexical.lire(question, PROFONDEUR_BRAS))
        verdict = "RÉPOND" if signaux["marge"] >= SEUIL_MARGE_REMPLACE else "se tait"
        print(f"  {question[:40]:40} {camp:12} {verdict:7} {_pc(signaux['marge'])} "
              f"{_f(signaux['score1']):>8}")
    print("  La marge dit le contraire du camp sur ces quatre-là — ce sont des")
    print("  queues de distribution, pas une inversion : voir l'en-tête. La")
    print("  colonne « score1 » dit la même chose que le camp sur les quatre.")


def imprimer_composition(cas: list[Cas]) -> None:
    """Sur combien de cas chaque proportion de ce banc est calculée.

    En tête, et pas en note de bas de page : c'est la règle que ce chantier a
    payée cher. Un chiffre mesuré sur sept cas n'est pas une garantie, et le
    seul moyen qu'on ne l'oublie pas est de dire l'effectif à l'endroit où le
    chiffre s'écrit.
    """
    import collections
    print()
    print("LE JEU, ET SUR COMBIEN DE CAS CHAQUE PROPORTION SERA CALCULÉE")
    print("-" * 78)
    corpus = [c for c in cas if c.du_corpus]
    etrangeres = [c for c in cas if not c.du_corpus]
    print(f"  questions du corpus      {len(corpus):>3}  (répondre est le succès)")
    print(f"  questions hors corpus    {len(etrangeres):>3}  (se taire est le succès)")
    familles = collections.Counter(c.famille for c in etrangeres)
    for f in FAMILLES_JEU + FAMILLES_MIENNES:
        if familles.get(f):
            marque = "  [écrites pour ce banc]" if f in FAMILLES_MIENNES else ""
            print(f"      {f:22} {familles[f]:>3}{marque}")
    autres = set(familles) - set(FAMILLES_JEU) - set(FAMILLES_MIENNES)
    for f in sorted(autres):
        print(f"      {f:22} {familles[f]:>3}")
    print("  partition : le champ `volet` du jeu, non refaite ici")


def imprimer_signal(cas: list[Cas], signal: str, detail: bool = False) -> None:
    front = frontiere(cas, signal)
    a = aire(cas, signal)
    n_c = front[0]["n_corpus"] if front else 0
    n_e = front[0]["n_etrangeres"] if front else 0

    print()
    print(f"SIGNAL « {signal} » — aire {a:.3f}".replace(".", ",")
          + f"   (sur {n_c} questions du corpus et {n_e} étrangères)")
    print(f"  {SIGNAUX[signal]}")
    if a < 0.5:
        print("  /!\\ AIRE SOUS 0,5 : le signal est INVERSÉ. Plus il est haut, plus")
        print("      la question est probablement étrangère au corpus.")
    print(f"  {'seuil':>10} {'refus à tort':>14} {'acceptées à tort':>18}   "
          f"{'rappel@1':>9} {'@3':>7} {'@5':>7}")
    lignes = front if detail else [f for f in front if f["acceptees_a_tort"] <= 6]
    for point in lignes:
        r = rappels(cas, signal, point["seuil"])
        print(f"  {_f(point['seuil']):>10} "
              f"{point['refus_a_tort']:>7} / {n_c:<4} "
              f"{point['acceptees_a_tort']:>9} / {n_e:<6}   "
              f"{_pc(r[1])} {_pc(r[3])} {_pc(r[5])}")


def imprimer_temoins(cas: list[Cas]) -> None:
    n_c = sum(1 for c in cas if c.du_corpus)
    n_e = len(cas) - n_c
    print()
    print("LES DEUX TÉMOINS, À LIRE AVANT TOUT TABLEAU")
    print("-" * 78)
    r = rappels(cas, None, 0.0)
    print(f"  répondre à tout     refus à tort 0 / {n_c:<4} "
          f"acceptées à tort {n_e} / {n_e}   "
          f"rappel {_pc(r[1])} {_pc(r[3])} {_pc(r[5])}")
    print(f"  se taire toujours   refus à tort {n_c} / {n_c:<4} "
          f"acceptées à tort 0 / {n_e}   "
          f"rappel {_pc(0.0)} {_pc(0.0)} {_pc(0.0)}")
    print("  Le second obtient 100 % d'abstention correcte et ne vaut rien : c'est")
    print("  pourquoi aucune abstention n'est imprimée ici sans son rappel.")


def imprimer_mecanisme(cas: list[Cas]) -> None:
    print()
    print("LE MÉCANISME DU DÉFAUT, VÉRIFIÉ OU DÉMENTI")
    print("-" * 78)
    r_marge_masse = correlation(cas, "marge", "masse5")
    print(f"  corrélation marge / masse5 : {r_marge_masse:+.3f}".replace(".", ","))
    print(f"  (sur {len(cas)} questions, les deux camps confondus)")
    if r_marge_masse < -0.3:
        print("  La prédiction tient : plus le voisinage est riche, plus la marge est")
        print("  petite. La marge et la masse mesurent bien des choses opposées, et")
        print("  c'est la masse qui pointe dans le bon sens.")
    elif r_marge_masse > 0.3:
        print("  La prédiction est DÉMENTIE : les deux signaux vont dans le même sens.")
        print("  L'explication du défaut est à réécrire avant de toucher à un seuil.")
    else:
        print("  La prédiction n'est ni confirmée ni démentie : les deux signaux sont")
        print("  à peu près indépendants. Le mécanisme raconté est donc, au mieux,")
        print("  incomplet — et il ne faut pas s'appuyer dessus pour choisir.")

    print()
    for camp, nom in ((True, "du corpus"), (False, "étrangères")):
        lot = [c for c in cas if c.du_corpus is camp]
        if not lot:
            continue
        for signal in ("marge", "masse5", "score1"):
            valeurs = sorted(c.signaux[signal] for c in lot)
            milieu = valeurs[len(valeurs) // 2]
            print(f"  {nom:11} {signal:8} n={len(lot):<3} "
                  f"min {_f(valeurs[0])}  médiane {_f(milieu)}  max {_f(valeurs[-1])}")


def imprimer_combinaisons(cas: list[Cas]) -> None:
    print()
    print("LES COMBINAISONS, ÉPROUVÉES EN DERNIER ET AVEC MÉFIANCE")
    print("-" * 78)
    for nom, (gauche, droite) in COMBINAISONS.items():
        front = frontiere_combinaison(cas, gauche, droite)
        n_c = front[0]["n_corpus"] if front else 0
        n_e = front[0]["n_etrangeres"] if front else 0
        print(f"  règle « {nom} » (sur {n_c} du corpus, {n_e} étrangères)")
        for point in front:
            if point["acceptees_a_tort"] > 4:
                continue
            sg, sd = point["seuils"]
            print(f"    {gauche} ≥ {_f(sg)} et {droite} ≥ {_f(sd)} : "
                  f"refus à tort {point['refus_a_tort']} / {n_c}, "
                  f"acceptées à tort {point['acceptees_a_tort']} / {n_e}")


def imprimer_classement(cas: list[Cas]) -> None:
    """Tous les signaux sur une seule page, au même point de comparaison.

    Le point de comparaison est : « combien de questions du corpus faut-il
    refuser pour n'accepter AUCUNE étrangère, puis au plus une ». Deux colonnes
    et non une, parce qu'un signal peut être excellent à zéro acceptation et
    s'écrouler juste après, ou l'inverse — et parce qu'exiger zéro erreur sur
    quinze cas est déjà un réglage sur le bruit.
    """
    print()
    print("TOUS LES SIGNAUX SUR UNE PAGE, AU MÊME POINT DE COMPARAISON")
    print("-" * 78)
    n_c = sum(1 for c in cas if c.du_corpus)
    n_e = len(cas) - n_c
    print(f"  {'signal':16} {'aire':>6}   {'0 étrangère acceptée':>22} "
          f"{'1 acceptée':>16}")
    rangs = sorted(SIGNAUX, key=lambda s: -aire(cas, s))
    for signal in rangs:
        front = {p["acceptees_a_tort"]: p for p in frontiere(cas, signal)}

        def _cout(n: int, _front=front, _signal=signal) -> str:
            p = _front.get(n)
            if p is None:
                return "(inatteignable)"
            r = rappels(cas, _signal, p["seuil"])
            return f"{p['refus_a_tort']:>2}/{n_c} refus, @5 {_pc(r[5])}"

        a = f"{aire(cas, signal):.3f}".replace(".", ",")
        print(f"  {signal:16} {a:>6}   {_cout(0):>22} {_cout(1):>22}")
    print(f"  rappel@5 sans aucune abstention : {_pc(rappels(cas, None, 0.0)[5])} "
          f"(sur {n_c} questions du corpus, {n_e} étrangères en face)")


def imprimer_rapport_controle(cas: list[Cas], signal: str, seuil: float) -> None:
    """Le seul chiffre qui ait valeur de mesure : la règle, sur la moitié écartée.

    Cette fonction ne choisit rien. Elle applique une règle DÉJÀ choisie sur la
    moitié « choix » à des questions qui n'ont pas servi à la choisir. L'écart
    entre les deux moitiés est le seul indicateur honnête de ce que le réglage
    vaudra sur des questions neuves — et s'il est grand, c'est le réglage qui
    est en cause, pas la moitié de contrôle.
    """
    du_corpus = [c for c in cas if c.du_corpus]
    etrangeres = [c for c in cas if not c.du_corpus]
    refus = [c for c in du_corpus if c.signaux[signal] < seuil]
    acceptees = [c for c in etrangeres if c.signaux[signal] >= seuil]
    r = rappels(cas, signal, seuil)
    r0 = rappels(cas, None, 0.0)

    print()
    print(f"RÈGLE « {signal} ≥ {_f(seuil)} » APPLIQUÉE À CETTE MOITIÉ")
    print("-" * 78)
    print(f"  refus à tort        {len(refus)} / {len(du_corpus)} questions du corpus")
    print(f"  acceptées à tort    {len(acceptees)} / {len(etrangeres)} questions étrangères")
    print(f"  abstention correcte {len(etrangeres) - len(acceptees)} / {len(etrangeres)} "
          f"= {_pc((len(etrangeres) - len(acceptees)) / max(len(etrangeres), 1))}")
    print(f"  rappel@1/@3/@5      {_pc(r[1])} {_pc(r[3])} {_pc(r[5])}")
    print(f"  (sans abstention    {_pc(r0[1])} {_pc(r0[3])} {_pc(r0[5])})")
    if acceptees:
        print("  Les étrangères encore servies :")
        for c in acceptees:
            print(f"    {c.id} {c.famille:12} {signal} {_f(c.signaux[signal])} — "
                  f"{c.question[:44]}")
    if refus:
        print("  Les questions du corpus refusées à tort :")
        for c in refus:
            print(f"    {c.id} {c.famille:12} {signal} {_f(c.signaux[signal])} — "
                  f"{c.question[:44]}")


def verifier_etrangeres() -> int:
    """Refuse une question étrangère dont le sujet serait traité par le Code.

    C'est le contrôle qui donne sa valeur à l'étiquette : sans lui, « hors
    corpus » serait une opinion de celui qui a écrit la question, et le banc
    mesurerait sa propre conviction.
    """
    corpus = charger_corpus()
    textes = [(a["numero"], depouiller(a["texte"])) for a in corpus.articles]
    echecs = 0
    print()
    print("VÉRIFICATION DES QUESTIONS ÉTRANGÈRES CONTRE LE CORPUS")
    print("-" * 78)
    for ident, question, famille, terme in ETRANGERES:
        if terme is None:
            print(f"  {ident} {famille:12} épargné explicitement — "
                  f"voir l'en-tête : {question[:40]}")
            continue
        touches = [n for n, t in textes if depouiller(terme) in t]
        if touches:
            echecs += 1
            print(f"  {ident} ÉCHEC : « {terme} » est dans les art. {touches[:6]} — "
                  "cette question n'est pas hors corpus.")
        else:
            print(f"  {ident} {famille:12} « {terme} » absent des "
                  f"{len(textes)} articles")
    print(f"  {len(ETRANGERES) - echecs} / {len(ETRANGERES)} vérifiées, {echecs} en échec")
    return echecs


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Quel signal distingue le dans-le-corpus du hors-corpus ?"
    )
    analyseur.add_argument("--controle", action="store_true",
                           help="le volet `verification`, à ne lire qu'une fois le seuil choisi")
    analyseur.add_argument("--tout", action="store_true",
                           help="les deux volets ensemble (pour décrire le jeu, pas pour régler)")
    analyseur.add_argument("--mes-etrangeres", action="store_true",
                           help="ajoute les 22 étrangères écrites dans ce fichier, en contre-épreuve")
    analyseur.add_argument("--detail", action="store_true",
                           help="la frontière entière et non son début")
    analyseur.add_argument("--verifier-etrangeres", action="store_true",
                           help="ne fait que vérifier que les questions étrangères le sont")
    analyseur.add_argument("--regle", default=None, metavar="SIGNAL:SEUIL",
                           help="rapporte une règle déjà choisie sur la moitié demandée "
                                "(ex. score1:0.4887) ; ne choisit rien")
    analyseur.add_argument("--json", default=None,
                           help="écrit les signaux de chaque question dans ce fichier")
    options = analyseur.parse_args(argv)

    if options.verifier_etrangeres:
        return 1 if verifier_etrangeres() else 0

    moitie = "tout" if options.tout else VOLETS["controle" if options.controle else "choix"]
    debut = time.time()
    cas, dense, lexical = collecter(moitie, options.mes_etrangeres)
    duree = time.time() - debut

    print("=" * 78)
    print(f"BANC D'ABSTENTION — volet « {moitie} », {len(cas)} questions, "
          f"{duree:.0f} s")
    print("=" * 78)
    imprimer_composition(cas)
    imprimer_sanite(dense, lexical)
    imprimer_temoins(cas)
    imprimer_mecanisme(cas)
    imprimer_classement(cas)
    for signal in SIGNAUX:
        imprimer_signal(cas, signal, detail=options.detail)
    imprimer_combinaisons(cas)

    if options.regle:
        nom, _, valeur = options.regle.partition(":")
        if nom not in SIGNAUX:
            raise SystemExit(f"Signal inconnu : {nom!r}. Attendu l'un de {sorted(SIGNAUX)}.")
        imprimer_rapport_controle(cas, nom, float(valeur))

    print()
    print("=" * 78)
    print("CE BANC NE RETIENT AUCUN SEUIL. Il imprime des courbes, et le seuil se")
    print("choisit sur la moitié « choix » puis se RAPPORTE sur « controle ». Un")
    print("seuil lu sur la moitié qui le juge n'est pas une mesure.")
    print("=" * 78)

    if options.json:
        chemin = _Path(options.json)
        if not chemin.is_absolute():
            chemin = _Path(__file__).resolve().parent / chemin
        chemin.write_text(
            json.dumps(
                {
                    "moitie": moitie,
                    "n": len(cas),
                    "partition": "champ `volet` de evaluation/questions.json",
                    "cas": [
                        {
                            "id": c.id,
                            "question": c.question,
                            "du_corpus": c.du_corpus,
                            "famille": c.famille,
                            "moitie": c.moitie,
                            "rendus": list(c.rendus),
                            "attendus": sorted(c.attendus),
                            "signaux": {k: round(v, 6) for k, v in c.signaux.items()},
                        }
                        for c in cas
                    ],
                    "aires": {s: round(aire(cas, s), 4) for s in SIGNAUX},
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"Signaux écrits dans {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
