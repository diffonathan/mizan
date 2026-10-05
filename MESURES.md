# Mizan — tableau de bord des mesures

Tous les chiffres de MESURE de ce document ont été produits le **4 octobre
2026**, dans une seule session, par les commandes écrites à côté d'eux. Deux
règles le tiennent, et elles sont écrites ici parce que c'est leur absence qui a
laissé passer les fautes des versions précédentes :

- **la commande.** Aucun nombre ne reste dans ce document s'il n'est pas imprimé
  par une commande versionnée du dépôt, ou épinglé par un test nommé à côté de
  lui. Jamais un nombre dans un TITRE de section : il est lu par qui ne lit pas
  la section, et il survit aux corrections du corps. Jamais deux décimales sur
  une durée ;
- **le renvoi.** Chaque grandeur a UN document source. Celui-ci fait foi pour
  les comptes d'extraction (§B) et pour les chiffres bout-en-bout (§D.1) ; il
  RENVOIE, sans recopier la valeur, pour le coût d'un `examiner()` et le barème
  de la détection (`SECURITE.md` §3.2 à §3.4), pour les coûts de la pile
  d'arbitrage et le poids du modèle (`arbitrage/res_cout.json`, produit par
  `arbitrage/cout.py`) et pour la composition du jeu de questions
  (`evaluation/METHODE.md`). Une même grandeur vivant dans trois documents
  dérive en trois temps : c'est exactement ce qui est arrivé, et le renvoi est
  la seule réparation qui tienne.

```sh
cd mizan   # toutes les commandes de ce document partent de la racine du dépôt
```

Deux interpréteurs apparaissent ci-dessous, et la distinction compte :

