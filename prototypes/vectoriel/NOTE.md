# Récupération vectorielle pour Mizan — note de défense

Prototype jetable, mesuré le 4 octobre 2026 sur les 589 articles de
`corpus/code-travail.json`. Aucun fichier de production n'a été écrit.
Supprimer le dossier `prototypes/vectoriel/` suffit à tout annuler.

Tout est installé dans `prototypes/vectoriel/.venv`, **jamais dans le Python
partagé** : un autre agent pouvait travailler au même moment sur le même
environnement, et un `pip install` dans `site-packages` l'aurait concerné.

### Comment lire les chiffres de cette note

Cette note a été relue en relançant ses propres commandes. La relecture a montré
que deux familles de chiffres ne se comportent pas du tout pareil, et elles ne
sont donc plus écrites pareil.

- **Ce qui se reproduit** — rappels, comptes d'articles, dimensions, tailles de
  fichier, rapports entre deux tailles — est donné en valeur exacte, avec la
  commande qui l'imprime. Quelqu'un qui clone le dépôt et lance la commande
  retrouve le chiffre.
- **Ce qui ne se reproduit pas** — durées, pics mémoire — est donné en **ordre de
  grandeur**. Ces mesures viennent d'une machine de bureau partagée : d'une
  exécution à l'autre, sur la même machine et le même code, l'indexation MiniLM a
  été relevée entre 11 et 15 s. Publier « 11,0 s » comme un fait, c'était publier
  un chiffre qui dérive au prochain rejeu. L'ordre de grandeur, lui, tient sur
  n'importe quelle machine, et c'est lui qui porte les décisions de cette note.
  Les secondes brutes des exécutions citées restent dans les `res_*.json` pour qui
  veut les regarder, mais elles valent pour cette exécution-là, pas comme
  référence.

Un cas mérite d'être signalé d'emblée, parce qu'il a failli condamner une
configuration qui tient en réalité : **deux chiffres de cette note étaient faux
d'un facteur 70 et d'un facteur 9, et pour la même raison** — une latence de
service mesurée dans le processus qui venait de faire l'indexation. Les deux sont
expliqués en section 2.

---

## 1. Ce que j'ai mesuré, pas ce que j'espérais

### Le banc

34 questions écrites à la main (`banc.py`), chacune après lecture de l'article
qui y répond. Elles sont posées dans la langue d'un usager — « on m'a viré »,
« ma femme accouche » — parce que recopier les mots du législateur dans la
question aurait fabriqué un banc que le vectoriel gagne d'avance.

Quatre paires sont volontairement hostiles à mon approche, parce que c'est là
qu'elle est dangereuse : naissance (269) contre maternité (152), âge d'admission
(143) contre âge de la retraite (526), délai de recours de 90 jours (65) contre
prescription de deux ans (395), seuil de dix salariés (430) contre seuil de
cinquante (336). Trois questions supplémentaires n'ont **aucune** réponse dans
le corpus ; elles ne comptent pas dans le rappel et servent à voir si l'approche
sait se taire.

La liste `attendu` est tenue au plus court. Pour Q29 par exemple, l'article 392
(économats) serait une seconde réponse défendable, mais seul l'article 362
(« les salaires doivent être payés en monnaie marocaine ») répond vraiment :
élargir la cible aurait gonflé mon rappel sans améliorer la réponse rendue.

### Les chiffres

```
.venv/Scripts/python.exe mesurer.py --rapide        # témoin + modèles légers
.venv/Scripts/python.exe mesurer.py --une 5         # embeddinggemma seul, processus neuf
.venv/Scripts/python.exe mesurer.py --une 7         # e5-large seul
.venv/Scripts/python.exe cout_service.py <modele>   # latence EN SERVICE, index déjà en cache
```

Les rappels sont exacts et déterministes : à index donné, les mêmes questions
donnent les mêmes rangs. Les deux colonnes de temps sont des ordres de grandeur,
pour la raison dite en tête de note. Surtout, **indexation et service sont deux
régimes différents, et la latence de service se lit avec `cout_service.py`, pas
avec `mesurer.py`** — c'est la confusion des deux qui a produit les deux chiffres
faux de la section 2.

