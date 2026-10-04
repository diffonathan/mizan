# Prototype jetable — recherche lexicale BM25

Trois fichiers, aucune dépendance hors bibliothèque standard.

| fichier | rôle |
|---|---|
| `bm25.py` | index BM25 Okapi en mémoire sur les 589 articles, + les signaux de doute |
| `questions.py` | banc de 25 questions dont la réponse a été établie en LISANT le corpus |
| `mesurer.py` | rappel, coût, échecs, ablations, seuils d'abstention |

## Lancer

Interroger le corpus :

    python bm25.py "quelle est la durée de la période d'essai pour un cadre ?"

La sortie donne, pour chaque article remonté : son score, sa citation
hiérarchique complète, sa page dans le PDF d'Adala, et le détail terme par
terme de **pourquoi** il est remonté.

Reproduire toutes les mesures du compte rendu :

    python mesurer.py

## Ce que ce prototype n'est pas

- **Pas du code de production.** Pas de tests, pas de validation d'entrée,
  pas de gestion d'erreur. L'index est reconstruit à chaque démarrage.
- **Pas un réglage fin.** Les ablations de `mesurer.py` montrent que tous les
  réglages essayés tiennent dans un écart d'une seule question sur 25 : sur un
  banc de cette taille, aucun n'est départageable. Les valeurs retenues sont
  les valeurs usuelles de BM25, pas des valeurs optimisées.
- **Pas un juge impartial de sa propre piste.** Le banc de `questions.py` est
  écrit par l'auteur du prototype. Il contient délibérément sept questions du
  registre « ordinaire » destinées à le mettre en difficulté, mais cela ne le
  rend pas neutre pour autant. Le vrai banc serait composé par quelqu'un
  d'autre, ou tiré de questions réellement posées.
- **La section 7 de `mesurer.py` n'est pas une mesure.** La table de synonymes
  y a été écrite après lecture des échecs, pour les combler. Elle donne une
  borne supérieure optimiste, utile seulement pour chiffrer l'ampleur du
  problème de vocabulaire.

## Rappel qui vaut pour toute couche bâtie là-dessus

Le corpus est consolidé au **26 octobre 2011**. `source.avertissement` du JSON
porte la phrase à afficher sous toute réponse ; `bm25.py` l'imprime à chaque
interrogation, et ce n'est pas décoratif.
