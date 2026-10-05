# -*- coding: utf-8 -*-
"""Tests du banc d'abstention (`arbitrage/abstention.py`).

    python tests/test_abstention.py       # suffit : bibliothèque standard seule

Ce banc sert à DÉCIDER quel signal d'abstention retenir, donc à produire des
chiffres qui seront publiés. Il a besoin des mêmes garanties que le code qu'il
mesure, et plus précisément de trois :

1. **La composition recopiée ne doit pas dériver.** Le banc a besoin des scores
   des DEUX bras séparément, que le `Resultat` du contrat n'expose pas : il
   recopie donc `Moteur._composer`. Une recopie qui dérive ferait imprimer un
   coût en rappel qui n'est plus celui du système réel, et personne ne le
   verrait. `test_compose_comme_le_noyau` l'épingle contre le moteur réel.

2. **Les deux erreurs doivent être comptées dans le bon sens.** Inverser
   « refus à tort » et « acceptées à tort » produirait un tableau parfaitement
   cohérent et parfaitement faux, qui recommanderait le pire signal. Les tests
   de `frontiere` fixent les deux comptes sur des cas écrits à la main.

3. **L'orientation des signaux doit rester celle qui est déclarée.** Tout le
   banc repose sur « plus haut veut dire plus confiant ». Un signal dont la
   grandeur naturelle décroît avec la confiance doit être nié à la source, et
   `test_moins_inconnus_est_bien_nie` vérifie que ça n'a pas été oublié.

Aucun de ces tests ne charge le modèle de 1,2 Go ni l'index vectoriel : ils
portent sur l'arithmétique du banc, pas sur la qualité de la récupération. Ce
que vaut la récupération, c'est le banc lui-même qui le mesure, et il s'exécute
à la main avec la commande écrite dans son en-tête.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))
if str(RACINE / "arbitrage") not in sys.path:
    sys.path.insert(0, str(RACINE / "arbitrage"))

import sortie  # noqa: E402,F401

import abstention  # noqa: E402
from noyau import corpus as module_corpus  # noqa: E402
from noyau import recherche as module_recherche  # noqa: E402


class BrasDenseFactice:
    """Un bras dense dont on écrit le classement à la main."""

    def __init__(self, classement) -> None:
        self.classement = list(classement)

    def classer(self, question: str, profondeur: int):
        return self.classement[:profondeur]


def _cas(ident, du_corpus, signaux, rendus=(), attendus=()):
    """Un `Cas` réduit à ce que les tests d'arithmétique regardent."""
    return abstention.Cas(
        id=ident,
        question=f"question {ident}",
        du_corpus=du_corpus,
        famille="essai",
        moitie="essai",
        attendus=frozenset(attendus),
        dense=(),
        rendus=tuple(rendus),
        signaux=dict(signaux),
    )


class CompositionFidele(unittest.TestCase):
    """La recopie de la composition doit rendre EXACTEMENT ce que rend le moteur."""

    def test_compose_comme_le_noyau(self):
        # Un classement dense dont les trois premiers sont intouchables, et un
        # classement lexical qui doit remplir la queue sans doublon. C'est le
        # cas où une recopie approximative se trahit : si la profondeur dense
        # dérivait, le quatrième article changerait de bras.
        corpus = module_corpus.charger()
        numeros = [a["numero"] for a in corpus.articles[:8]]
        dense = [(n, 0.9 - i * 0.1) for i, n in enumerate(numeros[:6])]
        lexical = [(numeros[5], 3.0), (numeros[6], 2.0), (numeros[7], 1.0)]

        moteur = module_recherche.Moteur(corpus, BrasDenseFactice(dense))
        attendu = [a.numero for a in moteur._composer(dense, lexical, 5)]
        obtenu = abstention._composer(dense, lexical, 5)
        self.assertEqual(
            obtenu, attendu,
            "La composition recopiée dans le banc a dérivé de Moteur._composer : "
            "le coût en rappel imprimé n'est plus celui du système réel.",
        )

    def test_compose_respecte_la_profondeur_dense_du_noyau(self):
        corpus = module_corpus.charger()
        numeros = [a["numero"] for a in corpus.articles[:10]]
        dense = [(n, 0.9 - i * 0.1) for i, n in enumerate(numeros[:5])]
        lexical = [(n, 1.0) for n in numeros[5:]]
        obtenu = abstention._composer(dense, lexical, 5)
        tete_dense = [n for n, _ in dense[: module_recherche.PROFONDEUR_DENSE]]
        self.assertEqual(obtenu[: module_recherche.PROFONDEUR_DENSE], tete_dense)


