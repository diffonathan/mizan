# -*- coding: utf-8 -*-
"""Le rédacteur : une interface, un client HTTP, un modèle factice.

    from moteur.llm import Redacteur, Demande, ClientHttp, ModeleFactice

Ce module est le SEUL endroit du projet qui parle à un modèle de langue. Tout
ce qui est en aval (`moteur.repondre`) reçoit un `Redacteur` et ignore d'où
vient le texte.

POURQUOI UNE INTERFACE, ET PAS UN CLIENT
----------------------------------------
Aucune clé de modèle de langue n'est disponible dans l'environnement où ce
projet est écrit. Un rédacteur injectable n'est donc pas une élégance
d'architecture, c'est la condition pour que les tests existent : le modèle
factice ci-dessous implémente la même interface et rend un texte choisi, ce
qui permet de vérifier la garde des citations — c'est-à-dire la seule garantie
du produit — sans dépendre de ce qui ne tourne que chez son auteur.

Le factice sert aussi à produire ce qu'une clé ne permettrait pas d'obtenir de
façon reproductible : une citation inventée, une réponse sans source, une
réponse vide. Avec un vrai modèle, obtenir ces trois cas à la demande relève
du hasard.

CE QUE L'INVITE DEMANDE, ET CE QU'ELLE NE GARANTIT PAS
------------------------------------------------------
L'invite dit au modèle de ne citer que les articles fournis. Cette consigne
est utile — elle améliore les chances — et elle ne garantit RIEN : elle cède à
la première injection, et elle cède aussi toute seule, sans attaque, parce
qu'un modèle de langue hallucine. La garantie est ailleurs, dans
`moteur.garde`, et c'est une inclusion d'ensembles vérifiée en code sur le
texte produit. Si quelqu'un renforce un jour cette invite en croyant renforcer
la sûreté du produit, il se trompe d'étage.

L'INVITE N'EST PLUS ÉCRITE ICI
------------------------------
Ce module composait d'abord ses propres consignes et son propre bloc
« Articles : ». Deux raisons l'ont fait céder la place à
`moteur.injection.assembler` :

  • le séparateur était imitable — un usager qui écrivait « Articles : » dans
    sa question obtenait deux blocs d'articles indistinguables dans l'invite,
    mesuré par `python -m moteur.mesurer_injection` ;
  • il y avait DEUX jeux de consignes dans le paquet, celui d'ici et celui de
    `moteur.injection`. Deux textes qui disent la même chose au modèle sont
    un texte qu'on corrigera une fois sur deux.

Il n'y a donc plus qu'un endroit où l'invite s'écrit, et c'est celui qui
délimite les données.

AUCUN PAQUET
------------
Le client HTTP est écrit sur `urllib.request`, de la bibliothèque standard.
`requests` ou un client de fournisseur auraient apporté une dépendance, sa
chaîne de dépendances transitives et une raison de plus de casser au prochain
déploiement, pour un seul POST en JSON.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .injection import Signalement, assembler

# ── Convention d'environnement, reprise des autres projets de l'auteur ──────
#
# LLM_PROVIDER / LLM_API_KEY / LLM_MODEL. Le nom du modèle vient de
# l'environnement et n'est pas écrit dans le code : sur ce compte, un
# fournisseur a déjà retiré sans préavis les modèles que deux projets voisins
# utilisaient, et la seule réparation a été de changer une variable. Un nom de
# modèle en dur transforme cette réparation en modification de code.
VARIABLE_FOURNISSEUR = "LLM_PROVIDER"
VARIABLE_CLE = "LLM_API_KEY"
VARIABLE_MODELE = "LLM_MODEL"
VARIABLE_URL = "LLM_BASE_URL"

# Les fournisseurs connus exposent tous la même route « /chat/completions » au
# format OpenAI. Ce n'est pas une adhésion à ce format, c'est un constat qui
# évite d'écrire quatre clients ; `LLM_BASE_URL` permet d'en viser un autre
# sans toucher à cette table.
RACINES = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "mistral": "https://api.mistral.ai/v1",
}

FOURNISSEUR_DEFAUT = "groq"

# Délai généreux : un modèle de raisonnement peut réfléchir plusieurs dizaines
# de secondes avant son premier octet, et un délai court transformerait une
# lenteur en panne.
DELAI_SECONDES = 90.0


class ErreurModele(RuntimeError):
    """Base des pannes de rédaction. Chaque message dit QUOI FAIRE.

    Elles ne sont pas rattrapées par `moteur.repondre` : une panne du rédacteur
    n'est pas une abstention. Le système a trouvé des articles ; les présenter
    comme un « je ne sais pas » mentirait sur ce qui s'est passé et masquerait
    une panne d'exploitation derrière un comportement de produit. La couche qui
    expose le service doit la traduire en indisponibilité.
    """


class CleAbsente(ErreurModele):
    """Il manque une variable d'environnement pour parler au fournisseur."""


