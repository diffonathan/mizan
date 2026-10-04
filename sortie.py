# -*- coding: utf-8 -*-
"""Force stdout et stderr en UTF-8. À importer en tête de tout script qui imprime.

POURQUOI CE FICHIER EXISTE
--------------------------
Sous Windows, la sortie standard de Python vaut cp1252 dès qu'elle n'est pas
un terminal moderne (un tube, un « | head », une redirection lue par un autre
outil). cp1252 est un jeu de 256 caractères : il ne contient ni la flèche
U+2192 « → » ni le filet vertical U+2502 « │ », qui sont partout dans les
tableaux et les comparaisons de ce projet.

Sans ce module, « python arbitrage/analyser.py » s'arrête au milieu de son
tableau sur exactement ceci :

    File ".../arbitrage/analyser.py", line 85, in principal
        print(f"  {qid:6} ... U+2192 ...")
    File ".../Lib/encodings/cp1252.py", line 19, in encode
        return codecs.charmap_encode(input, self.errors, encoding_table)[0]
    UnicodeEncodeError: 'charmap' codec can't encode character 'U+2192'
    in position 13: character maps to <undefined>

Et « python evaluation/banc.py », qui n'utilise pas de flèche, ne plante pas
mais rend ses accents illisibles : « Contrepoids à lire » ressort en
« Contrepoids ? lire ». Le second cas est le plus dangereux des deux, parce
qu'il ne signale rien : on lit un résultat abîmé en le croyant intact.

Le défaut n'est pas dans analyser.py, il est dans l'environnement — donc tout
script ajouté à ce projet le rencontrera à son tour. D'où un module, importé
une fois en tête, plutôt qu'une rustine par point d'impression.

POURQUOI PAS « PYTHONIOENCODING=utf-8 »
---------------------------------------
Cette variable corrige le symptôme mais déplace la charge sur l'utilisateur :
elle doit être posée dans chaque shell, par chaque personne, avant chaque
rejeu — et elle est absente de tout ce qui lance un script sans passer par ce
shell (un ordonnanceur, un CI, un double-clic, un « subprocess » lancé par un
autre script). Une consigne qu'il faut penser à appliquer n'est pas une
correction : c'est une consigne orale, et elle sera oubliée exactement le jour
où quelqu'un vérifie un chiffre du dossier. Le correctif doit voyager avec le
code, pas avec les habitudes de celui qui le lance.
"""
from __future__ import annotations

import sys

# « errors » reste à sa valeur par défaut : on veut qu'un caractère réellement
# inencodable lève, pas qu'il se change en « ? » dans un résultat mesuré.
_ENCODAGE = "utf-8"


def _deja_en_utf8(flux: object) -> bool:
    nom = (getattr(flux, "encoding", "") or "").lower().replace("-", "").replace("_", "")
    return nom in ("utf8", "utf8sig", "cp65001")


def _reconfigurer(flux: object) -> None:
    """Passe un flux en UTF-8, en abandonnant silencieusement si c'est impossible.

    Trois cas d'abandon volontaire, tous légitimes : le flux est déjà en UTF-8
    (Linux, terminal moderne, redirection vers un fichier UTF-8) et n'a rien à
    gagner ; le flux n'expose pas « reconfigure » (flux remplacé par un harnais
    de test, objet maison, Python antérieur à 3.7) ; le flux est détaché ou
    fermé — un tube coupé par un « | head » qui s'est arrêté. Dans aucun de ces
    cas l'absence d'UTF-8 ne justifie de faire échouer le script appelant : un
    module d'affichage qui empêche d'afficher serait pire que le défaut qu'il
    corrige.
    """
    if flux is None or _deja_en_utf8(flux):
        return
    reconfigure = getattr(flux, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding=_ENCODAGE)
    except (ValueError, OSError, AttributeError):
        # ValueError : flux détaché. OSError : tube déjà fermé.
        pass


# stderr autant que stdout : une trace d'erreur contenant un accent se perd
# sinon au moment précis où on en a le plus besoin, et une UnicodeEncodeError
# levée en écrivant le message d'une autre exception masque l'exception
# d'origine.
for _flux in (sys.stdout, sys.stderr):
    _reconfigurer(_flux)
