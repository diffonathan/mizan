# Déployer Mizan sur Hugging Face Spaces

Cible : **Space, SDK Docker, palier CPU Basic (gratuit)** — 2 vCPU, 16 Go de
RAM, 50 Go de disque.

Ce document est une recette. Les décisions qui l'ont produite sont dans les
commentaires du [`Dockerfile`](Dockerfile) et dans le paragraphe de
[`.gitignore`](.gitignore) qui lève l'interdiction de versionner l'index.

> **Ce qui n'a pas été éprouvé est marqué 🔲 dans tout ce document.** Aucun
> Space n'a été créé, et la construction de l'image n'a pas été jouée en
> entier sur cette machine. Les trous sont nommés à l'endroit où ils vous
> concernent, plutôt que résumés en bas de page. Voir aussi le §8.

---

## 1. Ce qu'il faut savoir avant de commencer

| | |
|---|---|
| le modèle de plongement | **1,2 Go**, téléchargé **à la construction de l'image** |
| l'index vectoriel | **1,8 Mo**, **versionné** dans le dépôt, jamais reconstruit au démarrage |
| mémoire au service | ~870 Mo de pic mesurés (`arbitrage/res_cout.json`) |
| port | **7860**, imposé par Hugging Face |
| clé de modèle | **secret du Space**, jamais un fichier — et l'application démarre sans |

**Le disque d'un Space n'est pas persistant.** Il repart à zéro à chaque
redémarrage ; l'image, elle, est mise en cache. C'est tout ce qui explique la
forme du `Dockerfile` : ce qui coûte cher est placé dans l'image, pas sur le
disque.

---

## 2. Créer le Space

1. <https://huggingface.co/new-space>
2. **Space SDK → Docker → Blank**. Pas Gradio : Gradio imposerait son
   apparence, et la charte du projet (palette 19, violet profond, l'or porte
   les citations) n'est pas négociable.
3. **Space hardware → CPU basic · 2 vCPU · 16 GB** (gratuit).
4. Visibilité : **Public** si le but est de donner l'adresse.

### Le bloc de configuration en tête de `README.md`

Hugging Face lit la configuration du Space dans un entête YAML au début du
`README.md` **du dépôt du Space**. Sans lui, le Space ne sait pas qu'il est en
Docker ni sur quel port frapper.

**Cet entête est en place**, en tête de `README.md`. Il n'est pas recopié ici :
le fichier livré est la source, et deux copies d'un même bloc de configuration
finiraient par se contredire sans que rien ne le signale. Pour le relire :

```sh
sed -n '1,10p' README.md
```

Il déclare `sdk: docker` et `app_port: 7860` — le port qu'`EXPOSE` et `CMD`
ouvrent dans le `Dockerfile` — et des couleurs prises dans la charte : Hugging
Face n'accepte que huit noms, dont `purple`, le plus proche du violet profond
de la palette 19.

**C'est le seul endroit de cette recette où deux exigences se contredisent**,
et il vaut mieux le dire que le découvrir : le `README.md` de ce dépôt est le
dossier du projet, et GitHub affiche un entête YAML comme un tableau en haut
de page. Trois sorties étaient possibles, dans l'ordre de ce qu'elles
coûtent :

- **Space et GitHub en dépôts séparés** (recommandé). Le Space reçoit le
  `README.md` que Hugging Face a généré, avec l'entête et trois lignes de
  présentation ; le dossier du projet reste sur GitHub, intact. C'est deux
  `git remote`, et aucun compromis sur l'un ou l'autre.
- **Entête ajouté au `README.md` du projet — c'est la sortie retenue.** Un
  dépôt unique, au prix d'un tableau de configuration en haut de la page
  GitHub. Choisie parce qu'un README de Space séparé est un deuxième document
  à tenir à jour, et que c'est là que les deux versions divergent.
- **Entête minimal sur le Space, dossier déplacé** dans un `DOSSIER.md` lié
  depuis le `README.md`. Le plus propre des trois, le plus intrusif pour le
  projet.

