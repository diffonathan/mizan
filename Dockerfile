# syntax=docker/dockerfile:1
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Mizan — image de déploiement, cible Hugging Face Spaces (SDK Docker)   ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Palier visé : CPU Basic, gratuit — 2 vCPU, 16 Go de RAM, 50 Go de disque.
# Le modèle (1,2 Go) et le pic de service (~870 Mo mesurés,
# `arbitrage/res_cout.json`) y tiennent très largement. Aucune contorsion
# d'architecture n'est faite pour économiser de la mémoire : ce serait payer
# un confort par une réindexation avec un autre modèle de plongement, donc
# par le déplacement des rappels mesurés qui sont l'argument du projet.
#
# ── POURQUOI DOCKER ET NON GRADIO ─────────────────────────────────────────
# Gradio irait plus vite et imposerait son apparence. La charte du projet
# (CHARTE.md, palette 19 — violet profond, l'or porte les citations) n'est pas
# négociable : on sert donc une interface écrite à la main derrière un service
# HTTP. Hugging Face attend le port 7860.
#
# ── LES DEUX CHOSES QUE CE FICHIER EXISTE POUR RÉSOUDRE ───────────────────
# Le disque d'un Space N'EST PAS PERSISTANT : il repart à zéro à chaque
# redémarrage. L'image, elle, est mise en cache. D'où :
#
#   1. LE MODÈLE EST TÉLÉCHARGÉ À LA CONSTRUCTION (couche ❸ ci-dessous).
#      Laissé au premier appel, il serait retéléchargé — 1,2 Go — à chaque
#      redémarrage, devant le visiteur.
#   2. L'INDEX VECTORIEL EST VERSIONNÉ et simplement copié (couche ❹).
#      Le reconstruire coûte 1 075 s mesurées et un pic de 9,4 Go. Le
#      paragraphe de `.gitignore` explique pourquoi l'interdiction de
#      versionner des vecteurs est levée pour ce fichier-là, et à quelle
#      condition : l'index porte l'empreinte du corpus, et le chargement
#      REFUSE un index dont l'empreinte ne correspond pas.
#
# ── L'ORDRE DES COUCHES EST UNE DÉCISION, PAS UNE HABITUDE ────────────────
# La couche du modèle (1,2 Go, lente) est placée AVANT la copie du code
# applicatif. Un changement dans `service/` ou `moteur/` ne réinvalide donc
# pas le téléchargement. Dans l'autre ordre, chaque correction d'interface
# coûterait un rapatriement de 1,2 Go.

# ── ❶ Base ─────────────────────────────────────────────────────────────────
# Python 3.12 : la version avec laquelle tous les chiffres du dossier ont été
# mesurés (3.12.10). Monter de version déplacerait potentiellement les
# vecteurs sans qu'une ligne de code ait changé, et l'index versionné serait
# alors scellé sur un corpus juste avec des poids calculés autrement — le seul
# trou connu du mécanisme d'empreinte, dit en clair dans DEPLOIEMENT.md.
FROM python:3.12-slim

# `libgomp1` : onnxruntime s'y lie pour son parallélisme OpenMP et ne se
# charge pas sans elle. L'image `slim` ne l'embarque pas, et l'erreur qu'on
# obtient alors — un ImportError sur un .so — ne dit pas de quoi il s'agit.
# C'est la seule dépendance système du projet.
RUN apt-get update \
 && apt-get install --no-install-recommends -y libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face exécute le conteneur sous l'UID 1000, pas sous root. Un fichier
