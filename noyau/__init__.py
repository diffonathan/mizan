# -*- coding: utf-8 -*-
"""Noyau de Mizan : la récupération d'articles du Code du travail marocain.

Le contrat, figé, que le reste du projet appelle :

    from noyau import chercher
    resultat = chercher("combien de jours de congé après deux ans ?", k=5)

    resultat.articles      # au plus k articles : numéro, texte, position, score
    resultat.sur           # le système estime-t-il avoir trouvé ?
    resultat.pourquoi      # en une phrase française, ce qui a décidé
    resultat.avertissement # la date de consolidation du corpus, toujours présente
    resultat.numeros       # l'ensemble des articles récupérés

`resultat.numeros` est la pièce maîtresse pour qui rédige une réponse en aval :
l'ensemble des articles cités doit y être INCLUS, et toute citation hors de cet
ensemble fait rejeter la réponse entière. C'est une inclusion d'ensembles
vérifiable en code, pas une consigne adressée à un modèle de langue.

Aucune clé de modèle de langue n'intervient ici : ce noyau ne rédige rien, il
récupère et il doute.
"""
from .corpus import Corpus, charger as charger_corpus
from .dense import BrasDense, IndexAbsent, ModeleAbsent
from .recherche import (
    PROFONDEUR_DENSE,
    SEUIL_MARGE,
    ArticleTrouve,
    Moteur,
    QuestionVide,
    Resultat,
    charger,
    chercher,
)

__all__ = [
    "ArticleTrouve",
    "BrasDense",
    "Corpus",
    "IndexAbsent",
    "ModeleAbsent",
    "Moteur",
    "PROFONDEUR_DENSE",
    "QuestionVide",
    "Resultat",
    "SEUIL_MARGE",
    "charger",
    "charger_corpus",
    "chercher",
]
