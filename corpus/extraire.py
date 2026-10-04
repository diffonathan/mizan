# -*- coding: utf-8 -*-
"""Extraction du Code du travail marocain : PDF Adala -> code-travail.json.

Ce script est la fondation de Mizan. Tout ce qui sera construit au-dessus
(recherche, citation, réponse) repose sur la fidélité de ce fichier JSON. Il
échoue donc en erreur plutôt que de produire un corpus douteux : un assistant
juridique qui cite un article tronqué est plus nuisible qu'un assistant qui
refuse de démarrer.

Usage :
    python extraire.py                 # extrait, contrôle, écrit le JSON
    python extraire.py --sans-ecrire   # extrait et contrôle seulement

Code de sortie 0 si tous les contrôles passent, 1 sinon.
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
import difflib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf  # « fitz » est l'ancien nom, déprécié depuis PyMuPDF 1.24.

RACINE = Path(__file__).resolve().parent
PDF = RACINE / "source" / "code-travail-adala.pdf"
SORTIE = RACINE / "code-travail.json"

# Date de consolidation du texte source, lue en page de garde du PDF. Elle est
# recopiée dans le JSON parce que c'est la seule chose qui empêche un usager de
# croire que ce corpus est à jour : le Code a été modifié après 2011.
DATE_CONSOLIDATION = "2011-10-26"

NOMBRE_ARTICLES_OFFICIEL = 589
# 102 notes de bas de page, comptées sur les textes reconstitués (numérotation
# continue de 1 à 102). Le compte des APPELS visibles comme spans séparés n'en
# donne que 100 : l'appel 1 est composé en 14,5 pt page 2, et l'appel 102 est
# fondu dans un span de corps page 200. Voir CORRECTIONS_NOMMEES.
NOMBRE_NOTES_ATTENDU = 102

# ───────────────────────────────────────────────────────────────────────────────
# Pourquoi la taille de police, et non des expressions régulières sur le texte
# ───────────────────────────────────────────────────────────────────────────────
#
# Le PDF mêle trois flux qui, dans `page.get_text()`, arrivent entrelacés : le
# texte de loi, les notes de bas de page, et le pied de page « - 101 - ». Un
# découpage par motifs textuels les confond — on l'a vérifié : la note 37
# collée à « De l'hygiène et de la sécurité des salariés » ressemble, pour une
# regex, à la fin de l'intitulé.
#
# La mise en page, elle, les sépare sans ambiguïté (mesuré sur les 201 pages) :
#
#   corps de loi          Book Antiqua        14 pt
#   intitulés             Book Antiqua Bold   15 / 16 / 18 / 22 pt
#   appels de note        Book Antiqua        9 / 9,5 / 10 / 10,6 pt
#   notes de bas de page  Times New Roman     12 pt, parfois Book Antiqua 10 pt
#   pied de page          Times New Roman     12 pt
#
# Le seuil de 13 pt sépare donc le flux législatif (>= 13) du paratexte (< 13),
# et aucune autre taille n'existe dans ce document. C'est une propriété de CE
# fichier, pas une règle générale sur les PDF : un autre tirage du Code
# demanderait de remesurer. Le script le vérifie (TAILLES_CONNUES) et refuse de
# tourner sur un PDF dont la typographie diffère.
SEUIL_FLUX = 13.0
TAILLES_CONNUES = {
    8.0,    # « er » en exposant, dans une note de bas de page
    9.0, 9.5, 10.0, 10.6,  # appels de note
    12.0,   # notes de bas de page et pied de page
    14.0,   # corps de loi
    14.5,   # l'appel de note 1, page 2 : seul appel composé AU-DESSUS du seuil
    15.0, 16.0, 18.0, 22.0, 36.0,  # intitulés, du plus fin au titre de couverture
}

# ───────────────────────────────────────────────────────────────────────────────
# Les défauts de la couche texte du PDF, corrigés nommément
# ───────────────────────────────────────────────────────────────────────────────
#
# Trois endroits du document ont une couche texte fautive : une espace
# manquante, ou un appel de note fondu dans le span du corps au lieu d'être un
# span de 9 pt. Aucun signal typographique ni géométrique ne permet de les
# traiter automatiquement — la faute est dans les caractères eux-mêmes.
#
# On ne les corrige donc PAS par une heuristique. Chaque correction est écrite
# ici, avec sa raison, et le contrôle n° 12 vérifie qu'il n'en reste aucune
# autre : dans un texte de loi, un chiffre ne suit jamais immédiatement une
# lettre. Si une révision du PDF en introduisait une nouvelle, le script
# échouerait et un humain trancherait, au lieu qu'un chiffre disparaisse en
# silence du Code du travail.
CORRECTIONS_NOMMEES = (
    (
        re.compile(r"\b(articles?)(\d)"),
        r"\1 \2",
        None,
        "espace manquante entre « article » et son numéro (pages 101 et 147)",
    ),
    (
        re.compile(r"\bà1000\b"),
        "à 1000",
        None,
        "espace manquante dans « de 500 à1000 dirhams » (page 147)",
    ),
    (
        re.compile(r"\bprofessionnels102\b"),
        "professionnels",
        102,
        "appel de note 102 fondu dans le corps du texte (page 200, article 586)",
    ),
)

# ───────────────────────────────────────────────────────────────────────────────
# Comment on retrouve les alinéas, que le flux brut du PDF a perdus
# ───────────────────────────────────────────────────────────────────────────────
#
# `get_text()` rend un texte sans paragraphes : les retours à la ligne y sont
# ceux de la MISE EN PAGE, pas ceux du législateur. Or un article de loi se cite
# par alinéa, et une énumération recollée en un seul bloc devient illisible.
#
# Deux mesures sur les 191 pages d'articles permettent de les reconstituer.
#
# 1. Le bord droit. 3 372 des 5 007 lignes de corps s'arrêtent à 528 points ;
#    en dessous, la distribution s'effondre (au plus 22 lignes par valeur). 528
#    est donc le fer du bloc justifié : une ligne qui s'arrête avant termine son
#    paragraphe. Le seuil est à 523 et non à 528, parce que trois glyphes finaux
#    laissent la ligne s'arrêter un peu court tout en la remplissant : le trait
#    d'union (vers 525), et l'appel de note des articles 43 et 217, dont le
#    chiffre occupe les quatre derniers points de la ligne (524) et qu'on vient
#    justement de retirer. Le bord droit est donc mesuré sur la ligne IMPRIMÉE,
#    appel de note compris, et non sur le texte qu'on en conserve.
#
# 2. L'indentation gauche, qui va par paires (première ligne, puis lignes
#    suivantes) : 99 → 71 pour un alinéa ordinaire, 117 → 135 pour un item
#    d'énumération. Une ligne moins indentée que la précédente sans revenir au
#    fer à gauche (71) ouvre donc un nouveau bloc — c'est ce qui rattrape le
#    « 3) Autres absences : » de l'article 274, dont la ligne précédente
#    atteignait presque la marge.
#
# Ce sont deux heuristiques, pas des certitudes, et aucune assertion ne peut les
# valider : VERIFICATION.md dit lesquels des 589 articles ont été relus à l'œil
# pour les éprouver.
MARGE_DROITE = 523.0
FER_A_GAUCHE = 85.0

MOTS_HIERARCHIE = ("Livre", "Titre", "Chapitre", "Section", "Sous-section")

# Débris de pied de page : « - », « 101 », « - 101 - »… PyMuPDF découpe
# « - 101 - » en plusieurs lignes distinctes à la même ordonnée, d'où le
# \d{0,3} : chaque morceau doit pouvoir être reconnu seul.
DEBRIS_PIED = re.compile(r"^[\s\-–—]*\d{0,3}[\s\-–—]*$")
# Même motif, mais en exigeant un nombre : sert d'ASSERTION sur le flux
# législatif, où un tel fragment ne doit jamais subsister.
PIED_RESIDUEL = re.compile(r"^[\s\-–—]*\d{1,3}[\s\-–—]*$")
# « - 101 - » égaré au milieu d'une phrase : le nombre doit être isolé par des
# espaces, sinon on attraperait les numéros de dahir (« n° 1-03-194 »).
PIED_INTERCALE = re.compile(r"(?:^|\s)-\s*\d{1,3}\s*-(?:\s|$)")

DEBUT_NOTE = re.compile(r"^(\d{1,3})\s*[-–—]?\s+(.*)$", re.S)

# Un appel de note retiré laisse un trou entre les deux spans de corps qui
# l'encadraient, et `coller` rend ce trou par une espace : « sécurité sociale37,
# d'accident » devient « sécurité sociale , d'accident ». L'espace est donc un
# artefact du retrait, pas un blanc du législateur.
#
# On ne la referme QUE devant le point et la virgule, et pas devant « ; : ! ? »
# qui prennent une espace fine légitime en typographie française — la refermer
# là réécrirait la source. Le contrôle 15 vérifie qu'il n'en subsiste aucune.
ESPACE_AVANT_PONCTUATION = re.compile(r"\s+([.,])")


# ───────────────────────────────────────────────────────────────────────────────
# Lecture du PDF
# ───────────────────────────────────────────────────────────────────────────────

@dataclass
class Ligne:
    """Une ligne du flux législatif, débarrassée de son paratexte."""

    page: int
    texte: str
    gras: bool
    x_gauche: float
    x_droite: float
    appels_de_note: list[int] = field(default_factory=list)


@dataclass
class Releve:
    """Ce que la lecture du PDF a produit, et ce qu'elle a mis de côté."""

    lignes: list[Ligne] = field(default_factory=list)
    notes: dict[int, str] = field(default_factory=dict)
    pieds_retires: int = 0
    corrections: int = 0
    tailles_vues: set[float] = field(default_factory=set)


