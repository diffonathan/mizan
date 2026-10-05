# Mesurer la RÉPONSE, et non la récupération — méthode du banc de bout en bout

`banc.py` répond à une question : **l'article attendu était-il sur la table ?**
C'est nécessaire, et ce n'est pas la promesse du produit. La promesse est une
réponse rédigée **qui cite**, et une citation fausse est pire qu'une absence de
réponse — parce que la citation est précisément ce qui donne confiance.

Ce document dit ce que `banc_bout_en_bout.py` mesure, ce qu'il ne mesure pas, et
pourquoi un chiffre obtenu avec un faux modèle n'est pas un chiffre de
production.

**Tout nombre de mesure écrit ici sort d'une commande du §7, lancée dans la
session qui a écrit ce fichier.** Trois nombres viennent d'ailleurs et sont
nommés avec leur source : la reprise de `CONCEPTION.md` §4 au §5, et la
couverture du jeu (57 articles sur 589) et la date de consolidation au §8, qui
viennent de `METHODE.md` et du corpus. Le compte de tests, lui, n'est plus
publié ici en valeur : il se périme à chaque test ajouté, et sa source unique
est `MESURES.md` §E, qui nomme sa commande à côté du total.

---

## 1. Les trois grandeurs, et pourquoi elles ne se confondent pas

### 1.1 Exactitude des citations

Mesurée sur les réponses **rendues** aux questions répondables, contre les
`articles_attendus` de `questions.json`. Quatre chiffres, parce qu'un seul
mentirait :

| mesure | définition |
|---|---|
| précision des citations | moyenne par question de `justes / (justes + fautives)` |
| couverture des articles attendus | moyenne par question de `justes / attendus` |
| au moins une citation attendue | part des réponses rendues qui citent au moins un article attendu |
| aucune citation attendue | leur complément, en nombres absolus — ce sont les réponses **fausses rendues**, et c'est la ligne à lire en premier |

Les articles `articles_toleres` du jeu ne comptent **ni en réussite ni en
faute** — même convention que `banc.py`, et pour la même raison : les compter en
réussite gonflerait l'exactitude, les compter en faute punirait une citation
correcte. Une réponse qui ne cite que des tolérés n'a donc pas de précision
définie et sort de la moyenne, plutôt que d'y entrer comme un zéro.

**Cette grandeur est plafonnée par la récupération**, et le banc imprime le
plafond à côté d'elle. Une citation ne peut être juste que si l'article a été
récupéré ; en dessous du plafond, la rédaction ne *pouvait pas* citer juste. La
ligne « exactitude sous ce plafond » isole donc la part qui appartient vraiment
à la rédaction. Sans ces deux lignes, on reprocherait à la génération ce que la
recherche n'a pas fourni.

**Ce qu'elle ne mesure pas** : la fidélité du texte aux articles qu'il cite. Une
réponse peut citer exactement les bons articles et dire le contraire de ce qu'ils
disent. Mesurer cela demanderait un jugement sur le fond — un annotateur humain,
ou un modèle juge, c'est-à-dire un chiffre que personne ne pourrait recalculer.
Ce banc n'y touche pas, et c'est le plus gros trou de l'évaluation du projet.

### 1.2 Rejet par la garde

C'est la mesure la plus intéressante du projet : **combien de fois le modèle a
inventé un numéro d'article**, et combien de fois cela a été attrapé.

La garantie du projet est une inclusion d'ensembles : l'ensemble des articles
cités doit être inclus dans `resultat.numeros`. Toute citation hors de cet
ensemble fait rejeter la réponse **entière** — et non la seule citation
fautive : une réponse dont on retire un article cesse de dire ce que son texte
dit.

Le banc distingue trois issues, qui ne se lisent pas de la même façon :

```
hallucination REJETÉE      le modèle a inventé, la garde a refusé      → attendu
hallucination RENDUE       le modèle a inventé, la garde a laissé passer
                           → FUITE. Un invariant brisé, pas une mesure.
rédaction loyale REJETÉE   rien d'inventé, et la garde a refusé
                           → garde trop zélée : du rappel perdu pour rien.
```

