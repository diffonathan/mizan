# Rejouer les trois prototypes, y compris les perdants

Ce dossier garde les trois prototypes d'origine, **tels que leurs auteurs les
ont écrits et mesurés**. Aucun n'a été retouché par l'arbitrage : les notes
`lexical/README.md`, `vectoriel/NOTE.md` et `hybride/NOTE.md` décrivent donc
exactement le code qui est ici.

La raison d'être de ce fichier est qu'un comparatif dont on ne peut pas
rejouer les perdants ne se vérifie pas. Les commandes ci-dessous ont toutes
été relancées sur cette machine, sans rien installer, et sortent toutes en
code 0.

**L'interpréteur n'est pas au choix.** Deux des trois candidats ont besoin de
`numpy`, `fastembed` et `onnxruntime`, que le `python` partagé de cette machine
n'a pas. Chaque commande ci-dessous nomme donc l'interpréteur avec lequel elle
a été vérifiée ; lancée avec le `python` nu, celles qui touchent au bras dense
s'arrêtent sur `ModuleNotFoundError: No module named 'numpy'` — ce n'est pas un
défaut du code, c'est l'environnement attendu.

## Ce dont tout dépend, et où il est

| artefact | emplacement | poids |
|---|---|---|
| environnement Python avec `fastembed` | `vectoriel/.venv/` | 161 Mo de paquets |
| modèles ONNX (4) | `vectoriel/.cache_modeles/` | 522 + 1 198 + 2 149 + 241 Mo |
| vecteurs déjà calculés, un par configuration | `vectoriel/.cache_vecteurs/` | 0,6 à 4,6 Mo pièce |

Le `.venv` du candidat 2 contient `py_rust_stemmers`, dont le candidat 3 a
besoin, et `.cache_modeles` contient le modèle MiniLM que le candidat 3
utilise. Un seul environnement suffit donc aux trois, alors que leurs auteurs
en avaient monté trois séparément pour ne pas se gêner.

## Candidat 1 — lexical (aucune dépendance)

Le seul des trois qui tourne avec le `python` partagé.

```sh
cd prototypes/lexical
python mesurer.py                                   # son propre banc, 25 questions
python bm25.py "quelle est la durée de la période d'essai pour un cadre ?"
```

## Candidat 2 — vectoriel

```sh
cd prototypes/vectoriel
.venv/Scripts/python.exe mesurer.py --rapide        # son banc : 34 répondables + 3 sans réponse
.venv/Scripts/python.exe abstention.py 5
.venv/Scripts/python.exe index_vectoriel.py "on m'a viré, j'ai droit à une indemnité ?" "google/embeddinggemma-300m"
```

## Candidat 3 — hybride

Sa note demande deux variables d'environnement qui pointaient vers un dossier
temporaire, aujourd'hui périssable. Les mêmes fichiers existent dans le cache
du candidat 2, et le chemin ci-dessous les y prend — il est **vérifié** :
avec lui, `comparer.py` rend exactement les chiffres de l'arbitrage
(`hybride-rrf60` 28,9 / 55,3 / 74,6).

```sh
cd prototypes/hybride
export MIZAN_PAQUETS=""      # inutile si l'on utilise le .venv du candidat 2
export MIZAN_MODELE="$PWD/../vectoriel/.cache_modeles/models--qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q/snapshots/faf4aa4225822f3bc6376869cb1164e8e3feedd0"
../vectoriel/.venv/Scripts/python.exe banc.py       # son propre banc, 25 questions
../vectoriel/.venv/Scripts/python.exe chercher.py "combien de jours de congés après deux ans ?"
```

`banc.py` sans option fait tourner le balayage complet des ablations — une
quinzaine de variantes, quelques minutes, et un pic de mémoire de 1,2 Go que le
rapport imprime lui-même. Il écrit `resultats_banc.json` avant de résumer, de
sorte que l'artefact de mesure existe même si l'on interrompt l'affichage.

## Les rejouer tous sur le banc INDÉPENDANT

C'est la seule comparaison qui a servi à décider, et c'est elle qui produit
les chiffres de `../CONCEPTION.md`. Elle ne vit pas ici mais dans
`../arbitrage/`, et **les commandes sont celles du §10 de `../CONCEPTION.md`**,
qui dit aussi lequel de ses tableaux chacune produit et dans quel JSON elle
l'écrit. Elles ne sont pas recopiées ici : deux copies d'une même recette
divergent, et c'est celle qu'on ne relance pas qui finit dans le dossier.

Pour mémoire, la commande qui remet les trois candidats côte à côte est la
première du §10. Avec le chemin de rechange ci-dessus pour le bras MiniLM du
candidat 3, elle rend bien les chiffres du dossier : `hybride-rrf60`
28,9 / 55,3 / 74,6, `lexical` 34,2 / 53,5 / 60,5, `vectoriel-gemma`
61,1 / 84,5 / 88,0.