def normaliser(texte: str) -> str:
    """Nettoie une chaîne sans en altérer le sens.

    Les espaces insécables et doublées viennent de la justification du PDF, pas
    du législateur : les réduire est sans risque. En revanche on ne touche NI
    aux apostrophes typographiques, NI à la casse, NI à la ponctuation — une
    citation doit pouvoir être collée telle quelle en face du PDF. Normaliser
    pour la recherche est le travail d'une autre couche, pas de celle-ci.
    """
    texte = unicodedata.normalize("NFC", texte)
    texte = texte.replace(" ", " ").replace("\t", " ")
    return re.sub(r" {2,}", " ", texte).strip()


def corriger(texte: str) -> tuple[str, list[int], int]:
    """Applique les corrections nommées de CORRECTIONS_NOMMEES.

    Retourne le texte corrigé, les numéros de note qu'une correction a permis
    de récupérer, et le nombre de substitutions effectuées — ce nombre est
    affiché à chaque exécution : une correction silencieuse sur un texte de loi
    n'en est pas une.
    """
    appels: list[int] = []
    total = 0
    for motif, remplacement, appel, _raison in CORRECTIONS_NOMMEES:
        texte, n = motif.subn(remplacement, texte)
        if n and appel is not None:
            appels.extend([appel] * n)
        total += n
    return texte, appels, total


def coller(spans: list[dict]) -> str:
    """Recolle des spans voisins en rétablissant les blancs perdus.

    Deux spans séparés sur le papier peuvent se toucher dans la chaîne : le
    blanc n'existe que comme un écart de coordonnées. On le rétablit quand
    l'écart dépasse un point et qu'aucun des deux côtés ne porte déjà d'espace.
    En dessous d'un point, les deux spans forment un seul mot (« l'em » +
    « ployeur ») et les souder est le bon geste.
    """
    morceaux: list[str] = []
    bord_precedent: float | None = None
    for span in spans:
        texte = span["text"]
        if (
            morceaux
            and bord_precedent is not None
            and span["bbox"][0] - bord_precedent > 1.0
            and not morceaux[-1].endswith(" ")
            and not texte.startswith(" ")
        ):
            morceaux.append(" ")
        morceaux.append(texte)
        bord_precedent = span["bbox"][2]
    return "".join(morceaux)


def lignes_visuelles(page) -> list[list[dict]]:
    """Rend les lignes de la page telles que l'œil les voit.

    PyMuPDF coupe en plusieurs « lines » distinctes ce qui, sur le papier, est
    une seule ligne : quand la justification étire les blancs, chaque mot
    devient sa propre entrée. Le pire cas du document est page 22, dans
    l'article 26 : « et tenir un registre dans les formes prévues par
    l'autorité » y est découpé en dix fragments. L'article 154 en donne un
    autre, page 65, en neuf fragments.

    Les laisser tels quels fausse les deux mesures dont dépend la
    reconstruction des alinéas : un fragment d'un mot a un bord droit très
    court (il aurait l'air de terminer un paragraphe) et une indentation
    gauche arbitraire. On regroupe donc par ordonnée, à un point près.

    Effet de bord utile : le pied de page, que PyMuPDF rend en quatre
    fragments (« - », « 101 », « - », « »), redevient la chaîne « - 101 - »
    reconnaissable d'un coup.
    """
    par_ordonnee: dict[int, list[dict]] = {}
    for bloc in page.get_text("dict")["blocks"]:
        for ligne in bloc.get("lines", []):
            par_ordonnee.setdefault(round(ligne["bbox"][1]), []).extend(
                ligne["spans"]
            )
    resultat = []
    for ordonnee in sorted(par_ordonnee):
        spans = sorted(par_ordonnee[ordonnee], key=lambda s: s["bbox"][0])
        resultat.append(spans)
    return resultat