**Ce qu'elle ne mesure pas** : la pertinence de ce que le modèle cite quand il
n'invente pas. Un article **réel, récupéré et hors sujet** traverse la garde
intacte — la garde vérifie une provenance, pas une pertinence. C'est la
grandeur 1 qui le voit, et c'est la raison pour laquelle les deux grandeurs sont
inséparables. Un système à 0 % d'hallucination et 30 % de citations justes est un
système qui ne sert à rien, et il n'est pas moins dangereux pour être honnête sur
ses sources.

### 1.3 Abstention

| mesure | sur | réussir, c'est |
|---|---|---|
| abstention correcte | les 7 questions sans réponse dans le Code | se taire |
| dérobade | les 57 questions répondables | ne pas se taire |

Les deux ne se lisent **jamais** l'une sans l'autre : un système qui se tait
toujours obtient 100 % d'abstention correcte et 100 % de dérobade. Le témoin
`menteur` du §5 le montre noir sur blanc, et c'est à cela qu'il sert.

Le banc décompose en outre les silences par leur **cause**, parce que les deux ne
se corrigent pas de la même façon :

- **silence décidé par la récupération** — la marge est sous le seuil, le
  répondeur n'a même pas fait rédiger. Se corrige en déplaçant le seuil.
- **silence décidé par la garde** — une rédaction a été produite puis refusée.
  Se corrige du côté du modèle ou de l'invite, pas du seuil.

---

## 2. Le banc ne croit pas le répondeur sur parole

C'est le principe du projet appliqué au banc lui-même. Le répondeur annonce
`abstenu` et `raison` ; le banc ne s'en contente pas, parce qu'un répondeur qui
laisse fuiter une hallucination n'a aucune raison de l'annoncer.

Le banc **fournit lui-même le modèle de rédaction**, enveloppé dans
`RedacteurObserve` : il garde le texte brut produit, en extrait les citations de
son côté, et vérifie l'inclusion dans l'ensemble récupéré tel qu'il figure sur la
`Reponse`. C'est la seule façon de distinguer une hallucination rejetée d'une
hallucination rendue — et donc de mesurer la garde au lieu de la croire.

Conséquence pratique à connaître : un répondeur qui **ne sait pas prendre** un
modèle en paramètre est mesuré **en aveugle**. Le banc l'écrit en tête de sa
sortie et laisse les lignes de la grandeur 2 vides, plutôt que d'imprimer des
zéros rassurants. Le banc inspecte la signature du répondeur et lui passe le
modèle si elle porte un paramètre `redacteur`, `modele` ou `generateur`.

Le banc refuse également de mesurer une sortie malformée. `controler_reponse`
vérifie, avant tout calcul : les six attributs du contrat
(`ATTRIBUTS_DE_REPONSE`, gelé par `test_controle_signale_un_attribut_manquant`),
les citations en chaînes et non en entiers, les citations qui existent dans le
corpus, l'avertissement de consolidation non vide, une abstention sans texte et
avec raison, une réponse rendue avec texte et citations. En cas d'anomalie, le banc
sort en **code 2** sans produire un chiffre — comme `banc.controler_jeu` refuse
de mesurer un jeu incohérent. Un banc qui mesure une sortie malformée produit un
chiffre faux avec aplomb.

---

## 3. Pourquoi un chiffre du factice n'est pas un chiffre de production

Aucune clé de modèle de langue n'est disponible dans l'environnement de ce
projet, et un banc qui ne tourne que chez son auteur ne mesure rien. Le banc
tourne donc par défaut avec un **modèle factice déterministe**, et il l'écrit en
tête de sa sortie ainsi que dans son JSON (`production: false`).

Un chiffre obtenu avec le factice mesure **la chaîne** — la garde, l'extraction
des citations, l'abstention, le comptage. Il ne mesure **rien du modèle** :

- le **taux d'hallucination** du factice est celui que le factice a décidé, pas
  celui d'un modèle de langue ;