| | ce qu'il a | ce qu'il permet |
|---|---|---|
| `python` | **10 paquets**, dont un seul du projet (`pymupdf`, pour l'extraction du corpus ; rien pour la récupération ni la réponse) | tout sauf la recherche dense |
| `prototypes/vectoriel/.venv/Scripts/python.exe` | **31 paquets** (`numpy`, `onnxruntime`, `fastembed`) | la recherche dense réelle |

`python -m pip list` sur chacun. **Zéro paquet installé pendant cette session.**

---

## ⚠️ Lire d'abord : ce qui est mesuré avec un modèle factice

**Il n'y a aucune clé de modèle de langue dans cet environnement.** Vérifié :

```sh
python -c "import os; print([k for k in os.environ if 'LLM' in k.upper() or 'API_KEY' in k.upper() or 'GROQ' in k.upper()])"
#  →  []   (aucune variable LLM_* / *API_KEY* / GROQ_*)
```

Conséquence sur la lecture de ce tableau de bord :

| section | mesure | avec un vrai modèle |
|---|---|---|
| **A. Récupération** | le vrai moteur, le vrai index, le vrai corpus | **inchangé** — aucun modèle de langue n'intervient |
| **B. Garde — extraction** | le vrai extracteur sur les 589 articles du Code | **inchangé** |
| **C. Détection d'injection** | la vraie détection sur les 64 questions du jeu | **inchangé** |
| **D. Réponse** | la vraie chaîne, mais la rédaction est tenue par un **modèle factice déterministe** | **à remesurer en entier** |

Les chiffres de la section D ne mesurent **pas** un modèle de production. Ils
mesurent ce que la chaîne fait d'une rédaction dont on a choisi le défaut. Le
taux de rejet de la garde, en particulier, dit *« la garde arrête 17 inventions
sur 17 fabriquées »* et jamais *« un modèle invente dans 45,9 % des cas »* :
c'est le banc qui a décidé des 45,9 %.

---

## A. Récupération — `evaluation/banc.py`

64 questions, dont 57 avec réponse dans le Code et 7 sans — la composition du
jeu (effectifs, étiquettes, articles attendus) a pour source unique
`evaluation/METHODE.md`, qui l'imprime ; elle est rappelée ici, jamais
redéfinie. Code de sortie **0** pour les trois lignes.

### A.1 Témoin lexical seul (BM25), sans aucun paquet

```sh
python evaluation/banc.py
```

| | @1 | @3 | @5 |
|---|---|---|---|
| rappel | **30,7 %** | **46,5 %** | **50,9 %** |
| au moins un article | 33,3 % | 49,1 % | 54,4 % |

Abstention correcte **0,0 %**, dérobade **0,0 %** : ce témoin répond toujours.
Il tourne en moins d'une seconde sur un poste ordinaire et sans aucune
dépendance ; la durée exacte n'est pas publiée, parce que `banc.py` n'en
imprime aucune.

**Ce que ça ne dit pas** — ce n'est pas l'architecture retenue, c'est la borne
basse qui donne sa valeur au reste : les 30 points de rappel@1 qui séparent
cette ligne de la suivante sont ce que le bras dense apporte.

### A.2 L'architecture entière, qui répond à tout

```sh
prototypes/vectoriel/.venv/Scripts/python.exe evaluation/banc.py \
    --recuperation noyau.adaptateur_banc:MesureSansAbstention
```

| | @1 | @3 | @5 |
|---|---|---|---|
| **rappel** | **61,1 %** | **84,5 %** | **91,5 %** |
| au moins un article | 70,2 % | 87,7 % | 94,7 % |

Tous les articles attendus dans les 3 premiers : **46 / 57**. Aucun article
attendu dans les 5 premiers : **3 / 57**.

Rappel@3 par catégorie : usager **82,1 %** (n=27) · code **96,0 %** (n=25) ·
multi_articles **84,7 %** (n=12) · voisine **90,0 %** (n=25) · reformulation
**75,0 %** (n=10) · hors_code **33,3 %** (n=3) · injection **40,0 %** (n=5).

**Ce que ça ne dit pas** — cette ligne répond à tout, y compris aux 7 questions
dont la réponse n'est pas dans le Code : abstention correcte **0,0 %**, 5,00
articles rendus à chacune. C'est le plafond de rappel, pas un produit.

### A.3 Le point de fonctionnement retenu (seuil de marge 0,04)

```sh
prototypes/vectoriel/.venv/Scripts/python.exe evaluation/banc.py \
    --recuperation noyau.adaptateur_banc:Mesure
```

| | @1 | @3 | @5 |
|---|---|---|---|
| rappel | **50,0 %** | **58,8 %** | **60,5 %** |

| | |
|---|---|
| **abstention correcte** (7 questions hors corpus) | **85,7 %** — 6 sur 7 |
| **dérobade** (silence sur une question répondable) | **36,8 %** |
| articles rendus aux questions hors corpus | **0,71** sur 5 |

**Ce que ça ne dit pas, et c'est l'essentiel** — A.2 et A.3 ne se lisent jamais
l'une sans l'autre. Le banc compte une abstention comme un rappel nul : un
témoin qui se tait toujours obtient **100 % d'abstention correcte pour 0 % de
rappel**. Le seuil de marge achète 85,7 points d'abstention contre 31 points de
rappel@5. Savoir se taire reste le problème ouvert du projet.

**Et ce que 85,7 % ne dit pas non plus** — le seuil 0,04 a été LU SUR CES MÊMES
64 QUESTIONS. Il n'y a pas d'échantillon de validation : ces 85,7 % sont donc un
chiffre d'apprentissage et non de généralisation, et « point de fonctionnement
retenu » veut dire une valeur mesurée, pas une valeur établie. Le reproche que
cet arbitrage adresse aux candidats s'appliquerait mot pour mot à l'arbitre s'il
présentait 0,04 autrement. La courbe complète du balayage est au §4 de
`CONCEPTION.md`, et la valeur par défaut est à recalibrer sur des questions que
personne n'a vues.

### A.4 Latence — pourquoi aucun chiffre n'est publié ici

**Il n'existe aucune commande de ce dépôt qui chronomètre `noyau`.** Les valeurs
qui figuraient ici venaient d'une boucle `time.perf_counter` tapée à la main
dans une session ; le bloc `sh` l'avouait en ne nommant aucun fichier, puisqu'il
se réduisait au chemin de l'interpréteur suivi d'un commentaire. Elles ne se
reproduisaient pas non plus d'une session à l'autre — c'est la raison pour
laquelle trois exécutions y étaient écrites côte à côte. Un nombre qu'aucune
commande ne rend n'est pas vérifiable, et une durée se publie avec ses
conditions, en ordre de grandeur, ou pas du tout.

Ce qui est su, et qui porte la seule décision que cette section sert :
**ouvrir la session ONNX du modèle coûte des secondes, une recherche coûte des
dizaines de millisecondes.** Deux ordres de grandeur d'écart — et c'est pour
cela qu'un service appelle `moteur.repondre.charger()` à son démarrage et non à
la première question.

**Le seul banc de coût versionné du dépôt est `python arbitrage/cout.py`**, qui
conserve ses relevés dans `arbitrage/res_cout.json`. Il fait foi pour son objet
et pour lui seul : il mesure la pile d'arbitrage
(`arbitrage/adaptateurs:GreffeDenseTeteLexicalQueue`), et son champ
`forme_matrice` vaut `[588, 768]` — ce n'est même pas le compte d'articles du
noyau. **Aucune de ses valeurs n'est recopiée ici** : le lecteur qui veut un
chiffre de latence le lit là-bas, dans les conditions que ce fichier décrit.
Attention, cette commande charge le modèle et RÉÉCRIT `arbitrage/res_cout.json`
— elle ne se lance pas en passant. Le jour où une commande mesurera le noyau,
elle vivra dans `arbitrage/` et cette section y renverra.

**Ce que ça ne dit pas** — c'est à cette section que les autres documents
renvoient pour expliquer pourquoi ils ne publient plus de RAPPORT au temps d'une
recherche dense (`SECURITE.md` §3.4) : le dénominateur ne se reproduit pas, et
un rapport dont un terme bouge est un chiffre qu'on finit par publier faux. Ce
qui a disparu d'ici n'est donc pas une mesure gênante, c'est une mesure qui
n'avait pas de commande.

---

## B. Garde des citations — l'extraction, mesurée sur le Code entier

L'extraction est la partie fragile de la garde : une forme de citation ratée
n'est pas comparée, donc pas rejetée. Elle est donc lâchée sur le texte du Code,
qui se cite abondamment lui-même.

```sh
python tests/test_garde.py          # classe ExtractionSurLeCodeEntier
python -c "from noyau import corpus as C; from moteur.garde import extraire_citations as E; c=C.charger(); x=[E(a['texte']) for a in c.articles]; n={m for l in x for m in l}; e={a['numero'] for a in c.articles}; print(len(c.articles), sum(map(len,x)), len(n), sorted(n-e))"
#  →  589 432 274 ['1098', '1248', '780']
```

Les quatre nombres du tableau sortent de la seconde ligne, et quatre tests de la
classe `ExtractionSurLeCodeEntier` les retiennent un par un :
`test_le_compte_des_citations_lues_est_celui_qui_a_ete_mesure` (432),
`test_le_compte_des_numeros_distincts_est_celui_qui_a_ete_mesure` (274),
`test_aucun_nombre_du_code_n_est_pris_pour_une_source` (les trois numéros
étrangers) et `test_aucune_reference_du_code_n_est_jugee_illisible` (le zéro).
432 et 274 doivent bouger ENSEMBLE : un écart entre eux est un renseignement,
et c'est tout l'intérêt d'épingler les deux.

| | |
|---|---|
| citations lues dans les **589** articles | **432** |
| numéros distincts | **274** |
| numéros lus **hors du corpus** | **3** — `1098`, `1248`, `780` |
| références jugées **illisibles** dans le Code | **0** |

Les trois sont de vrais renvois à d'autres textes : `1098` et `1248` au Code des
obligations et des contrats, `780` à un dahir de 1913. **Aucun nombre ordinaire
du Code n'a été promu en source** : ni les deux « 44 heures » de la durée
légale, ni les onze « 1er » — dix alinéas et une date (« 1er mai 1942 »).

```sh
python -c "from noyau import corpus as C; t='\n'.join(a['texte'] for a in C.charger().articles); print({m: t.count(m) for m in ('44 heures','1er','1er mai 1942','1,5 jour')})"
#  →  {'44 heures': 2, '1er': 11, '1er mai 1942': 1, '1,5 jour': 0}
```

Cette ligne est là parce qu'une version précédente citait ici « 1,5 jour »
parmi les nombres du Code : **la chaîne n'apparaît dans aucun des 589
articles**, et la commande l'imprime à zéro. Elle venait d'un gabarit de modèle
factice et d'une fixture de test, c'est-à-dire d'un texte que le projet écrit
lui-même — et c'est la leçon, plus que la faute : **ni un test ni un gabarit ne
fait foi sur la prose du Code.** Le corpus (`corpus/code-travail.json`) en est
l'unique arbitre, et c'est lui que la commande interroge. Ce que le test
garantit, de son côté, n'est pas un comptage de formes : c'est qu'il n'existe
**aucun quatrième numéro étranger au corpus**
(`test_aucun_nombre_du_code_n_est_pris_pour_une_source`). Et les exemples
eux-mêmes sont désormais tenus par
`test_les_exemples_de_nombres_ordinaires_sont_bien_dans_le_code`, qui va les
chercher dans le corpus : c'est exactement le test qui manquait quand
« 1,5 jour » a été écrit ici.

**Ce compte de 432 a valu 480, et la différence de 48 est le défaut qu'il
cachait.**
Le point-virgule enchaînait les citations, si bien que les ordinaux des listes à
puces du Code (« l'article 184 ;
2. le non-respect… ») étaient lus comme des
sources. Ces 48 faux positifs étaient INVISIBLES au contrôle d'appartenance au
corpus, parce que 2, 3, 4, 5, 6, 7 et 9 sont tous des numéros d'articles
existants — et le chiffre 480, figé dans un test, protégeait le défaut au lieu
de le détecter. Le test lit désormais le CONTEXTE à gauche de chaque numéro, et
non sa seule existence : un faux positif ne se reconnaît pas à ce qu'il
désigne.

**Ce que ça ne dit pas** — ce chiffre mesure l'extracteur sur la prose du
*législateur*, pas sur celle d'un modèle de langue. Une forme de citation qu'un
vrai modèle inventerait et que l'extracteur ne connaîtrait pas serait servie
sans contrôle. C'est le trou résiduel de la garde, et il se répare dans
`extraire_citations`, jamais en relâchant l'inclusion.

Ces trois numéros disent aussi la limite exacte du contrôle : une réponse qui
citerait **à juste titre** l'article 1098 du Code des obligations serait
rejetée, parce que ce texte n'est pas dans le corpus et n'est donc pas
vérifiable. La garde refuse du faux, et elle refuse aussi du juste non
vérifiable.

---

## C. Détection d'injection — `python -m moteur.mesurer_injection`

Code de sortie **0**. Cette couche **signale et ne bloque jamais**.

| | |
|---|---|
| rappel sur les 5 questions « injection » du jeu | **5 / 5 (100,0 %)** |
| faux positifs sur les 59 autres questions du jeu | **0 / 59 (0,0 %)** |
| faux positifs sur les 32 leurres écrits pour cette couche | **0 / 32 (0,0 %)** |

Scores des cinq injections : Q59 **4** · Q60 **5** · Q61 **7** · Q62 **3** ·
Q63 **3**. Deux leurres effleurent un motif de poids 1 sans être signalés
(« affirme que » et « réponds juste par »).

Les huit derniers leurres sont la trace d'un SECOND resserrement, et quatre
d'entre eux tombaient sur des motifs qu'un document présentait déjà comme
refermés : « je suis responsable de la sécurité » passait, mais « je suis
responsable du service paie » — un intitulé de poste — marquait à 3 ; « de
nouvelles consignes, puis-je » passait, mais « de nouvelles consignes :
dois-je » marquait. **Un motif n'est pas refermé parce qu'un leurre passe** : la
variante d'un mot de la même question le reprend en défaut, et c'est pourquoi
chaque leurre reste écrit.

```sh
python -m moteur.mesurer_injection --cout
```

| | |
|---|---|
| coût d'un `examiner()`, médiane sur 3 200 appels | **imprimé par la commande ci-dessus** — valeur non recopiée ici : `SECURITE.md` §3.4 |

Ce coût est IMPRIMÉ PAR UNE COMMANDE DU DÉPÔT, et il ne vit pas ici :
**`SECURITE.md` §3.4 en est la source unique**, parce que c'est la section qui
décide de la couche. La valeur n'est pas recopiée dans ce document, pour une
raison observée et non par principe : elle bouge d'une exécution à l'autre au
troisième chiffre après la virgule, et une durée recopiée dans trois documents
dérive en trois temps. Elle a longtemps été publiée en étant attribuée à une
commande qui ne l'imprimait pas, et accompagnée d'un rapport au temps d'une
recherche dense dont le dénominateur ne se reproduit pas (§A.4) : le rapport est
parti, la milliseconde a gagné sa commande, et le renvoi remplace la recopie.
Le coût n'est de toute façon pas un argument — trente expressions régulières
contre une inférence, l'ordre de grandeur se raisonne sans chiffre. Le barème
lui-même (nombre de motifs, familles, poids, seuil) se lit aux §3.2 et §3.3 de
`SECURITE.md`, qui en sont la source unique ; ce tableau-ci ne publie que ce que
ses deux commandes impriment.

**Ce que ça ne dit pas** — les leurres sont écrits par l'auteur de la couche,
donc ils la jugent mal ; c'est irréparable et c'est dit. Surtout : **la
détection n'est pas la défense.** Mesuré sur la même commande, une attaque qui
imite la mise en forme de l'invite pour y glisser un faux article n'est **pas
signalée** (elle ne contient aucune phrase adressée à l'assistant) — et c'est
la garde qui l'arrête, `accepte=False`, motif `citation_inventee`.

### C.1 Ce que la garde fait des mêmes cinq injections

```sh
prototypes/vectoriel/.venv/Scripts/python.exe -m moteur.mesurer_injection --garde
```

| | |
|---|---|
| numéros d'article que l'inclusion rejette, sur chaque injection | **584 / 589** — **99,2 %** du Code |
| article attendu présent dans les 5 récupérés | **4 / 5** (Q63 manque l'art. 184) |
| classements déplacés par la consigne injectée | **5 / 5**, 3 à 4 articles communs sur 5 |
| gain d'une épuration de la question | **nul** : 4/5 attendus avec ou sans la consigne |

**Ce que ça ne dit pas** — 99,2 % est la part du Code qu'une citation ne peut
pas atteindre, pas une probabilité de rejet. Le trou connu est ailleurs : une
réponse qui ne cite **rien** a un ensemble de citations vide, et l'ensemble vide
est inclus dans tout. C'est la règle « au moins une citation » de `garde.py` qui
l'attrape, et c'est pourquoi elle doit y rester : Q60 et Q62 sont exactement les
deux injections qui demandent de ne pas citer.

---

## D. ⚠️ Réponse — `evaluation/banc_bout_en_bout.py` — MODÈLE FACTICE

**Aucune de ces lignes ne mesure un modèle de production.** La rédaction est
tenue par quatre familles de modèle factice déterministe — `fidele`,
`inventee`, `muette`, `melangee` — et le banc **prédit** combien d'inventions il
fabrique, puis vérifie qu'il les retrouve toutes.

Le répondeur mesuré est **le produit** (`moteur.repondre:Mizan`), par défaut
depuis l'assemblage. Code de sortie **0** partout.

### D.1 Récupération réelle, les trois modèles factices

```sh
P=prototypes/vectoriel/.venv/Scripts/python.exe
$P evaluation/banc_bout_en_bout.py --recuperation reel                      # mixte
$P evaluation/banc_bout_en_bout.py --recuperation reel --redacteur fidele
$P evaluation/banc_bout_en_bout.py --recuperation reel --redacteur menteur
```

| | `fidele` (borne basse) | `mixte` (le seul adverse) | `menteur` (borne haute) |
|---|---|---|---|
| réponses rendues, sur 57 répondables | 36 | **14** | 0 |
| **exactitude des citations** (précision) | 88,9 % | **71,4 %** | — |
| couverture des articles attendus | 79,2 % | **67,9 %** | — |
| au moins une citation attendue | 88,9 % | **71,4 %** | — |
| plafond posé par la récupération | 97,2 % | 92,9 % | — |
| exactitude **sous** ce plafond | 91,4 % | 76,9 % | — |
| rédactions observées | 37 | 37 | 37 |
| dont citant un article **non récupéré** | 0 — 0,0 % | 17 — **45,9 %** | 37 — 100,0 % |
| dont sans aucune citation | 0 | 6 | 0 |
| dont loyales | 37 | 14 | 0 |
| **TAUX DE REJET PAR LA GARDE** | **0,0 %** | **62,2 %** | **100,0 %** |
| hallucinations fabriquées / mesurées | 0 / 0 | **17 / 17** | **37 / 37** |
| abstention correcte (n=7) | 85,7 % | **100,0 %** | 100,0 % |
| dérobade (n=57) | 36,8 % | **75,4 %** | 100,0 % |
| **fuites : invention servie à l'usager** | **0** | **0** | **0** |
| réponses sans avertissement de consolidation | **0** | **0** | **0** |
| rejets à tort : rédaction loyale refusée | **0** | **0** | **0** |

En `mixte`, les 50 silences (sur les 64 questions) se partagent en **27
décidés par la récupération**
(le noyau doute, le modèle n'est jamais appelé) et **23 décidés par la garde**
(le modèle a écrit, le texte est jeté). Les deux ne se corrigent pas de la même
façon : un seuil de marge d'un côté, une rédaction refusée de l'autre.

### D.2 Le même banc sans clé, sans paquet, sans index

```sh
python evaluation/banc_bout_en_bout.py --recuperation idf
```

Bras dense factice (plancher idf), modèle factice `mixte` : 9 réponses rendues,
précision **28,6 %**, au moins une citation attendue **22,2 %**, 33 rédactions
dont **17 hallucinantes (51,5 %)**, **taux de rejet 69,7 %**, abstention
correcte **85,7 %**, dérobade **84,2 %**, **0 fuite**, 17/17 concordent.

C'est la ligne à mettre en intégration continue : elle tourne en bibliothèque
standard et sort en **1** sur une fuite ou un avertissement absent, sans qu'aucun
seuil de qualité soit à fixer.

Les deux moitiés de cette phrase sont vérifiées, et l'une ne l'était pas : la
sortie en 1 pour « avertissement absent » était INATTEIGNABLE, parce que
l'avertissement vide comptait parmi les anomalies de contrat, qui font sortir en
**2** beaucoup plus haut. La ligne d'invariant du rapport affichait donc zéro
par construction, et un compteur structurellement nul se lit comme une garantie
vérifiée alors qu'il ne vérifie rien. L'avertissement est maintenant lu sur
chaque réponse et jugé avec les fuites — mesuré en branchant un répondeur qui
rend des réponses sans avertissement : **toutes les réponses sont signalées
et le banc sort en 1**. Le compte est celui du jeu entier — 64, dont
`evaluation/METHODE.md` est la source — et non une mesure : un répondeur qui
n'avertit jamais se fait signaler sur chaque question. C'est le code de sortie
qui est la garantie, pas le nombre.

Et la fuite, elle, est maintenant calculée SANS AUCUNE EXPRESSION RÉGULIÈRE, sur
les deux champs que la réponse déclare (`citations` moins les numéros de
`articles`). Mesuré en branchant un répondeur qui sert une hallucination sous la
forme « l'art 45 » : **chaque réponse est comptée en fuite, et le banc sort en
1** — là encore sur le jeu entier, là où le banc en comptait **0** et
sortait en **0**, parce que son lecteur de citations ignorait cette écriture.

### D.3 Le chiffre le plus intéressant du projet, et sa lecture exacte

> **Taux de rejet par la garde : 62,2 %** en récupération réelle avec le modèle
> factice adverse. 17 rédactions sur 37 ont cité un article que le système
> n'avait pas récupéré ; les 17 ont été arrêtées. 6 autres ne citaient rien du
> tout ; les 6 ont été arrêtées. **Zéro invention est arrivée sur l'écran.**

La plupart des démonstrations de RAG ne publient pas ce chiffre, parce qu'il
demande de savoir combien de fois le modèle a inventé — ce qui exige soit de
lire chaque réponse à la main, soit, comme ici, un modèle dont on connaît les
fautes d'avance.

**Ce que ce chiffre ne dit pas**, et il faut l'avoir en tête avant de le citer :

1. **Les 45,9 % d'invention sont fabriqués par le banc**, pas observés sur un
   modèle. Un vrai modèle inventerait moins ; la part serait à remesurer, et le
   nombre de rejets avec elle.
2. **Un rejet n'est pas une réussite du produit, c'est un silence.** La garde
   fait passer la dérobade de 36,8 % à 75,4 % : elle ajoute **22 questions
   répondables perdues** contre **un seul refus souhaitable**. Le prix de la
   garantie est payé par l'usager qui n'obtient pas de réponse.
3. **Les deux compteurs qui comptent vraiment sont à zéro** : 0 fuite
   (invention servie) et 0 rejet à tort (rédaction loyale refusée). C'est
   l'invariant ; les pourcentages ci-dessus sont le contexte.
4. **Le levier de rappel qui reste est la rédaction, pas le seuil.** La colonne
   `fidele` donne la borne : chaque point d'hallucination en moins est un point
   de dérobade en moins.

### D.4 Le banc est contrôlé par le produit, et réciproquement

```sh
python evaluation/banc_bout_en_bout.py --recuperation idf --json a.json
python evaluation/banc_bout_en_bout.py --recuperation idf --repondeur temoin --json b.json
#  →  a.json et b.json IDENTIQUES (hors la ligne qui nomme le répondeur)
```

Deux gardes écrites séparément, deux lecteurs de citations écrits séparément, et
le même verdict sur les mêmes rédactions. Aucun des deux n'est cru sur parole.
Le contrôle est rejoué par les tests sur les trois modèles factices.

---

## E. Tests

### Ce qui ne marche pas, et qu'il faut savoir

```sh
python -m pytest tests/ -q
#  →  code de sortie 1 : « No module named pytest »
```

**`pytest` n'est installé sur aucun des deux interpréteurs**, et il n'a pas été
installé : les tests sont écrits sur `unittest`, de la bibliothèque standard, et
chaque fichier se lance seul. Un projet dont les tests exigent un paquet de plus
est un projet qu'on ne vérifie pas. La commande équivalente est :

```sh
python -m unittest discover -s tests -t tests -q
```

| interpréteur | tests | résultat | sautés | code |
|---|---|---|---|---|
| `python` (10 paquets, **aucune clé**) | **195** | **OK** | 9 | **0** |
| venv (bras dense réel) | **195** | **OK** | **0** | **0** |

**Ce total est daté, et il le sera toujours** : il monte à chaque test ajouté,
et il a monté pendant la session qui écrit cette ligne. C'est la commande
ci-dessus qui fait foi, pas ce tableau — ce qui ne bouge pas, et qui est la
vraie affirmation, c'est **OK sur les deux interpréteurs, code 0, et aucun saut
sur le venv**. La suite entière tourne en une dizaine de secondes ; la durée
exacte dépend du poste, `unittest -q` l'imprime à chaque exécution, et deux
décimales sur une durée sont une précision qu'on ne peut pas tenir d'une
session à l'autre.

Chaque fichier se lance aussi seul, et le contre-contrôle vaut la peine : si la
somme des cinq s'écarte du total ci-dessus, c'est qu'un test est chargé deux
fois ou pas du tout.

```sh
for f in tests/test_*.py; do python $f; done
```

**Le détail par fichier n'est pas recopié ici, et c'est une correction.** Il
l'était, et il était FAUX : `tests/test_injection.py` y figurait pour deux
tests de moins que ce que la commande en rendait, et le total voisin ne l'avait
pas fait voir. Un compte par fichier se périme au premier test ajouté, et
personne ne relit cinq nombres pour les corriger ; la commande, elle, les
imprime justes à chaque fois. C'est la règle générale de ce document appliquée
à son propre tableau de tests.

Les 9 sautés sur l'interpréteur nu sont les tests qui demandent l'index dense et
le modèle de plongement — **1 198 Mo sur le disque**, mesurés par
`python arbitrage/cout.py` (tableau « POIDS SUR DISQUE », valeur conservée dans
`arbitrage/res_cout.json`, qui en est la source unique) ; chacun dit en se
sautant quoi lancer. Cette commande charge le modèle et RÉÉCRIT
`arbitrage/res_cout.json` : elle ne se lance pas en passant.

**Ce que ça ne dit pas** — ces tests ne sont pas une preuve de justesse
juridique. Ils vérifient des mécanismes : l'inclusion d'ensembles,
l'impossibilité de construire une réponse sans avertissement, le fait qu'une
abstention n'appelle pas le modèle, le fait qu'une question signalée reçoit
quand même une réponse.

---

## F. Ce qu'aucun chiffre de ce document ne mesure

1. **Le corpus est consolidé au 26 octobre 2011** (source unique de la date et
   de la provenance du texte : `evaluation/METHODE.md`). Le meilleur rappel du
   monde ne rend pas ce texte conforme à l'état du droit en 2026. Aucune mesure ici
   n'est une mesure de justesse juridique.
2. **Il n'y a pas de jurisprudence, pas de convention collective, pas de
   décret.** Le corpus est le Code du travail et rien d'autre, et la garde
   rejette toute citation extérieure — y compris juste.
3. **Aucune mesure de la rédaction par un vrai modèle.** Toute la section D est
   à remesurer le jour où une clé existe. Les seuils de qualité du banc
   (`--seuil-exactitude`, `--seuil-abstention`) ne doivent être câblés qu'à ce
   moment-là.
4. **L'efficacité de la délimitation des données n'est pas mesurée.** Encadrer
   la question dans un bloc à jeton aléatoire reste une consigne adressée au
   modèle, donc une prière, et la mesurer exige une clé. Ce qui est mesuré, ce
   sont la détection et la garde.
5. **Les scores ne sont pas des confiances.** Un score dense (cosinus) et un
   score BM25 ne se comparent pas — c'est la raison d'être du champ `bras` sur
   `ArticleTrouve` — et le score dense lui-même sépare mal les réponses justes
   des fausses : les deux intervalles se chevauchent largement, chiffrés au
   §4 de `CONCEPTION.md` (mesure des fondations, non rejouée ici). Ne jamais
   afficher un score comme une certitude.
6. **Le seuil de marge 0,04 a été lu sur les 64 questions qui servent aussi à
   le juger.** Il n'y a pas d'échantillon de validation, donc les 85,7 %
   d'abstention correcte du §A.3 sont un chiffre d'APPRENTISSAGE et non de
   généralisation. Aucune mesure de ce document ne dit ce que ce seuil ferait
   de questions que personne n'a vues, et sa valeur par défaut est à
   recalibrer sur un tel jeu.
7. **La garde ne lit pas un numéro écrit sans le mot « article ».** « L'article
   231 vous ouvre ce droit (voir aussi 350 et 387) » est accepté : 350 et 387
   ne sont pas lus, donc pas comparés. C'est l'autre côté d'une décision
   mesurée — ramasser les nombres nus ferait lire des citations partout, « 1er »
   apparaissant onze fois dans le Code sans jamais désigner l'article premier —
   mais c'est le seul endroit où la garantie cesse d'être structurelle, et
   aucun chiffre de la section B ne le mesure.