def lire_pdf(chemin: Path) -> Releve:
    document = pymupdf.open(chemin)
    releve = Releve()
    note_courante: int | None = None
    morceaux_note: list[str] = []

    def clore_note() -> None:
        nonlocal note_courante, morceaux_note
        if note_courante is not None:
            releve.notes[note_courante] = normaliser(" ".join(morceaux_note))
        note_courante, morceaux_note = None, []

    for index_page, page in enumerate(document, start=1):
        for spans in lignes_visuelles(page):
            for span in spans:
                if span["text"].strip():
                    releve.tailles_vues.add(round(span["size"], 1))

            flux = [s for s in spans if s["size"] >= SEUIL_FLUX]
            flux_visible = [s for s in flux if s["text"].strip()]

            if flux_visible:
                # Ligne de loi. Les spans sous le seuil qui la côtoient sont
                # des appels de note soudés au mot précédent : on les
                # recense pour pouvoir citer la note, puis on les retire du
                # texte. C'est le « salariés37 » du cahier des charges, et
                # aussi le « Article 25635 » que personne n'avait vu — là,
                # le 35 collait au NUMÉRO de l'article, ce qui décalait
                # silencieusement toute la numérotation.
                appels = [
                    int(m)
                    for s in spans
                    if s["size"] < SEUIL_FLUX
                    for m in re.findall(r"\d{1,3}", s["text"])
                ]
                texte = coller(flux)
                if not texte.strip():
                    continue
                texte, appels_fondus, corrigees = corriger(normaliser(texte))
                # Le trou laissé par les spans de paratexte qu'on vient
                # d'écarter se referme ici, et seulement ici : conditionner la
                # réparation à un retrait effectif garde le contrôle 15 mordant
                # pour toute autre cause d'espace avant la ponctuation.
                if len(flux_visible) < len([s for s in spans if s["text"].strip()]):
                    texte = ESPACE_AVANT_PONCTUATION.sub(r"\1", texte)
                appels.extend(appels_fondus)
                releve.corrections += corrigees
                releve.lignes.append(
                    Ligne(
                        page=index_page,
                        texte=texte,
                        gras=any("Bold" in s["font"] for s in flux_visible),
                        x_gauche=flux_visible[0]["bbox"][0],
                        x_droite=max(s["bbox"][2] for s in spans if s["text"].strip()),
                        appels_de_note=appels,
                    )
                )
                continue

            # Paratexte : pied de page ou note de bas de page.
            brut = normaliser(coller(spans))
            if not brut:
                continue
            if DEBRIS_PIED.match(brut):
                releve.pieds_retires += 1
                continue

            # Les notes sont numérotées 1..102 dans l'ordre du document. On
            # n'ouvre une note que si le nombre en tête est celui attendu :
            # sinon une ligne de continuation commençant par « 64 du… »
            # créerait une fausse note et en tronquerait une vraie.
            debut = DEBUT_NOTE.match(brut)
            attendu = (note_courante or 0) + 1
            if debut and int(debut.group(1)) == attendu:
                clore_note()
                note_courante = attendu
                morceaux_note = [debut.group(2)]
            elif note_courante is not None:
                morceaux_note.append(brut)

    clore_note()
    document.close()
    return releve


# ───────────────────────────────────────────────────────────────────────────────
# Reconstruction de la hiérarchie et des articles
# ───────────────────────────────────────────────────────────────────────────────

@dataclass
class Intitule:
    niveau: str
    reference: str
    intitule: str
    # Trois titres et sections portent un appel de note collé à leur libellé
    # (« …des salariés37 »), et un quatrième l'a sur sa seconde ligne. Écartés
    # par la taille comme tous les appels, ils n'étaient recensés nulle part :
    # les notes 37, 54, 60 et 88 — un arrêté viziriel, deux décrets, un renvoi
    # au code de procédure civile — devenaient incitables. Ils voyagent donc
    # avec l'intitulé, et le contrôle 16 vérifie qu'aucune note ne reste
    # orpheline.
    appels_de_note: list[int] = field(default_factory=list)

    def en_dict(self) -> dict[str, object]:
        return {
            "reference": self.reference,
            "intitule": self.intitule,
            "appels_de_note": sorted(set(self.appels_de_note)),
        }


# Chiffres romains où un « l » minuscule tient la place d'un « I » : le PDF
# écrit « Chapitre Il » et « Section Ill ». Le motif n'accepte qu'un groupe fait
# uniquement de I, V, X et l, contenant au moins un l ET au moins une majuscule
# — « Livre » et « préliminaire » n'y entrent pas.
ROMAIN_CONFONDU = re.compile(r"\b(?=[IVXl]*l)(?=[IVXl]*[IVX])[IVXl]{2,}\b")


def decouper_intitule(texte: str) -> tuple[str, str, bool]:
    """Sépare « Chapitre III : Du contrôle » en référence et intitulé.

    Retourne aussi un drapeau quand il a fallu corriger « Il » en « II » : le
    PDF écrit « Chapitre Il » (I majuscule suivi d'un l minuscule) à plusieurs
    endroits. Le nombre de corrections est rapporté, pas tu — on ne retouche
    pas un texte de loi en silence.
    """
    if ":" in texte:
        reference, intitule = texte.split(":", 1)
    else:
        reference, intitule = texte, ""
    reference = reference.strip().rstrip(":").strip()
    corrige = bool(ROMAIN_CONFONDU.search(reference))
    if corrige:
        reference = ROMAIN_CONFONDU.sub(
            lambda m: m.group(0).replace("l", "I"), reference
        )
    return reference, intitule.strip(), corrige


@dataclass
class Article:
    numero: str
    rang: int
    paragraphes: list[str] = field(default_factory=list)
    appels_de_note: list[int] = field(default_factory=list)
    page_debut: int = 0
    position: dict[str, "Intitule | None"] = field(default_factory=dict)


# Un intitulé d'article occupe une ligne à lui seul et ne contient rien d'autre.
# On ne peut PAS exiger qu'il soit en gras : les articles 156 et 458 sont
# composés comme du corps de texte (Book Antiqua 14, aligné sur l'indentation
# d'alinéa) au lieu du 15 pt gras centré des 587 autres. Un renvoi dans le
# corps s'écrit « à l'article 43 ci-dessus », en minuscule et au fil de la
# phrase : une ligne réduite à « Article 43 » ne peut être qu'un intitulé.
INTITULE_ARTICLE = re.compile(r"^Article\s+(premier|\d{1,3})\.?$", re.I)

