# -*- coding: utf-8 -*-
"""La garde des citations : le contrôle qui remplace la confiance.

    from moteur.garde import verifier, extraire_citations

    verdict = verifier(texte_du_modele, resultat.numeros)
    if not verdict.accepte:
        ...  # la réponse ENTIÈRE est jetée, et la raison est dans le verdict

CE QUE CE FICHIER EST
---------------------
C'est le cœur du projet, et sa seule promesse tenue. Un assistant juridique qui
invente un numéro d'article est pire qu'inutile : il est dangereux, parce que
la citation est précisément ce qui donne confiance. Une consigne du genre
« ne cite que les articles fournis » est une prière, pas une garantie — elle
cède à la première injection, et elle cède aussi toute seule, sans attaque,
parce qu'un modèle de langue hallucine.

La garantie est donc écrite en code, et elle tient en une inclusion :

    l'ensemble des articles CITÉS doit être inclus dans l'ensemble des
    articles RÉCUPÉRÉS.

Ce contrôle est vérifiable, testable, et insensible à ce que le modèle a
« compris ». C'est la même nature de garantie qu'un index unique en base de
données : il ne demande rien à personne, il refuse.

QUATRE RÈGLES, ET POURQUOI LA DERNIÈRE
--------------------------------------
1. Un numéro cité hors de l'ensemble récupéré fait rejeter la réponse entière.
2. Une réponse sans aucune citation est rejetée : une affirmation juridique
   sans source est exactement ce que ce produit refuse de servir.
3. Une RÉFÉRENCE QU'ON NE SAIT PAS RÉSOUDRE fait rejeter, au lieu de
   disparaître. « l'article L. 3121-1 », « l'article 231-1 », « l'article
   12bis » sont des numérotations du droit français ou des formes fabriquées :
   aucune ne se compare à l'ensemble récupéré, et les ignorer les faisait
   SERVIR. C'est le mode d'échec le plus dangereux de ce fichier, parce qu'il
   échoue ouvert, et il est détaillé plus bas.
4. La garde NE CORRIGE PAS. Elle ne retire pas la citation fautive, elle ne
   réécrit pas la phrase, elle ne garde pas « le reste ». Réparer silencieusement
   une réponse à moitié inventée donnerait un texte plausible dont plus personne
   ne saurait ce qu'il vaut — et le lecteur n'aurait aucun moyen de distinguer
   une réponse vérifiée d'une réponse rapiécée. Une réponse rejetée ne s'affiche
   pas ; elle devient un silence motivé.

L'EXTRACTION EST LA PARTIE FRAGILE, ET ELLE EST MESURÉE SUR LE CORPUS
---------------------------------------------------------------------
Rater une forme de citation, c'est laisser passer exactement ce que la garde
devait arrêter : le numéro inventé n'est pas lu, donc il n'est pas comparé,
donc la réponse est servie. Les formes reconnues ci-dessous ne sont pas
devinées, elles sont comptées dans le texte du Code lui-même (589 articles) :

    « l'article 9 »            235 occurrences
    « articles 154 et 156 »     36 occurrences
    « articles 27, 28 »         20 occurrences
    « articles 145 à 148 »      11 occurrences   (une plage, donc 145 à 148)
    « article premier »          1 occurrence
    « art. 45 »                  0 occurrence dans le Code, reconnue quand même :
                                 c'est un modèle de langue qui écrit, pas le
                                 législateur.
    « l'article **512** »        0 occurrence, reconnue pour la même raison :
                                 le Code est en texte brut, un modèle met ses
                                 numéros en gras. Une emphase non lue cachait
                                 le numéro, donc le soustrayait au contrôle.

Un piège mesuré, et c'est lui qui impose d'ancrer l'extraction sur le mot
« article » plutôt que de ramasser les nombres : « 1er » apparaît onze fois
dans le Code, et jamais une seule pour désigner l'article premier — toujours
dans « le 1er alinéa de l'article 9 » ou « 1er mai 1942 ». Une extraction qui
lirait « 1er » comme une citation lirait des articles partout.

L'extracteur est donc mesuré sur le Code entier, qui se cite abondamment
lui-même — c'est `tests/test_garde.py`, classe `ExtractionSurLeCodeEntier` :

    python tests/test_garde.py

432 citations lues dans les 589 articles, et exactement trois numéros hors du
corpus — qui sont de vraies citations d'AUTRES textes (articles 1098 et 1248 du
Code des obligations et des contrats, article 780 d'un dahir de 1913). Aucune
référence du Code n'est jugée illisible, et aucun ordinal de liste n'est pris
pour une source.

Ce compte a valu 480 tant que le point-virgule enchaînait les citations, et
cette différence de 48 est instructive : c'étaient les ordinaux des listes à
puces (« l'article 184 ;\n2. le non-respect… »), des nombres ordinaires promus
en sources. Ils étaient INVISIBLES au contrôle d'appartenance au corpus, parce
que 2, 3, 4, 5, 6, 7 et 9 sont tous des numéros d'articles existants — le test
lit donc désormais le contexte à gauche de chaque numéro, et non sa seule
existence. Un faux positif ne se reconnaît pas à ce qu'il désigne.

CE QUE CETTE GARDE REJETTE À TORT, ET QU'IL FAUT SAVOIR
-------------------------------------------------------
Ces trois numéros disent la limite exacte du contrôle : une réponse qui
citerait, à juste titre, l'article 1098 du Code des obligations et des contrats
serait rejetée, parce que ce texte n'est pas dans le corpus et ne peut donc pas
être vérifié. C'est le comportement voulu — Mizan ne répond que par le Code du
travail, et une citation non vérifiable est traitée comme une citation
inventée — mais c'est bien un refus de servir quelque chose de juste, et non un
simple refus de servir quelque chose de faux. Élargir le corpus est la seule
façon d'élargir ce que la garde autorise.

CE QUI RESTE OUVERT, ET QU'IL NE FAUT PAS CROIRE FERMÉ
------------------------------------------------------
L'inclusion d'ensembles est une garantie ; l'EXTRACTION qui l'alimente est une
heuristique de motifs. La garantie ne porte donc que sur les numéros LUS, et il
reste une forme connue qu'elle ne lit pas : le numéro NU, écrit sans le mot
« article ».

    « L'article 231 vous ouvre ce droit (voir aussi 350 et 387). »

350 et 387 ne sont pas lus, donc pas comparés, et la réponse est acceptée. Ce
n'est pas un oubli, c'est l'autre côté d'une décision mesurée : ramasser les
nombres nus ferait lire des citations partout, puisque « 1er » apparaît onze
fois dans le Code sans jamais désigner l'article premier. Le choix est entre
rater cette forme-là et rejeter des réponses justes en masse, et c'est le
premier terme qui a été retenu — mais il doit être écrit, parce que c'est le
seul endroit où la garantie cesse d'être structurelle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# ── Les formes reconnues ────────────────────────────────────────────────────

# Ce qui peut séparer le mot « article » de son numéro. L'espace ne suffit pas,
# et c'est une correction de sûreté : ce n'est pas le législateur qui rédige les
# réponses, c'est un modèle de langue, et un modèle de langue met les numéros
# d'article en gras (« l'article **512** »), les annonce après un deux-points
# (« Article : 512 ») ou les met entre guillemets. Chacune de ces écritures
# cachait le numéro à l'extracteur, donc le soustrayait à la comparaison.
#
# Le tiret est volontairement absent de cette classe, pour la même raison qu'il
# n'ouvre pas une plage : il est d'abord une ponctuation française. Les treize
# signes retenus sont mesurés sans effet sur le Code (432 citations lues avant
# comme après), parce que le législateur écrit ses renvois sans mise en forme.
#
# Le deux-points coûte UN faux positif connu, et il est gardé quand même :
# « Articles : 1. le salaire ; 2. la durée » — un en-tête suivi d'une liste
# numérotée — fait lire l'article premier. L'arbitrage est celui de tout ce
# fichier : ce faux positif échoue FERMÉ (une réponse juste est rejetée, rien de
# faux n'est servi), là où ne pas lire « Article : 512 » échouerait OUVERT. Le
# cas reste étroit, parce qu'il faut que le mot « article » soit immédiatement
# suivi du deux-points : « les articles applicables sont :\n1. l'article 231 »
# se lit correctement, les lettres n'étant pas dans la classe.
_SEPARATEUR = r"[\s*_`:«»\"'()\[\]]*"

# Le mot qui annonce une citation. L'ancrage se fait sur lui et jamais sur un
# nombre seul : « 44 heures » et « deux ans » ne sont pas des sources, et
# « le 1er alinéa » n'est pas l'article premier.
_ANNONCE_BRUTE = (
    r"\b(?:articles?|art\.?)" + _SEPARATEUR + r"(?:n[°o]" + _SEPARATEUR + r")?"
)
_ANNONCE = re.compile(_ANNONCE_BRUTE, re.IGNORECASE)

# « premier », « 1er », « 12 », « 012 ». Quatre chiffres au plus : le Code en
# compte 589, et une suite plus longue n'est pas un numéro d'article — la
# limite évite surtout d'avaler une année ou un montant.
#
# Le numéro doit se terminer vraiment : « article 231-1 » ne rend PAS la
# citation 231, parce que cette numérotation n'existe pas dans le Code
# marocain. Ce qui n'est pas lu ici est repris par `_FABRIQUEE` ci-dessous : ne
# rien rendre du tout ferait SERVIR la référence au lieu de la rejeter.
#
# Le souligné est le seul caractère de mot toléré DERRIÈRE le numéro, parce
# qu'il ferme une italique Markdown (« l'article _512_ ») et ne fait pas partie
# d'une numérotation. La lettre et le tiret restent exclus : ce sont eux qui
# distinguent « 12bis » et « 231-1 » d'un numéro du Code.
_NOMBRE = re.compile(
    r"(?:premier|1(?:er|ᵉʳ)|\d{1,4})(?![^\W_]|-)", re.IGNORECASE
)

# Les références qu'aucune lecture ne peut résoudre, et qui doivent donc faire
# rejeter plutôt que disparaître. C'EST LE CORRECTIF D'UN ÉCHEC OUVERT : une
# forme que `_NOMBRE` ne lit pas ne produit aucun numéro, donc rien n'est
# comparé, donc le texte est servi — et accompagnée d'une citation valable, une
# référence inventée passait la garde et s'affichait.
#
# Ce sont des numérotations du droit FRANÇAIS (« L. 3121-1 », « 231-1 »,
# « 12bis ») ou des nombres hors d'échelle, et chacune est mesurée à ZÉRO
# occurrence dans les 589 articles : les traiter comme des rejets ne coûte
# aucun faux positif sur du texte légitime.
#
# Le contrôle large qu'on pourrait croire plus sûr — « toute annonce sans
# numéro lisible fait rejeter » — est au contraire inutilisable : mesuré, il
# tombe 85 fois sur le Code lui-même (« au présent article », « artisanales »,
# « article. »), et il ferait rejeter une réponse qui écrit « l'article
# précité ». La liste de formes est donc un choix, pas une facilité.
# Les formes sont lues ENTIÈRES, et pas seulement jusqu'au premier caractère
# qui les trahit : la référence refusée est nommée dans la phrase rendue à
# l'usager, et « article L. 3 » ne lui dirait pas de quoi on parle.
_FABRIQUEE_CHIFFREE = re.compile(
    r"\d{5,}|\d+(?:-\d+)+|\d+\s*(?:bis|ter|quater)\b|L\.?\s*\d+(?:-\d+)*",
    re.IGNORECASE,
)

# Un numéro écrit en lettres n'est reconnu que juste après l'annonce, jamais
# après un lien : « l'article 12 et un salarié » est une phrase ordinaire, et
# « et un » y est un article indéfini, pas un numéro.
#
# La limite finale `\b` n'est pas décorative : sans elle, « article unique » et
# « article une fois par an » seraient lus comme des numéros en lettres.
_NOMBRE_EN_LETTRES = (
    r"(?:un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize"
    r"|quatorze|quinze|seize|vingts?|trente|quarante|cinquante|soixante"
    r"|cents?|mille)"
)
_FABRIQUEE_EN_LETTRES = re.compile(
    _NOMBRE_EN_LETTRES + r"(?:[-\s](?:et[-\s])?" + _NOMBRE_EN_LETTRES + r")*\b",
    re.IGNORECASE,
)

# Ce qui enchaîne deux numéros dans une même citation : « 154 et 156 »,
# « 27, 28 », « 27, 28 et 29 ».
#
# LE POINT-VIRGULE EN EST ABSENT, et c'est une décision mesurée. Le Code
# n'écrit aucune énumération d'articles avec un point-virgule ; ce qui suit un
# point-virgule, dans ses 589 articles, est l'ordinal d'une liste à puces
# (« l'article 184 ;\n2. le non-respect… »). L'accepter faisait lire 48 faux
# positifs sur le corpus — invisibles, parce que 2, 3, 4, 5, 6, 7 et 9 sont
# tous des articles existants — et faisait rejeter une réponse juste rédigée en
# liste numérotée, en lui reprochant une citation qu'elle n'avait pas écrite.
_LIEN = re.compile(r"\s*(?:,|et|ou|&)\s*", re.IGNORECASE)

# Un nombre de prose, qui n'est pas un numéro d'article même quand un lien le
# précède. « l'article 238, 18 jours ouvrables sont dus » est la formulation
# ORDINAIRE d'une réponse de droit du travail : l'article, puis la quantité
# qu'il fixe. La lire comme une énumération de citations faisait jeter des
# réponses exactes en accusant le rédacteur d'avoir inventé l'article 18.
#
# Le commentaire de `_PLAGE` raisonnait déjà sur ce danger pour le tiret, et le
# fermait de ce côté-là ; la virgule, qui est la ponctuation que le français
# met réellement à cet endroit, était restée ouverte.
_QUANTITE = re.compile(
    r"\d+,\d"                                   # 1,5 jour — virgule décimale
    r"|\d+\s+\d"                                # 30 000 dirhams — milliers
    r"|\d+\s*%"
    r"|\d+\s*(?:heures?|jours?|mois|ans?|années?|semaines?|alinéas?"
    r"|dirhams?|fois|minutes?)\b",
    re.IGNORECASE,
)

# Ce qui ouvre une plage : « articles 145 à 148 » cite aussi 146 et 147, et
# les ignorer laisserait passer deux numéros non contrôlés. Le mot « article »
# est avalé au passage, pour que « de l'article 231 à l'article 234 » soit lu
# comme la plage qu'il est et non comme ses deux bornes.
#
# DEUX ÉCRITURES REFUSÉES COMME OUVRE-PLAGE, et ce sont des décisions.
#   • le tiret, parce qu'il est d'abord une ponctuation française :
#     « l'article 231 — 1,5 jour par mois » serait lu comme une plage de 231 à
#     1, et « l'article 5 - 10 jours de congé » comme la plage 5 à 10, ce qui
#     ferait rejeter une réponse correcte à cause d'une habitude
#     typographique ;
#   • le « a » sans accent, parce qu'il est d'abord le verbe avoir :
#     « l'article 32 a 2 alinéas » fabriquerait la plage 32 à 2.
# Le corpus tranche dans le même sens : ses onze plages s'écrivent toutes
# « à », aucune avec un tiret.
#
# Les deux apostrophes sont acceptées dans « jusqu'à », comme elles le sont
# déjà dans « l' » : le Code n'écrit cette forme qu'avec l'apostrophe droite et
# jamais pour ouvrir une plage d'articles, donc cette écriture n'existe que
# dans la sortie d'un modèle — c'est-à-dire là où l'apostrophe typographique
# est la plus probable. N'en lire qu'une laissait le milieu de la plage sortir
# du texte sans être comparé.
_PLAGE = re.compile(
    r"\s*(?:jusqu['’]à|à)\s+(?:l['’]\s*)?(?:articles?\s*)?(?:n[°o]\s*)?",
    re.IGNORECASE,
)

# Au-delà, la plage est plus large que le Code entier : on garde ses deux
# bornes, qui suffisent à la faire rejeter, plutôt que de fabriquer des
# milliers de numéros.
_PLAGE_MAXIMALE = 600

# Les quatre écritures du premier article du Code, qui n'a pas de numéro
# chiffré dans le texte officiel. « article 1 » et « article 1er » désignent
# bien le même article que « article premier » : les ramener à une seule forme
# n'est pas une complaisance envers le modèle, c'est reconnaître une citation
# exacte écrite autrement.
_ECRITURES_DU_PREMIER = frozenset({"premier", "1", "1er", "1ᵉʳ"})
PREMIER = "premier"

# Combien de numéros fautifs la phrase rendue à l'usager nomme avant de compter
# le reste. `Verdict.inventees` n'est jamais tronqué, lui.
_NOMS_MONTRES = 5


def normaliser(brut: str) -> str:
    """Ramène une écriture de numéro à celle du corpus.

    Les zéros de tête sautent (« article 012 » cite l'article 12) et les
    écritures du premier article se rejoignent. Tout le reste est rendu tel
    quel : inventer une correspondance ferait de la garde une traductrice, et
    une traductrice finit par faire passer pour exact ce qui ne l'est pas.
    """
    jeton = brut.strip().lower().replace(" ", "")
    # Les zéros de tête sautent AVANT la comparaison aux écritures du premier
    # article, sans quoi « article 01 » se lirait « 1 » et resterait distinct de
    # « article premier » — deux numéros pour un seul article, dont l'un ferait
    # rejeter une réponse exacte.
    if jeton.isdigit():
        jeton = str(int(jeton))
    return PREMIER if jeton in _ECRITURES_DU_PREMIER else jeton


def extraire_citations(texte: str) -> tuple[str, ...]:
    """Les numéros d'articles cités, dans l'ordre d'apparition, sans doublon.

    Lecture gauche à droite ancrée sur le mot « article » : à chaque annonce,
    on consomme la suite de numéros qui l'accompagne, en s'arrêtant au premier
    mot qui n'en est pas un. C'est ce qui fait que « articles 12 et 13 » rend
    deux numéros, et que « l'article 12 et le salarié » n'en rend qu'un.

    Les références que cette lecture ne résout PAS n'apparaissent pas ici : il
    faut `_lire` pour les voir, et c'est `verifier` qui les utilise. Un
    appelant qui ne regarderait que cette fonction croirait qu'un texte truffé
    de « l'article L. 3121-1 » ne cite rien.
    """
    return _lire(texte)[0]


def _lire(texte: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Les citations lues, ET les références qu'on n'a pas su résoudre.

    Les deux sorties ne se remplacent pas : la première alimente l'inclusion
    d'ensembles, la seconde fait rejeter sans même la calculer. Rendre une
    référence fabriquée dans la première serait inventer un numéro pour le
    compte du modèle ; l'oublier serait la servir.
    """
    if not texte:
        return (), ()

    trouves: list[str] = []
    vus: set[str] = set()
    illisibles: list[str] = []

    def retenir(numero: str) -> None:
        if numero not in vus:
            vus.add(numero)
            trouves.append(numero)

    def signaler(fragment: str) -> None:
        if fragment not in illisibles:
            illisibles.append(fragment)

    for annonce in _ANNONCE.finditer(texte):
        position = annonce.end()
        premier = _NOMBRE.match(texte, position)
        if premier is None:
            fabriquee = _FABRIQUEE_CHIFFREE.match(
                texte, position
            ) or _FABRIQUEE_EN_LETTRES.match(texte, position)
            if fabriquee is not None:
                signaler(f"{annonce.group(0).strip()} {fabriquee.group(0)}")
            # Sinon : « l'article précité », « au même article ». Une mention
            # sans numéro n'est pas une citation, et n'en fabrique pas une.
            continue
        retenir(normaliser(premier.group(0)))
        position = premier.end()
        precedent = premier.group(0)

        while True:
            plage = _PLAGE.match(texte, position)
            lien = None if plage else _LIEN.match(texte, position)
            if plage is None and lien is None:
                break
            apres = (plage or lien).end()
            if _QUANTITE.match(texte, apres) is not None:
                # « l'article 238, 18 jours ouvrables » : une quantité, pas un
                # second numéro d'article. La citation s'arrête ici.
                break
            suite = _NOMBRE.match(texte, apres)
            if suite is None:
                fabriquee = _FABRIQUEE_CHIFFREE.match(texte, apres)
                if fabriquee is not None:
                    signaler(f"article {fabriquee.group(0)}")
                # Le lien n'annonçait pas un numéro (« et le salarié », « ou à
                # défaut ») : on ne consomme rien et la citation s'arrête ici.
                break
            if plage is not None:
                etendue = _etendre(precedent, suite.group(0))
                if etendue is None:
                    signaler(
                        f"articles {normaliser(precedent)} à "
                        f"{normaliser(suite.group(0))}"
                    )
                    break
                for numero in etendue:
                    retenir(numero)
            else:
                retenir(normaliser(suite.group(0)))
            precedent = suite.group(0)
            position = suite.end()

    return tuple(trouves), tuple(illisibles)


def _etendre(debut_brut: str, fin_brut: str) -> list[str] | None:
    """Les numéros d'une plage « 145 à 148 », bornes comprises.

    L'article premier compte pour 1 dans le calcul : « articles 1 à 12 » est
    une plage parfaitement calculable, puisque `_ECRITURES_DU_PREMIER`
    établit déjà que « article 1 » et « article premier » désignent le même
    article. Ne pas la déplier laissait un texte affirmer douze articles alors
    que deux seulement avaient été comparés.

    Rend `None` quand la plage est incompréhensible — bornes à l'envers, ou
    plus large que le Code entier. Ses bornes ne sont alors PAS rendues comme
    des citations : une plage qu'on ne sait pas lire n'est pas une citation
    vérifiable, et rendre ses deux bornes la faisait accepter quand les deux
    étaient récupérées, alors que le texte affirme tout ce qui se trouve entre
    elles.
    """
    def rang(brut: str) -> int | None:
        jeton = normaliser(brut)
        if jeton == PREMIER:
            return 1
        return int(jeton) if jeton.isdigit() else None

    premier, dernier = rang(debut_brut), rang(fin_brut)
    if premier is None or dernier is None:
        return None
    if not 0 < dernier - premier <= _PLAGE_MAXIMALE:
        return None
    return [normaliser(str(n)) for n in range(premier, dernier + 1)]


# ── Le verdict ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Verdict:
    """Ce que la garde décide, et de quoi l'expliquer sans relire le code.

    `motif` est un identifiant stable, pour les tests et les journaux ;
    `raison` est la phrase française qu'un usager peut lire. Les deux existent
    parce qu'un identifiant ne s'affiche pas et qu'une phrase ne se compare pas.
    """

    accepte: bool
    citations: tuple[str, ...] = ()
    inventees: tuple[str, ...] = ()
    motif: str = ""
    raison: str = ""
    illisibles: tuple[str, ...] = ()


# Les motifs de rejet. Quatre, et aucun ne corrige quoi que ce soit.
TEXTE_VIDE = "texte_vide"
SANS_CITATION = "sans_citation"
CITATION_INVENTEE = "citation_inventee"
CITATION_ILLISIBLE = "citation_illisible"


def verifier(texte: str, numeros_recuperes: Iterable[str]) -> Verdict:
    """Accepte ou rejette un texte rédigé, contre l'ensemble des articles récupérés.

    `numeros_recuperes` est exactement `Resultat.numeros` du noyau. Il est passé
    en argument et non relu ici : la garde ne doit pas pouvoir aller chercher
    un ensemble plus large que celui qui a servi à écrire la réponse, sans quoi
    le contrôle porterait sur autre chose que ce qui s'est réellement passé.
    """
    # Une chaîne est un `Iterable[str]` pour l'annotation, et l'itérer donne
    # ses CARACTÈRES : `verifier("…", "12")` fabriquait l'ensemble autorisé
    # {premier, 2} et rejetait une réponse exacte en imputant au rédacteur une
    # invention qu'il n'avait pas commise. Échouer en silence est le seul mode
    # de panne que ce fichier existe pour exclure.
    if isinstance(numeros_recuperes, str):
        raise TypeError(
            "numeros_recuperes est un ENSEMBLE de numéros, pas un numéro : "
            "une chaîne s'itère caractère par caractère et fabriquerait un "
            "ensemble autorisé faux. Passez `Resultat.numeros`, ou {« 12 »}."
        )
    # `str(n)` plutôt que `normaliser(n)` seul : un appelant qui range ses
    # numéros en entiers obtenait un AttributeError nu remontant d'une fonction
    # publique, au lieu d'un ensemble correct.
    autorises = frozenset(normaliser(str(n)) for n in numeros_recuperes)

    if not (texte or "").strip():
        return Verdict(
            accepte=False,
            motif=TEXTE_VIDE,
            raison=(
                "Le rédacteur n'a rien écrit : il n'y a pas de réponse à "
                "vérifier, donc pas de réponse à afficher."
            ),
        )

    citations, illisibles = _lire(texte)

    # AVANT l'inclusion, et avant même le contrôle « au moins une citation » :
    # une référence qu'on ne sait pas résoudre ne peut pas être comparée, donc
    # la seule conduite sûre est de rejeter. L'ordre compte, parce qu'un texte
    # qui mêle une citation valable et une référence fabriquée passait
    # l'inclusion sans que la seconde y entre jamais.
    if illisibles:
        return Verdict(
            accepte=False,
            citations=citations,
            illisibles=illisibles,
            motif=CITATION_ILLISIBLE,
            raison=_raison_illisible(illisibles),
        )

    if not citations:
        return Verdict(
            accepte=False,
            motif=SANS_CITATION,
            raison=(
                "La réponse rédigée ne cite aucun article : une affirmation "
                "juridique sans source ne peut pas être vérifiée, elle n'est "
                "donc pas servie."
            ),
        )

    inventees = tuple(n for n in citations if n not in autorises)
    if inventees:
        return Verdict(
            accepte=False,
            citations=citations,
            inventees=inventees,
            motif=CITATION_INVENTEE,
            raison=_raison_inventee(inventees, len(autorises)),
        )

    return Verdict(accepte=True, citations=citations)


def _raison_inventee(inventees: tuple[str, ...], combien_autorises: int) -> str:
    """Nomme les numéros fautifs, et dit que c'est la réponse entière qui tombe.

    Le nombre d'articles récupérés est donné pour que la phrase ne laisse pas
    croire que le système n'avait rien trouvé : il avait trouvé, et c'est la
    rédaction qui a dérapé. La distinction compte pour qui lit un journal de
    service aussi bien que pour l'usager.
    """
    # L'énumération est bornée, parce qu'une plage large déplie des centaines
    # de numéros et qu'une phrase de trois mille signes n'est pas une phrase.
    # `Verdict.inventees` reste complet pour les journaux et les tests : c'est
    # la même séparation des rôles que `motif` et `raison`.
    montres = [
        "premier" if n == PREMIER else n for n in inventees[:_NOMS_MONTRES]
    ]
    reste = len(inventees) - len(montres)
    noms = ", ".join(montres) + (f" et {reste} autres" if reste else "")
    # La phrase entière, et non un « s » suffixé : l'élision française donne
    # « l'article 12 » au singulier et « les articles 12, 13 » au pluriel.
    # « l'articles » n'est pas une forme de la langue, et cette phrase est la
    # seule que l'usager lit après un rejet.
    debut = "les articles" if len(inventees) > 1 else "l'article"
    verbe = "ne figurent pas" if len(inventees) > 1 else "ne figure pas"
    fonds = (
        "le seul article retrouvé"
        if combien_autorises == 1
        else f"les {combien_autorises} articles retrouvés"
    )
    return (
        f"Réponse rejetée en entier : elle cite {debut} {noms}, "
        f"qui {verbe} parmi {fonds} pour cette question. Une citation que le "
        "système n'a pas récupérée ne peut pas être vérifiée, et une réponse à "
        "moitié inventée n'est pas rapiécée."
    )


def _raison_illisible(illisibles: tuple[str, ...]) -> str:
    """Dit que la référence n'a pas pu être lue, donc pas pu être vérifiée.

    Le motif est distinct de l'invention, et la distinction est honnête : le
    système ne sait pas si l'article existe, il sait qu'il ne sait pas le
    résoudre. Affirmer l'invention serait affirmer un contrôle qui n'a pas eu
    lieu — exactement le défaut que ce rejet corrige.
    """
    montres = list(illisibles[:_NOMS_MONTRES])
    reste = len(illisibles) - len(montres)
    noms = ", ".join(f"« {r} »" for r in montres) + (
        f" et {reste} autres" if reste else ""
    )
    pluriel = "s" if len(illisibles) > 1 else ""
    return (
        f"Réponse rejetée en entier : elle porte la référence{pluriel} "
        f"{noms}, qu'aucune lecture ne résout en numéro d'article du Code du "
        "travail marocain. Une référence que le système ne peut pas comparer à "
        "ce qu'il a récupéré est traitée comme une citation inventée, parce "
        "que la servir serait affirmer un contrôle qui n'a pas eu lieu."
    )