| approche | poids disque | indexation des 588 | requête en service | @1 | @3 | @5 |
|---|---|---|---|---|---|---|
| **témoin BM25** (zéro dépendance) | 0 Mo | < 0,1 s | < 1 ms | 0,147 | 0,294 | 0,294 |
| potion-multilingual-128M | 522 Mo | quelques secondes | < 1 ms | 0,235 | 0,235 | 0,265 |
| MiniLM-L12 multilingue | 241 Mo | ~ 10 s | quelques ms | 0,353 | 0,500 | 0,500 |
| multilingual-e5-large | 2 149 Mo | ~ 1 h | quelques dizaines de ms (~ 2 × gemma) | 0,441 | 0,618 | 0,735 |
| **embeddinggemma-300m** | 1 199 Mo | ~ 15 min | ~ 20 ms | **0,588** | **0,853** | **0,853** |

**La case de e5 ne porte plus de millisecondes, et c'est délibéré.** Cette note a
publié « ~ 100 ms » ici, puis en a tiré au §5 la conclusion « un ordre de
grandeur plus lent que gemma ». Les deux sont fausses, et pour la cause que la
section 2 décrit déjà deux fois : une durée recopiée dans la prose au lieu d'être
renvoyée là où elle est mesurée. Ce qui se reproduit est le **rapport** e5/gemma,
parce que ses deux termes sont relevés dans la même exécution et subissent donc
la même charge — il vaut **un peu plus du double**. Ce rapport a un seul document
source, [`../../CONCEPTION.md`](../../CONCEPTION.md) §7, qui le publie avec ses
quatre paires mesurées ; cette note y renvoie au lieu d'en garder une copie qui
dériverait de son côté.

