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
    resultat.proximite     # ce qui DÉCIDE : la ressemblance de la question au Code
    resultat.seuil_proximite
    resultat.marge         # une OBSERVATION, qui ne décide plus rien

La décision de répondre ou de se taire se prend sur `proximite` — le score
dense absolu du premier article — depuis que le banc `arbitrage/abstention.py`
a mesuré que la marge entre les deux premiers rangs ne séparait presque pas les
questions du Code de celles qui lui sont étrangères. Le pourquoi est en tête de
`noyau/recherche.py`, avec les commandes qui impriment les chiffres.

Un seuil absolu se paie d'une sensibilité à l'ÉCRITURE de la question : taper
sans accents déplace la proximité, et le service est fait pour des salariés qui
écrivent depuis un téléphone. Le moteur rend donc au bras dense, avant de
plonger, les accents que le Code n'écrit jamais autrement (`noyau.accents`).
Ce que cela répare et ce que cela laisse derrière est mesuré par
`arbitrage/accents.py` et porté par la quatrième réserve du seuil.

`resultat.numeros` est la pièce maîtresse pour qui rédige une réponse en aval :
l'ensemble des articles cités doit y être INCLUS, et toute citation hors de cet
ensemble fait rejeter la réponse entière. C'est une inclusion d'ensembles
vérifiable en code, pas une consigne adressée à un modèle de langue.

Aucune clé de modèle de langue n'intervient ici : ce noyau ne rédige rien, il
récupère et il doute.
"""
from .accents import Reaccentueur, construire as construire_reaccentueur
from .corpus import Corpus, charger as charger_corpus
from .dense import BrasDense, IndexAbsent, ModeleAbsent
from .recherche import (
    PROFONDEUR_DENSE,
    SEUIL_PROXIMITE,
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
    "Reaccentueur",
    "Resultat",
    "SEUIL_PROXIMITE",
    "charger",
    "charger_corpus",
    "chercher",
    "construire_reaccentueur",
]