class CleRefusee(ErreurModele):
    """Le fournisseur refuse la clé."""


class ModeleRetire(ErreurModele):
    """Le modèle demandé n'existe pas, ou plus, chez le fournisseur."""


class QuotaDepasse(ErreurModele):
    """Le fournisseur impose d'attendre."""


class ServiceIndisponible(ErreurModele):
    """Le réseau ou le fournisseur n'a pas répondu."""


class ReponseIllisible(ErreurModele):
    """Le fournisseur a répondu autre chose qu'une complétion."""


# ── Ce qu'un rédacteur reçoit ───────────────────────────────────────────────


@runtime_checkable
class Extrait(Protocol):
    """La forme minimale d'un article fourni au rédacteur.

    Décrite en protocole plutôt qu'en important `noyau.ArticleTrouve` : ce
    module n'a aucune raison de dépendre du moteur de récupération, et les
    tests fabriquent des extraits à la main, sans corpus ni modèle de
    plongement.
    """

    numero: str
    texte: str
    position: str


@dataclass(frozen=True)
class Demande:
    """Une question et les articles récupérés pour y répondre.

    Les articles sont fournis par la récupération et jamais choisis par le
    rédacteur : c'est ce qui rend le contrôle de citations possible. L'ensemble
    des numéros présents ici est exactement celui contre lequel la garde
    vérifiera le texte produit.

    `avertissement` et `signalement` viennent des deux étages d'amont et
    traversent jusqu'ici parce que l'invite les porte : la consolidation au
    26 octobre 2011, que le modèle doit reproduire, et ce que la détection
    d'injection a vu dans la question. Ils ont une valeur par défaut pour que
    les rédacteurs qui n'en font rien — le factice, ceux des tests — restent
    constructibles en deux arguments ; `moteur.injection.assembler` refuse
    cependant de construire une invite sans avertissement, de sorte qu'un
    `ClientHttp` ne peut pas en envoyer une qui l'omette.

    Les deux champs sont rendus tels quels au rédacteur plutôt que comme une
    invite déjà composée : la forme de l'invite appartient au rédacteur, et un
    autre rédacteur que celui-ci pourra l'écrire autrement.
    """

    question: str
    articles: tuple[Extrait, ...]
    avertissement: str = ""
    signalement: Signalement | None = None

    @property
    def numeros(self) -> tuple[str, ...]:
        return tuple(a.numero for a in self.articles)


class Redacteur(Protocol):
    """Le contrat que `moteur.repondre` attend d'un rédacteur."""

    def rediger(self, demande: Demande) -> str:
        """Rend le texte d'une réponse, ou lève une `ErreurModele`."""
        ...


# ── L'invite ────────────────────────────────────────────────────────────────

# Les consignes et la mise en blocs sont dans `moteur.injection`, qui est le
# module dont c'est le métier : délimiter ce qui est une consigne de ce qui est
# une donnée. Ce qui reste ici est l'appel.
def composer(demande: Demande):
    """L'invite d'une demande, consignes et données séparées.

    La position hiérarchique de chaque article part avec son texte, parce
    qu'elle porte le sens : un article du chapitre « Du congé annuel payé » ne
    parle pas de la même durée qu'un article du chapitre sur le préavis, et le
    texte seul ne le dit pas toujours. C'est `assembler` qui l'écrit.
    """
    return assembler(
        demande.question, demande, signalement=demande.signalement
    )


# ── Le client HTTP ──────────────────────────────────────────────────────────

_AIDE_FOURNISSEUR = (
    "set " + VARIABLE_FOURNISSEUR + "=groq   (ou "
    + ", ".join(sorted(nom for nom in RACINES if nom != "groq"))
    + ")"
)