Ce que ces ordres de grandeur disent, et qui se reproduit partout : entre le plus
léger et le plus lourd, l'indexation couvre **plus de trois ordres de grandeur**
(la seconde contre l'heure) et la latence de service **deux ordres de grandeur**
(la fraction de milliseconde contre quelques dizaines). Entre MiniLM et gemma,
les deux candidats réels, l'indexation sépare de **près de deux ordres de grandeur** (la dizaine de
secondes contre le quart d'heure) tandis que la latence de service reste **du même
ordre** (quelques millisecondes contre quelques dizaines). C'est cette asymétrie
qui porte la recommandation de la section 5, et non des secondes précises.

Il n'y a plus de colonne mémoire : voir « la colonne que j'ai retirée », en
section 2.

Le poids disque est mesuré (`du -sm .cache_modeles/*/`) et non repris du champ
`size_in_GB` de fastembed. Ce champ, lui, s'imprime ainsi :

```
.venv/Scripts/python.exe -c "from fastembed import TextEmbedding as T; print(*sorted((round(d['size_in_GB']*1024), d['model']) for d in T.list_supported_models() if 'multilingual' in d['model'] or 'gemma' in d['model']), sep=chr(10))"
```

Annoncé / mesuré : 225 / 241 Mo pour MiniLM, 524 / 522 Mo pour potion,
1 270 / 1 199 Mo pour gemma, 2 294 / 2 149 Mo pour e5 — soit un écart de +7 %,
−0,4 %, −5,6 % et −6,3 %. L'annonce est donc utilisable pour choisir un modèle
sans l'avoir téléchargé, mais ce sont les valeurs mesurées qui sont dans le
tableau. Les valeurs annoncées que j'avais publiées — 220, 1 240 et 2 240 Mo —
n'étaient produites par aucune commande et étaient fausses de quelques
mégaoctets ; la commande ci-dessus est là pour que personne n'ait à me croire.

S'y ajoutent **172 Mo** de paquets Python, mesurés en section 2.

### Deux décisions, mesurées plutôt que supposées

**L'entête hiérarchique rapporte.** Plonger l'article précédé des intitulés de
son livre / titre / chapitre / section, au lieu de son texte seul, fait passer
MiniLM de 0,294 à 0,353 en @1 et de 0,441 à 0,500 en @3. C'est logique : le mot
« congé annuel » n'apparaît pas dans la première phrase de l'article 231, il est
dans le titre du chapitre.

**Le centrage anti-hubness ne rapporte rien — il coûte.** Retirer le vecteur
moyen du corpus est le remède classique à la hubness. Mesuré sur les trois
modèles, il dégrade systématiquement : gemma 0,853 → 0,765 en @3, e5 0,618 →
0,588, MiniLM 0,500 → 0,382. Je l'ai gardé dans le code (`centrer=True`) avec
son résultat négatif, parce que c'est l'idée que n'importe qui proposerait en
voyant le diagnostic de la section 3.

Le découpage des articles longs en passages de 600 caractères n'a rien donné de
net sur MiniLM (@1 identique, @3 0,500 → 0,441, @5 0,500 → 0,529) pour 195
vecteurs de plus. La médiane d'un article est de 390 caractères : il n'y a
presque rien à découper.

Ces trois décisions reposent sur des rappels, pas sur des durées : elles se
rejouent à l'identique avec `mesurer.py --rapide`.

---

## 2. Le coût réel

Pour la configuration que je recommande (embeddinggemma-300m, entête
hiérarchique, pas de découpage, pas de centrage) :

- **Environ 1 370 Mo sur disque** : 172 Mo de paquets + 1 199 Mo de modèle, les
  deux par `du -sm`. C'est la seule ligne de coût de cette section qui soit un
  chiffre exact plutôt qu'un ordre de grandeur, parce qu'une taille de fichier,
  elle, ne dérive pas.
- **Paquets installés** : `fastembed` seul en commande `pip`, qui tire
  `onnxruntime` (46 Mo, le moteur d'inférence), `numpy` (54 Mo avec ses
  bibliothèques natives), `tokenizers` (8 Mo), `huggingface-hub` + `hf_xet`
  (16 Mo, le téléchargement du modèle), `pillow` (16 Mo, inutile ici mais
  dépendance dure de fastembed pour ses modèles d'image). Mesure du total, puis
  du détail par paquet — avant que la troisième ligne soit écrite, les poids
  paquet par paquet de cette liste n'étaient produits par aucune commande :

  ```
  .venv/Scripts/python.exe -c "from pathlib import Path; print(round(sum(f.stat().st_size for f in Path('.venv/Lib/site-packages').rglob('*') if f.is_file())/1e6,1),'Mo de contenu')"
  du -sm .venv/Lib/site-packages/
  .venv/Scripts/python.exe -c "from pathlib import Path; [print(round(sum(f.stat().st_size for f in d.rglob('*') if f.is_file())/1e6,1),'Mo',d.name) for d in sorted(Path('.venv/Lib/site-packages').iterdir()) if d.is_dir() and not d.name.endswith(('.dist-info','__pycache__'))]"
  ```

  Cette troisième commande est la **source unique du poids d'un paquet** de ce
  `.venv` : `PIL` y pèse **16,0 Mo** de contenu.
  [`../../CONCEPTION.md`](../../CONCEPTION.md) §6, qui a besoin de ce chiffre pour
  décider ce qu'une image de déploiement peut écarter, y renvoie désormais au lieu
  d'en garder une copie — il en portait une, « 15,3 Mo », qui est le même dossier
  compté en mébioctets sans le dire.

  Les deux premières commandes rendent 169,2 Mo de contenu et 172 Mo de
  dossier. Les 169,2 Mo comptent `pip`
  (11 Mo), que tout environnement virtuel porte de toute façon ; c'est pour cela
  que je retiens les 172 Mo du dossier et non un total « net » qui dépendrait de
  ce qu'on décide d'exclure. J'avais publié 174 Mo et « 167,5 Mo de contenu » : la
  commande ci-dessus est désormais la seule référence.
  **Je n'ai installé ni torch ni sentence-transformers** : fastembed fait tourner
  les mêmes modèles en ONNX, et la mesure de la mémoire se fait en ctypes plutôt
  qu'en ajoutant `psutil` pour trois lignes.
- **Indexation : de l'ordre du quart d'heure** pour 588 articles (l'article
  abrogé 256 est vide et n'est pas indexé), soit de l'ordre de la seconde par
  article, sur CPU, une seule fois. C'est une durée : elle est publiée en ordre de
  grandeur, et ce qui compte pour la décision est qu'elle soit payée une fois à
  l'installation et non à chaque question.
- **Requête en service : de l'ordre de 20 ms**, avec un 95e centile du même ordre
  que la médiane — autrement dit pas de longue traîne, ce qui est le point utile
  et se vérifie d'un coup d'œil sur la sortie de `cout_service.py`. À quoi
  s'ajoute **une ouverture de session ONNX de l'ordre de la seconde**, payée une
  fois au démarrage du processus et non par question. La similarité cosinus, elle,
  ne compte pour rien dans ce total : **l'index entier pèse 1,81 Mo**
  (588 × 768 × 4 octets, imprimé par `cout_service.py`), et un produit
  matrice-vecteur de cette taille est invisible devant le plongement de la
  question. Ne rien publier ici allait un cran trop loin : ce qui se reproduit,
  c'est le **rapport** entre le produit scalaire et le temps d'une question, et il
  a un document source — [`../../CONCEPTION.md`](../../CONCEPTION.md) §6, qui le
  mesure à **moins de 0,2 % du temps de réponse, de l'ordre de 1 pour 600**, et le
  retrouve à chacune de ses exécutions. Ce que je retire est le point que j'avais
  mis (0,029 ms), une durée de plus à faire dériver ; ce que je ne retire pas,
  c'est l'ordre de grandeur, qui dit bien que tout le temps part dans le
  plongement de la question.

### Les chiffres que j'avais faux, et leur cause commune

Ma première mesure donnait, pour cette même configuration, **plus d'une seconde
par requête et une dizaine de gigaoctets de pic** (`res_5.json` garde les valeurs
brutes de cette exécution). C'est ce que mesure un processus qui vient de plonger
les 588 articles : deux sessions ONNX vivantes en même temps, chacune réclamant
tous les cœurs, et dix gigaoctets déjà résidents. Dans un processus neuf qui
charge un index tout fait — le régime d'un serveur qui répond à des questions — la
même question tombe à une vingtaine de millisecondes. L'écart est de près de deux
ordres de grandeur.

**Et j'ai refait exactement la même erreur sur e5-large, sans la voir.** La case
« requête en service » de e5 portait 1 028,6 ms. Ce chiffre ne venait pas de
`cout_service.py` mais de `mesurer.py --une 7` : le processus qui venait de passer
près d'une heure à plonger les 588 passages, avec ses dix gigaoctets résidents
(`res_7.json` : `secondes_index` 3 040, `memoire_pic_mo` 10 362, et une médiane de
requête de 1 128 ms relevée dans ce même processus). La case de gemma, elle,
venait bien de `cout_service.py`. **La colonne mélangeait donc les deux régimes
qu'elle prétendait séparer**, et c'est toute l'explication : en régime de service,
e5 tient dans les **quelques dizaines de millisecondes**, pas dans la seconde —
plus d'un ordre de grandeur sous le chiffre que je publiais.

**Et la correction a dérivé une seconde fois, qu'il faut écrire ici.** Après ce
constat, la case du tableau et le verdict ont porté « ~ 100 ms » et « un ordre de
grandeur plus lent que gemma ». C'était encore faux, d'un facteur quatre, et par
le même geste : un point recopié dans un document qui n'est pas celui où la
grandeur est mesurée. Deux documents ont alors corrigé la même grandeur chacun de
son côté et ont divergé. C'est de là que vient la règle appliquée depuis — **une
grandeur a un seul document source, les autres y renvoient** — et la source du
rapport e5/gemma est [`../../CONCEPTION.md`](../../CONCEPTION.md) §7.

La leçon est la même deux fois, et elle vaut plus que les chiffres : une latence
de service ne se mesure que dans un processus qui ne fait que servir. C'est la
raison d'être de `cout_service.py`, et j'avais le fichier sous la main sans
l'utiliser pour toutes les lignes du tableau.

### La colonne que j'ai retirée, et pourquoi

Le tableau de la section 1 portait une colonne « mém. en service », avec 1 150 Mo
pour potion et 653 Mo pour MiniLM. **Cette colonne ne mesurait pas ce que son
titre annonçait, et je l'ai supprimée plutôt que corrigée.**

`memoire_mo()` lit `PeakWorkingSetSize`, c'est-à-dire le plus haut niveau atteint
par le processus depuis son démarrage. Ce compteur ne redescend jamais. Or
`mesurer.py --rapide` enchaîne tous les modèles dans **un seul processus** :
chaque ligne hérite donc du pic de toutes celles qui l'ont précédée. La signature
du défaut est visible dans la sortie actuelle, qui rend la même valeur
(~2 694 Mo) pour potion et pour MiniLM — deux modèles dont l'un porte trois fois
plus de vecteurs que l'autre. Une colonne qui rend le même nombre pour deux
choses différentes ne mesure pas ces choses.

Les 1 150 et 653 Mo publiés ne sont reproduits par aucune commande du dépôt et je
ne sais pas les retracer. Je ne les remplace pas par les ~2 694 Mo d'aujourd'hui,
qui seraient tout aussi faux pour une autre raison. La mémoire n'est donc plus
donnée qu'une fois, pour la configuration recommandée, dans un processus neuf qui
ne fait que servir :

```
.venv/Scripts/python.exe cout_service.py google/embeddinggemma-300m
```

Ce qu'il faut en retenir : le service de embeddinggemma tient **sous le
gigaoctet** de pic — relevé une fois, le 4 octobre 2026, sur une machine de bureau
Windows partagée avec un autre agent. C'est un ordre de grandeur, pas une
garantie, et la sous-section suivante dit pourquoi je n'en tire plus la conclusion
que j'en tirais.

### Le `batch_size`, et une mesure que je retire

Le pic de dix gigaoctets de l'indexation n'était pas une fatalité mais le
`batch_size` par défaut de fastembed (256). J'avais publié un tableau de trois
lots (4, 16, défaut) avec leurs secondes et leurs pics mémoire, et j'en tirais une
extrapolation aux 588 passages. **Je retire les trois durées, je retire
l'extrapolation, et je suspends le rapport mémoire.** Ce n'est pas une question de
valeurs périmées, et voici pourquoi.

Ce tableau était produit par un balayage des trois lots **dans un seul
processus**, et il souffre donc exactement du défaut de la colonne mémoire :
seule la première ligne mesure son lot, les suivantes mesurent leur lot plus tout
ce que les précédentes ont laissé résident. La démonstration coûte deux secondes,
avec le modèle le plus léger et un script qui prend le lot en argument — c'est la
seule définition juste, un lot par processus :

```python
# lot.py — à lancer une fois par taille de lot, jamais en boucle dans un processus
import sys, time
sys.path.append(".")
from fastembed import TextEmbedding
from index_vectoriel import charger_articles, construire_passages, CACHE_MODELES
from mesurer import memoire_mo
modele, lot, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
passages = [p.texte for p in construire_passages(charger_articles()[1], True, None)][:n]
kw = {} if lot == "defaut" else {"batch_size": int(lot)}
e = TextEmbedding(modele, cache_dir=str(CACHE_MODELES))
t = time.perf_counter()
k = len(list(e.embed(passages, **kw)))
print(f"lot {lot:>7} : {time.perf_counter()-t:7.1f} s  pic {memoire_mo()[1]:6.0f} Mo  ({k} passages)")
```

Sur potion et 96 passages, les trois lots enchaînés dans un même processus donnent
des pics de ~1 150, ~2 190 et ~2 190 Mo ; **les mêmes trois lots, un par
processus, donnent ~1 150, ~1 150 et ~1 210 Mo.** Le quasi-doublement de la
deuxième ligne était l'ouverture d'une seconde session ONNX, pas l'effet du lot —
sur 96 passages, un lot de 16 et un lot de 256 traitent de toute façon le même
unique paquet. Ce balayage-là ne prouve rien sur gemma (potion est un plongement
statique : la taille du lot ne change presque rien à sa mémoire) ; il prouve que
**la méthode de mesure était fausse**, et donc que mon rapport de 3,8 entre le lot
par défaut et le lot de 4 n'est pas établi.

Ce qui reste debout, et qui ne demande aucune mesure : plonger par lots de 4
retient en mémoire les activations de 4 séquences au lieu de 256, donc le pic
d'indexation baisse. Le **sens** est certain, l'**ampleur** ne l'est pas. Et
l'ampleur était justement ce sur quoi je concluais.

**Conséquence sur ma conclusion, que je corrige dans le sens de la prudence :**
j'avais écrit qu'avec `batch_size=4` cette configuration tient dans le plafond
Docker de 1536 Mo du VPS de l'auteur, indexation comprise. Je n'ai pas de quoi
l'affirmer. Ce que j'ai : un pic de service sous le gigaoctet dans un processus
neuf, et la certitude que les petits lots baissent le pic d'indexation. Entre les
deux, la marge sous 1536 Mo est plausible et non démontrée — et un pic mémoire
relevé sur une machine de bureau partagée ne se transporte pas tel quel dans un
conteneur. **À vérifier sur la cible avant de s'engager**, avec le script
ci-dessus lancé un lot par processus sur les 588 passages réels.

Pour la configuration légère (MiniLM, 413 Mo sur disque au total : 172 + 241) :
une dizaine de secondes d'indexation, quelques millisecondes par requête — mais
0,353 en @1.

---

## 3. Où mon approche échoue, et pourquoi

Les échecs sont reproductibles par
`.venv/Scripts/python.exe mesurer.py --une 5 --cache --echecs`.

### Les trois échecs qui condamnent une mise en production naïve

**Q25 « à partir de quel âge on peut travailler au Maroc ? »**
Rendu : **article 526** — « Tout salarié qui atteint l'âge de soixante ans doit
être mis à la retraite. » Attendu : **article 143** — quinze ans révolus, et il
n'est pas dans les cinq premiers. Le piège prévu a été attrapé exactement comme
annoncé : les deux articles parlent d'un âge, et le vecteur ne sait pas que l'un
ouvre la vie professionnelle et l'autre la ferme. Un usager de quinze ans reçoit
« soixante ans » avec une citation d'apparence impeccable.

**Q12 « on m'a viré sans rien me dire, est-ce que c'est permis ? »**
Rendu : **article 480** — l'interdiction faite aux agences de recrutement privées
de percevoir des honoraires des demandeurs d'emploi. Attendu : **article 35** —
« Est interdit le licenciement d'un salarié sans motif valable », absent du top 5.
C'est l'ironie du dossier : la question qui justifie le vectoriel dans l'énoncé
du projet (« on m'a viré » ≈ « rupture du contrat ») est précisément celle qu'il
rate le plus franchement. Le modèle s'est accroché à « est-ce que c'est permis »
et a rendu une interdiction, n'importe laquelle.

**Q24 « j'ai droit à un jour de congé par semaine ? »**
Rendu : **article 231** — le congé annuel payé, 1,5 jour par mois de service.
Attendu : **article 205** — repos hebdomadaire de 24 heures. Le mot « congé »
employé par l'usager à la place de « repos » suffit à faire basculer la réponse
d'un chapitre à l'autre, et la réponse rendue est un droit réel qui ne répond pas
à la question posée. C'est le plus traître des trois : rien, dans la réponse,
n'a l'air faux.

**Deux autres, pour ne pas choisir que les plus commodes.** Q13 (« avant de me
renvoyer, doit-il m'écouter ? ») rend l'article 246, l'ordre des départs en
congé, au lieu de l'article 62 sur l'audition préalable, hors top 5. Q29 rend
l'article 392 (économats) au lieu de l'article 362 (paiement en monnaie
marocaine) — piège attrapé.

### Le diagnostic : le vecteur capte la forme, pas le sujet

Je comptais les articles qui reviennent dans les top 5 de toutes les questions
sans qu'aucune commande ne l'imprime. En voici une, sur la sortie brute de
`mesurer.py --rapide --json resultats_legers.json` :

```
.venv/Scripts/python.exe -c "import json,collections; r=[x for x in json.load(open('resultats_legers.json',encoding='utf-8')) if 'MiniLM' in x['modele'] and x['entete'] and not x['coupe'] and not x['centrer']][0]['resultats']; print(len(r),'questions'); print(*collections.Counter(n for g in r.values() for n,_ in g).most_common(8), sep=chr(10))"
```

Sur 34 questions, avec MiniLM, elle rend : articles **500** et **75** cinq fois
chacun, puis un groupe à quatre fois — **502**, mais aussi 156, 269 et 271. Je le
dis ainsi parce que l'honnêteté du diagnostic en dépend : 156 (reprise d'emploi
après accouchement), 269 (congé de naissance) et 271 (absence pour maladie) sont
des articles **thématiques**, qui répondent légitimement à plusieurs questions du
banc et n'ont rien d'anormal dans un top 5. Montrer une liste filtrée aurait fait
croire à un phénomène plus net qu'il n'est. Ce sont 500, 75 et 502 qui sont
anormaux, et leur texte dit pourquoi :

> art. 502 — « La période d'essai ne peut dépasser : 1. deux jours si le contrat
> est conclu pour une durée de moins d'un mois ; 2. trois jours… »

> art. 500 — « La tâche ne doit pas dépasser : 1. la durée de suspension du
> contrat en ce qui concerne le remplacement d'un salarié… »

Ce sont des énumérations de durées presque sans contenu thématique. Comme les 589
articles partagent le même registre juridique, ce que le plongement distingue le
mieux n'est pas le **sujet** (congé, salaire, licenciement) mais la **forme
rhétorique** de la disposition : un délai, un barème, une interdiction. Toute
question en « combien de temps » converge vers les articles qui sont des listes
de délais, quel que soit leur objet. C'est la version précise, sur ce corpus, du
reproche annoncé dans l'énoncé : le vectoriel confond les proches. Il les confond
sur un axe inattendu, et c'est pire, parce que l'axe n'est pas celui du droit.

Le centrage, qui devrait corriger exactement cela, l'aggrave (section 1).

---

## 4. Ce que mon approche peut offrir sur l'incertitude

C'est le point sur lequel je la défends le mieux, et il est mesuré :
`.venv/Scripts/python.exe abstention.py 5`

Tous les chiffres de cette section sont des scores et des comptes sur un index en
cache : ils se rejouent à l'identique, contrairement aux durées des sections
précédentes.

**Le score de similarité absolu ne sert à rien comme garde-fou.** Sur
embeddinggemma, les bonnes réponses ont un score entre 0,431 et 0,621, les
mauvaises entre 0,310 et 0,653 : **10 des 14 réponses fausses ont un score plus
élevé que la plus faible des réponses justes.** Séparation juste/faux (AUC) :
0,796. Afficher « confiance 65 % » à côté d'une réponse serait un mensonge
chiffré. Sur e5-large c'est pire encore : tous les scores sont tassés entre 0,80
et 0,90, AUC 0,716.

**La marge entre le premier et le deuxième résultat, elle, sépare.** AUC 0,886 sur
gemma. Table complète dans la sortie de la commande ; deux lignes suffisent :

| seuil de marge | questions répondues | justes | exactitude | hors-corpus refusées |
|---|---|---|---|---|
| 0 (aucune abstention) | 34/34 | 20 | 0,59 | 0/3 |
| ≥ 0,031 | 15/34 | 14 | 0,93 | 3/3 |
| ≥ 0,043 | 10/34 | 10 | **1,00** | 3/3 |

À une marge de 0,043, le prototype répond à **10 questions sur 34 et ne se trompe
sur aucune**, en refusant les trois questions dont la réponse n'est pas dans le
corpus. Il se tait sur 24 questions dont 10 auraient reçu la bonne réponse.

C'est exactement l'arbitrage que demande l'énoncé, et je le prends : sur un sujet
où les gens décident de démissionner ou d'aller au tribunal, un assistant qui
répond à trois questions sur dix sans se tromper vaut mieux qu'un assistant qui
répond à toutes et se trompe quatre fois sur dix.

**Avec la prudence qui s'impose : 10 bonnes réponses sur 10 est un résultat sur
dix questions.** Ce n'est pas un seuil validé, c'est un signal encourageant sur
un banc de 34 questions écrites par une seule personne. Il faudrait quelques
centaines de questions, et de plusieurs mains, avant d'inscrire 0,043 dans du
code.

---

## 5. Verdict

**Je ne recommande pas le vectoriel seul.** Mesuré sur mon propre banc, avec le
meilleur modèle que j'ai trouvé, il rend le bon article en premier dans 59 % des
cas. Pour un outil dont la raison d'être est de citer le bon article, 41 % de
premières réponses fausses n'est pas un point de départ acceptable. Ce n'est pas
le coût qui me fait reculer — environ 1 370 Mo sur disque, une vingtaine de
millisecondes par question et un pic de service sous le gigaoctet sont
supportables. C'est le taux d'erreur, et la nature des erreurs de la section 3.

**Mais il apporte quelque chose que le lexical n'a pas, et c'est chiffré.** Le
témoin BM25, écrit du mieux que je pouvais sans aucune dépendance en **69
lignes** (`wc -l temoin_lexical.py`, dont 60 hors blancs et commentaires),
obtient 0,147 en @1 et 0,294 en @3 : embeddinggemma fait **quatre
fois mieux en @1 et presque trois fois mieux en @3**. Ce sont des rappels, donc
des chiffres qui se rejouent à l'identique. L'écart n'est pas une nuance, il est
massif, et il se voit exactement là où on l'attendait : BM25 ne rapproche pas
« on m'a viré » de « licenciement », il ne rapproche rien du tout et rend
l'article 122 sur l'exécution des conventions collectives.

**Ce que je recommande honnêtement**, même si ce n'est pas ma piste :

1. **Un hybride, pas un choix.** Les deux approches échouent sur des questions
   différentes, et le témoin lexical coûte zéro octet. Fusionner les deux
   classements est la première chose à essayer, et mes rappels donnent la
   référence contre laquelle juger ce gain.
2. **Le reclassement, plus que le modèle.** Passer de MiniLM (0,353) à
   embeddinggemma (0,588) a coûté près de deux ordres de grandeur en temps
   d'indexation : la dizaine de secondes contre le quart d'heure. Les échecs de
   la section 3 montrent que le bon article est souvent au rang 2 ou 3 (gemma :
   @3 à 0,853 contre @1 à 0,588). L'écart entre @1 et @3 — 9 questions sur 34 —
   se gagne par un reclassement des cinq candidats, là où un modèle de langage a
   un rôle légitime, et non par un plongement plus gros.
3. **L'abstention, dès la première version.** La section 4 montre qu'un signal
   utilisable existe (la marge) et qu'un signal plausible est trompeur (le
   score). Quelle que soit l'architecture retenue, c'est la marge qu'il faut
   instrumenter, et il faut écrire « je ne trouve pas d'article qui réponde »
   plutôt que de rendre le cinquième voisin.
4. **Si le vectoriel est retenu : embeddinggemma, avec un petit `batch_size`.**
   Gemma coûte 1 199 Mo de disque contre 241 Mo à MiniLM, et une latence de
   service du **même ordre de grandeur** (quelques dizaines de millisecondes
   contre quelques millisecondes) — cette latence n'est donc pas un argument pour
   MiniLM, contrairement à ce que je croyais quand je comparais deux chiffres au
   dixième de milliseconde. Il rend le bon article dans le top 3 pour 29 questions
   sur 34 là où MiniLM n'en rend que 17 : payer 958 Mo de disque pour 12 questions
   sur 34 est un bon marché. Sur le plafond Docker de 1536 Mo, je ne tranche plus
   (voir section 2) : c'est la mesure à faire sur la cible, un lot par processus,
   avant de s'engager. e5-large est à écarter, mais sur **deux** raisons et non
   trois : il est 1,8 fois plus lourd que gemma sur disque, et moins bon sur les
   trois rappels. La troisième que j'avançais — « un ordre de grandeur plus lent
   par requête en service » — est fausse : le rapport e5/gemma vaut un peu plus du
   double ([`../../CONCEPTION.md`](../../CONCEPTION.md) §7, quatre paires
   mesurées, 2,12 à 2,16). Le temps de service n'est donc pas un argument contre
   e5 ; les deux autres suffisent, et c'est tout ce qu'il faut dire. Je le laisse
   écrit plutôt que de le retirer, parce que c'est ce raisonnement-là — et non le
   chiffre — que la correction a réparé.

Et dans tous les cas, la phrase de `source.avertissement` doit s'afficher sous
chaque réponse : le meilleur rappel du monde ne rend pas un texte consolidé en
2011 conforme à l'état du droit en 2026.

---

## Fichiers

| fichier | rôle |
|---|---|
| `banc.py` | 34 questions + 3 sans réponse, avec l'article attendu et sa justification |
| `index_vectoriel.py` | le prototype : passages, plongement, cosinus, CLI d'une question |
| `temoin_lexical.py` | BM25 sans dépendance, le contrôle |
| `mesurer.py` | rappel@1/3/5, temps, mémoire, échecs |
| `cout_service.py` | coût d'une requête index déjà construit (le régime du serveur) |
| `abstention.py` | le score et la marge savent-ils dire « je ne sais pas » |
| `res_*.json` | résultats bruts des exécutions citées ici — y compris les durées et les pics mémoire que cette note ne publie plus comme des points |

Essayer une question :

```
.venv/Scripts/python.exe index_vectoriel.py "on m'a viré après deux ans, j'ai droit à une indemnité ?" "google/embeddinggemma-300m"
```