NIVEAUX = ("livre", "titre", "chapitre", "section", "sous_section")
NIVEAU_PAR_MOT = {
    "Livre": "livre",
    "Titre": "titre",
    "Chapitre": "chapitre",
    "Section": "section",
    "Sous-section": "sous_section",
}


@dataclass
class Structure:
    articles: list[Article] = field(default_factory=list)
    intitules: list[Intitule] = field(default_factory=list)
    compteurs: dict[str, int] = field(default_factory=dict)
    corrections_romaines: int = 0


def ouvre_un_alinea(
    ligne: Ligne,
    precedente: Ligne | None,
    deja_commence: bool,
) -> bool:
    """Décide si cette ligne commence un nouvel alinéa ou prolonge le précédent.

    Trois signaux, du plus fiable au plus fin, détaillés plus haut à côté de
    MARGE_DROITE :
      — la ligne précédente n'atteignait pas le fer du bloc justifié ;
      — on passe du fer à gauche à une indentation (nouvel alinéa, ou item) ;
      — on se dé-indente sans revenir au fer à gauche (fin d'une énumération
        imbriquée, comme le « 3) Autres absences : » de l'article 274).

    Un quatrième signal, typographique celui-là, rattrape le seul cas où les
    trois précédents se taisent : voir plus bas, à propos de l'article 586.
    """
    if not deja_commence or precedente is None:
        return True
    # Passage du maigre au gras : un intertitre s'ouvre. Sans ce signal,
    # l'intertitre « Congé annuel payé : » de l'article 586 restait collé à
    # l'alinéa précédent — « …relatif aux cautionnements ; » s'arrête à 525,7
    # points, donc DANS la tolérance du bloc justifié, et son item ne tient
    # qu'une ligne : les quinze autres intertitres du même article suivent un
    # item qui finit court, et s'en détachaient par le bord droit.
    #
    # La règle est volontairement à sens unique. L'inverse (gras -> maigre) est
    # faux : `gras` signifie « cette ligne contient au moins un span gras », et
    # page 159 une ligne à fragment gras est prolongée par « échéant. » en
    # maigre, qu'il faut recoller.
    if ligne.gras and not precedente.gras:
        return True
    # Une ligne qui finit sur un trait d'union est forcément coupée en plein
    # mot (« dommages- / intérêts », « ci- / dessus ») : aucun alinéa de loi ne
    # se termine ainsi. Ce cas passe AVANT la mesure du bord droit, parce que
    # le trait d'union est un glyphe étroit qui laisse la ligne s'arrêter vers
    # 525 points au lieu de 528 — elle aurait donc l'air de clore un alinéa.
    if precedente.texte.endswith("-"):
        return False
    if precedente.x_droite < MARGE_DROITE:
        return True
    indentee = ligne.x_gauche > FER_A_GAUCHE
    if indentee and precedente.x_gauche <= FER_A_GAUCHE:
        return True
    if indentee and ligne.x_gauche < precedente.x_gauche - 5:
        return True
    return False


def construire(releve: Releve) -> Structure:
    courant: dict[str, Intitule | None] = {n: None for n in NIVEAUX}
    articles: list[Article] = []
    tous_intitules: list[Intitule] = []
    compteurs = {n: 0 for n in NIVEAUX}
    corrections_romaines = 0
    dernier_intitule: Intitule | None = None
    article: Article | None = None
    ligne_precedente: Ligne | None = None
    demarre = False

    for ligne in releve.lignes:
        mots = ligne.texte.split(":")[0].split()
        mot = mots[0] if mots else ""

        # Les dix premières pages (dahir de promulgation, préface, préambule)
        # ne contiennent aucun article. On n'entre dans le corpus qu'au premier
        # « Livre », sinon les titres en capitales de la préface seraient pris
        # pour des intitulés de hiérarchie.
        if not demarre:
            if mot == "Livre" and ligne.gras:
                demarre = True
            else:
                continue

        est_hierarchie = ligne.gras and mot in MOTS_HIERARCHIE
        correspondance = INTITULE_ARTICLE.match(ligne.texte)

        if correspondance and not est_hierarchie:
            numero = correspondance.group(1).rstrip(".")
            rang = 1 if numero.lower().startswith("premier") else int(numero)
            article = Article(
                numero=numero,
                rang=rang,
                appels_de_note=list(ligne.appels_de_note),
                page_debut=ligne.page,
                position={n: courant[n] for n in NIVEAUX},
            )
            articles.append(article)
            dernier_intitule = None
            ligne_precedente = ligne
            continue

        if est_hierarchie:
            niveau = NIVEAU_PAR_MOT[mot]
            reference, intitule, corrige = decouper_intitule(ligne.texte)
            corrections_romaines += corrige
            entree = Intitule(niveau, reference, intitule,
                              list(ligne.appels_de_note))
            courant[niveau] = entree
            tous_intitules.append(entree)
            # Un nouveau livre remet à zéro les niveaux inférieurs : sans cela,
            # un article du livre VII hériterait du dernier chapitre du livre VI
            # et sa citation désignerait un thème qui n'est pas le sien.
            for inferieur in NIVEAUX[NIVEAUX.index(niveau) + 1:]:
                courant[inferieur] = None
            compteurs[niveau] += 1
            dernier_intitule = entree
            article = None
            ligne_precedente = ligne
            continue

        # Ligne grasse sans mot-clé : suite d'un intitulé coupé en deux par la
        # mise en page (« Livre II: Des conditions de travail et de la » puis
        # « protection des salariés »). On ne l'accepte que juste après un
        # intitulé : sinon on avalerait les intertitres gras qui appartiennent
        # au CORPS de l'article 586 (« Cautionnements : ») et les items gras de
        # l'article 274 (« 1) Mariage : »), qui sont du texte de loi.
        if ligne.gras and dernier_intitule is not None and article is None:
            dernier_intitule.intitule = normaliser(
                (dernier_intitule.intitule + " " + ligne.texte).strip()
            )
            # La note 88 est appelée sur CETTE seconde ligne (« …de l'inspection
            # du travail88 ») : sans cette reprise, elle n'était citable nulle
            # part.
            dernier_intitule.appels_de_note.extend(ligne.appels_de_note)
            ligne_precedente = ligne
            continue

        dernier_intitule = None
        if article is None:
            ligne_precedente = ligne
            continue

        if ouvre_un_alinea(ligne, ligne_precedente, bool(article.paragraphes)):
            article.paragraphes.append(ligne.texte)
        else:
            precedent = article.paragraphes[-1]
            # Les 22 lignes du document qui finissent par « - » le font sur un
            # trait d'union réel (« dommages-intérêts », « ci-dessus »,
            # « sous-traitant ») : recoller avec une espace casserait le mot.
            liant = "" if precedent.endswith("-") else " "
            article.paragraphes[-1] = normaliser(precedent + liant + ligne.texte)
        article.appels_de_note.extend(ligne.appels_de_note)
        ligne_precedente = ligne

    return Structure(articles, tous_intitules, compteurs, corrections_romaines)