def _choisir(fourni: str | None, variable: str) -> str | None:
    """L'argument s'il est fourni, sinon la variable d'environnement.

    « ARGUMENT NON FOURNI » (None) ET « ARGUMENT FOURNI VIDE » ("") SONT DEUX
    CHOSES, et l'idiome `fourni or os.environ.get(...)` les confondait : une
    chaîne vide étant fausse, un argument explicite ne neutralisait pas
    l'environnement. La conséquence n'était pas théorique — deux tests de
    configuration basculaient selon la présence de LLM_MODEL dans le shell,
    c'est-à-dire testaient la machine et non le code, sur un projet dont la
    règle est que ses tests tournent partout et dont le README prescrit
    justement de poser cette variable.

    La clé faisait déjà cette distinction ; le fournisseur, le modèle et la
    racine ne la faisaient pas. Une valeur vide signifie donc « ne consulte
    pas l'environnement » : ce qui suit décide alors du défaut, ou refuse.
    """
    return fourni if fourni is not None else os.environ.get(variable)


class ClientHttp:
    """Un POST JSON vers une route « /chat/completions », et rien d'autre.

    La température est à zéro : à question et articles identiques, on veut la
    même réponse, pour que le rejet d'une réponse se reproduise et puisse être
    examiné. Ce n'est pas un déterminisme garanti — aucun fournisseur ne le
    promet — mais c'est le seul réglage qui s'en approche.
    """

    def __init__(
        self,
        cle: str | None = None,
        modele: str | None = None,
        fournisseur: str | None = None,
        racine: str | None = None,
        delai: float = DELAI_SECONDES,
    ) -> None:
        self.fournisseur = (
            _choisir(fournisseur, VARIABLE_FOURNISSEUR) or FOURNISSEUR_DEFAUT
        ).strip().lower()
        self.modele = (_choisir(modele, VARIABLE_MODELE) or "").strip()
        self.delai = delai

        brute = cle if cle is not None else os.environ.get(VARIABLE_CLE, "")
        self._cle = (brute or "").strip()
        if not self._cle:
            raise CleAbsente(
                f"Aucune clé de modèle de langue : {VARIABLE_CLE} est vide ou "
                "absente.\n"
                "Mizan récupère et doute sans clé — c'est `noyau.chercher` — "
                "mais il ne rédige pas.\n"
                f"    {_AIDE_FOURNISSEUR}\n"
                f"    set {VARIABLE_CLE}=...\n"
                f"    set {VARIABLE_MODELE}=<nom du modèle chez ce "
                "fournisseur>\n"
                "Pour les tests, `moteur.llm.ModeleFactice` remplace le client "
                "sans clé."
            )
        if not self.modele:
            raise CleAbsente(
                f"{VARIABLE_MODELE} est vide : le nom du modèle n'est "
                "volontairement pas écrit dans le code, parce qu'un "
                "fournisseur peut le retirer sans préavis.\n"
                f"    set {VARIABLE_MODELE}=<nom du modèle chez "
                f"{self.fournisseur}>"
            )

        choisie = _choisir(racine, VARIABLE_URL) or RACINES.get(self.fournisseur)
        if not choisie:
            connus = ", ".join(sorted(RACINES))
            raise CleAbsente(
                f"Fournisseur « {self.fournisseur} » inconnu de ce client. "
                f"Connus : {connus}.\n"
                "Pour un autre fournisseur compatible, donnez sa racine :\n"
                f"    set {VARIABLE_URL}=https://.../v1"
            )
        self.racine = choisie.rstrip("/")

    # -- le contrat ---------------------------------------------------------

    def rediger(self, demande: Demande) -> str:
        invite = composer(demande)
        corps = json.dumps(
            {
                "model": self.modele,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": invite.consignes},
                    {"role": "user", "content": invite.donnees},
                ],
            }
        ).encode("utf-8")

        requete = urllib.request.Request(
            f"{self.racine}/chat/completions",
            data=corps,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._cle}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(requete, timeout=self.delai) as flux:
                charge = json.loads(flux.read().decode("utf-8"))
        except urllib.error.HTTPError as erreur:
            raise self._traduire(erreur) from None
        except TimeoutError:
            raise ServiceIndisponible(
                f"{self.fournisseur} n'a pas répondu en "
                f"{self.delai:.0f} secondes."
            ) from None
        except urllib.error.URLError as erreur:
            raise ServiceIndisponible(
                f"{self.fournisseur} injoignable : {erreur.reason}.\n"
                "Réseau, pare-feu ou coupure du fournisseur. Rien à corriger "
                "dans Mizan."
            ) from None

        return self._extraire(charge)

    # -- les pannes, traduites en messages qui disent quoi faire ------------

    def _traduire(self, erreur: urllib.error.HTTPError) -> ErreurModele:
        """Une erreur HTTP devient une phrase actionnable, jamais une trace.

        Le cas 404 est traité à part parce que c'est celui qui s'est produit :
        un fournisseur a retiré les modèles de deux projets voisins de
        celui-ci, et le symptôme était un 404 sur le nom du modèle. Un service
        qui rend une trace de pile à ce moment-là fait chercher un défaut dans
        le code alors qu'il n'y en a pas.
        """
        detail = self._detail(erreur)
        code = erreur.code
        bas = detail.lower()

        if code == 404 or ("model" in bas and ("not" in bas or "decommission" in bas)):
            return ModeleRetire(
                f"Le modèle « {self.modele} » n'existe pas (ou plus) chez "
                f"{self.fournisseur}.\n"
                "Les fournisseurs retirent leurs modèles sans préavis ; ce "
                "n'est pas un défaut de Mizan et rien n'est à corriger dans "
                "le code.\n"
                "  1. lister les modèles encore servis :\n"
                f"       curl -H \"Authorization: Bearer <clé>\" "
                f"{self.racine}/models\n"
                f"  2. poser le nom retenu dans {VARIABLE_MODELE}.\n"
                f"(réponse du fournisseur : {detail})"
            )
        if code in (401, 403):
            return CleRefusee(
                f"{self.fournisseur} refuse la clé de {VARIABLE_CLE} "
                f"(HTTP {code}) : clé expirée, révoquée, ou émise pour un "
                f"autre fournisseur que « {self.fournisseur} ».\n"
                f"(réponse du fournisseur : {detail})"
            )
        if code == 429:
            return QuotaDepasse(
                f"{self.fournisseur} impose d'attendre (HTTP 429) : quota de "
                "jetons par minute ou de requêtes atteint.\n"
                "Réessayer plus tard, ou réduire le nombre d'articles envoyés "
                "— une demande de Mizan porte cinq articles entiers.\n"
                f"(réponse du fournisseur : {detail})"
            )
        if code >= 500:
            return ServiceIndisponible(
                f"{self.fournisseur} est en panne (HTTP {code}). Rien à "
                f"corriger dans Mizan.\n(réponse du fournisseur : {detail})"
            )
        return ErreurModele(
            f"{self.fournisseur} a refusé la demande (HTTP {code}).\n"
            f"(réponse du fournisseur : {detail})"
        )

    @staticmethod
    def _detail(erreur: urllib.error.HTTPError) -> str:
        """Le message du fournisseur, abrégé, jamais la charge entière."""
        try:
            brut = erreur.read().decode("utf-8", errors="replace")
        except Exception:
            return str(erreur.reason or "")
        try:
            charge = json.loads(brut)
        except ValueError:
            return brut.strip()[:300]
        bloc = charge.get("error") if isinstance(charge, dict) else None
        if isinstance(bloc, dict):
            return str(bloc.get("message") or bloc)[:300]
        return str(bloc if bloc is not None else charge)[:300]

    def _extraire(self, charge: object) -> str:
        """Le texte de la complétion, ou une erreur qui montre ce qui est arrivé.

        Un `KeyError` sur « choices » serait illisible en exploitation : une
        route compatible qui change de forme, un proxy qui renvoie une page,
        un modèle de raisonnement qui ne rend que son champ de réflexion —
        trois causes que cette erreur doit permettre de distinguer.
        """
        try:
            contenu = charge["choices"][0]["message"]["content"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            apercu = json.dumps(charge, ensure_ascii=False)[:300]
            raise ReponseIllisible(
                f"{self.fournisseur} n'a pas rendu de complétion exploitable "
                f"pour « {self.modele} ».\n(début de la réponse : {apercu})"
            ) from None
        if not isinstance(contenu, str) or not contenu.strip():
            raise ReponseIllisible(
                f"{self.fournisseur} a rendu une complétion vide pour "
                f"« {self.modele} ». Les modèles de raisonnement rendent "
                "parfois leur réflexion et un contenu vide quand le budget de "
                "jetons est trop court."
            )
        return contenu


# ── Le modèle factice ───────────────────────────────────────────────────────


class ModeleFactice:
    """Un rédacteur déterministe, qui écrit ce que le test a besoin de lire.

    Il ne simule pas un modèle de langue : il n'en a pas le style et n'essaie
    pas de l'avoir. Il produit, à partir des articles réellement fournis, les
    quelques textes dont la garde doit décider — un texte fidèle, un texte qui
    cite un article jamais récupéré, un texte sans aucune source, un texte
    vide. Ces cas sont exactement ceux qu'un vrai modèle ne rend pas à la
    demande.

    `appels` conserve les demandes reçues : c'est ce qui permet de prouver
    qu'une abstention de la récupération n'appelle PAS le rédacteur, une
    propriété qu'aucune inspection du texte rendu ne pourrait établir.
    """

    COMPORTEMENTS = (
        "fidele",
        "citation_inventee",
        "sans_citation",
        "vide",
        "formes_variees",
    )

    # Hors du corpus par construction : le Code du travail marocain compte
    # 589 articles, et aucune récupération ne peut donc rendre ce numéro.
    NUMERO_IMPOSSIBLE = "9999"

    def __init__(
        self,
        comportement: str = "fidele",
        texte: str | None = None,
        erreur: ErreurModele | None = None,
    ) -> None:
        if texte is None and comportement not in self.COMPORTEMENTS:
            connus = ", ".join(self.COMPORTEMENTS)
            raise ValueError(
                f"Comportement « {comportement} » inconnu. Connus : {connus}."
            )
        self.comportement = comportement
        self.texte_impose = texte
        self.erreur = erreur
        self.appels: list[Demande] = []

    def rediger(self, demande: Demande) -> str:
        self.appels.append(demande)
        if self.erreur is not None:
            raise self.erreur
        if self.texte_impose is not None:
            return self.texte_impose
        return getattr(self, f"_{self.comportement}")(demande)

    # -- les comportements --------------------------------------------------

    @staticmethod
    def _designer(numero: str) -> str:
        """« article premier » ou « article 12 ».

        Le premier article du Code n'a pas de numéro chiffré dans le corpus :
        l'écrire « article 1 » serait écrire une forme que le texte officiel ne
        porte pas.
        """
        return "article premier" if numero == "premier" else f"article {numero}"

    def _fidele(self, demande: Demande) -> str:
        numeros = demande.numeros[:2]
        if not numeros:
            return "Aucun article ne m'a été fourni."
        phrases = [
            f"D'après l'{self._designer(numeros[0])}, la réponse se trouve "
            "dans le texte cité."
        ]
        if len(numeros) > 1:
            phrases.append(f"Voir aussi l'{self._designer(numeros[1])}.")
        return " ".join(phrases)

    def _citation_inventee(self, demande: Demande) -> str:
        premier = demande.numeros[0] if demande.numeros else "12"
        return (
            f"D'après l'{self._designer(premier)}, la règle est celle-ci, et "
            f"l'article {self.NUMERO_IMPOSSIBLE} la complète."
        )

    @staticmethod
    def _sans_citation(demande: Demande) -> str:
        # Des nombres partout, aucun précédé du mot « article » : ce texte sert
        # aussi à vérifier que la garde ne prend pas un chiffre pour une source.
        return (
            "La durée normale du travail est de 44 heures par semaine, et le "
            "congé annuel s'acquiert après 6 mois de service continu, soit "
            "1,5 jour par mois."
        )

    @staticmethod
    def _vide(demande: Demande) -> str:
        return "   "

    def _formes_variees(self, demande: Demande) -> str:
        """Cite tous les articles fournis, chacun dans une forme différente.

        Sert à vérifier de bout en bout que la garde reconnaît les formes du
        corpus : si l'une lui échappe, elle lit une citation en moins et laisse
        passer une réponse qu'elle n'a pas vraiment contrôlée.
        """
        numeros = list(demande.numeros)
        if not numeros:
            return "Aucun article ne m'a été fourni."
        morceaux = [f"L'{self._designer(numeros[0])} pose la règle."]
        if len(numeros) > 1:
            morceaux.append(f"Voir art. {numeros[1]}.")
        if len(numeros) > 3:
            morceaux.append(
                f"Les articles {numeros[2]} et {numeros[3]} la précisent."
            )
        elif len(numeros) > 2:
            morceaux.append(f"L'article {numeros[2]} la précise.")
        if len(numeros) > 4:
            morceaux.append(f"Enfin, article {numeros[4]}.")
        return " ".join(morceaux)


# ── Le rédacteur de production ──────────────────────────────────────────────


def charger_redacteur() -> ClientHttp:
    """Construit le client depuis l'environnement. Échoue proprement sans clé.

    Explicite, comme le chargement du noyau : un service l'appelle à son
    démarrage et sait tout de suite s'il peut rédiger, plutôt que de le
    découvrir à la première question d'un usager.
    """
    return ClientHttp()
