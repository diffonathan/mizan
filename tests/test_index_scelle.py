# -*- coding: utf-8 -*-
"""L'index vectoriel est VERSIONNÉ : ces tests sont le filet qui le permet.

`.gitignore` interdisait tout fichier de vecteurs, avec un argument juste :
les versionner créerait une troisième source de vérité qui dériverait des deux
autres — corpus et modèle — sans que rien ne le signale.

L'interdiction a été levée pour UN fichier, et seulement parce que la dérive
n'y est plus silencieuse : `noyau/indexer.py` scelle l'index avec l'empreinte
des passages, et `noyau.dense.lire_index` REFUSE de servir un index dont
l'empreinte ne colle pas au corpus présent.

Ce module épingle les deux moitiés de ce contrat, parce qu'une garantie qu'on
n'éprouve pas est une intention :

    1. l'index livré dans le dépôt colle au corpus livré dans le dépôt ;
    2. un index dont l'empreinte est truquée est bien refusé.

Le second est le plus important des deux. Sans lui, le premier pourrait passer
sur un index juste alors que le mécanisme de refus est cassé — et l'on
publierait des vecteurs sans filet en croyant en avoir un.

POURQUOI UN FICHIER À PART, ET NON DEUX MÉTHODES DANS `test_noyau.py`
--------------------------------------------------------------------
Parce que ces tests ne mesurent pas la récupération : ils gardent une décision
de PUBLICATION, celle de committer un artefact calculé. Le jour où quelqu'un
voudra retirer l'index du dépôt, c'est ce fichier qu'il doit lire et retirer
avec, et le chercher au milieu des tests de fidélité le lui cacherait.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from noyau import corpus as module_corpus  # noqa: E402
from noyau import dense as module_dense  # noqa: E402


def _numpy_absent() -> str:
    """`lire_index` lit un .npz : sans numpy il n'y a rien à éprouver ici.

    Le saut dit quoi lancer, comme partout ailleurs dans cette suite : un test
    sauté qui ne dit pas pourquoi est un test qu'on croit passé.
    """
    try:
        import numpy  # noqa: F401
    except ImportError:
        return ("numpy absent de cet interpréteur — "
                "pip install -r requirements.txt")
    return ""


_MANQUE = _numpy_absent()


@unittest.skipIf(_MANQUE, _MANQUE or "disponible")
class IndexLivre(unittest.TestCase):
    """L'index présent dans le dépôt est-il celui du corpus présent ?"""

    def test_l_index_versionne_colle_au_corpus_versionne(self):
        """Le cas qui casse un déploiement sans rien dire d'autre.

        Si ce test échoue, l'index committé et le corpus committé ne sont plus
        le même couple : il faut reconstruire l'index et le recommitter,
        PAS relâcher le contrôle.
        """
        chemin = module_dense.chemin_index()
        if not chemin.exists():
            self.skipTest(
                f"index absent de ce clone : {chemin} — python -m noyau.indexer"
            )
        corpus = module_corpus.charger()
        index = module_dense.lire_index(corpus)  # lève IndexAbsent si décalé
        self.assertEqual(index.empreinte_corpus, corpus.empreinte())
        self.assertEqual(len(index.numeros), len(corpus.passages()))

    def test_l_index_versionne_nomme_le_modele_qui_l_a_produit(self):
        """Un index sans le nom de son modèle ne se vérifie pas.

        L'empreinte scelle l'index sur le CORPUS ; rien ne le scelle sur le
        modèle, parce qu'on ne peut pas prendre l'empreinte de 1,2 Go de poids
        à chaque démarrage. Le nom écrit dans les métadonnées est donc la
        seule trace de ce couple, et c'est la limite connue du mécanisme —
        elle est dite dans DEPLOIEMENT.md plutôt que cachée.
        """
        chemin = module_dense.chemin_index()
        if not chemin.exists():
            self.skipTest(f"index absent de ce clone : {chemin}")
        index = module_dense.lire_index(module_corpus.charger())
        self.assertEqual(index.modele, module_dense.MODELE)