def motif_abrogation(article: Article, notes: dict[int, str]) -> str | None:
    """Retourne la note qui justifie qu'un article soit vide, s'il en existe une."""
    for numero in article.appels_de_note:
        texte = notes.get(numero, "")
        if re.match(r"^\s*Abrog", texte, re.I):
            return texte
    return None


# ───────────────────────────────────────────────────────────────────────────────
# Contrôles. Ils ne décrivent pas le résultat, ils le refusent.
# ───────────────────────────────────────────────────────────────────────────────

def controler(
    structure: Structure,
    releve: Releve,
    notes: dict[int, str],
) -> dict[str, object]:
    articles = structure.articles
    compteurs = structure.compteurs
    echecs: list[str] = []
    rapport: dict[str, object] = {}

    def exiger(condition: bool, message: str) -> None:
        if not condition:
            echecs.append(message)

    # 1. Typographie du PDF. Si elle change, le seuil de 13 pt ne veut plus
    # rien dire et tout le reste de ce fichier est à revérifier.
    inconnues = releve.tailles_vues - TAILLES_CONNUES
    exiger(not inconnues,
           f"tailles de police inconnues dans le PDF : {sorted(inconnues)}")

    # 2. Le compte officiel. 589 est publié par le ministère : c'est un test,
    # pas une observation.
    exiger(
        len(articles) == NOMBRE_ARTICLES_OFFICIEL,
        f"{len(articles)} articles extraits, {NOMBRE_ARTICLES_OFFICIEL} attendus",
    )
    if not articles:
        rapport["echecs"] = echecs
        return rapport

    # 3. Numérotation : ordre, doublons, trous. Les trous peuvent être
    # légitimes (article abrogé), donc ils sont RAPPORTÉS et non interdits.
    rangs = [a.rang for a in articles]
    exiger(rangs == sorted(rangs), "les articles ne sont pas dans l'ordre du PDF")
    doublons = sorted({r for r in rangs if rangs.count(r) > 1})
    exiger(not doublons, f"numéros en double : {doublons}")
    exiger(articles[0].numero.lower().startswith("premier"),
           f"le premier article est « {articles[0].numero} », pas « premier »")
    trous = [n for n in range(1, max(rangs) + 1) if n not in set(rangs)]
    rapport["trous_de_numerotation"] = trous
    exiger(
        max(rangs) == NOMBRE_ARTICLES_OFFICIEL,
        f"dernier numéro {max(rangs)} au lieu de {NOMBRE_ARTICLES_OFFICIEL} — "
        "un appel de note est probablement resté collé à un numéro d'article",
    )

    # 4. Rattachement hiérarchique. Le cahier des charges demandait « chaque
    # article appartient à un livre ET à un titre ». La mesure dit que c'est
    # impossible : les livres IV à VII n'ont PAS de niveau « titre », ils
    # passent du livre au chapitre, et le livre VII n'a même pas de chapitre.
    # On exige donc ce qui est vrai — un livre pour tous — et on ÉPINGLE le
    # nombre d'articles dépourvus de titre : si le parseur régresse demain, ce
    # nombre bougera et le contrôle échouera.
    sans_livre = [a.numero for a in articles if a.position["livre"] is None]
    exiger(not sans_livre, f"articles sans livre : {sans_livre[:10]}")
    sans_titre = [a.numero for a in articles if a.position["titre"] is None]
    sans_rien = [a.numero for a in articles
                 if a.position["titre"] is None and a.position["chapitre"] is None]
    rapport["articles_sans_titre"] = len(sans_titre)
    rapport["articles_sans_titre_ni_chapitre"] = sans_rien
    exiger(
        len(sans_titre) == 115,
        f"{len(sans_titre)} articles sans titre au lieu des 115 mesurés "
        "(livres IV, V, VI et VII)",
    )
    exiger(
        sans_rien == ["586", "587", "588", "589"],
        f"articles sans titre ni chapitre : {sans_rien} au lieu du seul "
        "livre VII (586 à 589)",
    )
    livres_sans_titre = sorted({
        a.position["livre"].reference for a in articles
        if a.position["titre"] is None
    })
    rapport["livres_sans_niveau_titre"] = livres_sans_titre

    # 5. Textes vides ou suspects. Un article vide n'est toléré que s'il est
    # abrogé, et l'abrogation doit être PROUVÉE par une note de bas de page.
    vides, courts = [], []
    for a in articles:
        texte = "\n".join(a.paragraphes)
        if not texte.strip():
            if not motif_abrogation(a, notes):
                vides.append(a.numero)
        elif len(texte) < 40:
            courts.append([a.numero, len(texte), texte])
    exiger(not vides, f"articles vides sans note d'abrogation : {vides}")
    rapport["articles_courts"] = courts
    exiger(not courts, f"articles de moins de 40 caractères : {courts}")
    rapport["articles_abroges"] = [
        a.numero for a in articles
        if not "\n".join(a.paragraphes).strip() and motif_abrogation(a, notes)
    ]

    # 6. Pieds de page : ni dans le flux, ni au milieu d'une phrase.
    exiger(releve.pieds_retires > 0, "aucun pied de page retiré : filtre inopérant")
    rapport["pieds_retires"] = releve.pieds_retires
    for a in articles:
        texte = "\n".join(a.paragraphes)
        for paragraphe in a.paragraphes:
            if PIED_RESIDUEL.match(paragraphe):
                echecs.append(f"article {a.numero} : alinéa réduit à un pied de page")
        if PIED_INTERCALE.search(texte):
            echecs.append(f"article {a.numero} : « - N - » intercalé dans le texte")

    # 7. Appels de note collés aux intitulés. L'appel est un nombre en fin
    # d'intitulé — « Section 1 » est légitime, « …du travail88 » non. On
    # contrôle donc la partie APRÈS les deux-points.
    for entree in structure.intitules:
        if re.search(r"\d\s*$", entree.intitule):
            echecs.append(
                f"{entree.niveau} « {entree.reference} » : appel de note collé "
                f"à « {entree.intitule} »")
        if PIED_INTERCALE.search(entree.intitule):
            echecs.append(
                f"{entree.niveau} « {entree.reference} » : pied de page dans "
                "l'intitulé")
        if not entree.reference:
            echecs.append(f"{entree.niveau} sans référence")
        # Plus aucun « Chapitre Il » ni « Section Ill » ne doit subsister :
        # deux références différentes pour le même chapitre casseraient le
        # filtrage par thème et la citation.
        if ROMAIN_CONFONDU.search(entree.reference):
            echecs.append(
                f"{entree.niveau} « {entree.reference} » : chiffre romain "
                "contenant un « l » minuscule")
    rapport["intitules"] = len(structure.intitules)

    # 8. Hiérarchie attendue. Ces quatre nombres ont été mesurés une première
    # fois par un comptage naïf des lignes du texte brut, avant que ce script
    # n'existe ; les retrouver ici par un chemin complètement différent (les
    # polices) est une vérification croisée, pas une tautologie.
    attendu = {"livre": 8, "titre": 16, "chapitre": 64, "section": 42}
    for niveau, n in attendu.items():
        exiger(compteurs[niveau] == n,
               f"{compteurs[niveau]} {niveau}(s) au lieu de {n}")
    rapport["compteurs_hierarchie"] = dict(compteurs)

    # 9. Notes de bas de page : 102 notes sont numérotées dans le PDF, les 102
    # textes doivent avoir été reconstitués — sinon une abrogation manquerait.
    exiger(len(notes) == NOMBRE_NOTES_ATTENDU,
           f"{len(notes)} notes reconstituées au lieu de {NOMBRE_NOTES_ATTENDU}")
    exiger(sorted(notes) == list(range(1, NOMBRE_NOTES_ATTENDU + 1)),
           "la numérotation des notes n'est pas continue")
    rapport["notes"] = len(notes)
    appels_inconnus = sorted({
        n for a in articles for n in a.appels_de_note if n not in notes
    })
    exiger(not appels_inconnus,
           f"appels de note sans texte correspondant : {appels_inconnus}")

    # 10. Propreté du texte : ni espace doublée, ni alinéa vide.
    for a in articles:
        for paragraphe in a.paragraphes:
            if "  " in paragraphe:
                echecs.append(f"article {a.numero} : espace doublée résiduelle")
            if not paragraphe.strip():
                echecs.append(f"article {a.numero} : alinéa vide")

    # 11. Volume. Si l'extraction perdait un livre entier, les contrôles
    # ci-dessus pourraient tous passer. Ce garde-fou grossier compare le volume
    # conservé aux 348 665 caractères du texte brut du PDF, notes et pieds de
    # page compris — on doit en retrouver la très grande majorité.
    volume = sum(len("\n".join(a.paragraphes)) for a in articles)
    rapport["caracteres_articles"] = volume
    exiger(volume > 250_000,
           f"seulement {volume} caractères d'articles : extraction partielle ?")

    # 12. Aucun chiffre collé à une lettre. C'est la signature d'un appel de
    # note resté fondu dans le corps (« professionnels102 ») ou d'une espace
    # manquante (« l'article279 ») : deux défauts que la taille de police ne
    # peut pas voir. Les trois cas connus sont corrigés nommément en haut de ce
    # fichier ; ce contrôle garantit qu'il n'en reste aucun autre.
    for a in articles:
        for trouvaille in re.finditer(r"[A-Za-zÀ-ÿ]\d+", "\n".join(a.paragraphes)):
            echecs.append(
                f"article {a.numero} : chiffre collé à une lettre "
                f"(« {trouvaille.group(0)} »), appel de note ou espace manquante")

    # 13. Mots coupés par une espace parasite. Le PDF en contient deux, et deux
    # seulement : « le non- respect » aux articles 268 et 296, où l'espace est
    # DANS le span du PDF — c'est une faute de la source, pas de l'extraction,
    # et on ne réécrit pas un texte de loi sur une présomption. Le nombre est
    # épinglé : si le recollage des spans en fabriquait d'autres, il bougerait.
    coupes = [
        a.numero for a in articles
        if re.search(r"\w- \w", "\n".join(a.paragraphes))
    ]
    rapport["mots_coupes_par_une_espace"] = coupes
    exiger(
        coupes == ["268", "296"],
        f"mots coupés par une espace : {coupes} au lieu des deux défauts connus "
        "de la source (articles 268 et 296)",
    )

    # 14. Alinéas. Aucun ne doit finir sans ponctuation : un alinéa de loi se
    # termine par un point, un point-virgule ou un deux-points. Une fin nue est
    # la signature d'un alinéa coupé au mauvais endroit.
    sans_ponctuation = [
        (a.numero, paragraphe[-60:])
        for a in articles
        for paragraphe in a.paragraphes
        if not re.search(r"[.;:,!?»)]$", paragraphe)
    ]
    exiger(not sans_ponctuation,
           f"alinéas finissant sans ponctuation : {sans_ponctuation[:5]}")
    rapport["alineas"] = sum(len(a.paragraphes) for a in articles)
    # Le découpage en alinéas repose sur deux heuristiques géométriques
    # (MARGE_DROITE, FER_A_GAUCHE) qu'aucune propriété du texte ne permet de
    # valider. Le contrôle précédent attrape le découpage trop généreux ; celui
    # qui recollerait deux alinéas ne laisse, lui, aucune trace détectable. On
    # épingle donc le total obtenu une fois les 589 articles relus ou
    # échantillonnés : il devient une valeur de référence, et toute dérive du
    # découpage fait échouer l'extraction au lieu de passer inaperçue.
    exiger(
        rapport["alineas"] == 1553,
        f"{rapport['alineas']} alinéas au lieu des 1553 de référence : "
        "le découpage a changé, il faut le relire avant de l'accepter",
    )

    # 15. Aucune espace avant un point ou une virgule. C'est la trace du trou
    # laissé par un appel de note retiré (« sécurité sociale , d'accident ») :
    # 64 alinéas de 58 articles en portaient une. La réparation est faite à la
    # lecture, sur les seules lignes dont un span de paratexte a été écarté ;
    # ce contrôle couvre tout le reste, y compris le recollage d'alinéas et les
    # intitulés, où aucune réparation n'a lieu.
    for a in articles:
        for trouvaille in re.finditer(
            r".{0,20}\s[.,]", "\n".join(a.paragraphes)
        ):
            echecs.append(
                f"article {a.numero} : espace avant la ponctuation "
                f"(« {trouvaille.group(0)} »)")
    for entree in structure.intitules:
        if re.search(r"\s[.,]", entree.intitule):
            echecs.append(
                f"{entree.niveau} « {entree.reference} » : espace avant la "
                f"ponctuation dans « {entree.intitule} »")

    # 16. Aucune note orpheline. Une note que rien n'appelle n'est pas citable,
    # donc invisible à l'usager : c'était le cas des notes 37, 54, 60 (collées à
    # un titre ou une section) et 88 (sur la seconde ligne d'un intitulé).
    # La note 1 reste hors du compte, et c'est mesuré, pas excusé : son appel
    # est page 2, dans le dahir de promulgation, avant le premier « Livre » où
    # commence le corpus — elle renvoie au Bulletin Officiel de la loi entière,
    # pas à un article.
    cites = {n for a in articles for n in a.appels_de_note}
    cites |= {n for e in structure.intitules for n in e.appels_de_note}
    orphelines = sorted(set(notes) - cites)
    rapport["notes_non_citees"] = orphelines
    exiger(
        orphelines == [1],
        f"notes qu'aucun article ni intitulé n'appelle : {orphelines} au lieu "
        "de la seule note 1 (page 2, hors corpus)",
    )

    rapport["echecs"] = echecs
    return rapport


