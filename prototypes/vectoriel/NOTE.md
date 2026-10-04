# Récupération vectorielle pour Mizan — note de défense

Prototype jetable, mesuré le 4 octobre 2026 sur les 589 articles de
`corpus/code-travail.json`. Aucun fichier de production n'a été écrit. Aucun
chiffre de cette note ne vient d'ailleurs que d'une exécution de cette session ;
la commande est donnée à chaque fois.

Tout est installé dans `prototypes/vectoriel/.venv`, **jamais dans le Python
partagé** : un autre agent pouvait travailler au même moment sur le même
environnement, et un `pip install` dans `site-packages` l'aurait concerné.
Supprimer le dossier `prototypes/vectoriel/` suffit à tout annuler.

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
```

Indexation et service sont deux régimes qu'il faut mesurer séparément — voir la
section 2, où un premier chiffre faux d'un facteur 70 est expliqué.

| approche | poids disque | indexation des 588 | requête en service | mém. en service | @1 | @3 | @5 |
|---|---|---|---|---|---|---|---|
| **témoin BM25** (zéro dépendance) | 0 Mo | 0,04 s | 0,3 ms | 89 Mo | 0,147 | 0,294 | 0,294 |
| potion-multilingual-128M | 522 Mo | 0,1 s | 0,3 ms | 1 150 Mo | 0,235 | 0,235 | 0,265 |
| MiniLM-L12 multilingue | 241 Mo | 11,0 s | 4,8 ms | 653 Mo | 0,353 | 0,500 | 0,500 |
| multilingual-e5-large | 2 149 Mo | 3 027 s | 1 028,6 ms | 1 594 Mo | 0,441 | 0,618 | 0,735 |
| **embeddinggemma-300m** | 1 199 Mo | 964 s | 20,2 ms | 904 Mo | **0,588** | **0,853** | **0,853** |

Le poids disque est mesuré (`du -sm .cache_modeles/*/`) et non repris du champ
`size_in_GB` de fastembed. Les deux concordent à moins de 10 % près (annoncé /
mesuré : 220 / 241 Mo pour MiniLM, 1 240 / 1 199 Mo pour gemma, 2 240 / 2 149 Mo
pour e5), donc l'annonce est utilisable pour choisir — mais ce sont les valeurs
mesurées qui sont dans le tableau. S'y ajoutent **174 Mo** de paquets Python.

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

---

## 2. Le coût réel

Pour la configuration que je recommande (embeddinggemma-300m, entête
hiérarchique, pas de découpage, pas de centrage) :

- **1 373 Mo sur disque** : 174 Mo de paquets + 1 199 Mo de modèle.
- **Paquets installés** : `fastembed` seul en commande `pip`, qui tire
  `onnxruntime` (46 Mo, le moteur d'inférence), `numpy` (54 Mo avec ses
  bibliothèques natives), `tokenizers` (8 Mo), `huggingface-hub` + `hf_xet`
  (16 Mo, le téléchargement du modèle), `pillow` (16 Mo, inutile ici mais
  dépendance dure de fastembed pour ses modèles d'image). Mesure :
  `python -c` sur `site-packages`, 167,5 Mo de contenu, 174 Mo de dossier.
  **Je n'ai installé ni torch ni sentence-transformers** : fastembed fait tourner
  les mêmes modèles en ONNX, et la mesure de la mémoire se fait en ctypes plutôt
  qu'en ajoutant `psutil` pour trois lignes.
- **Indexation : 964 s** pour 588 articles (l'article abrogé 256 est vide et n'est
  pas indexé). Soit 1,6 s par article, sur CPU, une seule fois.
- **Requête en service : 20,2 ms en médiane, 22,8 ms au 95e centile**, plus
  1 271 ms d'ouverture de la session ONNX au démarrage du processus. La
  similarité elle-même ne compte pour rien : **0,029 ms**, car l'index entier
  pèse 1,81 Mo. Tout le temps part dans le plongement de la question.
- **Mémoire en service : 904 Mo de pic.**

### Le chiffre que j'avais faux, et comment

Ma première mesure donnait **1 456 ms par requête et 9 974 Mo de pic** pour cette
même configuration. C'est ce que mesure un processus qui vient de plonger les 588
articles : deux sessions ONNX vivantes en même temps, chacune réclamant tous les
cœurs, et dix gigaoctets déjà résidents. Dans un processus neuf qui charge un
index tout fait — le régime d'un serveur qui répond à des questions — la même
question prend 20 ms (`cout_service.py`, mesuré sur les quatre modèles).

Le pic de 9 974 Mo, lui, n'était pas une fatalité mais le `batch_size` par défaut
de fastembed (256). Mesuré sur 96 passages :

| batch_size | 96 passages | pic mémoire |
|---|---|---|
| 4 | 123,1 s | **903 Mo** |
| 16 | 138,4 s | 1 181 Mo |
| défaut (256) | 165,5 s | 3 438 Mo |

Par petits lots, l'indexation est à la fois **plus légère et plus rapide**
(extrapolé aux 588 passages : environ 754 s à batch 4, contre 964 s mesurées à
batch par défaut — l'extrapolation est linéaire et non mesurée en entier).

Conséquence, et elle change ma conclusion : avec `batch_size=4`, cette
configuration tient dans le plafond Docker de 1536 Mo du VPS de l'auteur,
indexation comprise. J'avais écrit le contraire sur la base du premier chiffre.

Pour la configuration légère (MiniLM, 415 Mo sur disque au total) : 11 s
d'indexation, 4,8 ms par requête, 653 Mo en service — mais 0,353 en @1.

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

En comptant les articles qui reviennent dans les top 5 de toutes les questions,
les articles **500** et **75** sortent cinq fois chacun et l'article **502**
quatre fois, sur 34 questions, avec MiniLM. Leur texte explique pourquoi :

> art. 502 — « La période d'essai ne peut dépasser : 1. deux jours si le contrat
> est conclu pour une durée de moins d'un mois ; 2. trois jours… »

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
le coût qui me fait reculer — après correction de ma propre mesure, 1 373 Mo sur
disque, 20 ms par question et 904 Mo en service sont parfaitement supportables.
C'est le taux d'erreur, et la nature des erreurs de la section 3.

**Mais il apporte quelque chose que le lexical n'a pas, et c'est chiffré.** Le
témoin BM25, écrit du mieux que je pouvais en cinquante lignes sans aucune
dépendance, obtient 0,147 en @1 et 0,294 en @3 : embeddinggemma fait **quatre
fois mieux en @1 et presque trois fois mieux en @3**. L'écart n'est pas une
nuance, il est massif, et il se voit exactement là où on l'attendait : BM25 ne
rapproche pas « on m'a viré » de « licenciement », il ne rapproche rien du tout
et rend l'article 122 sur l'exécution des conventions collectives.

**Ce que je recommande honnêtement**, même si ce n'est pas ma piste :

1. **Un hybride, pas un choix.** Les deux approches échouent sur des questions
   différentes, et le témoin lexical coûte zéro octet. Fusionner les deux
   classements est la première chose à essayer, et mes mesures donnent la
   référence contre laquelle juger ce gain.
2. **Le reclassement, plus que le modèle.** Passer de MiniLM (0,353) à
   embeddinggemma (0,588) a coûté un facteur 90 en temps d'indexation. Les
   échecs de la section 3 montrent que le bon article est souvent au rang 2 ou 3
   (gemma : @3 à 0,853 contre @1 à 0,588). L'écart entre @1 et @3 — 9 questions
   sur 34 — se gagne par un reclassement des cinq candidats, là où un modèle
   de langage a un rôle légitime, et non par un plongement plus gros.
3. **L'abstention, dès la première version.** La section 4 montre qu'un signal
   utilisable existe (la marge) et qu'un signal plausible est trompeur (le
   score). Quelle que soit l'architecture retenue, c'est la marge qu'il faut
   instrumenter, et il faut écrire « je ne trouve pas d'article qui réponde »
   plutôt que de rendre le cinquième voisin.
4. **Si le vectoriel est retenu : embeddinggemma, avec `batch_size=4`.** C'est
   l'inverse de ce que j'allais écrire avant de corriger ma mesure de coût.
   Gemma coûte 1 199 Mo de disque contre 241 Mo à MiniLM et 20 ms par requête
   contre 4,8 ms, mais il tient lui aussi dans le plafond de 1536 Mo, et il rend
   le bon article dans le top 3 pour 29 questions sur 34 là où MiniLM n'en rend
   que 17. Payer 958 Mo de disque pour 12 questions sur 34 est un bon marché.
   e5-large est à écarter sans hésiter : 1,8 fois plus lourd que gemma sur
   disque, 51 fois plus lent par requête, et moins bon sur les trois rappels.

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
| `res_*.json` | résultats bruts des exécutions citées ici |

Essayer une question :

```
.venv/Scripts/python.exe index_vectoriel.py "on m'a viré après deux ans, j'ai droit à une indemnité ?" "google/embeddinggemma-300m"
```