# que seul root peut lire devient illisible au démarrage, et l'erreur arrive
# sous forme de permission refusée sur un chemin de cache — un symptôme qui ne
# nomme pas sa cause. L'utilisateur est donc créé ici, et tout ce que le
# service doit lire lui appartiendra explicitement (couche ❸).
RUN useradd --create-home --uid 1000 user

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── ❷ Dépendances Python ───────────────────────────────────────────────────
# `requirements.txt` est installé TEL QUEL, versions épinglées comprises, et
# sans en retirer `pymupdf` qui ne sert qu'à l'extraction du corpus. La raison
# n'est pas la paresse : tous les rappels publiés dépendent de fastembed et
# d'onnxruntime à ces versions exactes. Une image qui installerait un
# sous-ensemble choisi à la main ne serait plus la pile sur laquelle les
# chiffres ont été mesurés, et c'est précisément ce que ce fichier épingle.
WORKDIR /opt/mizan
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# LE SERVICE WEB EST DANS `requirements.txt`, ET IL N'Y A RIEN À INSTALLER ICI.
#
# Cette ligne a existé, et elle a été SUPPRIMÉE :
#
#     RUN pip install --no-cache-dir "fastapi==0.142.2" "uvicorn[standard]==0.54.0"
#
# `requirements.txt` épingle désormais `fastapi==0.142.2` et `uvicorn==0.54.0`
# lui-même, et il dit explicitement qu'il est LA SEULE SOURCE de ces deux
# versions. Garder le `RUN` ci-dessus faisait exactement ce que ce paragraphe
# interdit, et le faisait en silence : venant APRÈS l'installation de
# `requirements.txt`, c'était lui qui gagnait.
#
# Et il ne réinstallait pas la même chose. `requirements.txt` choisit
# `uvicorn` SANS extras, et explique pourquoi (les extras apportent une pile
# WebSocket, un surveillant de fichiers et `uvloop`, dont ce service n'appelle
# rien). `uvicorn[standard]` en ajoutait six : l'image ne tournait donc plus
# sur la pile où les 24 tests de route ont été mesurés.
#
#   SI `service/requirements.txt` APPARAÎT un jour, c'est le `COPY` et le
#   `RUN` de `requirements.txt` ci-dessus qu'il faut étendre — jamais une
#   seconde installation ajoutée en dessous.

# ── ❸ Le modèle, À LA CONSTRUCTION ─────────────────────────────────────────
# `fastembed` connaît `google/embeddinggemma-300m` sous la source Hugging Face
# `onnx-community/embeddinggemma-300m-ONNX` (vérifié via
# `TextEmbedding.list_supported_models()`), et télécharge `onnx/model.onnx`
# plus son `model.onnx_data` de 1,18 Go, le tokeniseur et la configuration.
#
# Le téléchargement passe par le CONSTRUCTEUR de `TextEmbedding` et non par un
# `snapshot_download` écrit à la main, pour une raison de contrat : c'est le
# code que le service empruntera au démarrage, donc la disposition du cache
# est juste PAR CONSTRUCTION. Un `snapshot_download` maison devrait deviner la
# liste des fichiers et la forme du dossier `models--…`, et se tromperait en
# silence le jour où la bibliothèque changerait d'avis.
#
# `MIZAN_CACHE_MODELES` est la variable que `noyau/dense.py:dossier_modeles()`
# consulte en priorité — elle a le dernier mot sur les deux emplacements par
# défaut. On la pose ici pour la construction ET pour l'exécution.
#
# ── ET LA VARIABLE SANS LAQUELLE CETTE IMAGE NE SE CONSTRUIT PAS ──────────
# `HF_HUB_DISABLE_SYMLINKS=1` force la bibliothèque à COPIER les fichiers du
# cache au lieu d'y poser des liens symboliques. Sans elle, le téléchargement
# ci-dessous échoue — et il échoue UNIQUEMENT SOUS LINUX, ce qui en fait le
# pire genre de panne : tout marche sur le poste de développement.
#
# Le mécanisme, parce qu'il ne se devine pas. Le modèle dépasse la limite de
# 2 Go du format protobuf, donc ses poids vivent dans un fichier séparé,
# `model.onnx_data` (1,18 Go), que `model.onnx` désigne par un chemin
# RELATIF. Le cache range les fichiers en blobs — `blobs/<2 car.>/<empreinte>`
# — et pose des liens dans le dossier de version. onnxruntime résout alors ce
# chemin relatif depuis la cible RÉELLE du lien, c'est-à-dire depuis
# `blobs/d5/`, tandis que les données sont sous `blobs/12/`. Il refuse, par
# une sécurité qui a raison de refuser :
#
#   FAIL : External data path validation failed for initializer
#          model.embed_tokens.weight.
#          External data path escapes model directory.
#
# Sous Windows, les liens symboliques demandent un privilège qu'on n'a
# généralement pas : la bibliothèque bascule d'elle-même en copie, les deux
# fichiers se retrouvent côte à côte, et le chemin relatif tombe juste. D'où
# un modèle qui se charge en développement et une image qui ne se construit
# pas. Cette variable rend Linux identique à ce qu'on éprouve ici.
ENV MIZAN_CACHE_MODELES=/opt/mizan/modeles
ENV HF_HOME=/opt/mizan/hf
ENV HF_HUB_DISABLE_SYMLINKS=1

# Les dossiers sont créés AVANT le téléchargement, et non après : la
# bibliothèque les créerait d'elle-même, mais alors avec le masque de root et
# à un moment qui dépend de son implémentation. Les créer ici rend le `chown`
# qui suit complet par construction.
# Le propriétaire est posé ICI, sur des dossiers VIDES : l'opération ne
# coûte alors que quelques inodes. La même opération après le
# téléchargement coûterait une recopie de 1,26 Go (voir plus bas).
RUN mkdir -p /opt/mizan/modeles /opt/mizan/hf && chown -R user:user /opt/mizan