# ───────────────────────────────────────────────────────────────────────────────
# Contre-vérification par un chemin indépendant
# ───────────────────────────────────────────────────────────────────────────────
#
# Les seize contrôles valident la cohérence du résultat, pas le choix de départ.
# Si découper par la TAILLE DE POLICE était une mauvaise idée, ils la
# valideraient de bonne foi : tous mesurent le même texte, produit par la même
# logique.
#
# On renettoie donc le PDF une seconde fois par une règle purement TEXTUELLE,
# qui ne regarde aucune police, et on compare les 589 articles tranche par
# tranche. La règle : sur chaque page, le bloc de notes est précédé d'un filet
# que `get_text()` rend comme une ligne de blancs (vingt au moins) ; tout ce
# qui suit sur la page est du paratexte. Les débris de pied de page partent par
# le motif DEBRIS_PIED. Rien d'autre n'est retiré — en particulier les appels de
# note restent collés à leur mot, puisque seule la police les en distingue.
#
# Ce que la comparaison peut prouver : qu'aucun mot n'a été ajouté, perdu ou
# déplacé. Ce qu'elle ne peut pas prouver : que le PDF d'Adala soit conforme au
# Bulletin Officiel. Les deux chemins lisent le même fichier.
FILET_DE_NOTE = re.compile(r"^\s{20,}$")
MOT_DE_HIERARCHIE = re.compile(r"\b(?:%s)\s" % "|".join(MOTS_HIERARCHIE))


