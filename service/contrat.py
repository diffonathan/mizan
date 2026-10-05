# -*- coding: utf-8 -*-
"""Le contrat des deux routes : ce qui sort, ce qui est refusé, et pourquoi.

Bibliothèque standard uniquement. Aucune route, aucun `fastapi` : tout ce
fichier se teste sur un interpréteur nu.

LES TROIS REGISTRES, ET POURQUOI LE CHAMP `registre` EXISTE
-----------------------------------------------------------
Une réponse de `/api/question` est toujours un 200, et elle décrit l'un de
trois écrans :

    registre = "reponse"  le texte est rédigé, vérifié, servi — `texte` non nul
    registre = "doute"    la récupération n'est pas sûre, le modèle n'a JAMAIS
                          été appelé ; les candidats sont là et ne sont pas la
                          réponse
    registre = "rejet"    le modèle a écrit, et la garde a refusé son texte ;
                          c'est un RÉSULTAT du produit, pas une panne

`moteur.repondre` rend déjà `cause`, qui est plus fin (six valeurs). Mais une
interface qui aiguille sur six identifiants en oubliera un, et l'oubli le plus
probable est celui des trois rejets de la garde — qui tomberaient alors dans la
branche « doute » et seraient affichés comme une abstention de la recherche.
`registre` est une PROJECTION de `cause`, calculée ici une fois, sur les
invariants que `moteur.repondre.Reponse.__post_init__` garantit déjà. Aucune
règle de produit n'est décidée ici.

CE QUI N'EST PAS DANS LE JSON, ET QUI NE DOIT PAS Y REVENIR
-----------------------------------------------------------
`ArticleTrouve.score`, c'est-à-dire le score de CHAQUE article. Il n'est pas
omis par distraction :

  * un cosinus dense et un score BM25 ne vivent pas sur la même échelle, donc
    deux articles de la même liste portent des nombres incomparables ;
  * même entre deux articles du bras dense, le score sépare mal les réponses
    justes des fausses : mesuré sur le banc des fondations, les justes
    (0,472–0,721) et les fausses (0,458–0,641) se recouvrent presque
    entièrement.

Exposer ces nombres, c'est fabriquer la barre de confiance que la première
interface en tirera. `tests/test_service_contrat.py` épingle l'absence.

UN SEUL SCORE SORT, ET C'EST PARCE QU'IL DÉCIDE
-----------------------------------------------
`proximite` est le score dense du PREMIER article, et il voyage avec
`seuil_proximite`. Il sort pour la raison exacte qui garde les autres dedans :
c'est lui qui a décidé de `sur`, et une décision affichée sans le nombre qui
l'a prise est indiscutable, donc inaméliorable. Ce n'est pas une confiance par
article — c'est la distance de la QUESTION au Code, mesurée sur l'article qui
lui ressemble le plus.

Qu'il sépare mal les justes des fausses ne le disqualifie pas : ce ne sont pas
les mêmes populations. Sur « cette question parle-t-elle du Code du travail ? »,
son aire vaut 0,978 en réglage et 0,937 en vérification
(`arbitrage/abstention.py`). C'est pour avoir confondu ces deux questions que ce
fichier a longtemps annoncé la MARGE comme « le signal qui sépare ».

`marge` reste exposée, mais `seuil_marge` a disparu : la marge ne décide plus
rien et un seuil sans comparaison est l'affichage d'une décision qui n'est plus
prise. Une interface qui remettrait un seuil à côté de la marge réinstallerait
le défaut. Voir `noyau.recherche.Resultat` pour le détail du choix.

Le champ `bras` reste, lui, et c'est le but : il dit d'où vient chaque article
sans prétendre les classer entre eux.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from typing import Callable, Iterable

from moteur.injection import SEUIL_SIGNALEMENT, Signalement, Trace
from moteur.repondre import SILENCE_RECUPERATION, Reponse
from noyau import ArticleTrouve, QuestionVide, Resultat

# ── La limite de longueur de la question ────────────────────────────────────
#
# C'est une démonstration publique : elle sera visitée par des robots, et une
# question de 200 ko ferait tokeniser 200 ko au bras lexical et encoder autant
# au bras dense, pour un vecteur qui ne dirait rien de plus.
#
# 500 est une BORNE CHOISIE, pas une valeur mesurée, et il faut le dire plutôt
# que de l'habiller : une question de droit du travail écrite dans les mots de
# celui qui la pose tient très largement dedans — « combien de jours de congé
# après deux ans ? » en fait 38. Au delà, le modèle de plongement tronque de
# lui-même à sa propre longueur de contexte, donc le surplus ne déplace même
# plus le vecteur.
#
# Elle ne sert PAS de filtre anti-injection : tronquer une question pour en
# retirer une consigne injectée serait exactement la décision que ce projet
# refuse (`moteur.injection` signale et ne bloque jamais). Une invite collée de
# 400 caractères passe, part dans la récupération, et ressort signalée.
LIMITE_CARACTERES_QUESTION = 500

# ── La limite de débit ──────────────────────────────────────────────────────
#
# Vingt questions par minute et par adresse. Une personne qui lit vraiment les
# cinq articles d'une réponse n'en pose pas vingt en une minute ; un robot, si.
REQUETES_PAR_FENETRE = 20
FENETRE_SECONDES = 60.0

# Le nombre d'adresses suivies est BORNÉ, et c'est le point qui compte : un
# dictionnaire qui grandit à chaque adresse inconnue est une fuite de mémoire
# offerte à quiconque fait tourner ses adresses sources. Au delà, la plus
# anciennement vue est oubliée — elle repart donc avec un quota neuf, ce qui
# est le bon compromis pour une démonstration : on préfère laisser passer un
# robot patient que faire tomber le Space.
ADRESSES_SUIVIES = 4096


class QuestionTropLongue(ValueError):
    """La question dépasse la limite de longueur du service."""


class ChargementEnCours(RuntimeError):
    """La recherche n'est pas encore chargée. Ce n'est pas une panne.

    Elle existe comme type distinct d'`IndexAbsent` pour une raison
    d'affichage : « patientez quelques secondes » et « l'index est à
    reconstruire » demandent deux écrans différents, et les confondre ferait
    afficher une commande d'administration à un visiteur qui n'a qu'à
    réessayer.
    """


# Combien de secondes annoncer à qui frappe pendant le chargement. Le
# chargement a été mesuré à 2,83 s sur un poste tiède (DEPLOIEMENT.md §4) ;
# un conteneur froid qui lit 1,2 Go depuis un système de fichiers superposé
# est plus lent, donc ce nombre est délibérément plus large que la mesure. Il
# n'est pas une prédiction de durée : c'est le délai avant de réessayer.
ATTENDRE_PENDANT_CHARGEMENT = 5


def valider_question(brut: object) -> str:
    """Rend la question nettoyée, ou lève. Les deux exceptions sont attendues.

    `QuestionVide` est celle du NOYAU et non une nouvelle : le service n'a pas
    à inventer un second vocabulaire pour un cas que le cœur nomme déjà, et une
    seule traduction en statut HTTP suffit alors.
    """
    if not isinstance(brut, str) or not brut.strip():
        raise QuestionVide(
            "La question est vide. Envoyez un objet JSON de la forme "
            '{"question": "combien de jours de congé après deux ans ?"} '
            "sur POST /api/question."
        )
    question = brut.strip()
    if len(question) > LIMITE_CARACTERES_QUESTION:
        raise QuestionTropLongue(
            f"Question de {len(question)} caractères, pour une limite de "
            f"{LIMITE_CARACTERES_QUESTION}. Mizan cherche dans les 589 "
            "articles du Code du travail : une question posée en une ou deux "
            "phrases récupère mieux qu'un texte long, dont le modèle de "
            "plongement ne lirait de toute façon que le début."
        )
    return question


class Limiteur:
    """Un compteur de requêtes par adresse, en fenêtre glissante.

    En mémoire du processus, et c'est assumé : le Space est un seul conteneur,
    son disque n'est pas persistant, et un redémarrage remet les compteurs à
    zéro — ce qui est sans conséquence pour ce que cette limite protège.

    L'horloge est injectée pour que les tests se mesurent sans dormir : une
    suite qui attend soixante secondes pour vérifier l'expiration d'une fenêtre
    est une suite que personne ne relance.
    """

    def __init__(
        self,
        requetes: int = REQUETES_PAR_FENETRE,
        fenetre: float = FENETRE_SECONDES,
        adresses: int = ADRESSES_SUIVIES,
        horloge: Callable[[], float] | None = None,
    ) -> None:
        if requetes < 1:
            raise ValueError("Un quota de moins d'une requête ferme le service.")
        self.requetes = requetes
        self.fenetre = float(fenetre)
        self.adresses = adresses
        # Monotone et non `time.time()` : un ajustement d'horloge système ne
        # doit pas offrir un quota neuf ni bloquer une adresse pour une heure.
        self._horloge = horloge or time.monotonic
        self._vues: "OrderedDict[str, deque[float]]" = OrderedDict()
        # Les routes synchrones de FastAPI tournent dans un vivier de fils :
        # deux requêtes simultanées toucheraient la même file sans ce verrou.
        self._verrou = threading.Lock()

    def autoriser(self, adresse: str) -> tuple[bool, float]:
        """Rend (autorisé, secondes à attendre). L'attente vaut 0 si autorisé."""
        maintenant = self._horloge()
        with self._verrou:
            file = self._vues.get(adresse)
            if file is None:
                file = deque()
                self._vues[adresse] = file
            self._vues.move_to_end(adresse)

            while file and maintenant - file[0] >= self.fenetre:
                file.popleft()

            if len(file) >= self.requetes:
                attente = self.fenetre - (maintenant - file[0])
                return False, max(attente, 0.0)

            file.append(maintenant)
            while len(self._vues) > self.adresses:
                self._vues.popitem(last=False)
            return True, 0.0

    @property
    def adresses_suivies(self) -> int:
        with self._verrou:
            return len(self._vues)


