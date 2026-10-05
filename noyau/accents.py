# -*- coding: utf-8 -*-
"""Rendre au bras dense les accents que l'usager n'a pas tapés.

    reaccentueur = construire(corpus)
    reaccentueur.appliquer("duree du conge de maternite")
    # -> "durée du congé de maternité"

POURQUOI CE MODULE EXISTE
-------------------------
Le bras lexical dépouille déjà les accents des deux côtés
(`noyau.lexical.depouiller`) : pour lui, « conge » et « congé » sont le même
jeton. Le bras dense, lui, reçoit la question BRUTE et la compare à un index
calculé sur le texte officiel du Code, qui est accentué. Taper sans accents lui
présente donc des mots que son plongeur ne découpe pas comme ceux de l'index,
et la proximité tombe.

CE QUE CETTE CHUTE VAUT, et pourquoi elle n'est pas un cas limite :

    "prototypes/vectoriel/.venv/Scripts/python.exe" arbitrage/accents.py

Ce banc l'imprime sur les 93 questions du jeu. Sa médiane est nulle — la
plupart des questions ne bougent pas — mais sa queue atteint un quart de point
de cosinus, là où le seuil d'abstention (`noyau.recherche.SEUIL_PROXIMITE`) ne
tient qu'à quelques centièmes au-dessus du plus haut score étranger. Une
secousse qui vaut plusieurs fois l'écart sur lequel un réglage repose n'est pas
du bruit : c'est le réglage qui est en cause.

Et le public visé n'est pas accessoire : ce service est fait pour des salariés
marocains qui écrivent depuis un téléphone. Taper sans accents n'est pas le cas
limite, c'est le cas normal.

LA RÈGLE, ET CE QU'ELLE REFUSE DE FAIRE
---------------------------------------
On ne re-accentue un mot que si **le Code ne l'écrit JAMAIS sans accent**.

C'est la seule règle qu'on puisse défendre sans arbitrer du français : elle
n'invente aucune forme, elle ne tranche aucune ambiguïté, et elle ne peut
produire qu'un mot que l'index connaît déjà. « conge » devient « congé » parce
qu'aucun des articles n'écrit « conge » ; « ou » reste « ou » parce que le Code
écrit les deux (« ou » et « où »), et deviner lequel serait une correction
orthographique, c'est-à-dire un autre métier. Le banc imprime combien de formes
sont retenues et combien sont écartées pour cette ambiguïté.

Ce que ce module n'est donc PAS : un correcteur d'orthographe. Il ne répare ni
une faute de frappe, ni un pluriel, ni une conjugaison. Il rend des accents, et
seulement là où le corpus ne laisse aucun doute sur lesquels.

CE QUE LA RÈGLE NE RÉPARE PAS, mesuré et non supposé
----------------------------------------------------
Elle ramène les dérobades que la désaccentuation créait (voir le banc), mais
elle ne rend pas la décision indifférente aux accents : des questions décident
encore autrement selon qu'on tape les accents ou non, et les injections sont du
nombre. Le détail chiffré est dans la réserve écrite à côté de
`noyau.recherche.SEUIL_PROXIMITE`, et il est épinglé par `tests/test_accents.py`
pour qu'une régression se voie plutôt que de se raconter.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from . import corpus as module_corpus
from .lexical import depouiller

# Des suites de LETTRES, chiffres et soulignés exclus. L'apostrophe et le trait
# d'union coupent, comme ils coupent dans le bras lexical : « l'annee » doit
# offrir le mot « annee » à la substitution, et « dommages-interets » les deux
# siens. Sans cette coupure, les mots collés à un déterminant élidé — c'est la
# moitié du français juridique — ne seraient jamais reconnus.
_MOT = re.compile(r"[^\W\d_]+", re.UNICODE)


def _calquer_casse(origine: str, remplacant: str) -> str:
    """La casse de l'usager, portée sur le mot rendu."""
    if origine.isupper() and len(origine) > 1:
        return remplacant.upper()
    if origine[:1].isupper():
        return remplacant[:1].upper() + remplacant[1:]
    return remplacant