def nettoyage_textuel(chemin: Path) -> list[str]:
    """Renettoie le PDF sans jamais consulter la typographie."""
    document = pymupdf.open(chemin)
    gardees: list[str] = []
    for page in document:
        brutes = page.get_text().split("\n")
        filet = next(
            (i for i, l in enumerate(brutes) if FILET_DE_NOTE.match(l)), None
        )
        for brute in brutes[:filet] if filet is not None else brutes:
            ligne = brute.strip()
            if ligne and not DEBRIS_PIED.match(ligne):
                gardees.append(ligne)
    document.close()
    return gardees


def _aplatir(texte: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", texte)
                  .replace(" ", " ")).strip()


def _sans_blancs(texte: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", texte)
                  .replace(" ", " "))


def contre_verifier(structure: Structure) -> dict[str, object]:
    """Compare chaque article à sa tranche du nettoyage textuel indépendant.

    Rend trois ensembles qui partitionnent les articles non vides : ceux qui
    sont un extrait littéral contigu du nettoyage indépendant (aux blancs
    près), ceux dont tout l'écart s'explique par les appels de note retirés, et
    ceux où s'ajoute une ligne d'intitulé que la règle textuelle, faute de
    police, ne sait pas écarter. Tout article qui n'entre dans aucune case est
    rendu dans `inexpliques` : c'est le seul nombre qui doive rester à zéro.
    """
    lignes = nettoyage_textuel(PDF)
    articles = structure.articles

    # Comptage à l'aveugle, avant tout alignement : combien de lignes sont
    # exactement « Article N » ? C'est un troisième chemin vers le nombre 589,
    # qui ne doit rien à la typographie. Il en trouve trois de moins, et ce
    # manque est lui-même une mesure : ce sont les articles dont le numéro porte
    # un appel de note collé, que seule la police sait séparer.
    aveugle = sum(1 for l in lignes if INTITULE_ARTICLE.match(l))

    # Découpage en tranches sur les seuls intitulés d'article. Le numéro attendu
    # est connu, donc on tolère les chiffres qui le suivent : « Article 25635 »
    # est l'article 256 avec son appel de note 35, et c'est précisément ce que
    # la règle textuelle ne sait pas distinguer.
    debuts: list[int] = []
    position = 0
    for a in articles:
        attendu = "premier" if a.rang == 1 and not a.numero.isdigit() else a.numero
        motif = re.compile(r"^Article\s+(%s)\d{0,3}\.?$" % re.escape(attendu), re.I)
        while position < len(lignes) and not motif.match(lignes[position]):
            position += 1
        if position >= len(lignes):
            return {"introuvable": a.numero}
        debuts.append(position)
        position += 1

    litteraux: list[str] = []
    appels_seuls: list[str] = []
    appels_et_intitule: list[str] = []
    inexpliques: list[tuple[str, str, str]] = []

    for index, a in enumerate(articles):
        texte = "\n".join(a.paragraphes)
        if not texte.strip():
            continue
        fin = debuts[index + 1] if index + 1 < len(debuts) else len(lignes)
        tranche = _aplatir(" ".join(lignes[debuts[index] + 1:fin]))
        if _sans_blancs(texte) in _sans_blancs(tranche):
            litteraux.append(a.numero)
            continue

        causes: set[str] = set()
        cote_pdf, cote_json = tranche.split(" "), _aplatir(texte).split(" ")
        comparateur = difflib.SequenceMatcher(
            None, cote_pdf, cote_json, autojunk=False
        )
        for operation, i1, i2, j1, j2 in comparateur.get_opcodes():
            if operation == "equal":
                continue
            pdf = " ".join(cote_pdf[i1:i2])
            json_ = " ".join(cote_json[j1:j2])
            if MOT_DE_HIERARCHIE.search(pdf):
                pdf = MOT_DE_HIERARCHIE.split(pdf)[0]
                causes.add("intitule")
            # On ne retire que les numéros de note que le JSON revendique pour
            # CET article : l'écart doit s'expliquer par ce qui est recensé, pas
            # par n'importe quel chiffre qui traîne.
            reste = pdf
            for numero in sorted(set(a.appels_de_note)):
                reste = re.sub(r"(?<=\S)%d(?!\d)" % numero, "", reste, count=1)
            if _sans_blancs(reste) != _sans_blancs(json_):
                inexpliques.append((a.numero, pdf[:80], json_[:80]))
            elif _sans_blancs(pdf) != _sans_blancs(reste):
                causes.add("appel")
        if "intitule" in causes:
            appels_et_intitule.append(a.numero)
        else:
            appels_seuls.append(a.numero)

    return {
        "intitules_a_l_aveugle": aveugle,
        "non_vides": sum(1 for a in articles if "\n".join(a.paragraphes).strip()),
        "litteraux": litteraux,
        "appels_seuls": appels_seuls,
        "appels_et_intitule": appels_et_intitule,
        "inexpliques": inexpliques,
        "lignes_textuelles": len(lignes),
    }


