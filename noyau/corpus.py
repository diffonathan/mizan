# -*- coding: utf-8 -*-
"""Lecture du corpus et construction des passages à indexer.

Ce module est la seule porte d'entrée vers `corpus/code-travail.json` dans le
noyau. Il existe séparément des deux bras de récupération pour une raison
précise : le bras dense lit des vecteurs calculés une fois, et ces vecteurs ne
valent que pour un découpage de passages donné. Si deux endroits du code
construisaient les passages chacun à leur façon, l'index vectoriel vaudrait
pour l'un et serait silencieusement faux pour l'autre — un décalage d'un seul
passage suffit à attribuer le texte d'un article au vecteur de son voisin, et
rien ne le signalerait. Un seul constructeur, et une empreinte qui le scelle.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

# Le module se situe par rapport à son propre fichier : aucun chemin absolu,
# aucune dépendance au dossier courant de celui qui appelle. Le banc
# d'évaluation s'exécute depuis `evaluation/`, les tests depuis la racine, et
# un service web depuis ailleurs encore.
RACINE = Path(__file__).resolve().parent.parent
CHEMIN_CORPUS = RACINE / "corpus" / "code-travail.json"

# Les cinq niveaux de la hiérarchie du Code, dans l'ordre où le législateur les
# emboîte. L'ordre compte : il est repris tel quel dans le texte plongé.
NIVEAUX = ("livre", "titre", "chapitre", "section", "sous_section")


@dataclass(frozen=True)
class Passage:
    """Un texte plongé, et le numéro d'article dont il provient.

    Un article peut en principe donner plusieurs passages ; ici il en donne
    exactement un, parce que le découpage des articles longs a été mesuré sans
    gain et écarté (CONCEPTION.md §2). La structure reste en liste de passages
    plutôt qu'en liste d'articles pour que réintroduire un découpage ne demande
    pas de réécrire l'index — le bras dense réduit déjà par article.
    """

    numero: str
    texte: str


class Corpus:
    """Les articles du Code, leur ordre, et ce qui en dérive.

    L'instance est immuable en pratique : rien dans le noyau ne la modifie
    après construction. Elle est passée aux deux bras plutôt que relue par
    chacun, parce que la relire deux fois coûterait deux fois le chargement
    JSON et ouvrirait la porte à deux versions du corpus dans un même
    processus.
    """

    def __init__(self, donnees: dict) -> None:
        self.source = donnees["source"]
        self.articles: list[dict] = donnees["articles"]
        self.par_numero: dict[str, dict] = {a["numero"]: a for a in self.articles}

        # L'avertissement de consolidation est lu ici et nulle part ailleurs.
        # Il n'est pas recopié dans le code : une phrase recopiée se désynchronise
        # du corpus le jour où le corpus est réextrait sur une autre version du
        # texte, et un avertissement de date faux est pire qu'absent.
        avertissement = (self.source.get("avertissement") or "").strip()
        if not avertissement:
            raise ValueError(
                f"{CHEMIN_CORPUS} ne porte pas de « source.avertissement ». "
                "Le noyau refuse de servir un corpus dont la date de "
                "consolidation ne peut pas être affichée."
            )
        self.avertissement = avertissement
        self.date_consolidation = self.source.get("date_consolidation", "")

    # -- passages ----------------------------------------------------------

    def passages(self) -> list[Passage]:
        """Les textes à plonger, dans un ordre stable.

        Un article est plongé précédé des intitulés de sa hiérarchie. Ce n'est
        pas un ornement : le chapitre « Du congé annuel payé » porte des
        articles qui ne contiennent nulle part ces trois mots, et une question
        posée dans les mots du chapitre ne peut alors atteindre aucun d'eux.
        Les références (« Livre premier », « Chapitre IV ») sont écartées — un
        numéro de chapitre est identique pour des centaines d'articles et
        n'apporte que du bruit partagé.

        L'unique article sans texte (256, abrogé) est écarté : lui faire un
        vecteur serait fabriquer un voisin plausible pour n'importe quelle
        question à partir de rien.
        """
        sortie: list[Passage] = []
        for article in self.articles:
            if not article["texte"].strip():
                continue
            entete = self._entete(article)
            texte = f"{entete}\n{article['texte']}" if entete else article["texte"]
            sortie.append(Passage(numero=article["numero"], texte=texte))
        return sortie

    @staticmethod
    def _entete(article: dict) -> str:
        morceaux = [
            bloc["intitule"].strip()
            for niveau in NIVEAUX
            for bloc in (article["position"].get(niveau),)
            if bloc and bloc.get("intitule")
        ]
        return " — ".join(morceaux)

    def intitules(self, article: dict) -> str:
        """Les intitulés de hiérarchie d'un article, pour le bras lexical.

        Séparés par des espaces et non par un tiret cadratin : le bras lexical
        ne garde que des jetons alphanumériques, le séparateur n'y survit pas,
        et lui en donner un ferait croire qu'il compte.
        """
        return " ".join(
            bloc["intitule"]
            for niveau in NIVEAUX
            for bloc in (article["position"].get(niveau),)
            if bloc and bloc.get("intitule")
        )

    # -- scellement --------------------------------------------------------

    def empreinte(self) -> str:
        """Empreinte des passages, pour lier un index vectoriel à CE corpus.

        Elle ne couvre pas le fichier JSON entier mais exactement ce qui est
        plongé. Une correction de métadonnée (page PDF, note de bas de page)
        ne doit pas invalider quinze minutes de calcul ; une correction d'un
        texte d'article, si.
        """
        empreinte = hashlib.sha256()
        for passage in self.passages():
            empreinte.update(passage.numero.encode("utf-8"))
            empreinte.update(b"\x00")
            empreinte.update(passage.texte.encode("utf-8"))
            empreinte.update(b"\x00")
        return empreinte.hexdigest()


def charger(chemin: Path | None = None) -> Corpus:
    chemin = CHEMIN_CORPUS if chemin is None else Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(
            f"Corpus introuvable : {chemin}. Il est versionné avec le projet ; "
            "s'il manque, le dépôt est incomplet."
        )
    return Corpus(json.loads(chemin.read_text(encoding="utf-8")))