class LesDeuxErreurs(unittest.TestCase):
    """Les deux erreurs, comptées dans le bon sens et jamais l'une sans l'autre."""

    def setUp(self):
        # Trois questions du corpus à 0,6 / 0,5 / 0,4 et deux étrangères à
        # 0,45 / 0,2. Un seuil à 0,5 refuse donc deux questions du corpus et
        # n'accepte aucune étrangère ; un seuil à 0,3 n'en refuse aucune et
        # accepte une étrangère. Les deux cas sont écrits en dur pour que
        # l'inversion des colonnes soit visible.
        self.cas = [
            _cas("C1", True, {"s": 0.6}),
            _cas("C2", True, {"s": 0.5}),
            _cas("C3", True, {"s": 0.4}),
            _cas("E1", False, {"s": 0.45}),
            _cas("E2", False, {"s": 0.2}),
        ]

    def test_frontiere_compte_les_refus_a_tort_dans_le_corpus(self):
        front = {p["acceptees_a_tort"]: p for p in abstention.frontiere(self.cas, "s")}
        # Zéro étrangère acceptée exige un seuil au-dessus de 0,45 : il refuse
        # alors la seule question du corpus à 0,4.
        self.assertEqual(front[0]["refus_a_tort"], 1)
        self.assertEqual(front[0]["n_corpus"], 3)
        self.assertEqual(front[0]["n_etrangeres"], 2)

    def test_frontiere_atteint_zero_refus_en_acceptant_tout(self):
        front = {p["acceptees_a_tort"]: p for p in abstention.frontiere(self.cas, "s")}
        self.assertEqual(front[2]["refus_a_tort"], 0)

    def test_frontiere_est_monotone(self):
        """Accepter plus d'étrangères ne peut jamais coûter plus de refus.

        Si cette propriété tombe, c'est que la frontière ne garde pas le
        meilleur seuil par nombre d'acceptations, et les tableaux du banc
        recommanderaient un réglage dominé par un autre.
        """
        front = abstention.frontiere(self.cas, "s")
        refus = [p["refus_a_tort"] for p in front]
        self.assertEqual(refus, sorted(refus, reverse=True))

    def test_aire_vaut_un_quand_le_signal_separe_parfaitement(self):
        cas = [_cas("C1", True, {"s": 1.0}), _cas("E1", False, {"s": 0.0})]
        self.assertEqual(abstention.aire(cas, "s"), 1.0)

    def test_aire_vaut_zero_quand_le_signal_est_inverse(self):
        cas = [_cas("C1", True, {"s": 0.0}), _cas("E1", False, {"s": 1.0})]
        self.assertEqual(abstention.aire(cas, "s"), 0.0)

    def test_aire_compte_les_egalites_une_demie(self):
        cas = [_cas("C1", True, {"s": 0.5}), _cas("E1", False, {"s": 0.5})]
        self.assertEqual(abstention.aire(cas, "s"), 0.5)


class LeRappelPaieLAbstention(unittest.TestCase):
    """Une abstention compte un rappel NUL : c'est ce qui interdit de la vendre seule."""

    def test_se_taire_toujours_coute_tout_le_rappel(self):
        cas = [_cas("C1", True, {"s": 0.5}, rendus=("12",), attendus=("12",))]
        self.assertEqual(abstention.rappels(cas, "s", 99.0)[1], 0.0)

    def test_repondre_a_tout_rend_le_rappel_entier(self):
        cas = [_cas("C1", True, {"s": 0.5}, rendus=("12",), attendus=("12",))]
        self.assertEqual(abstention.rappels(cas, None, 0.0)[1], 1.0)

    def test_rappel_partiel_sur_plusieurs_articles_attendus(self):
        """Le rappel est une PART des articles attendus, pas un tout ou rien.

        Deux attendus dont un seul est au rang 1 : c'est 0,5, et non 0. La
        distinction compte parce que douze questions du jeu exigent plusieurs
        articles ; les compter en tout ou rien écraserait leur contribution.
        """
        cas = [_cas("C1", True, {"s": 0.5}, rendus=("12", "99"), attendus=("12", "13"))]
        self.assertEqual(abstention.rappels(cas, None, 0.0)[1], 0.5)
        self.assertEqual(abstention.rappels(cas, None, 0.0)[3], 0.5)
        # Un attendu hors des trois premiers ne compte pas : le rang borne bien.
        loin = [_cas("C2", True, {"s": 0.5},
                     rendus=("1", "2", "3", "4", "13"), attendus=("12", "13"))]
        self.assertEqual(abstention.rappels(loin, None, 0.0)[3], 0.0)
        self.assertEqual(abstention.rappels(loin, None, 0.0)[5], 0.5)

    def test_les_etrangeres_ne_pesent_pas_dans_le_rappel(self):
        """Le rappel se calcule sur les questions répondables, et sur elles seules.

        Compter les étrangères ferait baisser le rappel d'un système qui se
        tait correctement, c'est-à-dire punirait la bonne conduite.
        """
        cas = [
            _cas("C1", True, {"s": 0.5}, rendus=("12",), attendus=("12",)),
            _cas("E1", False, {"s": 0.5}, rendus=("99",)),
        ]
        self.assertEqual(abstention.rappels(cas, None, 0.0)[1], 1.0)