🔲 Non éprouvé : l'entête est écrit et conforme à ce que Hugging Face
documente, mais aucun Space n'a été construit avec lui — le seul contrôle
qui vaille est une construction verte.

---

## 3. Poser le secret `LLM_API_KEY`

**Settings → Variables and secrets → New secret.**

| nom | type | valeur |
|---|---|---|
| `LLM_API_KEY` | **Secret** | la clé chez le fournisseur |
| `LLM_PROVIDER` | Variable | `groq`, `openai`, `openrouter` ou `mistral` |
| `LLM_MODEL` | Variable | le nom du modèle **chez ce fournisseur** |

Les trois noms sont la convention du projet, reprise des autres projets de
l'auteur : un modèle retiré par son fournisseur se répare en changeant une
variable, pas du code.

Trois choses à savoir, et la troisième surprend :

- `LLM_API_KEY` doit être un **Secret** et non une Variable. Une Variable est
  visible de toute personne qui ouvre la page du Space.
- `LLM_MODEL` **n'a pas de valeur par défaut dans le code**, exprès
  (`moteur/llm.py`). Une clé posée sans `LLM_MODEL` ne rédige pas davantage
  qu'une absence de clé — le client refuse de se construire et le dit.
- Les secrets ne sont **pas** disponibles pendant la construction de l'image,
  seulement à l'exécution. Ce n'est pas une gêne ici : rien dans le
  `Dockerfile` n'en a besoin, et c'est volontaire.

### Ce qui se passe SANS la clé — le cas normal, pas le cas dégradé

**L'application démarre et fonctionne.** C'est une exigence, pas une
tolérance : la récupération est réelle et mesurée, c'est elle l'argument du
projet, et elle ne demande aucune clé.

Ce qui change : **la rédaction est FACTICE**, produite par
`moteur.llm.ModeleFactice`, un rédacteur déterministe qui assemble des phrases
à partir des articles réellement récupérés. Il n'a pas le style d'un modèle de
langue et n'essaie pas de l'avoir.

**L'écran doit le dire, visiblement.** Un visiteur ne doit jamais pouvoir
croire qu'un vrai modèle a rédigé ce qu'il lit. Ce n'est pas une mention
légale à mettre en pied de page en gris clair : c'est la différence entre une
démonstration honnête et une démonstration trompeuse, sur un outil juridique.

⚠️ **Le piège qui empêcherait l'application de démarrer sans clé.**
`moteur.repondre.charger()` appelle `charger_redacteur()`, qui lève
`CleAbsente` quand `LLM_API_KEY` est vide. Appelé nu, il **fait donc échouer
le démarrage sans clé** — l'inverse de ce qu'on veut ici. Le service doit
rattraper cette erreur et repasser la main au factice :

```python
from moteur.repondre import charger
from moteur.llm import CleAbsente, ModeleFactice, charger_redacteur

try:
    moteur, rédaction_réelle = charger(charger_redacteur()), True
except CleAbsente:
    # Pas une panne : le mode sans clé est un mode de fonctionnement prévu.
    # `rédaction_réelle` remonte jusqu'à l'écran, qui DOIT l'afficher.
    moteur, rédaction_réelle = charger(ModeleFactice("fidele")), False
```

Ne rattrapez que `CleAbsente`. Les autres `ErreurModele` — `CleRefusee`,
`ModeleRetire`, `QuotaDepasse`, `ServiceIndisponible` — sont de vraies pannes
d'exploitation : les traduire en rédaction factice masquerait une panne
derrière un comportement de produit, et le visiteur lirait du factice en
croyant que la clé fonctionne.

---

## 4. Le démarrage à froid et le contrôle de santé

**C'est le point qui coûte un déploiement quand on le rate**, et il a déjà
coûté une migration sur un autre projet de l'auteur — un contrôle de santé
arrivé à 16 s sur un service qui n'était pas prêt.

### Le mécanisme

Hugging Face attend que **le port 7860 réponde**. `uvicorn` exécute le
démarrage du cycle de vie (`lifespan`) **avant d'ouvrir la prise réseau**.
Donc :