def adresse_appelante(client: str | None, entete_transmise: str | None) -> str:
    """L'adresse à compter, derrière le mandataire de Hugging Face.

    Sur un Space, `request.client.host` est l'adresse du mandataire : toutes
    les visites partageraient un seul quota, et le premier robot fermerait le
    service à tout le monde. L'entête `X-Forwarded-For` porte la vraie adresse
    en tête de liste.

    CE QUE CETTE FONCTION NE PEUT PAS GARANTIR, et qu'il faut lire avant de
    s'appuyer dessus : `X-Forwarded-For` est un entête, donc forgeable. Derrière
    un mandataire qui la réécrit — c'est le cas ici — la valeur de tête est la
    bonne ; en direct, un appelant peut s'inventer autant d'adresses qu'il veut
    et se donner autant de quotas. On accepte ce défaut parce que la limite
    protège le processeur d'un Space de démonstration, pas un secret : la seule
    chose qu'un robot gagne en la contournant, c'est de faire tourner une
    recherche qui ne lui apprend rien.
    """
    if entete_transmise:
        premiere = entete_transmise.split(",")[0].strip()
        if premiere:
            return premiere
    return (client or "inconnue").strip() or "inconnue"


# ── La mise en JSON ─────────────────────────────────────────────────────────


def article_en_json(article: ArticleTrouve) -> dict:
    """Un article récupéré. La POSITION part avec le texte, et c'est le sujet.

    En droit, un article sans son chapitre ne dit pas la même chose : « Du
    congé annuel payé » et « Du préavis » portent des durées qui se
    ressemblent et ne se confondent pas. `position` est la citation
    hiérarchique complète telle que le corpus la porte — livre, titre,
    chapitre, section — et non une étiquette abrégée reconstruite ici.

    Pas de `score`. La raison est en tête de ce fichier.
    """
    return {
        "numero": article.numero,
        "position": article.position,
        "texte": article.texte,
        "bras": article.bras,
        "page_pdf": article.page_pdf,
    }