class OrientationDesSignaux(unittest.TestCase):
    """« Plus haut veut dire plus confiant », sans exception."""

    def test_moins_inconnus_est_bien_nie(self):
        class LectureFactice:
            classement = []
            couverture = 0.0
            termes_inconnus = ("couscous", "recette")

        signaux = abstention._signaux([("1", 0.5), ("2", 0.4)], LectureFactice())
        self.assertEqual(signaux["moins_inconnus"], -2.0)
        self.assertLess(
            signaux["moins_inconnus"], 0.0,
            "Le signal doit être NIÉ : deux mots inconnus sont moins rassurants "
            "que zéro, et toutes les courbes du banc se lisent dans ce sens.",
        )

    def test_marge_nulle_sur_les_cas_degeneres(self):
        """Les deux cas dégénérés du noyau, tranchés de la même façon ici.

        Si le banc et la production divergeaient sur un classement vide ou un
        premier score négatif, le banc mesurerait un système qui n'existe pas.
        """
        class LectureFactice:
            classement = []
            couverture = 0.0
            termes_inconnus = ()

        self.assertEqual(abstention._signaux([], LectureFactice())["marge"], 0.0)
        self.assertEqual(
            abstention._signaux([("1", -0.2), ("2", -0.5)], LectureFactice())["marge"],
            0.0,
        )
        self.assertEqual(
            abstention._signaux([("1", 0.5)], LectureFactice())["marge"], 0.0
        )

    def test_masse_est_la_moyenne_et_non_la_somme(self):
        """La moyenne, pour que masse3 et masse5 se comparent entre elles.

        Une somme ferait mécaniquement gagner masse5 sur masse3 sans rien dire
        du voisinage, et le tableau de comparaison du banc serait un artefact.
        """
        class LectureFactice:
            classement = []
            couverture = 0.0
            termes_inconnus = ()

        classement = [(str(i), 0.5) for i in range(5)]
        signaux = abstention._signaux(classement, LectureFactice())
        self.assertAlmostEqual(signaux["masse5"], 0.5)
        self.assertAlmostEqual(signaux["masse3"], 0.5)


class LeJeuEtSaPartition(unittest.TestCase):
    """Le camp de chaque question, et la partition, viennent du jeu et non d'ici."""

    def test_les_questions_hors_code_sont_du_corpus(self):
        """Correction nº 1 de l'en-tête, épinglée.

        `hors_code` désigne une question dont le CHIFFRE est dans un texte
        réglementaire, mais dont l'article de renvoi est dans le Code et est
        attendu. S'en abstenir est une faute. Les classer hors corpus — ce que
        l'énoncé de ce chantier supposait — mettrait trois questions
        répondables du mauvais côté de la frontière mesurée.
        """
        import json
        jeu = json.loads(abstention.JEU.read_text(encoding="utf-8"))
        hors_code = [q for q in jeu["questions"] if "hors_code" in q["etiquettes"]]
        self.assertTrue(hors_code, "Le jeu ne porte plus d'étiquette hors_code.")
        camps = {q["id"]: du_corpus
                 for q, (_i, _q, du_corpus, _f, _v, _a)
                 in zip(jeu["questions"], abstention._questions())}
        for q in hors_code:
            self.assertTrue(q["articles_attendus"],
                            f"{q['id']} porte hors_code sans article attendu.")
            self.assertTrue(camps[q["id"]],
                            f"{q['id']} est hors_code et doit compter DU corpus.")

    def test_le_hors_corpus_est_sans_reponse_et_non_hors_code(self):
        import json
        jeu = json.loads(abstention.JEU.read_text(encoding="utf-8"))
        for _i, _q, du_corpus, _f, _v, attendus in abstention._questions():
            self.assertEqual(bool(attendus), du_corpus,
                             "Le camp doit se lire sur articles_attendus seul.")
        sans_reponse = [q for q in jeu["questions"] if "sans_reponse" in q["etiquettes"]]
        self.assertFalse(
            [q for q in sans_reponse if q["articles_attendus"]],
            "Une question sans_reponse porte des articles attendus : le jeu se contredit.",
        )

    def test_la_partition_vient_du_jeu(self):
        volets = {v for _i, _q, _c, _f, v, _a in abstention._questions()}
        self.assertTrue(volets <= {"partout", "reglage", "verification"}, volets)

    def test_mes_etrangeres_ne_comptent_pas_par_defaut(self):
        """Elles sont une contre-épreuve, jamais un apport silencieux au chiffre.

        Si elles entraient par défaut, une proportion publiée mélangerait des
        questions écrites par l'agent d'évaluation et des questions écrites par
        l'arbitre, et ce mélange ne serait plus démêlable après coup.
        """
        sans = {i for i, _q, _c, _f, _v, _a in abstention._questions(False)}
        avec = {i for i, _q, _c, _f, _v, _a in abstention._questions(True)}
        self.assertEqual(avec - sans, {e[0] for e in abstention.ETRANGERES})
        self.assertFalse(sans & {e[0] for e in abstention.ETRANGERES})


if __name__ == "__main__":
    unittest.main(verbosity=2)
