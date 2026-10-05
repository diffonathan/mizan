# Mizan — piste « combinaison lexical + dense, fusion par rang réciproque »

Prototype jetable, et **écarté**. Aucun fichier de ce dossier n'est destiné
à la production. Cette note n'a pas pour but de dire combien de
millisecondes coûtait la fusion un jour d'octobre 2026 : elle doit dire
**pourquoi la piste a été écartée**, de façon que l'argument tienne encore
quand la machine aura changé.

**Règle d'écriture des chiffres**, appliquée partout dans ce qui suit.

- Ce qui se reproduit à l'identique chez qui clone le dépôt et lance la
  commande — rappels, comptages, rangs, tailles de fichier — est publié
  comme un nombre, avec la commande qui le produit.
- Ce qui dépend de la machine et de sa charge — durées, mémoire, débits —
  n'est **pas** publié comme un point. Pour la seule construction de l'index
  dense, dont le code n'a pas changé d'une ligne, une version précédente de
  cette note publiait 45 975 ms ; deux rejeux de `banc.py` donnent 15,2 s et
  15,5 s. Republier l'un de ces nombres, ce serait reposer un chiffre qui
  dérivera au prochain rejeu, et la même remarque reviendrait dans trois
  mois. Ces grandeurs sont donc données en **ordre de grandeur**, en
  **rapport** ou en **intervalle observé**, et jamais au dixième.
- Là où je n'ai pas mesuré, je l'écris.

Deux durées font exception et sont citées telles quelles, parce qu'elles
disent l'ampleur d'un problème : elles sont signalées en gras à l'endroit où
elles apparaissent (§4) comme **non rejouables et à ne pas citer** — aucune
commande de ce dépôt ne les reproduit.

---

## 1. Ce que le prototype fait

Trois fichiers de recherche, un fichier de fusion, un banc.