- l'**exactitude des citations** du factice reflète seulement la règle qu'il
  suit (citer l'article de tête) ;
- la **dérobade** mesurée dépend directement du taux d'hallucination du factice,
  donc du factice.

En revanche, trois choses mesurées avec le factice valent pour la production,
parce qu'elles ne dépendent pas du modèle : **zéro fuite**, **zéro réponse sans
avertissement**, et la **concordance** du §4. Ce sont des propriétés du code.

Le drapeau `production` du JSON n'est vrai que si **les deux étages** le sont :
un vrai modèle branché sur la récupération factice ne mesure pas le produit, et
l'inverse non plus.

---

## 4. Le factice n'est pas complaisant, et le banc le vérifie

Un banc dont le faux modèle réussit toujours ne mesure rien : il mesurerait
seulement qu'un répondeur sait recopier un numéro. Le factice fabrique donc, de
façon déterministe et documentée, les sorties qu'une chaîne honnête doit refuser.

Quatre familles, tirées par un condensé `blake2b` du texte de la question —
`hashlib` et non `hash`, dont le salage par processus ferait changer la
composition à chaque lancement :

| famille | ce qu'elle écrit | ce que la garde doit faire |
|---|---|---|
| `fidele` | cite l'article de tête, récupéré | rendre |
| `inventee` | cite un article **réel du corpus mais non récupéré** | rejeter |
| `muette` | rédige un texte plausible sans aucun numéro | rejeter |
| `melangee` | cite un article récupéré **et** un article non récupéré | rejeter **entièrement** |

L'article inventé est choisi **dans le corpus**, pas hors de lui : un modèle de
langue n'invente pas « l'article 9 000 », il cite de mémoire un article réel qui
ne répond pas à la question. C'est ce cas-là qu'il faut attraper, et il est plus
difficile que l'autre — un contrôle d'existence le laisserait passer, seule
l'inclusion dans l'ensemble récupéré l'arrête.

Deux replis, pour que le factice ne fabrique jamais une citation à partir de
rien : `fidele` et `melangee` retombent sur `muette` quand la récupération n'a
rendu aucun article, et une famille hallucinante retombe sur `fidele` ou
`muette` s'il ne reste aucun article non récupéré à citer. **La famille
enregistrée au journal est le tirage, pas le repli** — `RedacteurObserve.famille`
rend le tirage brut : un repli déclenché ferait donc apparaître un écart entre
hallucinations fabriquées et mesurées qui ne viendrait pas de la garde. Aucun ne
se déclenche sur ce jeu, et c'est la condition du contrôle du paragraphe
suivant.

**Le contrôle du banc sur lui-même.** Comme la composition est déterministe, le
banc sait **prédire** combien d'hallucinations il doit mesurer :
`inventee + melangee`. Il imprime les deux nombres et dit s'ils concordent. Sur
les sept exécutions du §6, ils concordent à chaque fois. Un écart ne signalerait
pas un mauvais modèle : il signalerait que la garde, l'extraction des citations ou
le comptage ne font pas ce qu'ils disent. Un banc qui ne sait pas prédire ses
propres rejets ne vérifie pas la garde, il la croit.

### Le banc lit les citations avec son propre lecteur, et c'est voulu

Un banc qui vérifierait la garde avec **l'extracteur de la garde** ne pourrait
pas détecter un défaut de cet extracteur : les deux se tromperaient ensemble, et
le banc imprimerait « zéro fuite » sur une chaîne percée. Le banc a donc son
lecteur, écrit séparément, et le désaccord des deux lecteurs est **visible dans
deux compteurs** :

- une citation que **seul le banc** lit → la réponse est servie et le banc la
  compte en **fuite** ;
- une citation que **seul le produit** lit → la réponse est rejetée et le banc
  la compte en **rejet à tort**. Avec une réserve, et elle est du côté
  défavorable : `rejet_a_tort` exige une rédaction *loyale*, c'est-à-dire que
  le lecteur DU BANC y ait lu au moins une citation. Une citation que seul le
  produit lit laisse donc le banc avec zéro citation lue, et la ligne tombe en
  « rejetée sans citation » plutôt qu'en rejet à tort. Ce sens-là du désaccord
  reste invisible, et c'est une raison de plus de tenir les deux périmètres
  alignés.

**L'indépendance porte sur l'ÉCRITURE du lecteur, pas sur son périmètre**, et
cette phrase est une correction : les deux lecteurs ne déclaraient pas lire la
même chose. Le lecteur du
banc ignorait « art 45 » sans point et « article n° 45 » — une hallucination
réellement servie sous cette forme était comptée **0 fuite** et le banc sortait
en **0** —, et il traitait « - » et « a » comme des ouvre-plages, les deux
écritures que la garde refuse par décision documentée et testée : une rédaction
loyale contenant « soit 1,5 jour par mois » faisait alors déclarer **33 fuites**
et sortir en **1** sur un comportement correct du produit. Deux lecteurs qui ne
couvrent pas le même périmètre ne se contrôlent pas, ils se contredisent.

**Et l'invariant lui-même ne dépend plus d'aucun lecteur.** Une réponse rendue
qui déclare citer un article qu'elle ne déclare pas avoir récupéré est une
fuite, calculée sur `citations` moins les numéros de `articles` — deux champs
que la réponse porte déjà. C'est l'invariant du projet pris littéralement, sans
expression régulière, et c'est ce qui empêche le banc de rester vert à travers
une régression de la garde.

Les deux lecteurs sont ancrés sur le mot « article » et jamais sur les nombres
seuls — « le 1er alinéa de l'article 9 » et « 1er mai 1942 » existent dans le
Code, et une lecture qui ramasserait les nombres y verrait des citations partout.
Celui du banc lit « l'article 231 », « art. 231 et 238 », « art 231 » sans
point, « article n° 231 », « articles 27, 28 et 30 », « l'article premier », et
**déplie les plages** : « les articles 205 à 208 » rend quatre numéros, parce
que n'en rendre que deux laisserait deux numéros hors du contrôle d'inclusion,
c'est-à-dire laisserait passer ce que la garde devait arrêter. Il refuse les
mêmes ouvre-plages que la garde — le tiret, qui est d'abord une ponctuation, et
le « a » sans accent, qui est d'abord le verbe avoir —, il n'enchaîne pas une
citation sur un nombre de prose (« l'article 238, 18 jours ouvrables »), et il
ferme le numéro, si bien que « l'article 65-99 » ne rend pas 65. Une plage à
l'envers, à borne non chiffrée, ou dont les bornes s'écartent de plus de 50
(`PLAGE_MAXIMALE`, gelée par `test_une_plage_absurde_n_est_pas_depliee`), n'est
pas dépliée : ses deux bornes sont rendues telles quelles, parce que déplier
« les articles 1 à 589 » fabriquerait des centaines de citations pour le compte
du modèle. C'est l'écart entre les deux bornes qui est plafonné, et non le
nombre de numéros rendus : « les articles 1 à 51 » est donc encore déplié, et il
en rend 51.

Les six écritures listées plus haut sont toutes figées par un test, ainsi que
deux des trois refus de dépliage : la plage à l'envers et la plage trop large.
Le troisième, la plage à borne non chiffrée (« l'article premier à 5 »), n'a
aucun test — c'est le seul endroit de cette liste qui tient sur la lecture du
code et non sur une vérification. Un test de plus compare les deux lecteurs sur
les écritures où ils divergeaient.

---

## 5. Les trois témoins, qui encadrent la mesure

Ils sont au banc de bout en bout ce que `mots`, `idf` et `muet` sont à
`banc.py` : ils ne concourent pas, ils empêchent une lecture flatteuse.

| témoin | ce qu'il force | ce que la garde doit mesurer |
|---|---|---|
| `--redacteur fidele` | aucune invention | **0 %** de rejet |
| `--redacteur menteur` | invention systématique | **100 %** de rejet |
| `--redacteur mixte` | les quatre familles | entre les deux |

Mesuré au §6 : `fidele` → 0,0 % de rejet, `menteur` → 100,0 % de rejet. Si le
premier rejetait quoi que ce soit, la garde serait trop zélée ; si le second
laissait passer quoi que ce soit, elle serait une prière. Les deux bornes
vérifient le banc **avant** qu'on lise le chiffre du milieu.

Le témoin `fidele` sur la récupération réelle a une seconde vertu : comme il cite
toujours l'article de rang 1, son « au moins une citation attendue » **est** la
justesse au rang 1 des questions servies. Mesuré ici (modèle factice `fidele`,
récupération réelle, et c'est en réalité une mesure de la RÉCUPÉRATION au
rang 1) : **32 des 36 réponses rendues**, soit 88,9 %. *(Pour comparaison, et
c'est un nombre repris de `CONCEPTION.md` §4 et non remesuré ici : l'arbitrage
des fondations annonce
32 bonnes premières réponses au seuil de marge 0,04. Les deux chemins se
rejoignent, ce qui est le contrôle de cohérence le moins coûteux que ce banc
puisse offrir sur son branchement au noyau.)*

### Le répondeur par défaut est le produit ; le témoin reste une borne

`RepondeurTemoin` est la chaîne la plus courte qui respecte le contrat partagé :
récupérer, faire rédiger, vérifier, rendre ou se taire. Il n'a ni mise en forme,
ni affichage des candidats sous le seuil, ni soin apporté à l'invite. Il a
existé pour que le banc produise des chiffres avant que l'étage de réponse soit
écrit, et pour qu'on puisse vérifier le banc avant de lui faire confiance.

**Depuis l'assemblage du projet, `--repondeur` vaut par défaut
`moteur.repondre:Mizan` : le banc mesure le produit.** Un banc qui mesure par
défaut sa propre reconstitution de la chaîne mesure quelque chose qui n'est
livré à personne — les deux rapports se superposaient au moment où ils ont été
comparés, mais rien n'obligeait le produit à rester d'accord. `--repondeur
temoin` reste atteignable comme borne de comparaison, et deux tests retiennent
l'ensemble : l'un vérifie que le défaut est bien le produit, l'autre que les
deux rapports se superposent encore.

### Le contrôle croisé avec le répondeur du produit

L'étage de réponse du produit existe (`moteur/`), et le banc a été branché
dessus : `--repondeur moteur.repondre:Mizan`. **Sur les trois modèles factices,
les deux rapports se superposent ligne pour ligne** — mêmes rédactions
observées, mêmes hallucinations, mêmes rejets, mêmes abstentions, zéro fuite des
deux côtés — en récupération réelle par la comparaison des JSON ci-dessous, et en
récupération factice par `test_les_deux_gardes_rejettent_la_meme_chose`, qui
rejoue le contrôle sur les trois modèles. Comparaison des JSON en mode `reel` :

| | témoin du banc | `moteur.repondre:Mizan` |
|---|---|---|
| `mixte` | 37 rédactions, 17 hallucinations, 62,2 % de rejet | **identique** |
| `fidele` | 37 rédactions, 0 hallucination, 0,0 % de rejet | **identique** |
| `menteur` | 37 rédactions, 37 hallucinations, 100,0 % de rejet | **identique** |

Ce n'est pas une redondance, c'est la seule mesure du dossier qui ne repose sur
la parole de personne : **deux gardes écrites séparément, deux lecteurs de
citations écrits séparément, et le même verdict sur les 37 rédactions**. Si l'un
des deux avait un trou, le compteur de fuites ou celui des rejets à tort le
dirait. Le contrôle est rejoué par les tests, et il se **saute** proprement si
`moteur/` n'est pas là — le banc doit rester mesurable seul.

---

## 6. Ce qui a été mesuré

Sept exécutions dont les rapports JSON ont été comparés, dans la session qui a
écrit ce fichier : les quatre ci-dessous avec le répondeur par défaut, qui est le
produit (`moteur.repondre:Mizan`), et les trois du contrôle croisé du §5,
lancées avec `--repondeur temoin`, qui leur sont identiques. Les deux étages
sont nommés sur chaque ligne, et aucune de ces lignes n'est une mesure de
production.

**Récupération réelle** (noyau, index dense `google/embeddinggemma-300m`, seuil de
marge 0,04, k = 5), **modèle factice** :

> **Les valeurs de ce tableau vivent dans `MESURES.md` §D.1, et nulle part
> ailleurs.** Ce document-ci est celui de la MÉTHODE : il dit ce que chaque
> ligne mesure et pourquoi elle existe. Les recopier ici en ferait une seconde
> source, qui dériverait de la première au premier rejeu sans que rien ne le
> signale — c'est précisément ce qui est arrivé à ce dossier, et le renvoi est
> la seule réparation qui tienne.

Ce que les lignes mesurent, et ce qu'il faut lire ensemble :

- **réponses rendues**, **précision des citations**, **couverture des articles
  attendus** — la qualité de ce qui sort, sur les seules questions répondables.
- **plafond posé par la récupération** et **exactitude sous ce plafond** — les
  deux ne se lisent jamais séparément : la rédaction ne peut pas citer un
  article que la récupération ne lui a pas donné, donc la juger sans son
  plafond revient à lui reprocher le travail d'une autre couche.
- **rédactions observées** contre **dont citant un article non récupéré** — le
  numérateur de l'hallucination. Le factice en FABRIQUE un nombre connu : c'est
  ce qui permet de vérifier que la garde les voit toutes.
- **taux de rejet par la garde**, **hallucinations fabriquées / mesurées** — la
  seule garantie du dossier, et elle se vérifie par l'égalité des deux termes :
  autant d'hallucinations mesurées que fabriquées, sinon la garde en laisse
  passer.
- **abstention correcte** et **dérobade** — les deux faces du silence. La
  première est un succès (la question n'avait pas de réponse dans le corpus),
  la seconde un coût (elle en avait une). Publier l'une sans l'autre
  permettrait à un système qui se tait toujours d'afficher 100 %.
- **fuites**, **réponses sans avertissement**, **rejets à tort** — des
  invariants : ils doivent valoir zéro, et un zéro qui vaut zéro *par
  construction* ne vérifie rien. Les trois ont été rendus atteignables dans
  cette session, et le §7 dit par quelles commandes.

**Récupération factice** (plancher `idf`, ni modèle ni index), modèle `mixte` :
9 réponses rendues, 22,2 % d'au moins une citation attendue, 33 rédactions dont
17 hallucinantes (51,5 %), 69,7 % de rejet, 85,7 % d'abstention correcte,
84,2 % de dérobade, 0 fuite, 17 hallucinations fabriquées et 17 mesurées. Cette
ligne ne dit rien de la qualité du produit — le plancher `idf` n'est pas le bras
dense — et elle sert à une seule chose : la chaîne entière tourne et se mesure
**sans aucun paquet installé, sans index, sans modèle et sans clé**.

### Les trois choses que ces chiffres disent, et qui comptent

1. **La garde tient. Zéro fuite sur les sept exécutions**, dont deux où le
   modèle invente à chaque réponse. Ce n'est pas un espoir : c'est une inclusion
   d'ensembles, et les 37 rejets du témoin `menteur` sont la mesure de cette
   inclusion. C'est la différence entre espérer et garantir.

2. **La garde se paie en dérobade, et le prix est lourd.** Sur la même
   récupération, un modèle loyal donne 36,8 % de dérobade — exactement celle du
   noyau seul, puisque la garde n'y rejette rien — et le modèle `mixte`
   la porte à **75,4 %**. Les vingt-trois rédactions que la garde refuse se
   répartissent en **vingt-deux questions répondables perdues** et **un seul
   refus souhaitable** (Q55, point 3) : l'échange est à vingt-deux contre un, et
   il est dans le mauvais sens — **sous un modèle factice qui invente sur
   45,9 % de ses rédactions. Le rapport est fabriqué par le banc : un vrai
   modèle inventerait moins, et les deux nombres seraient à remesurer.**
   L'abstention était déjà désignée comme le problème ouvert du projet ; ce banc
   montre qu'elle a une seconde source, indépendante du seuil de marge, et que
   cette source est le modèle. **Améliorer la rédaction est donc un levier de
   rappel que le réglage du seuil ne remplace pas** — et non, sur ces chiffres,
   « le plus important qui reste » : ce classement-là demande un vrai modèle.

3. **Les 100 % d'abstention correcte du mode `mixte` sont un coup de chance, et
   il ne faut pas les lire autrement.** Le noyau seul en refuse six sur sept
   (85,7 %, ligne `fidele`). La septième est Q55, « Quelles sont les règles du
   congé sabbatique ? », que la marge laisse passer : elle n'est refusée en mode
   `mixte` que parce que le condensé de son texte lui a tiré la famille
   `muette`. Avec un autre tirage, elle serait rendue. Écrire « 100 %
   d'abstention correcte » sans cette phrase serait précisément le genre de
   chiffre que ce projet ne peut pas se permettre.

---

## 7. Reproduire

```sh
cd <racine du projet>

# Sans clé, sans paquet, sans index : la chaîne entière sur le plancher idf.
python evaluation/banc_bout_en_bout.py --recuperation idf

# Les tests du banc. Bibliothèque standard seule, aucun test sauté. Le compte,
# lui, se périme à chaque test ajouté : son total vit dans MESURES.md §E.
python tests/test_banc_bout_en_bout.py

# Le contrôle croisé : le même rapport doit sortir des deux côtés.
python evaluation/banc_bout_en_bout.py --recuperation idf \
    --repondeur moteur.repondre:Mizan

# Récupération réelle : il faut numpy, fastembed, onnxruntime et l'index.
PY=prototypes/vectoriel/.venv/Scripts/python.exe
$PY evaluation/banc_bout_en_bout.py --recuperation reel --redacteur mixte
$PY evaluation/banc_bout_en_bout.py --recuperation reel --redacteur fidele
$PY evaluation/banc_bout_en_bout.py --recuperation reel --redacteur menteur

# Les mêmes avec le témoin du banc : c'est la colonne de gauche du tableau du
# §5. Sans --repondeur, toutes les commandes ci-dessus mesurent le PRODUIT,
# parce que c'est lui qui est le défaut (moteur.repondre:Mizan).
$PY evaluation/banc_bout_en_bout.py --recuperation reel --repondeur temoin --redacteur mixte
$PY evaluation/banc_bout_en_bout.py --recuperation reel --repondeur temoin --redacteur fidele
$PY evaluation/banc_bout_en_bout.py --recuperation reel --repondeur temoin --redacteur menteur

# Le 32 repris au §5 ne sort pas d'ici : il sort de la courbe d'abstention de
# CONCEPTION.md §4, dont la commande est au §10 du même document.

# Le détail question par question, et le JSON pour un suivi dans le temps.
$PY evaluation/banc_bout_en_bout.py --recuperation reel --detail
$PY evaluation/banc_bout_en_bout.py --recuperation reel --json res_bout_en_bout.json

# Le répondeur du produit, et le jour où un vrai modèle existera.
$PY evaluation/banc_bout_en_bout.py --recuperation reel \
    --repondeur moteur.repondre:Mizan --redacteur mon_module:ModeleGroq
```

Si l'index dense manque, `--recuperation reel` s'arrête en nommant la commande à
lancer (`python -m noyau.indexer`) : c'est le noyau qui le dit, pas le banc.

Durées d'**une** exécution, sur la machine qui a écrit ce fichier et sous une
charge que personne ne peut reproduire : **0,47 s** pour le mode `idf`,
**3,76 s** pour le mode `reel` — dont l'essentiel est le chargement du modèle
ONNX et les 64 requêtes denses — et une dizaine de secondes pour la suite de
tests complète. Le factice ne coûte rien ;
un vrai modèle coûterait 64 appels réseau et la durée n'aurait plus aucun
rapport.

### Les trois formes de branchement d'un répondeur extérieur

`--repondeur module:attribut` accepte une **classe**, une **fabrique**, ou la
**fonction `repondre(question)`** du contrat, prise telle quelle. Dans les deux
premiers cas, le banc lit la signature et remet les pièces que celle-ci nomme :

| paramètre attendu | ce que le banc remet |
|---|---|
| `redacteur`, `modele` ou `generateur` | son modèle observé — **sans lui, la mesure est aveugle** |
| `chercheur` | la méthode `chercher(question, k=...)` du moteur |
| `moteur` ou `recherche` | le moteur lui-même |
| `k` | le nombre d'articles |

Les trois formes sont testées, parce que la première est un piège : une classe
porte un `repondre` **non lié**, qui passe tous les contrôles du banc et n'échoue
qu'au premier appel, sur un argument manquant. Le banc est tombé dans ce piège
pendant son écriture ; un test l'y empêche désormais.

Et deux conventions d'appel du rédacteur se rencontrent dans ce projet —
`rediger(question, articles)` et `rediger(demande)`. Le banc traduit dans les
deux sens, d'après la signature, plutôt que d'imposer la sienne : un banc qui
impose sa convention au code qu'il mesure demande à ce code d'être écrit pour
lui.

**Codes de sortie.** `0` mesuré · `1` un invariant du produit est brisé (fuite,
avertissement absent) ou un seuil passé en option n'est pas tenu · `2` le banc
n'a pas pu mesurer (jeu incohérent, réponse non conforme).

Aucun seuil n'est câblé par défaut, pour la raison que `banc.py` donne déjà : un
seuil inventé avant toute mesure n'est pas un garde-fou mais un ornement. Les
deux invariants, eux, ne sont **pas** réglables : une fuite ou un avertissement
absent font sortir en 1 sans qu'on ait à le demander.

Et aucun des deux seuils ne doit être câblé sur un chiffre du §6 : ce sont des
chiffres de factice, et un seuil calibré sur eux mesurerait la composition du
banc, pas le produit. Le jour où un vrai modèle sera évalué,
`--seuil-exactitude` et `--seuil-abstention` se régleront sur SES chiffres ;
jusque-là, les laisser vides est la seule valeur honnête.

---

## 8. Ce que ce banc ne prouve pas

- **Il ne mesure pas la fidélité du texte aux articles cités.** Voir §1.1. C'est
  le plus gros trou de l'évaluation du projet, et il demande un jugement humain
  ou un modèle juge.
- **Il ne mesure pas la pertinence d'un article réel et récupéré.** La garde
  vérifie une provenance. Un article hors sujet passe, et seule la grandeur 1 le
  voit — sur 14 réponses rendues en mode `mixte` (modèle factice), **4 ne citent
  aucun article attendu** tout en ayant franchi la garde.
- **Il n'a jamais mesuré un modèle de langue.** Aucun des chiffres du §6 n'est un
  chiffre de production. Ce que le §6 mesure est la chaîne.
- **Le jeu de 64 questions est celui des fondations**, avec toutes ses limites,
  qui sont écrites dans `METHODE.md` et ne sont pas levées ici : écrit par la
  même main que le système, 57 articles visités sur 589 — deux comptes repris de
  `METHODE.md`, qui fait foi pour la composition du jeu, et de `MESURES.md` §B
  pour le corpus, et non remesurés ici —, effectifs par catégorie trop petits
  pour être lus comme des taux. Un écart de deux points sur 57
  questions vaut une question.
- **Les cinq questions `injection` ne mesurent pas la sûreté de la génération.**
  Elles mesurent si une consigne de détournement déplace la récupération, puis,
  ici, ce que le factice en fait — c'est-à-dire rien, puisque le factice ne lit
  pas la consigne. **Tester si un vrai modèle obéit à une injection reste
  entièrement à faire**, et la garde d'inclusion n'en protège qu'à moitié : elle
  empêche de citer un article non récupéré, elle n'empêche pas d'écrire un texte
  détourné autour d'un article qui, lui, a bien été récupéré.
- **L'extraction des citations reste la pièce fragile de toute la chaîne.** Les
  formes reconnues sont celles du Code et quelques formes de modèle ; une forme
  non prévue serait **lue par aucun des deux lecteurs**, donc comparée à rien.
  Le contrôle croisé du §5 attrape un désaccord entre les deux lecteurs ; il
  n'attrape pas une forme qu'ils ignorent tous les deux. Deux des exemples que
  cette puce donnait ont été fermés depuis — « l'art 231 » sans point est
  maintenant lu par les deux lecteurs, et un numéro écrit en lettres fait
  rejeter au lieu de disparaître —, mais le mode d'échec reste, et il porte
  désormais sur un numéro écrit **sans le mot « article »** : « voir aussi 350
  et 387 » n'est lu par personne. C'est la faiblesse structurelle de la garde,
  elle n'a pas de mesure ici, et c'est pourquoi l'invariant de fuite se calcule
  aussi sur les champs que la réponse déclare, sans lecteur.
- **La date de consolidation est le 26 octobre 2011**, celle que porte
  l'avertissement du corpus et que `METHODE.md` reprend. Aucune exactitude de
  citation ne rend ce texte conforme à l'état du droit en 2026, et aucun chiffre
  de ce document ne doit être lu comme une mesure de justesse juridique. Le banc
  compte les réponses sans avertissement — mesuré : **0** sur les sept
  exécutions — mais compter n'est pas garantir : la garantie est dans le
  `__post_init__` du `Resultat` du noyau et dans celui de la `Reponse`. Ce
  compteur-là valait d'ailleurs **0 par construction** jusqu'à cette session :
  l'avertissement vide comptait parmi les anomalies de contrat, qui font sortir
  en **2** avant l'écriture du rapport, si bien que la sortie en **1** annoncée
  pour lui était inatteignable. Il est désormais lu sur chaque réponse et jugé
  avec les fuites, et un répondeur extérieur qui rend des réponses sans
  avertissement fait sortir le banc en **1**, signalé sur chaque question du jeu.
  Le nombre est celui du jeu (source : `evaluation/METHODE.md`), pas une mesure.