```
charger() dans le lifespan   →  le port n'existe pas pendant tout le chargement
                             →  si le contrôle arrive avant, le Space est déclaré mort
```

Mesuré sur un poste tiède, index et modèle en cache système chaud :

```sh
python -c "import time; t=time.perf_counter(); import noyau; m=noyau.charger(); print('%.2f s' % (time.perf_counter()-t))"
```

→ **2,83 s**, dont 2,77 s pour `charger()` lui-même.

🔲 Ce chiffre n'est **pas** celui d'un Space froid. Il suppose les 1,2 Go de
poids déjà dans le cache de fichiers du système. Sur un conteneur qui démarre
et lit depuis un système de fichiers superposé, comptez davantage — et c'est
exactement pourquoi la conception ci-dessous ne parie pas sur une durée.

### Ce que `service/app.py` doit faire

**Ouvrir le port d'abord, charger ensuite, dans un fil d'arrière-plan.**

```python
import threading
from fastapi import FastAPI

app = FastAPI()
_etat = {"pret": False, "erreur": None, "redaction_reelle": False}

def _charger_en_fond() -> None:
    try:
        # ... le bloc du §3 ...
        _etat["pret"] = True
    except Exception as erreur:           # journalisé, pas avalé
        _etat["erreur"] = f"{type(erreur).__name__}: {erreur}"

# Le fil est LANCÉ, jamais attendu : la prise réseau s'ouvre tout de suite.
threading.Thread(target=_charger_en_fond, daemon=True).start()

@app.get("/sante")
def sante():
    # 200 DÈS QUE LE PROCESSUS VIT, même pas prêt. C'est le contrat avec
    # Hugging Face : « le port répond » n'est pas « le moteur est chaud ».
    return {"pret": _etat["pret"], "erreur": _etat["erreur"],
            "redaction_reelle": _etat["redaction_reelle"]}
```

Trois règles qui vont avec, et qu'on regrette de ne pas avoir suivies :

1. **`/sante` rend 200 même pendant le chargement.** Rendre 503 pendant le
   préchauffage, c'est reconstruire soi-même la panne qu'on évitait.
2. **L'interface gère `pret: false`** — un écran d'attente qui dit ce qui se
   passe, et qui réessaie. Pas une page blanche, pas une erreur.
3. **Une erreur de chargement est MONTRÉE**, pas avalée. Un index qui ne colle
   pas au corpus doit s'afficher comme tel ; sinon le Space est « vivant » et
   muet, l'état le plus coûteux à diagnostiquer.

Le `HEALTHCHECK` du `Dockerfile` vise `/sante` avec 120 s de période de grâce.
Il sert aux exécutions **locales** : Hugging Face interroge le port lui-même
et ne lit pas cette directive.

🔲 Non éprouvé : `service/app.py` n'existait pas quand ce document a été
écrit. Le §4 est un **contrat proposé** à l'agent qui l'écrit, pas la
description d'un code lu. `/sante` est le nom retenu ici et dans le
`Dockerfile` ; s'il change, les deux changent ensemble.

---

## 5. Envoyer le code

```sh
git remote add space https://huggingface.co/spaces/<compte>/mizan
git push space main
```

Vérifiez **avant de pousser** que l'index part bien — c'est la seule chose de
cette recette qui ne se répare pas en changeant une variable :

```sh
git ls-files --error-unmatch .cache_vecteurs/dense-google_embeddinggemma-300m.npz
```

Si la commande échoue, l'index n'est pas suivi. Ajoutez-le :

```sh
git add -f .cache_vecteurs/dense-google_embeddinggemma-300m.npz
```

Le `-f` n'est pas nécessaire depuis que `.gitignore` porte l'exception ; il ne
nuit pas et dépanne un clone dont le `.gitignore` serait antérieur.

> Hugging Face impose Git LFS au-delà de 10 Mo par fichier. L'index pèse
> 1,8 Mo : rien à faire. Le modèle, lui, n'est jamais dans le dépôt — il est
> téléchargé à la construction.

---

## 6. La construction

Elle se suit dans l'onglet **Logs → Build** du Space.

