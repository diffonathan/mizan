# -*- coding: utf-8 -*-
"""Tests du noyau de récupération.

    python tests/test_noyau.py            # suffit : bibliothèque standard seule

AUCUNE CLÉ, AUCUN PAQUET. C'est une condition, pas une commodité : un projet
dont les tests ne tournent que chez son auteur n'est pas un projet. Les tests se
répartissent donc en deux familles, et la deuxième se SAUTE en disant pourquoi.

1. **Le contrat** — k respecté, déterminisme, abstention, avertissement
   obligatoire, phrase d'explication. Ces tests injectent un bras dense factice
   et déterministe, et tournent partout, sans modèle de 1,2 Go, sans `numpy`, et
   sans l'index vectoriel.

2. **La fidélité** — une question du Code retrouve bien son article, une
   question hors du Code déclenche bien l'abstention, et le chargement tient
   dans la seconde. Ces tests ont besoin de l'index et du modèle ; ils se
   sautent avec un message qui dit quoi lancer quand ils manquent.

Les deux familles sont nécessaires et aucune ne remplace l'autre : la première
vérifie que l'architecture est bien celle qui a été décidée, la seconde qu'elle
récupère bien le droit.
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

# Sous Windows, la sortie de Python vaut cp1252 dès qu'elle n'est pas un
# terminal moderne, et `unittest` écrit ses noms de test sur stderr : sans cette
# importation, « marge serrée » se lit « marge serr?e » dans un rapport de test,
# c'est-à-dire exactement là où l'on vérifie quelque chose.
import sortie  # noqa: E402,F401

from noyau import corpus as module_corpus  # noqa: E402
from noyau import dense as module_dense  # noqa: E402
from noyau import lexical as module_lexical  # noqa: E402
from noyau import recherche as module_recherche  # noqa: E402


# ── Le bras dense factice ───────────────────────────────────────────────────

class BrasDenseFactice:
    """Un bras dense dont on écrit le classement à la main.

    Il ne simule pas un modèle : il le remplace par ce dont les tests ont
    besoin, c'est-à-dire un classement et une marge CHOISIS. C'est la seule
    façon de tester le seuil d'abstention des deux côtés sans chercher une
    question réelle dont la marge tombe au bon endroit — une telle question
    existerait, mais le test dépendrait alors du modèle, du corpus et du hasard,
    et ne dirait plus rien du code qu'il prétend vérifier.
    """

    def __init__(self, classement: list[tuple[str, float]]) -> None:
        self.classement = list(classement)
        self.appels = 0

    def classer(self, question: str, profondeur: int) -> list[tuple[str, float]]:
        self.appels += 1
        return self.classement[:profondeur]


def _moteur_factice(classement, seuil=module_recherche.SEUIL_MARGE):
    corpus = module_corpus.charger()
    return module_recherche.Moteur(corpus, BrasDenseFactice(classement), seuil)


# Deux classements de référence. Les scores sont des cosinus plausibles — la
# plage mesurée sur le banc des fondations va de 0,458 à 0,721 — pour que la
# marge calculée soit du même ordre que celles du produit.
NET = [("14", 0.70), ("502", 0.58), ("13", 0.55), ("80", 0.52), ("17", 0.50)]
SERRE = [("354", 0.52), ("350", 0.5055), ("353", 0.50), ("355", 0.49), ("361", 0.48)]


class ContratDeRecherche(unittest.TestCase):
    """Ce que trois agents vont appeler juste après. Rien ici ne doit bouger."""

    def test_k_est_respecte(self):
        moteur = _moteur_factice(NET)
        for k in (1, 2, 3, 5, 8):
            with self.subTest(k=k):
                resultat = moteur.chercher("congé annuel payé", k=k)
                self.assertEqual(len(resultat.articles), k)
                # Pas de doublon : deux fois le même article dans les cinq
                # rendus réduirait silencieusement le service à quatre.
                self.assertEqual(len(resultat.numeros), k)

    def test_k_invalide_est_refuse(self):
        moteur = _moteur_factice(NET)
        for k in (0, -1, 2.5, None):
            with self.subTest(k=k):
                with self.assertRaises((ValueError, TypeError)):
                    moteur.chercher("congé annuel payé", k=k)

    def test_question_vide_est_refusee(self):
        moteur = _moteur_factice(NET)
        for question in ("", "   ", "\n"):
            with self.subTest(question=repr(question)):
                with self.assertRaises(module_recherche.QuestionVide):
                    moteur.chercher(question)

    def test_le_meme_appel_rend_le_meme_resultat(self):
        moteur = _moteur_factice(NET)
        question = "Durée maximale de la période d'essai pour un cadre"
        premier = moteur.chercher(question, k=5)
        second = moteur.chercher(question, k=5)
        self.assertEqual(premier, second)
        self.assertEqual(
            [(a.numero, a.score, a.bras) for a in premier.articles],
            [(a.numero, a.score, a.bras) for a in second.articles],
        )

    def test_la_tete_vient_du_bras_dense_et_la_queue_du_lexical(self):
        """L'architecture décidée, vérifiée là où elle se voit.

        Les rangs 1 à 3 sont ceux du bras dense, intouchables : c'est ce qui
        rend le rappel@1 et le rappel@3 du noyau égaux, question par question, à
        ceux du bras dense seul.
        """
        moteur = _moteur_factice(NET)
        resultat = moteur.chercher("licenciement pour faute grave", k=5)
        bras = [a.bras for a in resultat.articles]
        self.assertEqual(bras[:3], ["dense"] * 3)
        self.assertEqual([a.numero for a in resultat.articles[:3]],
                         [n for n, _ in NET[:3]])
        self.assertIn("lexical", bras[3:])

    def test_une_marge_nette_autorise_a_affirmer(self):
        moteur = _moteur_factice(NET)
        resultat = moteur.chercher("période d'essai", k=5)
        self.assertTrue(resultat.sur)
        self.assertGreaterEqual(resultat.marge, module_recherche.SEUIL_MARGE)
        self.assertIn("14", resultat.pourquoi)

    def test_une_marge_serree_declenche_l_abstention(self):
        moteur = _moteur_factice(SERRE)
        resultat = moteur.chercher("Montant de la prime d'ancienneté", k=5)
        self.assertFalse(resultat.sur)
        self.assertLess(resultat.marge, module_recherche.SEUIL_MARGE)
        # L'abstention ne vide PAS la liste : le registre de doute montre les
        # candidats sans les présenter comme la réponse.
        self.assertEqual(len(resultat.articles), 5)

    def test_sans_aucun_candidat_le_systeme_se_tait(self):
        moteur = _moteur_factice([])
        resultat = moteur.chercher("xyzzy plugh", k=5)
        self.assertFalse(resultat.sur)
        self.assertEqual(resultat.articles, ())
        self.assertIn("aucun article", resultat.pourquoi.lower())

    def test_un_seul_candidat_ne_suffit_pas_a_affirmer(self):
        """Rien dont se détacher, donc rien qui autorise à désigner une réponse."""
        moteur = _moteur_factice([("14", 0.70)])
        self.assertFalse(moteur.chercher("période d'essai", k=5).sur)

    def test_le_seuil_est_un_parametre_et_non_une_constante_enfouie(self):
        """Le seuil est lu sur le banc qui sert aussi à juger : il doit se régler."""
        question = "Montant de la prime d'ancienneté"
        self.assertFalse(_moteur_factice(SERRE).chercher(question).sur)
        self.assertTrue(_moteur_factice(SERRE, seuil=0.0).chercher(question).sur)

    def test_pourquoi_est_une_phrase_lisible(self):
        for classement in (NET, SERRE, []):
            with self.subTest(classement=len(classement)):
                phrase = _moteur_factice(classement).chercher("congé").pourquoi
                self.assertTrue(phrase.endswith("."))
                self.assertGreater(len(phrase.split()), 5)
                # Pas de code, pas de nom de variable : la phrase est pour un
                # humain. Les chiffres s'écrivent à la française.
                self.assertNotIn("_", phrase)
                self.assertNotIn("0.0", phrase)

    def test_chaque_article_porte_de_quoi_etre_verifie(self):
        resultat = _moteur_factice(NET).chercher("période d'essai", k=5)
        for article in resultat.articles:
            self.assertTrue(article.numero)
            self.assertTrue(article.texte.strip())
            # La position dans la hiérarchie, pas seulement le numéro : c'est
            # elle qui permet de retrouver l'article dans le texte officiel.
            self.assertIn("article", article.position)
            self.assertIn("Livre", article.position)
            self.assertIsInstance(article.score, float)
            self.assertIn(article.bras, ("dense", "lexical"))


class GardeFouDeConsolidation(unittest.TestCase):
    """Le corpus est arrêté au 26 octobre 2011, et le code doit l'imposer."""

    def test_tout_resultat_porte_l_avertissement(self):
        for classement in (NET, SERRE, []):
            with self.subTest(classement=len(classement)):
                resultat = _moteur_factice(classement).chercher("congé")
                self.assertIn("2011", resultat.avertissement)

    def test_un_resultat_sans_avertissement_est_impossible_a_construire(self):
        """La garantie est structurelle, pas recommandée.

        Si ce test tombe, l'avertissement est redevenu une consigne — et une
        consigne s'oublie le jour où quelqu'un écrit un second affichage.
        """
        for vide in ("", "   "):
            with self.subTest(avertissement=repr(vide)):
                with self.assertRaises(ValueError):
                    module_recherche.Resultat(
                        question="q", articles=(), sur=False, pourquoi="p.",
                        avertissement=vide, marge=0.0, seuil_marge=0.04,
                    )