# Endossé AVANT le téléchargement, pour la raison ci-dessus. Tout ce qui
# suit s'exécute donc sous l'UID 1000, celui que Hugging Face emploie.
USER user

# Le chemin n'est PAS réécrit en dur dans la commande : il est relu depuis
# `MIZAN_CACHE_MODELES`, la même variable que `noyau/dense.py` consultera au
# démarrage. Deux copies d'un même chemin dans un seul fichier finissent par
# différer, et celle-là différerait en silence — le modèle serait téléchargé
# à un endroit, cherché à un autre, et l'erreur dirait « modèle absent ».
#
# ── POURQUOI TOUT TIENT DANS UN SEUL `RUN`, ET C'EST MESURÉ ───────────────
# Le téléchargement, le ramassage des blobs et la relecture de contrôle sont
# enchaînés dans UNE couche. En deux couches — télécharger, puis nettoyer —
# l'image mesurait 4,23 Go : une couche ne peut pas alléger la précédente, et
# les blobs supprimés dans la seconde restaient présents dans la première.
# Le `rm` donnait l'illusion de l'économie sans l'économie.
#
# Et la relecture est placée APRÈS la suppression, exprès : si le nettoyage
# emportait un fichier nécessaire, la construction s'arrête ici plutôt que
# devant le premier visiteur.
RUN python -c "import os; from fastembed import TextEmbedding; d = os.environ['MIZAN_CACHE_MODELES']; TextEmbedding('google/embeddinggemma-300m', cache_dir=d); print('modele telecharge dans', d)" && rm -rf /opt/mizan/modeles/*/blobs && python -c "import os; from fastembed import TextEmbedding; d = os.environ['MIZAN_CACHE_MODELES']; m = TextEmbedding('google/embeddinggemma-300m', cache_dir=d); v = next(iter(m.embed(['essai de chargement']))); print('modele relu apres nettoyage, vecteur de', len(v), 'composantes')"

# À partir d'ici, plus aucun accès réseau à la bibliothèque de modèles n'est
# permis. Posé APRÈS le téléchargement, et pas avant, sinon la couche
# ci-dessus échouerait. `noyau/dense.py` force déjà le mode hors ligne le
# temps du chargement ; cette variable rend la propriété vraie pour tout le
# processus, y compris un code futur qui oublierait de passer par `_hors_ligne`.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# 2 vCPU sur le palier visé. Sans plafond, onnxruntime ouvre un fil par cœur
# visible du HÔTE — pas du conteneur — et se met à se battre contre lui-même.
ENV OMP_NUM_THREADS=2
#
# ── IL N'Y A PLUS DE `chown -R` ICI, ET C'EST MESURÉ ─────────────────────
# Ce fichier portait `RUN chown -R user:user /opt/mizan` à cet endroit. Un
# changement de propriétaire réécrit les métadonnées de chaque fichier, donc
# Docker RECOPIE tout le contenu dans la nouvelle couche : les 1,26 Go du
# modèle se retrouvaient DEUX FOIS dans l'image, qui mesurait 4,23 Go.
#
# Le propriétaire est désormais posé sur les dossiers quand ils sont encore
# VIDES, et l'utilisateur est endossé AVANT le téléchargement : les fichiers
# naissent avec le bon propriétaire, et aucune couche ne recopie l'autre.
#
# À retenir si l'on retouche ce fichier : ce n'est pas le `rm` d'un doublon
# qui allège une image — un `rm` dans une couche postérieure ne récupère
# rien — c'est de ne jamais écrire deux fois.

# ── ❹ Le code et l'index ───────────────────────────────────────────────────
# Dernière couche : c'est ce qui change à chaque correction. L'index vectoriel
# arrive avec, par `.cache_vecteurs/` — 1,8 Mo, versionné, scellé sur le
# corpus. Ce que `.dockerignore` laisse entrer est décidé là-bas, en
# n'autorisant que l'énumération explicite.
COPY --chown=user:user . /opt/mizan/

# (L'utilisateur a déjà été endossé plus haut, avant le téléchargement du
# modèle, pour que ses 1,26 Go naissent avec le bon propriétaire. Un
# second `USER user` ici ne ferait que laisser croire que c'est ici que
# ça se joue.)
ENV PYTHONPATH=/opt/mizan

# ── ❺ Le contrôle qui fait ÉCHOUER LA CONSTRUCTION, pas le Space ──────────
# Ce bloc est la pièce la plus utile du fichier. Il charge le noyau hors ligne
# et pose une vraie question, exactement comme le fera le service, et sans
# aucune clé de modèle. Il échoue donc ICI, dans un journal de construction
# qu'on lit, plutôt que sur un Space qui démarre et se déclare mort :
#
#   • index absent ou exclu par `.dockerignore`  → IndexAbsent
#   • index qui ne colle pas au corpus livré     → IndexAbsent (empreinte)
#   • modèle mal téléchargé ou mal placé         → ModeleAbsent
#   • `libgomp1` oubliée                         → ImportError onnxruntime
#
# `sur` n'est PAS vérifié : la question peut légitimement tomber sous le seuil
# d'abstention, et exiger une certitude ici reviendrait à épingler un chiffre
# de récupération dans un Dockerfile — le genre de nombre qui dérive et qu'on
# finit par contourner. Ce qu'on vérifie, c'est que la chaîne répond et que
# l'avertissement de consolidation est bien là.
RUN python -c "import noyau; m = noyau.charger(); r = m.chercher('duree du preavis de licenciement'); assert r.articles, 'aucun article recupere'; assert r.avertissement.strip(), 'avertissement de consolidation vide'; print('noyau OK :', len(r.articles), 'articles,', 'sur' if r.sur else 'doute', '| avertissement present')"

# Le second contrôle : le point d'entrée que `CMD` lancera existe-t-il, et
# porte-t-il bien un objet `app` ?
#
# Il est séparé du précédent pour que l'échec dise LEQUEL des deux a cassé.
# Et il existe parce qu'une image qui se construit en vert puis meurt sur son
# `CMD` est le pire des livrables : le journal de construction est propre, et
# la panne n'apparaît qu'au démarrage du Space, où elle ressemble à un
# problème de plateforme.
#
# ⚠️ Ce contrôle ÉCHOUE TANT QUE `service/app.py` N'EXISTE PAS. C'est voulu :
# `service/` est écrit par un autre agent, et la convention arrêtée est
# `service/app.py`, objet `app`, port 7860, statique dans `service/statique/`.
# Tant que le fichier manque, l'image n'est pas déployable, et il vaut mieux
# que la construction le dise que de livrer un conteneur qui redémarre en
# boucle.
#
# L'import exécute le module, donc le fil de chargement d'arrière-plan décrit
# dans DEPLOIEMENT.md §4 — il est `daemon`, le processus rend la main aussitôt.
# Si cet import BLOQUE, c'est que le chargement est fait au niveau du module
# ou dans le `lifespan` au lieu d'un fil : la panne du §4, attrapée ici.
RUN python -c "import importlib; m = importlib.import_module('service.app'); assert hasattr(m, 'app'), \"service/app.py n'expose pas d'objet 'app'\"; print('service.app:app importable')"

# ── ❻ Le service ───────────────────────────────────────────────────────────
EXPOSE 7860

# UN SEUL worker, et c'est une contrainte et non un défaut de réglage : chaque
# worker ouvrirait sa propre session ONNX, donc ~870 Mo de plus. Deux workers
# tiendraient dans les 16 Go, mais ne serviraient à rien — une question coûte
# 23 ms de médiane mesurée (`arbitrage/res_cout.json`), la concurrence n'est
# pas le problème de cette démonstration.
#
# ⚠️ CE QUE LE SERVICE DOIT FAIRE, ET QUE CE FICHIER NE PEUT PAS GARANTIR
# `uvicorn` exécute le démarrage du cycle de vie AVANT d'ouvrir la prise
# réseau. Un `charger()` appelé dans le `lifespan` de FastAPI retarde donc le
# port d'autant — 2,8 s mesurées sur un poste tiède, davantage sur un Space
# froid qui lit 1,2 Go de poids depuis un système de fichiers superposé. Si le
# contrôle de Hugging Face arrive pendant ce temps, le Space est déclaré mort.
# `service/app.py` doit charger dans un FIL D'ARRIÈRE-PLAN et répondre tout de
# suite, en disant « pas encore prêt ». Le détail est dans DEPLOIEMENT.md, §4.
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]

# Le contrôle de santé sert aux exécutions LOCALES : Hugging Face interroge le
# port lui-même et ne lit pas cette directive. La période de grâce est longue
# exprès — un contrôle qui tue un service pendant son préchauffage reproduit
# dans Docker exactement la panne qu'on cherche à éviter sur le Space.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/sante', timeout=4).status == 200 else 1)"