| étape | ce qui se passe | durée attendue |
|---|---|---|
| base + `libgomp1` | `apt-get` | ~20 s |
| `requirements.txt` | pymupdf, fastembed, onnxruntime, numpy | 1 à 3 min |
| **le modèle** | **1,2 Go** depuis Hugging Face | **2 à 6 min** |
| le code et l'index | quelques Mo | quelques s |
| **contrôle 1** | charge le noyau et pose une vraie question | ~5 s |
| **contrôle 2** | importe `service.app` et vérifie l'objet `app` | ~5 s |

🔲 **Ces durées sont des estimations, pas des mesures.** La construction n'a
pas été jouée. Le téléchargement du modèle part d'une machine Hugging Face
vers un registre Hugging Face, ce qui devrait jouer en sa faveur.

Repère : **comptez 5 à 12 minutes** pour la première construction, et une
poignée de secondes pour les suivantes qui ne touchent qu'au code — la couche
du modèle est placée **avant** la copie du code, exprès, pour que corriger
l'interface ne coûte pas 1,2 Go.

### Le contrôle de construction, et pourquoi il est là

Les deux dernières couches du `Dockerfile` chargent le noyau hors ligne et
posent une question, sans clé, puis importent le point d'entrée du service.
**Elles font échouer la construction** plutôt que de produire un Space qui
démarre et se déclare mort. Elles attrapent :

| ce qui a été raté | ce que la construction imprime |
|---|---|
| index absent du contexte (`.dockerignore` trop large) | `IndexAbsent: Index vectoriel absent` |
| index qui ne colle pas au corpus livré | `IndexAbsent: … calculé sur un autre corpus` |
| modèle mal téléchargé ou mal placé | `ModeleAbsent: Modèle … introuvable hors ligne` |
| `libgomp1` oubliée | `ImportError` sur une bibliothèque partagée |
| `service/app.py` absent | `ModuleNotFoundError: No module named 'service'` |
| `service/app.py` sans objet `app` | `AssertionError: … n'expose pas d'objet 'app'` |
| chargement bloquant au niveau du module | **la construction se fige** sur le contrôle 2 — c'est la panne du §4, attrapée avant le Space |

Un journal de construction se lit. Un Space mort ne dit rien.

⚠️ **Le contrôle 2 échoue tant que `service/app.py` n'existe pas**, et c'est
voulu. `service/` est écrit par un autre agent ; tant qu'il manque, l'image
n'est pas déployable, et mieux vaut l'apprendre d'une construction rouge que
d'un conteneur qui redémarre en boucle. Si vous devez construire avant que
`service/` existe — pour éprouver les couches du modèle et de l'index —
commentez cette seule ligne du `Dockerfile`, et remettez-la ensuite.

---

## 7. Ce qui tombe en panne si on se trompe

La partie que les documents de déploiement omettent.

### L'index n'est pas parti dans le dépôt
**Symptôme :** la construction échoue au contrôle, sur `IndexAbsent`.
**Pourquoi c'est une bonne nouvelle :** l'erreur est dans un journal de
construction. Sans ce contrôle, le Space démarrerait, et chaque question
rendrait une erreur — ou, pire, le service tenterait, à chaque redémarrage,
une indexation d'un quart d'heure avec un pic d'une dizaine de gigaoctets.
L'ordre de grandeur et sa dispersion se lisent au §6 de CONCEPTION.md, qui
est la source pour ces deux grandeurs ; aucune valeur précise n'est recopiée
ici, parce qu'elle dépend de la charge de la machine et vieillirait dans ce
document sans que rien ne le signale.
**Réparation :** `git add -f` l'index, repousser.

### Le corpus a été réextrait sans reconstruire l'index
**Symptôme :** `IndexAbsent: … calculé sur un autre corpus (empreinte …)`.
**Pourquoi ça compte :** c'est le mode de panne que le mécanisme d'empreinte
existe pour rendre bruyant. Sans lui, les vecteurs seraient décalés d'un cran
et le service rendrait **des réponses fausses mais plausibles** — sur un outil
juridique, le pire des comportements.
**Réparation :**
```sh
python -m noyau.indexer --forcer
git add -f .cache_vecteurs/dense-google_embeddinggemma-300m.npz
```