@unittest.skipIf(_MANQUE, _MANQUE or "disponible")
class LeRefusEstReel(unittest.TestCase):
    """Le mécanisme de refus fonctionne-t-il vraiment ?

    C'est CE test qui autorise à versionner l'index. Il fabrique un index dont
    l'empreinte est fausse et vérifie qu'il est rejeté, au lieu d'être servi.
    """

    def _ecrire_index(self, chemin: Path, empreinte: str, passages: int) -> None:
        """Écrit un index minimal, de la même forme que `noyau.indexer`."""
        import numpy as np

        corpus = module_corpus.charger()
        numeros = [p.numero for p in corpus.passages()][:passages]
        vecteurs = np.zeros((len(numeros), 8), dtype=np.float32)
        meta = {
            "modele": module_dense.MODELE,
            "empreinte_corpus": empreinte,
            "passages": len(numeros),
            "dimension": 8,
        }
        np.savez(
            chemin,
            vecteurs=vecteurs,
            numeros=np.array(numeros, dtype=str),
            meta=np.array(json.dumps(meta, ensure_ascii=False)),
        )

    def test_une_empreinte_qui_ne_correspond_pas_fait_refuser_l_index(self):
        """Le cœur du filet : un index périmé doit ÉCHOUER, pas décaler.

        Un index calculé sur un autre corpus ne casse rien de visible — il
        décale les vecteurs d'un cran et rend des réponses fausses mais
        plausibles. C'est exactement le mode de panne qu'un assistant
        juridique ne peut pas se permettre, et la raison pour laquelle le
        contrôle existe.

        L'index truqué est lu PAR LE CHEMIN DE PRODUCTION : `chemin_index()`
        consulte `MIZAN_INDEX_DENSE`, et l'on s'en sert pour faire relire le
        faux fichier par le code du service lui-même, sans toucher à l'index
        du dépôt. Un test qui n'emprunterait pas ce chemin ne prouverait rien
        du comportement réel au démarrage.
        """
        import os
        import tempfile

        corpus = module_corpus.charger()
        ancienne = os.environ.get("MIZAN_INDEX_DENSE")
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "truque.npz"
            self._ecrire_index(
                chemin, empreinte="0" * 64, passages=len(corpus.passages())
            )
            os.environ["MIZAN_INDEX_DENSE"] = str(chemin)
            try:
                with self.assertRaises(module_dense.IndexAbsent) as capture:
                    module_dense.lire_index(corpus)
                message = str(capture.exception)
                # Le message doit dire QUOI FAIRE : un refus qui ne donne pas
                # la commande de reconstruction se contourne en supprimant le
                # contrôle, ce qui est le contraire du but.
                self.assertIn("autre corpus", message)
                self.assertIn("noyau.indexer", message)
            finally:
                if ancienne is None:
                    os.environ.pop("MIZAN_INDEX_DENSE", None)
                else:
                    os.environ["MIZAN_INDEX_DENSE"] = ancienne

    def test_un_index_absent_dit_quoi_lancer(self):
        """Le cas du clone neuf : l'index manque, le message doit le dire.

        Il reste atteignable même avec l'index versionné — un `.dockerignore`
        trop large, un export de sources sans les binaires — et c'est
        précisément un cas où l'on cherche une explication dans un journal.
        """
        import os

        corpus = module_corpus.charger()
        ancienne = os.environ.get("MIZAN_INDEX_DENSE")
        os.environ["MIZAN_INDEX_DENSE"] = str(
            Path("ce_chemin_n_existe_pas") / "rien.npz"
        )
        try:
            with self.assertRaises(module_dense.IndexAbsent) as capture:
                module_dense.lire_index(corpus)
            self.assertIn("noyau.indexer", str(capture.exception))
        finally:
            if ancienne is None:
                os.environ.pop("MIZAN_INDEX_DENSE", None)
            else:
                os.environ["MIZAN_INDEX_DENSE"] = ancienne

    def test_un_index_incoherent_est_refuse(self):
        """Autant de vecteurs que de numéros, sinon refus.

        Cette incohérence-là ne vient pas d'une dérive de corpus mais d'une
        écriture interrompue — un disque plein, un conteneur tué pendant
        l'indexation. Elle décalerait aussi les réponses en silence.
        """
        import os
        import tempfile

        import numpy as np

        corpus = module_corpus.charger()
        ancienne = os.environ.get("MIZAN_INDEX_DENSE")
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "tronque.npz"
            numeros = [p.numero for p in corpus.passages()]
            np.savez(
                chemin,
                vecteurs=np.zeros((len(numeros) - 3, 8), dtype=np.float32),
                numeros=np.array(numeros, dtype=str),
                meta=np.array(json.dumps({
                    "modele": module_dense.MODELE,
                    "empreinte_corpus": corpus.empreinte(),
                }, ensure_ascii=False)),
            )
            os.environ["MIZAN_INDEX_DENSE"] = str(chemin)
            try:
                with self.assertRaises(module_dense.IndexAbsent) as capture:
                    module_dense.lire_index(corpus)
                self.assertIn("incohérent", str(capture.exception))
            finally:
                if ancienne is None:
                    os.environ.pop("MIZAN_INDEX_DENSE", None)
                else:
                    os.environ["MIZAN_INDEX_DENSE"] = ancienne


if __name__ == "__main__":
    if _MANQUE:
        print(f"[tests de l'index scellé sautés] {_MANQUE}\n", flush=True)
    unittest.main(verbosity=2)
