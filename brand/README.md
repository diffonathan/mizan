# Marque — Mizan

| Fichier | Usage |
|---|---|
| `logo.svg` | le symbole seul. **Aucune police requise** : formes pures, rendu identique partout. |
| `logo-complet.svg` | symbole + nom, pour un en-tête web où DM Sans est chargée. |
| `logo-mono.svg` | une seule couleur, héritée du texte environnant (`currentColor`). Tampon, gravure, fond coloré. |

## Couleurs

| Rôle | Valeur |
|---|---|
| Violet (marque, action) | `#7c3aed` — dégradé `#b793f5` → `#612db9` |
| Or (valeur, citation) | `#f9a825` |
| Fond nuit | `#0a0a0c` |

Le détail et les raisons sont dans [`../CHARTE.md`](../CHARTE.md).

## Le symbole

**Mizan** (ميزان) veut dire *balance*. C'est donc à la fois le nom du produit
et le cliché du droit — et le prendre quand même n'avait d'intérêt qu'à
condition de lui faire dire autre chose que « justice ».

Le fléau est **droit**, en équilibre : penché, il dirait l'injustice, ce qui
est le contraire du propos. Et les deux plateaux ne pèsent pas la même chose.

Le plateau de gauche, blanc, porte **la question**. Celui de droite, en or,
porte **l'article** qui la soutient. L'or est le rôle « valeur » de la charte
maison, et dans ce projet il est réservé aux citations : le symbole dit donc
qu'une réponse ne tient que si un article la contrebalance.

C'est la promesse du produit, et elle se lit sans légende.

## Ce qui a été écarté

**Le marteau de juge.** Il n'existe pas dans la procédure marocaine, et un
symbole emprunté à une autre culture judiciaire sur un outil de droit
marocain est une faute de fond, pas de goût.

**Le livre ou le parchemin.** Ils disent « texte », pas « réponse sourcée »,
et ils ressemblent à un logo d'édition ou d'école.

**Un fléau penché du côté de l'or**, pour signifier que la source l'emporte.
L'image était plus bavarde et moins juste : une balance penchée, dans toutes
les cultures, dit le déséquilibre.

## La lisibilité, mesurée

La contrainte est l'onglet de navigateur : 16 px, soit un quart d'unité du
viewBox par pixel. Les nombres ci-dessous sont mesurés, pas estimés.

| Grandeur | Valeur | À 16 px |
|---|---|---|
| Épaisseur la plus fine | 5 u | 1,25 px |
| Vide fléau ↔ plateau | 6 u | 1,50 px |
| Vide plateau ↔ socle | 4 u | 1,00 px |
| Diamètre d'un plateau | 10 u | 2,50 px |

Une première version plaçait les plateaux à **0,5 unité** du fléau. Chaque
pièce était pourtant assez épaisse : c'est le **vide** entre les formes qui
décide de la lisibilité, pas leur taille, et l'ensemble se soudait en une
tache. La leçon vaut d'être écrite — on vérifie spontanément les traits, pas
les intervalles.

## Le monochrome a sa propre géométrie

`logo-mono.svg` n'est pas la version couleur dépouillée. Sans le cadre violet
ni le plateau d'or, tout ce qui portait la différence disparaît, et les formes
doivent s'écarter davantage : le cadre devient un contour évidé, et le vide
fléau ↔ plateau passe de 6 à 5 unités sur une composition resserrée.

Surtout, le plateau de droite garde sa distinction **par la forme** — un
anneau plutôt qu'un disque. C'est la seule façon de conserver le sens du
symbole quand la couleur n'est plus disponible : sans cela, le monochrome
dirait « deux plateaux identiques », c'est-à-dire plus rien.