| fichier | rôle |
|---|---|
| `normaliser.py` | minuscules, accents rabattus, élisions coupées, radicalisation Snowball française |
| `corpus.py` | chargement du JSON, découpage en 781 passages (jamais au milieu d'un alinéa) |
| `lexical.py` | bras A : BM25 Okapi sur les mots radicalisés ; bras C : BM25 sur tranches de 4 caractères |
| `dense.py` | bras B : encodeur multilingue ONNX (fastembed), un vecteur par passage, score d'article = max de ses passages |
| `fusion.py` | RRF, variante CombSUM min-max, et le verdict d'incertitude |
| `banc.py` | 25 questions à réponse connue + 5 hors corpus, rappel@1/3/5, ablations, coûts |
| `chercher.py` | interrogation en ligne de commande |

Reproduction, depuis `prototypes/hybride/`. Les deux variables
d'environnement d'origine pointaient vers un dossier temporaire ; le chemin
ci-dessous prend les mêmes fichiers dans le cache du candidat 2, et c'est lui
qui a produit tous les chiffres de cette note :

```sh
export MIZAN_MODELE="$PWD/../vectoriel/.cache_modeles/models--qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q/snapshots/faf4aa4225822f3bc6376869cb1164e8e3feedd0"
../vectoriel/.venv/Scripts/python.exe banc.py      # écrit resultats_banc.json
../vectoriel/.venv/Scripts/python.exe chercher.py "combien de jours de congés après deux ans ?"
```

`MIZAN_PAQUETS` est inutile avec cet interpréteur : le `.venv` du candidat 2
contient déjà `fastembed`, `numpy` et `py_rust_stemmers`. La variable ne sert
que si l'on rejoue avec l'interpréteur partagé et un `pip install --target`
séparé, comme à l'origine (voir §4).

**Un seul fichier tourne sans ces paquets : `lexical.py`** (`python
lexical.py` sort en code 0 avec l'interpréteur partagé — le radicaliseur a un
repli en pure bibliothèque standard). Une version précédente de cette note
annonçait aussi `banc.py --rapide` : c'est faux, `--rapide` ne saute que les
ablations et `main()` importe `dense` dans tous les cas. Sans les paquets,
`python banc.py --rapide` s'arrête sur `ModuleNotFoundError: No module named
'numpy'` (dense.py, ligne 16), vérifié.

---

## 2. Les mesures

**Convention.** Un seul article attendu par question, celui qu'un juriste
citerait en premier. `rappel@k` = part des 25 questions dont cet article est
dans les k premiers. Avec un seul article pertinent c'est aussi le taux de
réussite@k. C'est plus sévère qu'un ensemble d'articles acceptables, qui
gonflerait les trois chiffres sans rien prouver de plus.

**Commande :** celle du §1 (`banc.py`, sans `--rapide`) → `resultats_banc.json`

| | rappel@1 | rappel@3 | rappel@5 |
|---|---|---|---|
| bras lexical seul (BM25) | **0,36** | 0,48 | 0,52 |
| bras dense seul | 0,16 | 0,52 | 0,56 |
| **fusion RRF, k=60** | 0,32 | 0,52 | **0,64** |
| plafond d'un oracle qui choisirait le bon bras | 0,40 | 0,68 | 0,76 |

Ces douze rappels sont déterministes : ils sortent identiques de chaque
exécution et se relisent dans `resultats_banc.json`, champs `resultats.*` et
`ablations.plafond_oracle_choix_du_bras`.

**Ce tableau n'a plus de colonne « ms/requête ».** Il en avait une, et elle
contredisait le §4 du même document : on y lisait 0,32 / 17,07 / 17,95 là où
le §4 chiffrait 0,13 et 17,74 pour deux des trois mêmes mesures. Un document
qui se contredit lui-même ne se répare pas en corrigeant un côté, alors
voici la décision : **le §4 fait foi pour tout ce qui est coût**, et il n'y
parle qu'en ordres de grandeur. `banc.py` imprime toujours cette médiane,
mais cette note ne la republie plus comme un nombre.

Ce qu'il faut retenir du coût ici, et qui tient sur n'importe quelle
machine : **une requête du bras lexical coûte un à deux ordres de grandeur
moins qu'une requête du bras dense** — le rapport entre les deux a été
mesuré entre 40 et 55 selon l'exécution — et la fusion coûte ce que coûte le
bras dense, à quelques pour cent près. C'est tout ce dont la suite a besoin.

Il faut lire ce tableau dans cet ordre :

1. **La fusion gagne 0,08 de rappel@5** sur le meilleur bras seul. C'est le
   seul gain réel, et c'est le chiffre qui compte si l'interface montre cinq
   articles cités plutôt qu'un seul.
2. **La fusion PERD du rappel@1** : 0,32 contre 0,36 pour BM25 seul. Sur 25
   questions, la fusion dégrade le rang de l'article attendu dans **11 cas**
   et l'améliore dans **5** (9 inchangés). `banc.py` imprime la liste sous
   « ce que la fusion a gagné ou perdu par rapport à chaque bras » ; le
   comptage, lui, se refait sur le JSON — ces trois nombres sont
   déterministes :

   ```sh
   python -c "import json; d=json.load(open('resultats_banc.json',encoding='utf-8')); I=10**6; c=[(min(q['rang_lexical'] or I, q['rang_dense'] or I), q['rang_fusion'] or I) for q in d['detail']]; print('degrade', sum(f>b for b,f in c), 'ameliore', sum(f<b for b,f in c), 'inchange', sum(f==b for b,f in c))"
   ```
3. **Le plafond de l'oracle est 0,76 @5.** Aucune fusion de ces deux bras ne
   dépassera ça. L'écart 0,64 → 0,76 est ce que la fusion laisse sur la
   table ; l'écart 0,76 → 1,00 est ce que les *bras* ne savent pas trouver,
   et c'est là que se trouve l'essentiel du travail restant.

### Pourquoi RRF perd au rang 1

Mécanisme, visible dans `chercher.py "combien de jours de congés après deux
ans ?"`. L'article 231 est **premier** pour BM25 et seulement **27e** pour le
bras dense : 1/61 + 1/87 = **0,0279**. L'article 269, 7e pour l'un et 4e pour
l'autre, vaut 1/67 + 1/64 = **0,0306**. Le premier passe au rang 7 de la
fusion, le second au rang 1. **Le médiocre-partout bat le
premier-quelque-part.** Avec deux bras et k=60, l'avance de 231 là où il est
bon (1/61 contre 1/67, soit 0,0015) est trois fois plus petite que son retard
là où il est mauvais (1/87 contre 1/64, soit 0,0041). C'est structurel, pas un
défaut de réglage : à k=60, passer du rang 1 au rang 7 coûte 9 % du poids, et
passer du rang 4 au rang 27 en coûte 26 %.

### « RRF ne demande aucun réglage de poids » — mesuré, c'est faux

| k de RRF | @1 | @3 | @5 |
|---|---|---|---|
| 1 | 0,36 | 0,56 | 0,68 |
| 2 | 0,40 | 0,56 | 0,64 |
| 5 | **0,44** | 0,56 | **0,68** |
| 10 | 0,36 | 0,56 | 0,68 |
| 20 | 0,36 | 0,56 | 0,64 |
| **60 (valeur canonique)** | 0,32 | 0,52 | 0,64 |
| 120 | 0,32 | 0,52 | 0,64 |

k=5 donnerait 0,44/0,56/0,68. Je ne le retiens pas et je ne le présente pas
comme mon résultat : choisir k après avoir vu les scores sur un banc de 25
questions écrites par moi, c'est régler un paramètre sur le jeu de test. Mais
l'argument « RRF est sans paramètre » ne survit pas à la mesure : l'écart
entre le meilleur et le pire k est de 0,12 au rappel@1, c'est-à-dire trois
questions sur vingt-cinq. Sur un corpus de 589 articles et deux bras
seulement, k=60 — calibré dans la littérature sur des fusions de nombreux
systèmes TREC — est trop grand.

### Une fusion plus simple fait mieux

| variante de fusion | @1 | @3 | @5 |
|---|---|---|---|
| RRF k=60 | 0,32 | 0,52 | 0,64 |
| somme des scores remis à l'échelle min-max | 0,36 | 0,56 | 0,68 |

La fusion par scores ne demande pas plus de réglage que RRF (l'échelle est
calculée par requête) et garde ce que RRF jette : l'**écart** entre le premier
et le deuxième. Sur ce corpus, cette information valait d'être gardée. Je
n'ai pas de mesure qui dise si cela tient sur un corpus plus grand ou sur
d'autres questions ; sur celui-ci, le choix de RRF n'est pas justifié par les
chiffres.

### Un troisième bras gratuit n'apporte rien à RRF

Bras C : BM25 sur tranches de 4 caractères. **Zéro paquet**, et une
indexation d'une **fraction de seconde** — du même ordre que celle du bras
lexical, c'est-à-dire négligeable devant celle du bras dense. `banc.py`
l'imprime en dernière ligne de ses ablations, sous « indexation du bras
caracteres » (champ `ablations._indexation_caracteres_ms` du JSON).

Aucune valeur n'est donnée ici, et c'est le fait marquant : les versions
successives de cette note ont publié, pour cette unique mesure, **465 ms,
puis 317 ms, puis 140,5 ms, puis 125,6 ms**. Quatre nombres pour la même
opération, dont le code n'a pas bougé d'une ligne entre-temps. **C'est la
dispersion qui est l'information, pas le dernier tirage en date** — et ce
qu'elle dit suffit à l'argument de ce paragraphe : **ce bras ne coûte rien
devant le bras dense**. Dans l'absolu, un quart de seconde n'est pas rien ; c'est
devant les dizaines de secondes du §4 que ça l'est, et c'est la seule forme sous
laquelle cette phrase est vraie.
Les rappels ci-dessous, eux, ne bougent pas d'une exécution à l'autre.

| | @1 | @3 | @5 |
|---|---|---|---|
| caractères seul | 0,36 | 0,48 | 0,60 |
| RRF(lexical, caractères) — aucun modèle, 0 Mo | 0,36 | 0,44 | 0,52 |
| RRF(dense, caractères) | 0,36 | 0,60 | 0,64 |
| RRF(lexical, dense, caractères) | 0,36 | 0,56 | 0,64 |

Deux choses se lisent ici. D'abord, **RRF(lexical, caractères) n'améliore
aucun des deux bras qu'il fusionne** : 0,52 @5, c'est-à-dire exactement le
bras lexical seul (0,52) et moins que le bras caractères seul (0,60). Il perd
aussi du rappel@3 (0,44 contre 0,48 pour chacun des deux bras). Fusionner deux
bras qui se trompent de la même façon ne corrige rien et ajoute du bruit —
mais la parenthèse dit « égal, puis pire », pas « pire que les deux », et une
version précédente de cette note écrivait « pire que chacun des deux bras
pris seul au rappel@5 » au-dessus des chiffres qui la démentent.
Ensuite, le troisième bras n'améliore pas la fusion à deux
bras (0,64 → 0,64 @5). **La combinaison ne vaut que si les bras échouent
pour des raisons différentes** — c'est l'hypothèse à vérifier avant d'écrire
la moindre ligne de fusion, et le bras caractères ne la vérifie pas, parce
qu'il échoue là où BM25 échoue : sur le vocabulaire, pas sur la morphologie.

### Ablations de détail

| | @1 | @3 | @5 |
|---|---|---|---|
| lexical, chemin de titres non indexé | 0,36 | 0,48 | 0,52 |
| lexical, chemin de titres compté deux fois | 0,32 | 0,44 | 0,52 |
| dense, passages sans chemin de titres | 0,16 | 0,48 | 0,60 |
| fusion avec le dense sans titres | 0,40 | 0,56 | 0,64 |
| fusion, profondeur 10 / 20 / 50 par bras | 0,32 / 0,32 / 0,32 | 0,52 | 0,64 / 0,68 / 0,64 |

Le recopiage du chemin hiérarchique en tête de chaque passage, que j'avais
justifié par l'article 205 (« il doit être accordé obligatoirement aux
salariés un repos hebdomadaire… », qui ne contient pas le mot de son propre
chapitre), **ne se voit pas dans les chiffres** : la fusion est même meilleure
sans. Je le laisse dans le code parce que je ne sais pas trancher sur 25
questions, mais je n'ai aucun résultat qui le soutienne.