### Le modèle a été laissé au premier appel
**Symptôme :** le premier visiteur après chaque redémarrage attend le
téléchargement de 1,2 Go. Ou, plus probablement, n'attend pas.
**Pourquoi ça arrive :** le disque n'est pas persistant. Un cache construit à
l'exécution disparaît au redémarrage suivant ; une couche d'image, non.
**Réparation :** ne pas toucher à la couche ❸ du `Dockerfile`, et surtout pas
à `MIZAN_CACHE_MODELES`, qui est ce qui relie le cache construit au cache lu.

### `charger()` a été appelé dans le `lifespan`
**Symptôme :** le Space reste en « Building » puis passe en « Runtime error »,
sans qu'aucune ligne du journal n'indique une faute. C'est la panne la plus
chère à diagnostiquer de cette liste, parce qu'elle ressemble à un problème de
code alors que c'est un problème d'ordre.
**Réparation :** le §4.

### `LLM_API_KEY` posé en Variable au lieu de Secret
**Symptôme :** aucun — **et c'est le problème**. L'application fonctionne, et
la clé est lisible par tout visiteur de la page du Space.
**Réparation :** retirer la Variable, **révoquer la clé chez le
fournisseur**, en créer une autre, la poser en Secret. Une clé exposée reste
exposée après sa suppression de l'interface.

### Une clé posée, mais pas `LLM_MODEL`
**Symptôme :** la rédaction reste factice alors que la clé est là, et
l'écran continue de l'annoncer.
**Pourquoi :** le nom du modèle n'est pas écrit dans le code, exprès — un
fournisseur peut le retirer sans préavis. Le client refuse de se construire
sans lui.
**Réparation :** poser `LLM_MODEL`, redémarrer le Space.

### Le Space a été créé en SDK Gradio
**Symptôme :** le `Dockerfile` est ignoré, le Space cherche un `app.py` à la
racine.
**Réparation :** `sdk: docker` dans l'entête YAML du `README.md`, ou recréer
le Space. Changer le matériel ne change pas le SDK.

### `*.md` a été retiré du `.dockerignore`
**Symptôme :** aucun à court terme. L'image grossit de quelques centaines de
kilooctets de documents. Mentionné parce que l'inverse — réautoriser trop
largement avec un `!` — est la seule façon de faire entrer les 4,1 Go de
`prototypes/` dans le contexte, et que le `.dockerignore` fonctionne par
énumération explicite précisément pour que ça n'arrive pas par oubli.

---

## 8. Ce qui n'a pas été éprouvé

Dit franchement, parce qu'une recette dont les trous sont nommés vaut mieux
qu'une recette qui prétend avoir été jouée.

**Ce qui EST vérifié sur cette machine :**

- l'index versionné **colle au corpus versionné** — empreinte
  `9349e6a0178abd33…`, identique dans le `.npz` et recalculée sur le corpus ;
- le **refus** d'un index dont l'empreinte ne correspond pas, par le chemin de
  production, épinglé par `tests/test_index_scelle.py` (5 tests) ;
- la suite complète : **333 tests, 0 échec, code de sortie 0**, sur
  l'interpréteur du dépôt comme sur un interpréteur nu — **42 sautés** sur
  l'interpréteur nu (ceux qui demandent l'index dense), **aucun** sur celui du
  dépôt. La commande est écrite juste en dessous, et elle l'est parce qu'il a
  longtemps figuré ici « 200 tests, 14 sautés » : un chiffre faux dans une
  recette de mise en ligne est un chiffre que personne ne vérifie, puisque
  c'est le document qu'on suit.

  ```sh
  python -m unittest discover -s tests -t tests -q
  prototypes/vectoriel/.venv/Scripts/python.exe -m unittest discover -s tests -t tests -q
  ```

  Ce total monte à chaque test ajouté. Ce qui ne bouge pas, et qui est la vraie
  exigence avant de pousser, c'est **OK sur les deux interpréteurs, code 0, et
  aucun saut sur celui du dépôt** ; le tableau des totaux a pour source unique
  `MESURES.md` §E ;