def trace_en_json(trace: Trace) -> dict:
    return {
        "motif": trace.motif,
        "famille": trace.famille,
        "extrait": trace.extrait,
    }


def signalement_en_json(signalement: Signalement | None) -> dict | None:
    """Ce que la détection d'injection a vu — fragment exact compris.

    `signale` vrai N'EST PAS UN REFUS, et le JSON le montre : la réponse est
    rendue dans le même objet, avec son texte s'il a été servi. Une interface
    qui transformerait ce booléen en écran de blocage contredirait la mesure
    qui a tranché (épurer la question ne récupère pas un meilleur article, et
    « mon patron peut-il ignorer le règlement intérieur » n'attaque personne).

    `extrait` est le fragment qui a fait marquer le motif. Il est exposé parce
    qu'une défense qui signale sans montrer est indiscutable, donc
    inaméliorable : c'est ce qui permet à quelqu'un de contester un faux
    positif en citant la phrase.

    `score` est ici le BARÈME de la détection — un compte pondéré de motifs —
    et le seul champ `score` de tout le contrat. Il n'a rien à voir avec un
    score de récupération, qui, lui, n'est pas exposé. `seuil` vient de la
    constante que `moteur.repondre` laisse par défaut en appelant `examiner`.
    """
    if signalement is None:
        return None
    return {
        "signale": signalement.signale,
        "score": signalement.score,
        "seuil": SEUIL_SIGNALEMENT,
        "familles": list(signalement.familles),
        "pourquoi": signalement.pourquoi,
        "traces": [trace_en_json(t) for t in signalement.traces],
    }


def registre(reponse: Reponse) -> str:
    """« reponse », « doute » ou « rejet ». Voir l'en-tête du fichier.

    Dérivé des invariants du contrat partagé, et non d'une liste de chaînes
    recopiée : un texte non nul signifie servi (`Reponse.__post_init__` refuse
    un texte sous une réserve de doute), et la seule cause de silence qui ne
    vient pas de la garde est celle de la récupération. Un septième `cause`
    ajouté un jour en amont tombera donc dans « rejet » plutôt que dans un
    `KeyError` — mais relire ces trois lignes sera le bon réflexe.
    """
    if reponse.texte is not None:
        return "reponse"
    if reponse.cause == SILENCE_RECUPERATION:
        return "doute"
    return "rejet"