# ───────────────────────────────────────────────────────────────────────────────
# Sortie
# ───────────────────────────────────────────────────────────────────────────────

def citation(a: Article) -> str:
    """Référence affichable sous une réponse.

    C'est la raison d'être de la hiérarchie : « article 279 » seul ne dit pas
    de quoi il parle, et l'usager ne peut pas juger si la réponse est hors
    sujet. « article 279, livre II, titre III » le lui dit.
    """
    morceaux = [f"article {a.numero}"]
    for niveau in NIVEAUX:
        entree = a.position[niveau]
        if entree is None:
            continue
        morceaux.append(
            f"{entree.reference} — {entree.intitule}" if entree.intitule
            else entree.reference
        )
    return ", ".join(morceaux)


def en_json(
    structure: Structure,
    releve: Releve,
    rapport: dict[str, object],
) -> dict[str, object]:
    articles, notes = structure.articles, releve.notes
    sortie_articles = []
    for a in articles:
        texte = "\n".join(a.paragraphes)
        motif = motif_abrogation(a, notes) if not texte.strip() else None
        sortie_articles.append(
            {
                "numero": a.numero,
                "rang": a.rang,
                "reference": f"article {a.numero}",
                "texte": texte,
                "abroge": motif is not None,
                "motif_abrogation": motif,
                "page_pdf": a.page_debut,
                "appels_de_note": sorted(set(a.appels_de_note)),
                "position": {
                    niveau: (a.position[niveau].en_dict()
                             if a.position[niveau] else None)
                    for niveau in NIVEAUX
                },
                "citation": citation(a),
            }
        )
    return {
        "source": {
            "intitule": "Loi n° 65-99 formant Code du travail (Royaume du Maroc)",
            "fichier": PDF.name,
            "portail": "Adala, ministère de la Justice",
            "date_consolidation": DATE_CONSOLIDATION,
            "avertissement": (
                "Texte consolidé au 26 octobre 2011. Les modifications "
                "postérieures à cette date ne figurent pas dans ce corpus : "
                "aucune réponse construite sur ce fichier ne peut être "
                "présentée comme l'état du droit en vigueur."
            ),
        },
        "controles": {
            "articles": len(articles),
            "hierarchie": dict(structure.compteurs),
            "intitules": rapport["intitules"],
            "trous_de_numerotation": rapport["trous_de_numerotation"],
            "articles_abroges": rapport["articles_abroges"],
            "articles_sans_titre": rapport["articles_sans_titre"],
            "livres_sans_niveau_titre": rapport["livres_sans_niveau_titre"],
            "notes_de_bas_de_page": len(notes),
            "notes_non_citees": rapport["notes_non_citees"],
            "alineas": rapport["alineas"],
            "caracteres_articles": rapport["caracteres_articles"],
            "pieds_de_page_retires": rapport["pieds_retires"],
            "corrections_nommees_appliquees": releve.corrections,
            "romains_l_corriges_en_I": structure.corrections_romaines,
        },
        "notes_de_bas_de_page": {str(k): v for k, v in sorted(notes.items())},
        "articles": sortie_articles,
    }


def main() -> int:
    analyse = argparse.ArgumentParser(description="Extraction du Code du travail.")
    analyse.add_argument("--sans-ecrire", action="store_true",
                         help="contrôle sans produire le JSON")
    analyse.add_argument("--contre-verifier", action="store_true",
                         help="recompare les articles à un nettoyage "
                              "purement textuel du PDF")
    options = analyse.parse_args()

    if not PDF.exists():
        print(f"PDF introuvable : {PDF}", file=sys.stderr)
        return 1

    releve = lire_pdf(PDF)
    structure = construire(releve)
    rapport = controler(structure, releve, releve.notes)

    print(f"PDF                      {PDF.name}")
    print(f"lignes de loi            {len(releve.lignes)}")
    print(f"pieds de page retires    {releve.pieds_retires}")
    print(f"corrections nommees      {releve.corrections}")
    print(f"romains l -> I corriges {structure.corrections_romaines}")
    print(f"notes de bas de page     {len(releve.notes)}")
    print(f"articles                 {len(structure.articles)}")
    print(f"hierarchie               {structure.compteurs}")
    print(f"intitules                {rapport.get('intitules')}")
    print(f"alineas                  {rapport.get('alineas')}")
    print(f"caracteres d'articles    {rapport.get('caracteres_articles')}")
    print(f"trous de numerotation    {rapport.get('trous_de_numerotation') or 'aucun'}")
    print(f"articles abroges         {rapport.get('articles_abroges') or 'aucun'}")
    print(f"articles sans titre      {rapport.get('articles_sans_titre')} "
          f"({', '.join(rapport.get('livres_sans_niveau_titre') or [])})")

    echecs = rapport["echecs"]
    if echecs:
        print(f"\n{len(echecs)} CONTROLE(S) EN ECHEC :", file=sys.stderr)
        for echec in echecs:
            print(f"  - {echec}", file=sys.stderr)
        return 1
    print("\ntous les controles passent")

    if options.contre_verifier:
        contre = contre_verifier(structure)
        if "introuvable" in contre:
            print(f"\narticle {contre['introuvable']} introuvable dans le "
                  "nettoyage textuel", file=sys.stderr)
            return 1
        print("\ncontre-verification par nettoyage purement textuel")
        print(f"  lignes gardees               {contre['lignes_textuelles']}")
        print(f"  « Article N » a l'aveugle    {contre['intitules_a_l_aveugle']}")
        print(f"  articles non vides           {contre['non_vides']}")
        print(f"  extraits litteraux contigus  {len(contre['litteraux'])}")
        print(f"  ecart = appels de note       {len(contre['appels_seuls'])}")
        print(f"  ... + ligne d'intitule       "
              f"{len(contre['appels_et_intitule'])} "
              f"({', '.join(contre['appels_et_intitule'])})")
        print(f"  ecarts inexpliques           {len(contre['inexpliques'])}")
        for numero, cote_pdf, cote_json in contre["inexpliques"][:10]:
            print(f"    - article {numero} : PDF « {cote_pdf} » / "
                  f"JSON « {cote_json} »")
        if contre["inexpliques"]:
            return 1

    if not options.sans_ecrire:
        donnees = en_json(structure, releve, rapport)
        SORTIE.write_text(
            json.dumps(donnees, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"ecrit              {SORTIE} ({SORTIE.stat().st_size} octets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