---

## 3. Où ça échoue

Neuf des 25 questions n'ont pas l'article attendu dans les cinq premiers.
En voici cinq, avec ce que la fusion rend et ce qu'elle aurait dû rendre.

**1. « mon chef me fait des avances, que dit la loi ? »**
Rendu : articles **548, 41, 293, 546, 7**. Attendu : **40** (le harcèlement
sexuel est l'une des quatre fautes graves de l'employeur). Rang de l'article
40 dans la fusion : **60**. Aucun bras ne le trouve : BM25 parce que la
question et l'article n'ont pas un mot en commun, le bras dense parce qu'il
est entraîné à rapprocher des paraphrases, pas à faire le lien entre un récit
de salariée et une énumération juridique. C'est l'échec le plus grave de la
série : la question est exactement celle pour laquelle on construirait cet
outil, et la réponse rendue (art. 548, dispositions pénales diverses) est
plausible à l'œil et fausse.

**2. « au bout de combien de temps je ne peux plus réclamer ce qu'on me doit ? »**
Rendu : **541, 462, 74, 442, 373**. Attendu : **395** (« se prescrivent par
deux années »). L'article 395 n'est même pas dans les 50 premiers de la
fusion. Le mot « prescription » n'est ni dans la question ni, sous cette
forme, dans le corps de l'article.