- le chargement du noyau et une vraie question, **sans clé**, en 2,83 s ;
- l'exception du `.gitignore` : l'index est versionnable, **tous** les autres
  fichiers de vecteurs du dépôt restent ignorés ;
- la source Hugging Face que `fastembed` emploie pour ce modèle
  (`onnx-community/embeddinggemma-300m-ONNX`), lue dans
  `TextEmbedding.list_supported_models()` et non supposée.

**Ce qui n'est PAS éprouvé :**

- 🔲 **La construction de l'image, en entier.** Le démon Docker n'était pas
  disponible pendant la rédaction. Les couches sont écrites à partir des
  chemins réellement lus dans `noyau/dense.py` et du contenu réel du cache de
  modèles sur cette machine, mais **aucune n'a été exécutée**.
- 🔲 **Le téléchargement du modèle à la construction.** Le chemin choisi est
  le constructeur de `TextEmbedding`, c'est-à-dire le même code que celui qui
  relira le cache — la disposition est donc juste par construction plutôt que
  par supposition. Reste à le voir tourner.
- 🔲 **La sémantique exacte de `.dockerignore`** sur le motif « tout exclure
  puis réautoriser un fichier dans un dossier exclu ». C'est l'idiome
  documenté, et le contrôle de la couche ❺ échouerait bruyamment s'il ne
  fonctionnait pas — mais il n'a pas été observé ici.
- 🔲 **Tout le §2 et le §5** : aucun Space n'a été créé, aucun `git push`
  vers Hugging Face n'a été fait.
- 🔲 **Les durées de construction du §6**, qui sont des estimations.
- 🔲 **Le démarrage à froid sur un Space.** 2,83 s est une mesure locale à
  cache chaud, et elle ne se transporte pas.
- 🔲 **`service/app.py`**, qui n'existait pas : le §4 est un contrat proposé.
- 🔲 **La rédaction par un vrai modèle.** Aucune clé n'existe dans cet
  environnement. C'est la réserve n°4 du `README.md`, et le déploiement ne la
  lève pas.

### La limite connue du mécanisme d'empreinte

L'empreinte scelle l'index sur le **corpus**, pas sur le **modèle de
plongement** : on ne prend pas l'empreinte de 1,2 Go de poids à chaque
démarrage. Le nom du modèle écrit dans les métadonnées du `.npz` est la seule
trace de ce couple.

Conséquence : **changer de modèle d'embedding, ou de version d'`onnxruntime`
assez pour déplacer les vecteurs, passerait le contrôle sans rien dire.** Les
versions de `requirements.txt` sont épinglées pour cette raison, et l'image
fixe Python 3.12 pour la même. C'est le trou résiduel, il est étroit, et il
est écrit ici plutôt que laissé à découvrir.

---

## 9. Vérifications locales

Elles n'exigent ni Space ni clé.

```sh
# L'index livré colle-t-il au corpus livré, et le refus fonctionne-t-il ?
python tests/test_index_scelle.py

# La suite entière.
python -m unittest discover -s tests -t tests -q

# L'index part-il bien dans le dépôt ?
git ls-files --error-unmatch .cache_vecteurs/dense-google_embeddinggemma-300m.npz

# Ce que Docker enverrait vraiment (exige le démon).
docker build -t mizan .
docker run --rm -p 7860:7860 mizan
# puis : http://127.0.0.1:7860/sante  →  {"pret": …, "redaction_reelle": false}
```

Pour éprouver le mode **avec** clé en local, sans la mettre dans un fichier :

```sh
docker run --rm -p 7860:7860 \
  -e LLM_PROVIDER=groq -e LLM_MODEL=<le modèle> -e LLM_API_KEY=<la clé> \
  mizan
```

`-e` et non un fichier : une clé dans un fichier du dossier finit par être
committée. Sur le Space, c'est un Secret et rien d'autre.
