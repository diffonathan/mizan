# -*- coding: utf-8 -*-
"""La composition : chercher, rédiger, VÉRIFIER. Le contrat partagé du projet.

    from moteur.repondre import repondre, Reponse

    reponse = repondre("combien de jours de congé après deux ans ?")

Cinq étapes, dans cet ordre, et l'ordre est la moitié de la garantie :

    1. examiner — la question est inspectée pour les tournures adressées à
       l'assistant ; cela SIGNALE et ne bloque jamais rien ;
    2. chercher — le noyau récupère cinq articles et dit s'il est sûr ;
    3. si le noyau n'est pas sûr, on s'abstient SANS appeler le modèle ;
    4. sinon le rédacteur écrit, en ne recevant que ces cinq articles ;
    5. la garde compare les citations du texte à l'ensemble récupéré, et
       rejette la réponse entière au premier numéro étranger.

POURQUOI L'EXAMEN EST LA PREMIÈRE ÉTAPE ET NON UN FILTRE
--------------------------------------------------------
`moteur.injection.examiner` ne rend pas un refus, il rend une observation. Une
question signalée est récupérée et rédigée comme les autres, pour deux raisons
mesurées : épurer la question de sa consigne injectée ne récupère pas un
meilleur article (quatre attendus sur cinq dans les deux cas), et les leurres
montrent qu'un salarié peut écrire « mon patron peut-il ignorer le règlement
intérieur » sans attaquer personne. Bloquer sur ce signal, c'est refuser de
répondre à quelqu'un qui a une question de droit.

Le signalement sert à deux choses : il part dans l'invite comme une
observation sur les données, et il ressort sur la `Reponse` pour que
l'interface puisse montrer ce que la défense a vu. Une défense qui signale
sans montrer est indiscutable, donc inaméliorable.

POURQUOI L'ABSTENTION COURT-CIRCUITE LE MODÈLE
----------------------------------------------
C'est une économie — on ne paie pas des jetons pour un texte qu'on jetterait —
mais c'est d'abord une garantie : on ne peut pas halluciner ce qu'on n'a pas
demandé. Tant que le modèle n'est pas appelé, il n'y a aucun texte à contrôler,
donc aucun risque qu'un texte plausible échappe au contrôle. Et sur les sept
questions du banc des fondations dont la réponse n'est pas dans le Code, c'est
ce chemin-là qui s'emprunte six fois.

L'AVERTISSEMENT DE CONSOLIDATION EST POSÉ ICI, DANS LA STRUCTURE
----------------------------------------------------------------
Le corpus est arrêté au 26 octobre 2011. Un assistant qui laisse croire qu'il
connaît le droit en vigueur aujourd'hui est dangereux. `Reponse` refuse donc
d'exister sans son avertissement : ce n'est pas une recommandation adressée à
celui qui écrira l'interface, c'est une impossibilité. Le texte de
l'avertissement n'est jamais recopié dans ce fichier — il vient du corpus, par
le `Resultat` du noyau, pour qu'une réextraction sur une autre version du Code
ne laisse pas derrière elle une date fausse dans du code.

CE QUE CE MODULE NE RATTRAPE PAS
--------------------------------
Une panne du rédacteur (clé absente, modèle retiré, quota, coupure) remonte
telle quelle, en `moteur.llm.ErreurModele`. Elle n'est pas transformée en
abstention, et c'est délibéré : le système AVAIT trouvé des articles, et
afficher « je ne trouve pas » parce que le fournisseur est en panne serait
mentir sur ce qui s'est passé, en plus de cacher une panne d'exploitation
derrière un comportement de produit. La couche qui expose le service doit la
traduire en indisponibilité — et chaque message de ces erreurs dit quoi faire.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from noyau import ArticleTrouve, Resultat
from noyau import charger as charger_noyau
from noyau import chercher as chercher_noyau

from . import garde as module_garde
from .injection import Signalement, examiner
from .llm import Demande, Redacteur, charger_redacteur

# Cinq articles : c'est le `k` sur lequel les fondations ont mesuré
# l'architecture, et le nombre que le registre de doute affiche quand il ne
# désigne pas de réponse.
ARTICLES_PAR_REPONSE = 5

# Les causes, au-delà du booléen `abstenu`. Un identifiant stable se compare
# dans un test et se compte dans un journal ; la phrase de `raison`, elle, se
# lit. Les deux sont nécessaires et ne se remplacent pas.
REPONSE_SERVIE = "reponse"
SILENCE_RECUPERATION = "silence_recuperation"


class Chercheur(Protocol):
    """Ce que la composition attend de la récupération : le contrat du noyau."""

    def __call__(self, question: str, k: int = ...) -> Resultat:
        ...


@dataclass(frozen=True)
class Reponse:
    """Le contrat partagé du projet. Trois agents s'y tiennent.

    `texte` vaut None dès que le système ne sert pas de réponse, que ce soit
    parce que la récupération doute ou parce que la garde a rejeté le texte
    rédigé. Dans les deux cas `articles` reste rempli : les candidats se
    montrent sans être présentés comme la réponse, et la personne voit sur quoi
    le système a travaillé plutôt qu'un écran vide.

    `cause` et `signalement` sont des additions au contrat partagé, pour les
    tests, les journaux et le bandeau d'interface ; les six champs du contrat
    sont au-dessus et ne bougent pas.
    """

    texte: str | None
    citations: tuple[str, ...]
    articles: tuple[ArticleTrouve, ...]
    abstenu: bool
    raison: str
    avertissement: str
    cause: str = REPONSE_SERVIE
    signalement: Signalement | None = None

    def __post_init__(self) -> None:
        # Le garde-fou de consolidation, structurel et non recommandé : il n'y
        # a pas d'autre chemin pour construire une Reponse, donc pas de chemin
        # de code qui puisse rendre l'avertissement vide. Le noyau garantit la
        # même chose sur le Resultat ; les deux contrôles ne sont pas
        # redondants, parce qu'une Reponse peut être construite ailleurs.
        if not (self.avertissement or "").strip():
            raise ValueError(
                "Une Reponse sans avertissement de consolidation ne peut pas "
                "être construite : le corpus est arrêté au 26 octobre 2011 et "
                "toute réponse doit le porter."
            )
        # Deux incohérences qu'un futur chemin de code pourrait introduire sans
        # que rien ne le signale : servir un texte en se déclarant abstenu
        # (l'interface afficherait le texte et le doute), ou se déclarer
        # répondant sans texte (l'interface afficherait un vide affirmatif).
        if self.abstenu and self.texte is not None:
            raise ValueError(
                "Une Reponse abstenue ne porte pas de texte : un texte rédigé "
                "qui s'affiche sous une réserve de doute est lu comme la "
                "réponse."
            )
        if not self.abstenu and not (self.texte or "").strip():
            raise ValueError(
                "Une Reponse non abstenue doit porter un texte : annoncer une "
                "réponse et n'en montrer aucune est pire que le silence."
            )
        if not self.abstenu and not self.citations:
            raise ValueError(
                "Une Reponse servie doit porter au moins une citation : c'est "
                "la garde qui les a vérifiées, et une réponse sans source "
                "n'est pas servie."
            )
        if self.abstenu and not (self.raison or "").strip():
            raise ValueError(
                "Une Reponse abstenue doit dire pourquoi : un silence sans "
                "motif ne se distingue pas d'une panne."
            )


class Mizan:
    """La composition, avec ses deux dépendances injectées.

    Le rédacteur ET le chercheur sont des paramètres, pour la même raison : les
    tests de ce fichier tournent sans clé de modèle de langue, sans index
    vectoriel et sans les 1,2 Go du modèle de plongement. Un projet dont les
    tests ne tournent que chez son auteur n'est pas un projet.
    """

    def __init__(
        self,
        redacteur: Redacteur,
        chercheur: Chercheur | Callable[..., Resultat] = chercher_noyau,
        k: int = ARTICLES_PAR_REPONSE,
    ) -> None:
        self.redacteur = redacteur
        self.chercheur = chercheur
        self.k = k

    def repondre(self, question: str) -> Reponse:
        """Le contrat partagé. Deux exceptions traversent, et c'est volontaire.

        `noyau.QuestionVide` sur une question vide : ce n'est pas un doute du
        système, c'est un appel mal formé, et le transformer en abstention
        ferait répondre « je ne trouve pas » à quelqu'un qui n'a rien demandé.
        `moteur.llm.ErreurModele` sur une panne de rédaction, pour la raison
        dite en tête de ce fichier.
        """
        # Avant la récupération, parce que c'est à la question qu'il s'adresse
        # et que son coût ne pèse pas dans la balance : cette couche passe sur
        # la question les expressions régulières de `MOTIFS` — quelques
        # dizaines, le barème les compte — là où la recherche dense encode
        # cette même question avec un modèle de plongement. C'est ce RAPPORT
        # qui justifie l'ordre des deux appels, et il se reproduit sur
        # n'importe quelle machine.
        #
        # Aucune durée n'est écrite ici, et c'est délibéré. Ce commentaire a
        # porté « 0,033 ms » en l'attribuant à `python -m moteur.injection`,
        # qui n'imprimait aucune durée ; puis « 0,045 ms », cette fois
        # imprimée, mais à trois décimales dans un commentaire que personne ne
        # relance. Une médiane de milliseconde recopiée à côté du code dérive
        # au premier rejeu et personne ne le voit. Celui qui veut la valeur la
        # demande à la commande qui la mesure :
        #
        #     python -m moteur.mesurer_injection --cout
        #
        # et `SECURITE.md` §3.4 fait foi pour ce que coûte cette couche.
        signalement = examiner(question)

        resultat = self.chercheur(question, k=self.k)

        if not resultat.sur:
            return self._silence(
                resultat, SILENCE_RECUPERATION, resultat.pourquoi, signalement
            )

        texte = self.redacteur.rediger(
            Demande(
                question=question,
                articles=tuple(resultat.articles),
                avertissement=resultat.avertissement,
                signalement=signalement,
            )
        )

        # Le contrôle porte sur l'ensemble que le noyau a récupéré, et sur rien
        # d'autre : c'est exactement l'ensemble qui a été envoyé au rédacteur.
        verdict = module_garde.verifier(texte, resultat.numeros)
        if not verdict.accepte:
            # La réponse rejetée n'est pas rapiécée et n'est pas affichée. Elle
            # n'est pas non plus retentée : une seconde rédaction sur la même
            # question et les mêmes articles n'est pas une correction, c'est un
            # tirage de plus, et elle rendrait la garantie dépendante de la
            # chance tout en doublant le coût.
            return self._silence(
                resultat, verdict.motif, verdict.raison, signalement
            )

        return Reponse(
            texte=texte.strip(),
            citations=verdict.citations,
            articles=resultat.articles,
            abstenu=False,
            raison="",
            avertissement=resultat.avertissement,
            cause=REPONSE_SERVIE,
            signalement=signalement,
        )

    @staticmethod
    def _silence(
        resultat: Resultat,
        cause: str,
        raison: str,
        signalement: Signalement | None = None,
    ) -> Reponse:
        """Un silence motivé, qui garde les candidats sous les yeux.

        Les articles récupérés restent dans la réponse, y compris après un
        rejet de la garde : ils ont été trouvés par un mécanisme qui ne rédige
        rien, et ce n'est pas eux que la garde met en doute.
        """
        return Reponse(
            texte=None,
            citations=(),
            articles=resultat.articles,
            abstenu=True,
            raison=raison,
            avertissement=resultat.avertissement,
            cause=cause,
            signalement=signalement,
        )


# ── Le point d'entrée du processus ──────────────────────────────────────────
#
# Même forme que `noyau.charger` / `noyau.chercher` : un chargement explicite
# au démarrage d'un service, et une fonction de confort qui charge au premier
# appel.

_mizan: Mizan | None = None


def charger(redacteur: Redacteur | None = None, k: int = ARTICLES_PAR_REPONSE) -> Mizan:
    """Construit la composition de production, et échoue tout de suite si elle manque.

    Les deux étages se chargent ici, et dans cet ordre : le rédacteur d'abord,
    parce que l'absence de clé se constate sans rien ouvrir, puis le noyau,
    dont l'ouverture de la session ONNX se compte en secondes. Échouer sur la
    clé après avoir payé le chargement du modèle, c'est perdre ces secondes à
    chaque démarrage mal configuré — et l'ordre coûte une ligne.

    Le chargement du noyau n'est chiffré ni ici ni ailleurs : aucune commande
    du dépôt ne le mesure, et les trois valeurs qui ont circulé pour lui
    venaient chacune d'une session différente. L'ordre de grandeur suffit à
    justifier l'ordre des deux appels, ce qui est tout ce que ce docstring a à
    faire. Le jour où une commande le mesurera, elle vivra dans `arbitrage/`.

    Rien de tout cela n'est fait à la première question d'un usager : un
    service qui découvre sa configuration en répondant n'est pas lent, il est
    en panne.
    """
    global _mizan
    redacteur = redacteur or charger_redacteur()
    _mizan = Mizan(redacteur, charger_noyau().chercher, k)
    return _mizan


def repondre(question: str) -> Reponse:
    """Le contrat partagé du projet. Charge au premier appel."""
    if _mizan is None:
        charger()
    assert _mizan is not None
    return _mizan.repondre(question)
