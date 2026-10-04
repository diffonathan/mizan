"""Ajoute au chemin d'import le dossier ou fastembed a ete installe a part.

fastembed, onnxruntime, numpy et tokenizers n'ont PAS ete installes dans
l'environnement Python partage : d'autres agents travaillaient sur le meme
interpreteur au moment de ce prototype, et un pip concurrent dans le meme
site-packages est un risque qu'on ne prend pas pour un jetable. Ils vivent
donc dans un dossier passe par MIZAN_PAQUETS. Si la variable est absente, les
imports normaux font foi : c'est le cas d'une machine ou tout est installe.
"""

import os
import sys

_dossier = os.environ.get("MIZAN_PAQUETS")
if _dossier and os.path.isdir(_dossier) and _dossier not in sys.path:
    sys.path.insert(0, _dossier)

MODELE_LOCAL = os.environ.get("MIZAN_MODELE")
