# -*- coding: utf-8 -*-
"""Mizan, étage de la réponse : rédiger, puis vérifier avant de servir.

    from moteur.repondre import repondre
    reponse = repondre("combien de jours de congé après deux ans ?")

    reponse.texte          # la réponse rédigée, ou None si rien n'est servi
    reponse.citations      # les NUMÉROS d'articles cités dans le texte
    reponse.articles       # les articles récupérés, tels que le noyau les rend
    reponse.abstenu
    reponse.raison         # pourquoi, en français, quand abstenu ou rejeté
    reponse.avertissement  # la consolidation 2011, jamais vide

Quatre fichiers, et un seul qui porte la promesse du produit :

    llm.py        l'interface du rédacteur, un client HTTP, un modèle factice
    injection.py  la détection qui signale, et la délimitation des données
    garde.py      LE CONTRÔLE : les articles cités ⊆ les articles récupérés
    repondre.py   la composition, et l'avertissement rendu impossible à omettre

`repondre` a besoin d'une clé de modèle de langue (LLM_PROVIDER /
LLM_API_KEY / LLM_MODEL) ; sans clé, `charger` lève une `CleAbsente` dont le
message dit quoi poser. Tout le reste — la récupération par `noyau.chercher`,
la garde, et l'intégralité des tests — tourne sans clé.

UNE NOTE DE NOMMAGE, QUI A DÉJÀ COÛTÉ UNE SÉRIE DE TESTS
--------------------------------------------------------
La fonction `repondre` n'est volontairement PAS réexportée ici, alors que tout
le reste l'est. Elle porte le nom de son module, et la réexporter remplace
l'attribut `moteur.repondre` — le module — par la fonction : `from moteur
import repondre as m` rend alors la fonction, et `m.Reponse` lève un
`AttributeError` que rien n'explique. La forme à écrire est donc celle du haut
de ce texte, et `from moteur import Reponse, verifier` pour le reste.
"""
from .garde import Verdict, extraire_citations, verifier
from .injection import Invite, Signalement, Trace, assembler, examiner
from .llm import (
    ClientHttp,
    CleAbsente,
    CleRefusee,
    Demande,
    ErreurModele,
    ModeleFactice,
    ModeleRetire,
    QuotaDepasse,
    Redacteur,
    ReponseIllisible,
    ServiceIndisponible,
    charger_redacteur,
)
from .repondre import Mizan, Reponse, charger

__all__ = [
    "CleAbsente",
    "CleRefusee",
    "ClientHttp",
    "Demande",
    "ErreurModele",
    "Invite",
    "Mizan",
    "ModeleFactice",
    "ModeleRetire",
    "QuotaDepasse",
    "Redacteur",
    "Reponse",
    "ReponseIllisible",
    "ServiceIndisponible",
    "Signalement",
    "Trace",
    "Verdict",
    "assembler",
    "charger",
    "charger_redacteur",
    "examiner",
    "extraire_citations",
    "verifier",
]
