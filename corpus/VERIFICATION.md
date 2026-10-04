# Vérification du corpus — Code du travail marocain

Ce document dit trois choses, dans cet ordre : ce que le script **contrôle**
tout seul, ce qu'il a **trouvé**, et ce qu'il **ne peut pas contrôler**. La
troisième partie est la plus importante. Un assistant juridique qui ne sait pas
dire où s'arrête sa garantie est un assistant dangereux.

Tous les nombres ci-dessous viennent d'une exécution de `python extraire.py`
ou de `python extraire.py --contre-verifier`, dont les sorties sont reproduites
plus bas. Aucun n'est estimé. Les six sabotages du § 1 sont là pour qu'on
puisse vérifier que les contrôles mordent, sans avoir à nous croire.

---

## 0. Avertissement qui conditionne tout le reste

Le texte source est **consolidé au 26 octobre 2011**.

Nous sommes en 2026. Entre-temps le Code du travail marocain a pu être modifié,
complété ou partiellement abrogé ; ce corpus n'en sait rien. Il est également
muet sur tout le droit qui vit **autour** du Code : conventions collectives,
décrets d'application postérieurs, jurisprudence de la Cour de cassation.

Une réponse construite sur ce fichier décrit donc l'état du droit **tel qu'il
était le 26 octobre 2011**, et rien d'autre. Le champ
`source.date_consolidation` du JSON porte cette date, et
`source.avertissement` la phrase à afficher. Les deux sont dans le fichier pour
qu'aucune couche supérieure ne puisse l'oublier.