@dataclass(frozen=True)
class Reaccentueur:
    """Un lexique figé, et la substitution qui s'en sert.

    Immuable parce qu'il est construit une fois par processus, en même temps que
    le moteur : un lexique qu'on pourrait compléter en cours de route rendrait
    deux appels identiques différents, et le déterminisme exigé par le contrat
    du noyau ne serait plus vrai que par habitude.
    """

    lexique: dict[str, str]
    # Les formes écartées parce que le Code écrit les deux. Gardées pour que le
    # banc puisse les imprimer : une règle qui dit ce qu'elle refuse est
    # vérifiable, une règle qui ne garde que ses succès ne l'est pas.
    ambigues: tuple[str, ...] = ()

    def appliquer(self, question: str) -> str:
        """Rend la question avec les accents que le Code ne discute pas.

        La casse d'origine est conservée. Ce n'est pas de la cosmétique : le
        plongeur découpe « Conge » et « conge » en jetons différents, et rendre
        « congé » là où l'usager avait écrit « Conge » introduirait une deuxième
        modification non mesurée dans une opération qui en mesure une.
        """
        morceaux: list[str] = []
        fin = 0
        for trouve in _MOT.finditer(question):
            mot = trouve.group(0)
            bas = mot.lower()
            # Un mot DÉJÀ accentué n'est jamais touché : `depouiller(bas) != bas`
            # signifie que l'usager a tapé ses accents, et on n'a pas à le
            # corriger. C'est ce qui rend cette passe presque inoffensive sur
            # une question accentuée — le banc mesure ce « presque ».
            remplacant = self.lexique.get(bas) if depouiller(bas) == bas else None
            if remplacant is None:
                continue
            morceaux.append(question[fin:trouve.start()])
            morceaux.append(_calquer_casse(mot, remplacant))
            fin = trouve.end()
        if not morceaux:
            # Aucune substitution : on rend la MÊME chaîne et non une copie
            # reconstruite. C'est le cas de toutes les questions correctement
            # accentuées, et il doit coûter zéro.
            return question
        morceaux.append(question[fin:])
        return "".join(morceaux)


def construire(corpus: module_corpus.Corpus) -> Reaccentueur:
    """Le lexique, lu dans le corpus et nulle part ailleurs.

    Il est bâti sur `corpus.passages()`, c'est-à-dire sur le TEXTE EXACTEMENT
    PLONGÉ — intitulés de hiérarchie compris. C'est le seul choix cohérent : ce
    lexique sert à écrire une question dans les mots que l'index connaît, et
    l'index ne connaît que ces passages-là. Le bâtir sur les textes d'articles
    seuls y perdrait le vocabulaire des intitulés, qui est justement celui dans
    lequel un usager pose sa question (« congé annuel payé » est un titre de
    chapitre).

    Le coût est une passe sur le corpus, payée une fois au chargement du moteur.
    `arbitrage/accents.py --cout` l'imprime.
    """
    formes: Counter[str] = Counter()
    for passage in corpus.passages():
        for trouve in _MOT.finditer(passage.texte):
            formes[trouve.group(0).lower()] += 1

    # La forme accentuée la plus fréquente pour chaque dépouillement. Le
    # départage par fréquence puis par ordre alphabétique, et non par ordre de
    # rencontre : deux constructions sur le même corpus doivent rendre le même
    # lexique, sinon la mesure de ce module n'est pas reproductible.
    meilleures: dict[str, str] = {}
    for forme in sorted(formes, key=lambda f: (-formes[f], f)):
        nu = depouiller(forme)
        if nu == forme:
            continue
        meilleures.setdefault(nu, forme)

    # LA GARDE. Si le Code écrit aussi la forme nue, on ne touche à rien : le
    # choix entre « ou » et « où » est une décision de langue, pas de corpus, et
    # la prendre ici reviendrait à réécrire la question de l'usager sur une
    # conviction. Mieux vaut laisser passer une chute mesurée qu'introduire une
    # correction qu'on ne sait pas justifier.
    lexique = {nu: acc for nu, acc in meilleures.items() if nu not in formes}
    ambigues = tuple(sorted(nu for nu in meilleures if nu in formes))
    return Reaccentueur(lexique=lexique, ambigues=ambigues)


def desaccentuer(question: str) -> str:
    """La question telle qu'un usager pressé la tape : sans accents, casse gardée.

    Elle sert aux bancs et aux tests, et elle est ici plutôt que recopiée dans
    chacun pour que « sans accents » veuille dire la même chose partout. Elle
    diffère de `noyau.lexical.depouiller` sur un point voulu : elle ne passe pas
    en minuscules. Mesurer la perte des accents ne doit pas mesurer en même
    temps la perte de la casse.
    """
    decompose = unicodedata.normalize("NFD", question)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")