class BrasLexical(unittest.TestCase):
    """Le bras de queue, qui tourne sans modèle et sans dépendance."""

    @classmethod
    def setUpClass(cls):
        cls.corpus = module_corpus.charger()
        cls.index = module_lexical.IndexLexical(cls.corpus)

    def test_un_terme_exact_remonte_son_article(self):
        lecture = self.index.lire("prime d'ancienneté", profondeur=5)
        self.assertIn("350", [n for n, _ in lecture.classement])

    def test_les_mots_absents_du_code_sont_nommes(self):
        lecture = self.index.lire("mon bébé vient de naître, et le télétravail ?",
                                  profondeur=5)
        self.assertIn("bebe", lecture.termes_inconnus)
        self.assertLess(lecture.couverture, 1.0)

    def test_aucune_racinisation(self):
        """Le rogneur de suffixes maison coûtait cinq points de rappel@1.

        Le vérifier par le comportement et non par un drapeau : « licenciement »
        et « licencier » ne doivent PAS produire le même jeton, sans quoi le
        rogneur est revenu par une porte ou une autre.
        """
        self.assertNotEqual(module_lexical.decouper("licenciement"),
                            module_lexical.decouper("licencier"))

    def test_les_apostrophes_et_les_accents_ne_bloquent_pas(self):
        self.assertEqual(module_lexical.decouper("l'employeur"), ["employeur"])
        self.assertEqual(module_lexical.decouper("ancienneté"),
                         module_lexical.decouper("anciennete"))