Le PDF lui-même mentionne deux modifications intégrées : le dahir 1.11.170 du
25 octobre 2011 (loi 58.11, cour de cassation) et le dahir 1.06.233 du 17 avril
2007 (loi 48.06, suppression du service militaire — c'est elle qui a vidé
l'article 256).

---

## 1. Ce que le script contrôle lui-même

Les contrôles sont des **assertions dans `extraire.py`**, pas des paragraphes
dans ce document : le script sort en code 1 et n'écrit pas le JSON si l'un
échoue. Seize contrôles, dans l'ordre du fichier.

| # | Contrôle | Pourquoi il existe |
|---|---|---|
| 1 | Les tailles de police du PDF sont celles attendues | Tout le découpage repose sur elles ; un autre tirage du PDF invaliderait le reste |
| 2 | Exactement **589** articles | Nombre publié par le ministère : c'est un test, pas une observation |
| 3 | Numérotation ordonnée, sans doublon, premier article nommé « premier », dernier numéro = 589 | Un appel de note collé à un numéro produirait « article 25635 » et casserait tout silencieusement |
| 4 | Chaque article rattaché à un livre ; nombre d'articles sans titre épinglé à 115 ; seuls 586–589 sans titre **ni** chapitre | Sans position hiérarchique, la citation ne dit pas de quoi l'article parle |
| 5 | Aucun article vide sauf abrogation **prouvée** par une note de bas de page ; aucun texte sous 40 caractères | Un article tronqué à une ligne est pire qu'un article absent |
| 6 | Aucun pied de page résiduel, ni comme alinéa, ni intercalé dans une phrase | « - 101 - » s'insère au milieu du fil de texte, y compris dans un article |
| 7 | Aucun appel de note collé à un intitulé ; aucune référence vide ; aucun chiffre romain écrit avec un « l » minuscule | « De l'hygiène et de la sécurité des salariés37 » — le 37 n'appartient pas au titre |
| 8 | **8** livres, **16** titres, **64** chapitres, **42** sections | Mesurés d'abord par comptage naïf du texte brut, retrouvés ici par la typographie : vérification croisée |
| 9 | **102** notes de bas de page, numérotation continue ; tout appel renvoie à une note existante | Une note manquante peut masquer une abrogation |
| 10 | Aucune espace doublée, aucun alinéa vide | Hygiène de la chaîne de recherche à venir |
| 11 | Plus de 250 000 caractères d'articles | Garde-fou grossier : si un livre entier disparaissait, les contrôles 2 à 10 pourraient tous passer |
| 12 | **Aucun chiffre collé à une lettre** | Signature d'un appel de note resté fondu (« professionnels102 ») ou d'une espace manquante (« l'article279 »), que la taille de police ne voit pas |
| 13 | Exactement deux mots coupés par une espace parasite (articles 268 et 296) | Défaut de la source, épinglé pour que le recollage des spans n'en fabrique pas d'autres |
| 14 | Aucun alinéa finissant sans ponctuation ; total épinglé à **1553** alinéas | Le découpage en alinéas est heuristique : le total sert de valeur de référence contre toute dérive |
| 15 | **Aucune espace avant un point ou une virgule** | Trace du trou laissé par un appel de note retiré : « sécurité sociale , d'accident ». Pas de contrôle devant « ; : ! ? », qui prennent une espace fine légitime |
| 16 | Aucune note de bas de page orpheline, hormis la note 1 | Une note que rien n'appelle n'est pas citable, donc invisible à l'usager |

### Les contrôles mordent-ils vraiment ?

Six sabotages volontaires, exécutés dans cette session. Chacun remet la faute
que le contrôle existe pour attraper, et on lit ce que le script en dit :

| Sabotage | Résultat |
|---|---|
| `CORRECTIONS_NOMMEES = ()` | 5 échecs : contrôle 12 sur les articles 280, 427, 428 et `article 586 : chiffre collé à une lettre (« s102 »)`, puis contrôle 16 : `notes qu'aucun article ni intitulé n'appelle : [1, 102]` |
| `MARGE_DROITE = 400` (recolle les alinéas) | 1 échec, contrôle 14 : `1456 alinéas au lieu des 1553 de référence` |
| `MARGE_DROITE = 528` (hache les alinéas) | 2 échecs, contrôle 14 : `4606 alinéas` et alinéas finissant sans ponctuation |
| `ESPACE_AVANT_PONCTUATION` rendu incapable de mordre | 64 échecs, contrôle 15, le premier étant `article 3 : espace avant la ponctuation (« meubles d'habitation . »)` ; le volume remonte de 279 378 à 279 442 caractères |
| Appels de note non repris sur les intitulés | 1 échec, contrôle 16 : `notes qu'aucun article ni intitulé n'appelle : [1, 37, 54, 60]` (la note 88, reprise par la branche de recollage, survit à ce sabotage-là) |
| Signal de graisse retiré de `ouvre_un_alinea` | 1 échec, contrôle 14 : `1552 alinéas au lieu des 1553 de référence` — l'intertitre de l'article 586 se recolle |

---

## 2. Ce que le script a trouvé

```
$ python extraire.py
PDF                      code-travail-adala.pdf
lignes de loi            5793
pieds de page retires    200
corrections nommees      4
romains l -> I corriges 14
notes de bas de page     102
articles                 589
hierarchie               {'livre': 8, 'titre': 16, 'chapitre': 64, 'section': 42, 'sous_section': 5}
intitules                135
alineas                  1553
caracteres d'articles    279378
trous de numerotation    aucun
articles abroges         ['256']
articles sans titre      115 (Livre IV, Livre V, Livre VI, Livre VII)

tous les controles passent
ecrit              code-travail.json (958194 octets)
```

- **589 articles**, numérotés sans trou de l'article premier à l'article 589.
- **Un seul article vide** : l'article 256, abrogé par l'article unique de la
  loi 48-06 portant suppression du service militaire. Le JSON porte
  `abroge: true` et le texte de la note en `motif_abrogation`.
- **Hiérarchie** : 8 livres, 16 titres, 64 chapitres, 42 sections, et
  **5 sous-sections** que le cahier des charges ne mentionnait pas (livre III,
  titre II, chapitre II, section III — procédure électorale). Elles sont
  conservées : 135 intitulés en tout.
- **Article le plus court** : 468, 70 caractères (« Les membres du comité
  d'entreprise sont tenus au secret professionnel. »). **Le plus long** : 586,
  5 802 caractères. **Médiane** : 390 caractères.
- **Une seule note orpheline** : la note 1, dont l'appel est page 2, dans le
  dahir de promulgation — avant le premier « Livre » où commence le corpus. Elle
  renvoie au Bulletin Officiel de la loi entière, pas à un article. Le champ
  `controles.notes_non_citees` du JSON porte cette liste, et le contrôle 16
  exige qu'elle ne contienne que `1`.

### Pièges du PDF, et comment chacun est traité

Les quatre premiers étaient annoncés par le cahier des charges. Les huit
suivants ont été trouvés en lisant le PDF.

| Piège | Traitement |
|---|---|
| Pied de page « - 101 - » au fil du texte | Il est en Times New Roman 12 pt, le corps en Book Antiqua 14 pt : écarté par la taille. 200 retirés, un par page de 2 à 201. PyMuPDF le rend en quatre fragments à la même ordonnée, recollés avant filtrage |
| Appel de note collé à un intitulé (« …salariés37 ») | Les appels sont en 9 à 10,6 pt : écartés par la taille. Quatre intitulés de hiérarchie en portent un — **Titre IV** (note 37), **Section II** du salaire minimum légal (54), **Section III** de la saisie-arrêt (60) et **Chapitre premier** des agents chargés de l'inspection du travail (88, appelée sur la *seconde* ligne de l'intitulé). Ils sont recensés dans le champ `appels_de_note` **de l'intitulé**, qui voyage avec chaque article dans son bloc `position` : c'est ce qui les rend citables, et le contrôle 16 vérifie qu'aucun ne se perd |
| Espaces doublées, phrases coupées en fin de ligne | Espaces réduites ; lignes recollées selon la géométrie du bloc justifié |
| Numéros « bis », « ter », « 12-1 » | **Aucun dans ce PDF.** Les 589 numéros sont « premier » puis 2 à 589. Le code accepte le format, il ne l'a pas rencontré |
| **Appel de note collé à un NUMÉRO D'ARTICLE** | « Article 25635 » (art. 256 + note 35), « Article 32748 », « Article 33450 », et dans le corps « l'article 109814 » (art. 73 et 76). Sans traitement, l'article 256 aurait porté le numéro 25635 et trois articles auraient disparu du décompte |
| **Deux articles composés comme du corps de texte** | Les articles **156** et **458** sont en Book Antiqua 14 pt aligné à gauche, pas en 15 pt gras centré comme les 587 autres. Détectés par la forme de la ligne (« Article N » seul sur sa ligne), sans exiger le gras |
| **Une ligne visuelle découpée en plusieurs « lines » par PyMuPDF** | Quand la justification étire les blancs, chaque mot devient une entrée. Pire cas du document : **dix** fragments page 22, dans l'article 26 (« et tenir un registre dans les formes prévues par l'autorité ») ; l'article 154 en a **neuf** page 65. Regroupement par ordonnée avant tout traitement |
| **Trait d'union en fin de ligne** | 22 lignes finissent sur un trait d'union **réel** (« dommages-intérêts », « ci-dessus », « sous-traitant ») : recollées sans espace. Aucune coupure syllabique dans ce PDF |
| **Chiffres romains écrits avec un « l » minuscule** | « Chapitre Il », « Section Ill » : 14 corrections, comptées et affichées. Sans elles, un même chapitre aurait deux références différentes |
| **Quatre fautes dans la couche texte du PDF** | « l'article279 » (art. 280) et « l'article426 » (art. 428), espace manquante ; « de 500 à1000 dirhams » (art. 427) ; « professionnels102 » (art. 586), appel fondu dans le span du corps. Trois règles nommées dans `CORRECTIONS_NOMMEES` les corrigent — la première couvre deux occurrences, d'où les **4 substitutions** affichées. Le contrôle 12 garantit qu'il n'en reste aucune autre |
| **Espace laissée par l'appel de note retiré** | Retirer le span « 37 » de « sécurité sociale37, d'accident » laisse un trou entre les deux spans de corps, que le recollage géométrique rendait par une espace : **64 alinéas de 58 articles** portaient « salariés , » ou « réglementaire . ». Le trou est refermé à la lecture, sur les seules lignes dont un span de paratexte a été écarté, et uniquement devant le point et la virgule — pas devant « ; : ! ? », où l'espace fine est correcte. Contrôle 15 |
| **Intertitre en gras collé à l'alinéa précédent** | Les seize intertitres du corps de l'article 586 (« Cautionnements : », « Congé annuel payé : ») se détachent normalement parce que l'item qui les précède finit court. Un seul y échappait : « …relatif aux cautionnements ; » s'arrête à 525,7 points, **dans** la tolérance du bloc justifié, et son item ne tient qu'une ligne. Un quatrième signal, le passage du maigre au gras, ouvre l'alinéa. La règle est à sens unique : l'inverse est faux, page 159 une ligne à fragment gras est prolongée en maigre par « échéant. » |

### Incohérences de la source, volontairement NON corrigées

Elles sont dans le PDF, elles sont dans le JSON. On ne réécrit pas un texte de
loi sur une présomption ; on signale.

- **« le non- respect »**, articles 268 et 296 : l'espace est dans le span du
  PDF. Le contrôle 13 épingle ces deux cas, et seulement eux. Une recherche
  sur « non-respect » ne les trouvera pas sans normalisation.
- **Casse des références** : « Titre PREMIER », « Titre Premier » et
  « Titre premier » coexistent, de même que « Chapitre Premier » et
  « Chapitre premier ».
- **Une section numérotée en chiffres arabes** : « Section 1 » (livre VI,
  chapitre II) quand les 41 autres sont en chiffres romains.
- **Deux formes d'apostrophe** : 2 808 apostrophes ASCII (U+0027) contre 6
  typographiques (U+2019), ces dernières aux articles 246, 340, 458, 512 et
  586. La couche de recherche devra normaliser ; le corpus, non.

### Ce que le cahier des charges demandait et qui s'est révélé faux

Il demandait que « chaque article appartienne à un livre **et** à un titre ».
La mesure dit que c'est impossible : les livres IV, V, VI et VII n'ont pas de
niveau « titre », ils passent du livre au chapitre, et le livre VII (articles
586 à 589) n'a même pas de chapitre. **115 articles n'ont donc pas de titre**,
légitimement.

Le contrôle 4 exige ce qui est vrai — un livre pour les 589 — et **épingle** le
nombre 115 ainsi que la liste exacte des quatre articles sans titre ni
chapitre. Une régression du parseur ferait bouger ces valeurs et échouer
l'extraction.

---

## 3. Ce que le script ne peut PAS contrôler

Le script sait compter 589 articles. **Il ne sait pas dire si le texte de
l'article 279 est fidèle.** Aucune assertion ne peut le savoir : il faudrait
une seconde source du Code du travail pour comparer, et nous n'en avons pas.

Voici donc, précisément, ce qui a été vérifié autrement — et ce qui reste un
acte de foi.

### 3.1 Relecture à la main : 20 articles sur 589

Comparés mot à mot, à l'œil, avec les pages correspondantes du PDF :

**premier, 12, 43, 57, 73, 89, 105, 154, 156, 217, 256, 274, 279, 280, 303,
335, 458, 533, 586, 589.**

Ils n'ont pas été tirés au hasard. Chacun éprouve un piège précis :

| Article | Ce qu'il éprouve |
|---|---|
| premier | Le tout premier article, numéro en lettres |
| 12, 303 | Article ordinaire, témoin |
| 43, 217 | Appel de note en **fin** de ligne, qui raccourcit la ligne et faisait croire à une fin d'alinéa |
| 57, 105, 533 | Énumérations à lettres (a., b., c., d.) imbriquées dans une énumération à chiffres |
| 73 | « article 109814 » : appel de note collé à un numéro **dans le corps** |
| 89, 105, 335 | Bloc de notes **et** pied de page intercalés au milieu de l'article, items d'énumération à cheval sur deux pages |
| 154 | Justification extrême : une ligne découpée en neuf fragments par PyMuPDF |
| 156, 458 | Les deux articles composés comme du corps de texte |
| 256 | Article abrogé, texte vide, justification par note |
| 274 | Énumération à trois niveaux, avec un alinéa qui s'arrête à 525 points et manquait d'être recollé au suivant |
| 279, 280 | L'exemple du cahier des charges, et l'article qui le cite avec une espace manquante |
| 586 | Le plus long (5 802 caractères, 55 alinéas), avec seize intertitres **en gras** qui appartiennent au corps |
| 589 | Le dernier article |

Les **135 intitulés** de la hiérarchie ont également été relus un par un contre
l'inventaire des lignes en gras du PDF.

### 3.2 Contre-vérification automatique des 588 autres

Relire 589 articles à la main n'était pas possible. À la place, une
**contre-vérification par un chemin indépendant**, rejouable :

```bash
python extraire.py --contre-verifier
```

Les pages du PDF y sont renettoyées par une règle purement **textuelle**, qui
ne consulte aucune police — donc sans réutiliser la décision de départ de
`extraire.py` : sur chaque page, le bloc de notes est précédé d'un filet que
`get_text()` rend comme une ligne de vingt blancs ou plus, et tout ce qui suit
sur la page est écarté ; les débris de pied de page partent par motif. Rien
d'autre n'est retiré — **les appels de note restent collés à leur mot**,
puisque seule la taille de police les en distingue.

Le texte ainsi gardé est découpé en tranches sur les seuls intitulés
d'article, puis chaque article est comparé **mot à mot** à sa tranche.

Sortie de l'exécution :

```
contre-verification par nettoyage purement textuel
  lignes gardees               6086
  « Article N » a l'aveugle    586
  articles non vides           588
  extraits litteraux contigus  509
  ecart = appels de note       69
  ... + ligne d'intitule       10 (5, 32, 76, 103, 258, 413, 424, 525, 545, 581)
  ecarts inexpliques           0
```

La première ligne est un comptage **à l'aveugle**, fait avant tout alignement :
**586** lignes du nettoyage textuel sont exactement « Article N ». Il en manque
trois, et ce manque est lui-même une mesure — ce sont les articles 256, 327 et
334, dont le numéro porte un appel de note collé (« Article 25635 ») que seule
la police sait séparer. 586 + 3 = 589.

Les trois ensembles suivants **partitionnent** les 588 articles non vides —
509 + 69 + 10 = 588 — et c'est la seule lecture qui se tienne :

- **509** articles sont, aux blancs près, un **extrait littéral contigu** du
  nettoyage indépendant. « Aux blancs près » absorbe au passage les traits
  d'union recollés (« dommages- » + « intérêts ») et les deux espaces
  manquantes corrigées nommément (« l'article279 », « à1000 »), qui ne sont
  rien d'autre que des blancs ;
- **69** articles n'en diffèrent que par des **appels de note** que le
  nettoyage textuel ne sait pas voir. L'écart est accepté seulement si le
  retrait des numéros que le JSON revendique pour **cet** article — son champ
  `appels_de_note` — redonne mot pour mot la tranche. C'est ce qui range ici
  l'article 73 (« l'article 109814 » → « l'article 1098 », note 14 collée à un
  numéro **dans le corps**) et l'article 586 (« professionnels102 ») ;
- **10** articles y ajoutent une **ligne d'intitulé de hiérarchie** que la
  règle textuelle, faute de police, ne sait pas écarter — le nettoyage
  typographique, lui, l'écarte. Ce sont les articles 5, 32, 76, 103, 258, 413,
  424, 525, 545 et 581 ;
- **0** écart reste inexpliqué, et le script sort en code 1 s'il en apparaît un.

**Ce que cela prouve :** aucun mot n'a été ajouté, perdu ou déplacé entre le PDF
et le JSON, hors des transformations ci-dessus.
**Ce que cela ne prouve pas :** que le PDF d'Adala soit lui-même conforme au
Bulletin Officiel. Les deux chemins lisent le même fichier.

### 3.3 Ce qui reste un acte de foi

1. **La fidélité du PDF source.** Tout ce qui précède vérifie que le JSON dit
   la même chose que le PDF. Si le portail Adala a publié une coquille, elle
   est dans le corpus. Les défauts de couche texte trouvés (« l'article279 »,
   « l'article426 », « à1000 », « professionnels102 », « non- respect »)
   montrent que ce PDF n'est pas exempt de fautes de transcription. Une
   vérification réelle exigerait le Bulletin Officiel n° 5210 du 6 mai 2004 et
   ses rectificatifs.

2. **Le découpage en alinéas.** Les 1 553 alinéas reposent sur deux
   heuristiques géométriques mesurées dans ce PDF (bord droit du bloc justifié
   à 528 points, indentations à 71/99/117/135), plus un signal de graisse qui
   ne sert qu'à un alinéa, celui de l'article 586. Le contrôle 14 attrape le
   découpage trop généreux, et le total épinglé attrape la dérive — mais un
   alinéa recollé à son voisin dans un article non relu resterait invisible.
   20 articles ont été relus, 569 ne l'ont pas été.

3. **Les intitulés recollés sur deux lignes.** Quand la mise en page coupe un
   intitulé en deux (« Livre II: Des conditions de travail et de la » /
   « rémunération du salarié »), la seconde ligne est reconnue parce qu'elle
   est en gras et suit immédiatement un intitulé. La règle écarte bien les
   intertitres gras qui appartiennent au corps de l'article 586
   (« Cautionnements : ») et les items gras de l'article 274 (« 1) Mariage : »),
   mais c'est une règle de position, pas une certitude. Les 135 intitulés ont
   été relus, ce qui est la seule garantie ici.

4. **Le sens juridique.** Le corpus ne sait pas quels articles sont encore en
   vigueur en 2026 (hors l'article 256), ni lesquels ont été modifiés depuis
   2011, ni ce que la jurisprudence en a fait. `abroge` ne vaut que pour les
   abrogations **mentionnées par le PDF de 2011**.

5. **Le nombre 589 lui-même.** Il est repris des sources officielles et sert de
   test. Si ces sources se trompaient, le script validerait une erreur avec
   aplomb. C'est la seule assertion du fichier qui ne se vérifie pas
   elle-même. Deux chemins indépendants y mènent et concordent : la détection
   typographique en trouve 589, et le comptage à l'aveugle du nettoyage
   textuel en trouve 586 plus les 3 numéros porteurs d'un appel de note collé
   (§ 3.2). C'est un indice, pas une preuve : les deux chemins lisent le même
   PDF.

---

## 4. Reproduire

```bash
cd mizan/corpus
python extraire.py                   # extrait, contrôle, écrit code-travail.json
python extraire.py --sans-ecrire     # contrôle sans rien écrire
python extraire.py --contre-verifier # ajoute la contre-vérification du § 3.2
echo $?                              # 0 si tous les contrôles passent, 1 sinon
```

La contre-vérification relit le PDF une seconde fois, ce qui se paie peu :
1,43 s pour `--sans-ecrire`, 1,58 s en y ajoutant `--contre-verifier`.

Dépendance unique : **PyMuPDF** (importé sous le nom `pymupdf` ; `fitz` est son
ancien nom, déprécié). Aucune clé d'API, aucun modèle de langage, aucun accès
réseau : l'extraction et ses contrôles sont reproductibles par quiconque clone
le dépôt.

Environnement de l'exécution rapportée ici : Python 3.12.10, PyMuPDF 1.28.2,
Windows 11.