def question_en_json(
    reponse: Reponse,
    resultat: Resultat | None,
    redaction: dict,
) -> dict:
    """Le corps de `POST /api/question`.

    `resultat` est le `Resultat` que la récupération a rendu pour CETTE
    question : il porte `sur`, `pourquoi`, `proximite`, `seuil_proximite`,
    `marge` et `termes_inconnus`, que le contrat partagé `Reponse` ne
    transporte pas. Il
    est capté au passage par le chercheur injecté dans `moteur.Mizan`, et non
    recalculé — une seconde recherche rendrait un second verdict, et les deux
    pourraient différer dans l'affichage d'une même réponse.

    Il vaut None seulement si l'appel n'a pas atteint la récupération, ce qui
    n'arrive pas sur ce chemin ; les six champs sont alors nuls plutôt
    qu'inventés — jamais remplacés par des valeurs plausibles.
    """
    return {
        "question": resultat.question if resultat is not None else "",
        "registre": registre(reponse),
        "texte": reponse.texte,
        "abstenu": reponse.abstenu,
        "cause": reponse.cause,
        "raison": reponse.raison,
        "citations": list(reponse.citations),
        "articles": [article_en_json(a) for a in reponse.articles],
        # Jamais vide : le noyau et le moteur refusent tous deux de construire
        # un objet sans lui. L'interface n'a donc aucun cas « absent » à gérer
        # — elle a l'obligation de l'AFFICHER, visiblement et en permanence.
        "avertissement": reponse.avertissement,
        "sur": resultat.sur if resultat is not None else None,
        "pourquoi": resultat.pourquoi if resultat is not None else "",
        # Ce qui a décidé, avec son seuil.
        "proximite": resultat.proximite if resultat is not None else None,
        "seuil_proximite": (
            resultat.seuil_proximite if resultat is not None else None
        ),
        # Une observation. Sans seuil, volontairement : voir l'en-tête.
        "marge": resultat.marge if resultat is not None else None,
        "termes_inconnus": list(resultat.termes_inconnus)
        if resultat is not None
        else [],
        "signalement": signalement_en_json(reponse.signalement),
        # Répété ici et pas seulement sur `/api/etat` : une interface qui ne
        # lirait l'état qu'au chargement afficherait « vraie rédaction » après
        # qu'une clé a expiré en cours de session.
        "redaction": dict(redaction),
    }


# ── Les erreurs ─────────────────────────────────────────────────────────────
#
# Une seule forme pour toutes, parce qu'une interface qui doit reconnaître
# trois formes d'erreur en affichera une en texte brut.

CODE_QUESTION_VIDE = "question_vide"
CODE_QUESTION_TROP_LONGUE = "question_trop_longue"
CODE_CORPS_ILLISIBLE = "corps_illisible"
CODE_TROP_DE_REQUETES = "trop_de_requetes"
CODE_CHARGEMENT_EN_COURS = "chargement_en_cours"
CODE_INDEX_ABSENT = "index_absent"
CODE_MODELE_ABSENT = "modele_absent"
CODE_REDACTION_EN_PANNE = "redaction_en_panne"


def erreur_en_json(code: str, message: str, commande: str | None = None) -> dict:
    """La forme unique d'une erreur du service.

    `commande` est la ligne EXACTE à lancer quand il y en a une — c'est ce que
    font déjà tous les messages du cœur, et une interface peut l'afficher en
    mono sans la reconstruire à partir d'une phrase.
    """
    return {
        "erreur": {
            "code": code,
            "message": message,
            "commande": commande,
        }
    }


def commande_dans(message: str) -> str | None:
    """La première ligne indentée d'un message du cœur, qui est sa commande.

    Les erreurs du noyau et du moteur écrivent déjà quoi lancer, indenté de
    quatre espaces sur sa propre ligne (`    python -m noyau.indexer`). On la
    relève plutôt que de la recopier : une commande recopiée dans la couche
    HTTP dérive de celle que le cœur imprime, et c'est alors la mauvaise des
    deux qui s'affiche à l'écran.
    """
    for ligne in (message or "").splitlines():
        nettoyee = ligne.strip()
        if ligne.startswith("    ") and nettoyee and not nettoyee.startswith("•"):
            return nettoyee
    return None


def numeros(articles: Iterable[ArticleTrouve]) -> list[str]:
    """Les numéros, dans l'ordre d'affichage. Pour les journaux et les tests."""
    return [a.numero for a in articles]