class Corpus(unittest.TestCase):
    def test_l_article_sans_texte_n_est_pas_plonge(self):
        """Un vecteur calculé sur du vide serait un voisin plausible pour tout."""
        corpus = module_corpus.charger()
        passages = corpus.passages()
        self.assertLess(len(passages), len(corpus.articles))
        for passage in passages:
            self.assertTrue(passage.texte.strip())

    def test_l_empreinte_des_passages_est_stable(self):
        corpus = module_corpus.charger()
        self.assertEqual(corpus.empreinte(), module_corpus.charger().empreinte())


# ── Fidélité : ces tests ont besoin de l'index et du modèle ─────────────────

def _indisponible() -> str:
    """Dit en une phrase ce qui manque et quoi lancer, ou une chaîne vide."""
    try:
        import numpy  # noqa: F401
    except ImportError:
        return ("numpy absent de cet interpréteur — pip install -r "
                "requirements.txt pour mesurer le bras dense")
    try:
        corpus = module_corpus.charger()
        module_dense.lire_index(corpus)
    except Exception as erreur:
        return f"index vectoriel indisponible — {str(erreur).splitlines()[0]}"
    try:
        module_dense.charger_plongeur()
    except Exception as erreur:
        return f"modèle dense indisponible — {str(erreur).splitlines()[0]}"
    return ""