**3. « ma femme vient d'accoucher, combien de jours le père peut prendre ? »**
Rendu : **161, 154, 156, 153, 157** — tout le chapitre de la protection de la
maternité. Attendu : **269** (trois jours à l'occasion de chaque naissance).
Le meilleur bras seul plaçait 269 au rang 10 ; la fusion l'a repoussé au rang
**20**, parce que les deux bras sont d'accord sur le mauvais chapitre. Quand
les deux bras se trompent ensemble, RRF renforce l'erreur au lieu de la
corriger : c'est le risque que la littérature ne mentionne pas.

**4. « combien de jours de repos par semaine au minimum ? »**
Rendu : **227, 213, 206, 219, 222**. Attendu : **205** (« un repos
hebdomadaire d'au moins vingt-quatre heures »). Le meilleur bras seul le
plaçait au rang 3, la fusion au rang 13. L'article fait une phrase ; il n'a
presque aucun mot à offrir, et le mot « semaine » de la question n'y figure
pas — c'est « hebdomadaire ».

**5. « je suis enceinte, combien de temps dure mon congé ? »**
Rendu : **161, 269, 238, 232, 239**. Attendu : **152** (quatorze semaines).
Rang 13 pour la fusion contre 2 pour le meilleur bras seul. « Enceinte »
n'apparaît pas dans le code, qui dit « en état de grossesse ».

Les quatre autres échecs sont de la même famille : art. **43** (préavis,
demandé sans le mot), **72** (certificat de travail, demandé comme « quel
papier »), **363** (périodicité du salaire, demandé avec « versé » quand le
texte dit « payé »), **516** (salarié étranger, demandé par la négation « qui
n'est pas marocain »).

**Le diagnostic est unique : c'est un problème de vocabulaire, pas de
classement.** Ni BM25 ni un encodeur de paraphrase ne sait que « avances »
renvoie à « harcèlement sexuel », que « papier » renvoie à « certificat de
travail », que « périmé » renvoie à « prescrit ». Une fusion de deux
méthodes qui ignorent toutes les deux cette correspondance ne peut pas la
fabriquer.

---

## 4. Le coût réel, mesuré

**Paquets installés** — dans un dossier isolé (`pip install --target`), **pas**
dans l'environnement partagé : d'autres agents travaillaient sur le même
interpréteur Python pendant ce prototype et un `pip` concurrent dans le même
`site-packages` est un risque que je n'ai pas pris pour un jetable.

Commande : `pip install --target ./paquets fastembed`, puis `du -sm`.

| | poids sur disque |
|---|---|
| **total du dossier de paquets** | **161 Mo** |
| dont onnxruntime | 46 Mo |
| dont numpy (+ numpy.libs) | 34 + 21 Mo |
| dont PIL (tiré par fastembed, inutile ici) | 16 Mo |
| dont hf_xet | 10 Mo |
| dont tokenizers | 8 Mo |
| dont huggingface_hub | 8 Mo |
| dont fastembed | 2 Mo |
| dont py-rust-stemmers *(seul paquet du bras lexical)* | 1 Mo |

**Modèle** : `qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`, **241 Mo**
sur disque — `du -sm` sur le dossier de snapshot que le §1 nomme, donc des
mébioctets — dont `model_optimized.onnx` 224,2 et `tokenizer.json` 16,3 dans la
même unité ; les trois fichiers restants du snapshot sont des JSON de
configuration de quelques kilo-octets, et le total est bien la somme des deux
premiers.

Cette note a publié **255 Mo**, en additionnant un troisième fichier,
`unigram.json` (14,1 Mo), **qui n'existe nulle part** : ni dans ce snapshot, ni
ailleurs dans le cache de modèles que le §1 désigne comme la source de tous les
chiffres de cette note. Une taille de fichier est le genre de nombre qui se
vérifie en une seconde, et celui-là ne se vérifiait pas. Le poids de ce snapshot
a maintenant un seul document source — le §1 de
[`../vectoriel/NOTE.md`](../vectoriel/NOTE.md), qui le mesure par la même
commande — et cette note y renvoie au lieu de refaire son addition.

Le coût des deux bras, mis côte à côte. La ligne « disque » est mesurée au
`du -sm` indiqué au-dessus ; la ligne « mémoire » sort du champ
`memoire_pic_mo` de `resultats_banc.json`. Les deux lignes de temps ne
viennent d'aucune exécution en particulier, et c'est le point :

| | bras lexical seul | les deux bras |
|---|---|---|
| disque (paquets + modèle) | **1 Mo** (0 avec le repli) | **402 Mo** |
| indexation des 589 articles | une fraction de seconde | **des dizaines de secondes** |
| requête, médiane sur 25 questions | quelques dixièmes de ms | quelques ms |
| pic mémoire du processus | **23,6 Mo** | **≈ 845 Mo** |

**Les deux lignes de temps de ce tableau — « indexation » et « requête » —
n'ont plus de valeur chiffrée, et une troisième ligne, « pire cas », a été
retirée.** Aucune des trois ne se reproduit. Les deux lignes qui restent
chiffrées, disque et mémoire, viennent d'exécutions précises et se reproduisent,
elles. Pour mémoire, et comme
intervalles observés et non comme mesures : l'indexation du bras lexical est
tombée entre 57 et 80 ms, celle des deux bras entre 15 et 46 secondes, la
médiane par requête entre 0,1 et 0,3 ms pour le bras lexical et entre 5 et
18 ms pour la fusion. Quant au pire cas, il dépasse la médiane d'un facteur
1,3 à 3 selon l'exécution, et ce facteur ne mesure pas le système : il mesure ce
que la machine faisait d'autre pendant la passe. C'est pour cela qu'il est donné
comme intervalle, et qu'aucune conclusion de cette note ne s'appuie dessus — une
version précédente en publiait pourtant deux valeurs au centième (0,64 ms et
53,44 ms).

Les deux chiffres de mémoire, eux, sont donnés. Ils sortent du champ
`memoire_pic_mo` de `resultats_banc.json`, et trois exécutions les ont placés
à 844,8, 845,0 puis 845,3 Mo pour les deux bras, et à 23,6 Mo exactement,
deux fois, pour le bras lexical seul. Cette grandeur-là tient parce qu'elle
mesure ce que le processus alloue, et non le temps que la machine lui
accorde ; et elle est publiée parce qu'elle se compare à un budget — voir les
trois remarques plus bas.

Restent les **rapports** entre les deux colonnes, qui sont la seule forme
sous laquelle ce §4 mérite d'être cité :

| | rapport | se reproduit ? |
|---|---|---|
| disque | **× 400** | oui — ce sont des tailles de fichier |
| mémoire | **× 36** | oui — 845 / 23,6, stable aux trois exécutions |
| indexation | **deux ordres de grandeur** | l'ordre oui, la valeur non |
| requête | **un à deux ordres de grandeur** | l'ordre oui, la valeur non |

Une version précédente annonçait ici « 580 en indexation, 140 en requête ».
Recalculés sur les exécutions suivantes, ces deux facteurs valent 254 et 46.
Ce ne sont pas des corrections, ce sont **deux tirages de plus** : le facteur
d'indexation est passé de 580 à 254 sans qu'une ligne de code change. Seuls
l'ordre de grandeur, et les facteurs de disque et de mémoire, sont des faits.

Ce prix-là — deux ordres de grandeur sur le temps, 400 sur le disque, 36 sur
la mémoire — est payé pour **+0,08 de rappel@5 et −0,04 de rappel@1**. Ces
deux derniers nombres, eux, se reproduisent exactement.

Détail de l'indexation dense, étape par étape. Ce découpage ne sort pas de
`banc.py` ; il faut le reproduire à part, et la mesure ci-dessous vient de ce
script, lancé avec le même `MIZAN_MODELE` que `banc.py` :

```python
import time
t = time.perf_counter(); import numpy, fastembed; print("imports", time.perf_counter() - t)
import chemin_paquets, corpus as mc
from fastembed import TextEmbedding
t = time.perf_counter()
enc = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    specific_model_path=chemin_paquets.MODELE_LOCAL)
print("modele", time.perf_counter() - t)
ps = mc.passages(mc.charger())
t = time.perf_counter(); v = list(enc.embed([x for _, x in ps], batch_size=32))
print("encodage", len(ps), time.perf_counter() - t)
t = time.perf_counter(); list(enc.query_embed("combien de jours de conges ?"))
print("une question", time.perf_counter() - t)
```

| étape | ce qui s'en garde d'une machine à l'autre |
|---|---|
| `import numpy` + `import fastembed` | une demi-seconde environ |
| chargement du modèle ONNX | de l'ordre de la seconde |
| encodage des 781 passages | **des dizaines de secondes** — tout le temps d'indexation passe ici |
| matrice résultante, 781 × 384 flottants | **1,14 Mio** (781 × 384 × 4 octets : arithmétique, pas mesure) |
| encodage d'une question, médiane sur 20 | **quelques millisecondes** — négligeable |

Deux conclusions, et aucune des deux n'a besoin d'un chiffre pour tenir :

- **le chargement du modèle est négligeable devant l'encodage du corpus** —
  une seconde contre des dizaines. Mettre la matrice en cache sur disque
  supprime donc l'essentiel du coût de démarrage, et non une part marginale ;
- **l'encodage de la question n'est pas le problème, celui du corpus l'est** :
  trois ordres de grandeur séparent les deux, dans toutes les exécutions.

Les valeurs ponctuelles sont retirées de ce tableau parce qu'elles ne se
reproduisent pas, et dans des proportions qui interdisent d'y croire. La
version précédente publiait **29 508 ms** pour l'encodage des 781 passages
(37,8 ms par passage) et une médiane de **14,5 ms** (max 29,3) pour
l'encodage d'une question. Les mêmes lignes rejouées donnent 14 157 ms
(18,1 ms par passage) et 3,6 ms (max 4,6) : un facteur 2 sur la première, un
facteur 4 à 6 sur la seconde. Le script, lui, est inchangé — il est recopié
ci-dessus et se relance tel quel.

**Pourquoi ce §4 ne publie aucune durée au dixième.** Le bras dense est très
sensible à ce que fait le reste de la machine. Une version précédente de
cette note le démontrait par la comparaison de deux points : construire
l'index dense (modèle chargé + 781 passages encodés) valait 45 975 ms dans
l'exécution de `banc.py` et 30 486 ms dans le script détaillé lancé quelques
minutes plus tard (978 + 29 508) — « un facteur 1,5 entre deux exécutions de
la même opération, sur la même machine, le même jour ».

**Cette démonstration ne tient plus, parce que ses deux points ont bougé.**
Rejoué, `banc.py` donne 15,2 s puis 15,5 s pour cette même étape, et le
script détaillé environ 15 s (14 157 ms d'encodage plus le chargement du
modèle) : le facteur 1,5 entre les deux a disparu. Un raisonnement bâti sur
l'écart entre deux mesures instables ne survit pas au rejeu de ces mesures.
C'est pourquoi il est remplacé ici au lieu d'être recalculé avec les
nouveaux nombres : les nouveaux nombres bougeront aussi.

Ce qui se reproduit, et qui dit la même chose en plus fort, c'est **la
dispersion elle-même**. Pour cette unique étape, dont le code n'a pas changé
d'une ligne, les exécutions conservées donnent **15,2 s, 15,5 s, 30,5 s et
46 s** — un facteur 3 entre la plus rapide et la plus lente. Et une session
antérieure, où plusieurs agents travaillaient en parallèle sur la même
machine, portait pour la même étape 238 803 ms et, pour l'encodage d'une
question, 194,8 ms — un facteur 15 au-delà. **Ces deux derniers chiffres ne
sont pas rejouables et ne doivent pas être cités** : ils viennent d'un script
qui n'a pas été conservé, et aucune commande de ce dépôt ne les reproduit. Je
les laisse visibles parce qu'ils disent l'ampleur du problème, pas pour qu'on
s'en serve.

La conclusion est une propriété du système, et non d'une exécution : **le
coût du bras dense n'a pas de valeur, il n'a qu'un ordre de grandeur**, et
cet ordre bouge d'un facteur 3 sur une machine au repos, d'un facteur 15 sous
charge concurrente. Je ne sais pas isoler la contention — et c'est bien le
reproche fait à ce bras, pas une excuse pour ne pas le chiffrer : un
composant dont le coût varie d'un facteur 15 selon les voisins est un
composant qu'on ne sait pas dimensionner. Le bras lexical, lui, reste entre
0,1 et 0,3 ms de médiane par requête sur toutes les exécutions : c'est la
seule partie du système dont le coût ne dépend pas de ce que fait le reste de
la machine. Les rappels, enfin, sont déterministes : identiques d'une
exécution à l'autre.

Trois remarques sur ces chiffres :
- Le pic de 845 Mo interdit l'hébergement visé par les autres projets de
  l'auteur (plafonds Docker de 192 à 1536 Mo sur son VPS). Le bras lexical
  seul tient dans 24 Mo.
- L'indexation dense est à refaire à chaque démarrage du processus dans ce
  prototype. En production on sérialiserait la matrice (781 × 384 flottants =
  1 199 616 octets, soit **1,14 Mio**) ; il resterait le chargement du modèle
  ONNX à chaque démarrage. Le tableau ci-dessus écrit « 1,14 Mio » et cette
  remarque écrivait « 1,14 Mo » pour le même produit : la seconde forme était
  fausse, le mébioctet et le mégaoctet s'écartant ici de 5 % (1,14 contre 1,20).
- `pip` a tiré PIL (16 Mo) et hf_xet (10 Mo) dont ce prototype ne se sert
  jamais. Un vrai déploiement les épinglerait hors de l'image.

---

## 5. Ce que cette approche peut dire quand elle ne sait pas

C'est la partie qui, à mon avis, décide de la piste — et c'est le seul
endroit où la combinaison est clairement supérieure à un bras unique.

Trois signaux, dont les seuils ont été fixés **avant** la première mesure et
non retouchés ensuite (`fusion.py`, `SEUIL_COUVERTURE = 0.6`) :

- **couverture lexicale** : part des mots porteurs de la question qui
  existent dans le vocabulaire du corpus. Détecte « CNSS », « télétravail ».
- **accord des deux bras** : nombre d'articles communs aux cinq premiers de
  chaque bras. **Ce signal n'existe pas sans la combinaison.**
- **marge** : écart relatif entre le premier et le deuxième score fusionné.
  Mesuré, il ne sépare rien, et il trompe : sur les 25 questions, les
  **échecs** au rang 1 couvrent 0,001 à 0,404 et les **réussites** 0,007 à
  0,098 — la plus grosse marge du banc est donc une erreur, et l'intervalle
  des réussites est entièrement contenu dans celui des échecs
  (`resultats_banc.json`, champ `marge` de chaque question). Je le laisse
  affiché mais je ne m'en servirais pas.

La règle testée : refuser si couverture < 0,6 **ou** si l'accord est nul.

**Mesuré sur les 25 questions valides et les 5 hors corpus :**

| | résultat |
|---|---|
| questions hors corpus signalées | **3 / 5** |
| refus sur une question valide | **6 / 25** |
| parmi ces 6 refus, nombre où la fusion avait pourtant mis le bon article **en tête** | **0 / 6** |
| quand le système **accepte de répondre** (19 questions), bon article au rang 1 | 8 / 19 |
| quand le système **accepte de répondre**, bon article dans les 5 | 14 / 19 |
| quand le système **se tait** (6 questions), bon article au rang 1 | 0 / 6 |
| quand le système **se tait**, bon article dans les 5 | 2 / 6 |

La ligne « parmi ces 6 refus, bon article en tête : **0 / 6** » est le seul
résultat de ce prototype dont je sois content : **sur ce banc, chaque fois que
le système a annoncé son incertitude, il avait effectivement tort au rang 1.**
Six refus, six fois à raison. Ce n'est pas une garantie — six cas ne font pas une statistique, et le
signal décisif (désaccord des deux bras) se déclenche aussi sur des questions
dont la bonne réponse est au rang 2 ou 3, donc il coûte deux bonnes réponses
sur six. Mais dans un contexte où rendre le mauvais article est une réponse
fausse et non une imprécision, un détecteur qui ne crie jamais au loup pour
rien vaut mieux qu'un rappel@1 supérieur de quatre points.

**Les deux échecs d'abstention sont instructifs** et aucune version de cette
approche ne les corrigera :
- « ai-je le droit de télétravailler deux jours par semaine ? » — couverture
  0,80, accord 1, pas de refus, rend l'article 49. Tous les mots de la
  question existent dans le code, pris un par un.
- « ai-je droit à un congé parental de trois ans pour élever mon enfant ? » —
  couverture 0,86, accord 2, pas de refus, rend l'article **156**, qui parle
  bien de la mère qui s'abstient de reprendre son emploi pour élever son
  enfant… mais dit quatre-vingt-dix jours ou un an, **jamais trois ans**.
  L'article rendu est le bon article et la réponse serait fausse.

Autrement dit : la récupération sait détecter qu'un **sujet** est absent du
corpus, elle ne sait pas détecter qu'un **chiffre** demandé est absent de
l'article qu'elle rend. Ce contrôle-là ne peut pas vivre dans la couche de
récupération ; il doit vivre dans la consigne donnée au modèle de langue et
dans l'affichage, qui doit montrer le texte cité à côté de la réponse pour que
l'écart soit visible par le lecteur.

---

## 6. Ce que je ne peux pas défendre, et mon verdict

### Ce que la mesure ne couvre pas

- **25 questions écrites par l'auteur du banc.** Un écart de 0,04 de rappel,
  c'est une question. La plupart des écarts de cette note sont dans le bruit
  d'un banc de cette taille ; seuls les écarts de 0,08 et plus (fusion contre
  bras seul au rappel@5, plafond de l'oracle) survivraient probablement à un
  banc dix fois plus grand. Je n'ai pas calculé d'intervalle de confiance et
  je ne devrais pas : sur 25 points, il engloberait tout.
- **Un seul encodeur dense testé.** Le modèle testé est un modèle de
  **paraphrase symétrique**, pas un modèle de récupération question →
  passage ; un modèle entraîné pour cette tâche asymétrique ferait
  probablement mieux. **Je ne l'ai pas mesuré et je n'ai donc aucun chiffre à
  avancer.** C'est le trou principal de cette note : il est possible que la
  piste « combinaison » soit meilleure que ce que je rapporte, et que j'aie
  mesuré un mauvais bras dense plutôt qu'une mauvaise idée.

  **Correction.** Une version précédente de ce paragraphe excusait ce trou en
  affirmant que « le catalogue fastembed n'offre, en multilingue, que ce
  modèle à 255 Mo et un e5 à 2,24 Go ». C'est faux. Vérifié dans
  l'environnement même qui fait tourner ce prototype (fastembed 0.8.1) :

  ```sh
  ../vectoriel/.venv/Scripts/python.exe -c "from fastembed import TextEmbedding
  for m in TextEmbedding.list_supported_models():
      if 'ultiling' in m.get('description',''): print(m['model'], m['size_in_GB'])"
  ```

  → **dix** modèles multilingues, de 0,22 à 2,38 Go : MiniLM 0,22 ·
  potion-multilingual-128M 0,512 · jina-v2-base-de 0,64 ·
  jina-v2-base-code 0,64 · paraphrase-multilingual-mpnet-base-v2 1,0 ·
  Qwen3-Embedding-0.6B-Q 1,12 · siglip2-base 1,13 ·
  **embeddinggemma-300m 1,24** · multilingual-e5-large 2,24 ·
  Qwen3-Embedding-0.6B 2,38.

  Le trou reste entier — je n'ai mesuré aucun de ces neuf autres modèles —
  mais il n'a pas l'excuse que je lui donnais : un encodeur de récupération
  multilingue à 1,24 Go était dans le catalogue, et le candidat 2 l'a
  effectivement mesuré (`prototypes/vectoriel/mesurer.py`, configurations
  `google/embeddinggemma-300m`). Je ne l'ai pas cherché.
- **Rien sur la qualité de la réponse finale.** Ce prototype rend des
  articles, pas des réponses. La récupération est mesurée sans modèle de
  langue, exprès, pour que la mesure soit reproductible sans clé.
- **Le corpus est arrêté au 26 octobre 2011** (`source.date_consolidation`).
  `chercher.py` imprime l'avertissement du corpus sous chaque réponse.

### Verdict

**Je ne recommande pas de livrer la combinaison telle que je l'ai mesurée.**

Elle coûte 402 Mo de disque, près de 0,9 Go de mémoire et des dizaines de
secondes d'indexation pour gagner 0,08 de rappel@5 et perdre 0,04 de
rappel@1 face à un BM25 de **137 lignes** (`wc -l lexical.py` ; 243 avec
`normaliser.py`, qu'il importe) qui tient dans 24 Mo. Un gain de cette taille,
sur 25 questions, ne paie pas ce facteur 400. Et le plafond de l'oracle (0,76 @5) dit que le
problème n'est pas la fusion : c'est que **les deux bras ignorent le même
dictionnaire** entre le français des salariés et celui du législateur.

Ce que je recommande à la place, dans cet ordre :

1. **BM25 seul, avec un lexique de correspondances écrit à la main** (patron →
   employeur, virer → licenciement, enceinte → grossesse, papier →
   certificat, périmé → prescrit, avances → harcèlement sexuel…). Les neuf
   échecs de ce banc sont tous de ce type. Je ne l'ai **pas** mesuré, et
   volontairement : construire ce lexique à partir de ma propre liste
   d'échecs, c'est régler le système sur le jeu de test. Il faut l'écrire à
   partir d'un glossaire du droit du travail, puis mesurer sur des questions
   écrites par quelqu'un d'autre.
2. **Afficher cinq articles cités, pas un.** Tout dans ces chiffres dit que
   le rappel@5 est atteignable et le rappel@1 non : 0,64 contre 0,32. Une
   interface qui impose de choisir un article garantit une réponse fausse une
   fois sur trois.
3. **Garder le second bras uniquement pour le signal de désaccord**, qui est
   la seule chose que ce prototype fait bien (6 refus, 6 fois à raison) — et
   seulement si l'on peut le payer. Si ces 0,9 Go sont hors budget, ce signal
   se reconstruit à moindre coût avec deux bras lexicaux **réellement
   différents** (par exemple BM25 sur le texte contre BM25 sur les intitulés
   de la hiérarchie), à mesurer.
4. **Avant toute autre chose, refaire ce banc avec un encodeur de
   récupération asymétrique multilingue.** C'est la seule mesure qui peut
   réhabiliter la piste qui m'a été confiée, et je ne l'ai pas faite.

Si l'on tient malgré tout à fusionner deux bras sur ce corpus : **k=60 n'est
pas le bon réglage** (0,32 @1), et la somme des scores remis à l'échelle
min-max fait mieux que RRF sur les trois rappels (0,36 / 0,56 / 0,68) sans
demander davantage de réglage. L'argument « RRF ne demande rien à régler »
est le principal argument de vente de cette piste, et il ne tient pas à la
mesure.
