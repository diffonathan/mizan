# -*- coding: utf-8 -*-
"""Le service HTTP de Mizan : une couche MINCE au-dessus de `noyau` et `moteur`.

    service/contrat.py     ce que les deux routes rendent, en JSON — AUCUN paquet
    service/chargement.py  le chargement unique du démarrage, et l'état honnête
    service/app.py         l'application FastAPI, l'objet `app`, le port 7860
    service/statique/      l'interface, servie telle quelle

POURQUOI LA LOGIQUE N'EST PAS DANS `app.py`
-------------------------------------------
`contrat.py` et `chargement.py` n'importent RIEN d'autre que la bibliothèque
standard, `noyau` et `moteur`. C'est la règle du projet et non une élégance :
la suite de tests tourne sur un interpréteur nu, sans clé, sans paquet et sans
l'index de 1,8 Mo. Si la forme du JSON, la limite de longueur, le compteur de
débit et la traduction des pannes vivaient dans les fonctions de route, ils ne
seraient vérifiables qu'avec `fastapi` installé — c'est-à-dire pas vérifiés sur
la machine de celui qui clone.

`app.py` ne contient donc que du câblage : la validation d'entrée, l'appel, et
le code de statut. Les tests de route, eux, sautent quand `fastapi` manque, et
disent en se sautant quoi lancer.

CE QUE CETTE COUCHE NE FAIT PAS, ET NE DOIT JAMAIS FAIRE
-------------------------------------------------------
Elle ne récupère pas, ne rédige pas, ne vérifie pas une citation et ne décide
pas d'une abstention. Tout cela est écrit, mesuré et testé en amont. Elle
expose, elle compte les requêtes, et elle traduit des exceptions en statuts.

Le jour où une règle de produit s'écrit ici, elle échappera aux 195 tests des
fondations.
"""