_MANQUE = _indisponible()


@unittest.skipIf(_MANQUE, _MANQUE or "disponible")
class Fidelite(unittest.TestCase):
    """La récupération réelle, avec le modèle et l'index de production."""

    @classmethod
    def setUpClass(cls):
        cls.corpus = module_corpus.charger()
        depart = time.perf_counter()
        bras = module_dense.charger_bras_dense(cls.corpus)
        cls.moteur = module_recherche.Moteur(cls.corpus, bras)
        cls.secondes_chargement = time.perf_counter() - depart

    def test_une_question_du_code_retrouve_son_article(self):
        resultat = self.moteur.chercher(
            "Durée maximale de la période d'essai pour un cadre en contrat à "
            "durée indéterminée", k=5
        )
        self.assertEqual(resultat.articles[0].numero, "14")
        self.assertTrue(resultat.sur)

    def test_une_question_en_langue_d_usager_retrouve_son_article(self):
        """Le seul écart que l'architecture retenue justifie : la langue de l'usager."""
        resultat = self.moteur.chercher(
            "Combien de jours de congés j'ai droit après deux ans chez le même "
            "employeur ?", k=5
        )
        self.assertIn("231", resultat.numeros)

    def test_une_question_hors_du_code_declenche_l_abstention(self):
        resultat = self.moteur.chercher(
            "Combien coûte un avocat spécialisé en droit du travail au Maroc ?",
            k=5,
        )
        self.assertFalse(resultat.sur)
        self.assertLess(resultat.marge, module_recherche.SEUIL_MARGE)
        # Le silence du produit n'est pas un écran vide : les candidats restent
        # là, et la phrase dit pourquoi ils ne sont pas présentés comme la
        # réponse.
        self.assertEqual(len(resultat.articles), 5)
        self.assertIn("marge", resultat.pourquoi)

    def test_le_meme_appel_rend_le_meme_resultat(self):
        """Le déterminisme du modèle lui-même, pas seulement de l'assemblage."""
        question = "Un salarié peut-il être licencié pendant son congé de maladie ?"
        premier = self.moteur.chercher(question, k=5)
        second = self.moteur.chercher(question, k=5)
        self.assertEqual(premier, second)

    def test_k_est_respecte(self):
        for k in (1, 3, 5, 10):
            with self.subTest(k=k):
                resultat = self.moteur.chercher("licenciement abusif", k=k)
                self.assertEqual(len(resultat.articles), k)

    def test_le_corpus_et_les_index_se_chargent_en_moins_d_une_seconde(self):
        """Le corpus et les deux index, pas la session ONNX.

        La distinction n'est pas une échappatoire, c'est la mesure : lire le
        corpus, l'index vectoriel et construire l'index lexical se compte en
        dizaines de millisecondes, tandis qu'ouvrir la session ONNX du modèle en
        demande près de deux secondes à elle seule. Les additionner sous un seul
        chiffre masquerait lequel des deux il faudrait optimiser — et le second
        ne s'optimise pas, il se paie une fois au démarrage du service.
        """
        depart = time.perf_counter()
        corpus = module_corpus.charger()
        module_dense.lire_index(corpus)
        module_lexical.IndexLexical(corpus)
        secondes = time.perf_counter() - depart
        self.assertLess(secondes, 1.0, f"{secondes:.3f} s")


if __name__ == "__main__":
    if _MANQUE:
        print(f"[tests de fidélité sautés] {_MANQUE}\n", flush=True)
    unittest.main(verbosity=2)
