# -*- coding: utf-8 -*-
"""Tests du banc de bout en bout.

    python tests/test_banc_bout_en_bout.py     # suffit : bibliothèque standard seule

AUCUNE CLÉ, AUCUN PAQUET, AUCUN MODÈLE DE 1,2 Go. C'est la contrainte du
projet, et elle porte ici une exigence de plus : un banc n'est pas un
programme ordinaire. Quand un programme se trompe, il plante ; quand un banc
se trompe, il imprime un chiffre et on le croit.

Ces tests vérifient donc le banc lui-même, dans cet ordre :

1. **Le contrat de réponse** — ce qui ne peut pas être construit, et ce que le
   banc refuse de mesurer.
2. **L'extraction des citations** — y compris le trou de la plage « 205 à 208 »,
   testé pour qu'il reste documenté et non découvert par surprise.
3. **Le modèle factice** — qu'il soit déterministe et qu'il produise réellement
   les quatre familles annoncées. Un faux modèle qui ne fabrique pas les cas
   que la garde doit attraper rendrait tout le reste décoratif.
4. **La garde du répondeur témoin** — rejette l'hallucination, rejette la
   rédaction sans citation, rend la rédaction loyale.
5. **Les mesures** — et surtout qu'une FUITE, c'est-à-dire une hallucination
   rendue à l'usager, soit vue et fasse sortir le banc en code 1. C'est le
   test le plus important du fichier : il vérifie que le banc sait détecter
   l'échec qu'il est censé détecter.

Le bras dense est le plancher `idf` : la chaîne entière tourne sans index.
"""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
for chemin in (str(RACINE), str(RACINE / "evaluation")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

# Sous Windows, la sortie de Python vaut cp1252 dès qu'elle n'est pas un
# terminal moderne, et `unittest` écrit ses noms de test sur stderr.
import sortie  # noqa: E402,F401

import banc  # noqa: E402
import banc_bout_en_bout as bbb  # noqa: E402
from noyau import corpus as module_corpus  # noqa: E402
from noyau import recherche as module_recherche  # noqa: E402

_CORPUS = module_corpus.charger()
_NUMEROS = frozenset(a["numero"] for a in _CORPUS.articles)
_AVERTISSEMENT = _CORPUS.avertissement


def _article(numero: str, bras: str = "dense", score: float = 0.5):
    return module_recherche.ArticleTrouve(
        numero=numero, texte="(texte)", position="(position)",
        score=score, bras=bras,
    )


def _moteur_idf(seuil: float = module_recherche.SEUIL_MARGE):
    return module_recherche.Moteur(
        _CORPUS, bbb.BrasDenseIdf(_CORPUS.articles), seuil
    )


class ContratDeReponse(unittest.TestCase):
    """Ce qu'une Reponse ne peut pas être."""

    def test_avertissement_obligatoire(self):
        # Le garde-fou de consolidation est structurel : il n'y a pas d'autre
        # chemin pour construire une Reponse, donc rien à se rappeler ailleurs.
        with self.assertRaises(ValueError):
            bbb.Reponse(texte="x", citations=("231",), articles=(), abstenu=False,
                        raison="", avertissement="   ")

    def test_reponse_rendue_sans_citation_impossible(self):
        with self.assertRaises(ValueError):
            bbb.Reponse(texte="Le Code règle ce point.", citations=(), articles=(),
                        abstenu=False, raison="", avertissement=_AVERTISSEMENT)

    def test_abstention_sans_citation_est_valide(self):
        reponse = bbb.Reponse(texte=None, citations=(), articles=(), abstenu=True,
                              raison="marge trop faible", avertissement=_AVERTISSEMENT)
        self.assertTrue(reponse.abstenu)

    def test_controle_signale_une_citation_entiere(self):
        class Fausse:
            texte, citations, articles = "x", (231,), ()
            abstenu, raison, avertissement = False, "", _AVERTISSEMENT

        anomalies = bbb.controler_reponse("Q01", Fausse(), _NUMEROS)
        self.assertTrue(any("n'est pas une chaîne" in a for a in anomalies))

    def test_controle_signale_un_attribut_manquant(self):
        class Tronquee:
            texte = "x"

        anomalies = bbb.controler_reponse("Q01", Tronquee(), _NUMEROS)
        self.assertTrue(any("citations" in a for a in anomalies))

    def test_controle_signale_une_abstention_bavarde(self):
        class Bavarde:
            texte, citations, articles = "je me taisais", (), ()
            abstenu, raison, avertissement = True, "doute", _AVERTISSEMENT

        anomalies = bbb.controler_reponse("Q01", Bavarde(), _NUMEROS)
        self.assertTrue(any("porte quand même un texte" in a for a in anomalies))


class ExtractionDesCitations(unittest.TestCase):

    def test_formes_courantes(self):
        self.assertEqual(
            bbb.extraire_citations("D'après l'article 231 du Code.", _NUMEROS),
            ("231",))
        self.assertEqual(
            bbb.extraire_citations("Les articles 205 et 206 se complètent.", _NUMEROS),
            ("205", "206"))
        self.assertEqual(
            bbb.extraire_citations("Voir l'article premier.", _NUMEROS),
            ("premier",))

    def test_un_numero_hors_corpus_n_est_pas_une_citation(self):
        # « la loi 65-99 » ne doit pas être comptée comme une citation
        # d'article, sans quoi l'exactitude serait calculée sur du bruit.
        self.assertEqual(bbb.extraire_citations("la loi 65-99 formant Code", _NUMEROS),
                         ())
        self.assertEqual(bbb.extraire_citations("l'article 999 du Code", _NUMEROS), ())
        # AVEC l'ancre « article », qui est le cas que le filtre par le corpus
        # ne pouvait pas attraper : l'article 65 existe, donc « l'article 65-99 »
        # rendait une citation — et, tant que le tiret ouvrait une plage, 35.
        self.assertEqual(
            bbb.extraire_citations("l'article 65-99 formant Code", _NUMEROS), ())
        # Et un numéro trop long n'est pas tronqué en un numéro qui existe.
        self.assertEqual(
            bbb.extraire_citations("l'article 1234 du Code", _NUMEROS), ())

    def test_sans_citation(self):
        self.assertEqual(
            bbb.extraire_citations("Le Code traite de cette question.", _NUMEROS), ())

    def test_une_plage_est_depliee(self):
        # Ne rendre que les deux bornes laisserait 206 et 207 hors du contrôle
        # d'inclusion, c'est-à-dire laisserait passer ce que la garde devait
        # arrêter.
        self.assertEqual(
            bbb.extraire_citations("les articles 205 à 208", _NUMEROS),
            ("205", "206", "207", "208"))

    def test_une_plage_absurde_n_est_pas_depliee(self):
        # Déplier « 1 à 589 » fabriquerait 589 citations pour le compte du
        # modèle : seules les bornes sont rendues, et « 1 » n'existe pas dans
        # le corpus (le premier article s'appelle « premier »).
        self.assertEqual(
            bbb.extraire_citations("les articles 1 à 589", _NUMEROS), ("589",))

    def test_une_plage_a_l_envers_n_est_pas_depliee(self):
        self.assertEqual(
            bbb.extraire_citations("les articles 208 à 205", _NUMEROS),
            ("208", "205"))

    def test_la_forme_abregee_est_lue(self):
        # Ce n'est pas le législateur qui écrit, c'est un modèle de langue.
        self.assertEqual(bbb.extraire_citations("art. 231 et 238", _NUMEROS),
                         ("231", "238"))

    def test_un_nombre_sans_le_mot_article_n_est_pas_une_citation(self):
        # « 1er » apparaît dans le Code sans jamais désigner l'article premier.
        self.assertEqual(
            bbb.extraire_citations("le 1er alinéa de l'article 9", _NUMEROS),
            ("9",))

    def test_un_lien_qui_n_annonce_pas_un_numero_arrete_la_citation(self):
        self.assertEqual(
            bbb.extraire_citations("l'article 12 et le salarié", _NUMEROS),
            ("12",))

    def test_sans_doublon_et_dans_l_ordre(self):
        self.assertEqual(
            bbb.extraire_citations("l'article 231, puis l'article 12, puis 231.",
                                   _NUMEROS),
            ("231", "12"))


class ModeleFactice(unittest.TestCase):
    """Le faux modèle doit être adverse, et prévisible sans être complaisant."""

    def setUp(self):
        self.numeros = sorted(_NUMEROS, key=bbb._ordre_numero)
        self.factice = bbb.RedacteurFactice(self.numeros)
        self.articles = (_article("231"), _article("238"), _article("240"))
        self.recuperes = frozenset(a.numero for a in self.articles)

    def test_deterministe_entre_deux_instances(self):
        autre = bbb.RedacteurFactice(self.numeros)
        for question in ("congé annuel ?", "licenciement abusif", "SMIG"):
            self.assertEqual(self.factice.famille(question), autre.famille(question))
            self.assertEqual(self.factice.rediger(question, self.articles),
                             autre.rediger(question, self.articles))

    def test_les_quatre_familles_sortent_sur_le_jeu(self):
        jeu = banc.charger_questions()
        tirees = {self.factice.famille(q["question"]) for q in jeu["questions"]}
        self.assertEqual(tirees, set(bbb.FAMILLES))

    def test_chaque_famille_produit_ce_qu_elle_annonce(self):
        vus: dict[str, tuple[str, ...]] = {}
        jeu = banc.charger_questions()
        for question in jeu["questions"]:
            texte = question["question"]
            famille = self.factice.famille(texte)
            citations = bbb.extraire_citations(
                self.factice.rediger(texte, self.articles), _NUMEROS)
            vus.setdefault(famille, citations)

        self.assertEqual(vus["muette"], ())
        self.assertTrue(set(vus["fidele"]) <= self.recuperes)
        self.assertTrue(set(vus["inventee"]) - self.recuperes)
        self.assertFalse(set(vus["inventee"]) & self.recuperes)
        self.assertTrue(set(vus["melangee"]) & self.recuperes)
        self.assertTrue(set(vus["melangee"]) - self.recuperes)

    def test_l_article_invente_existe_dans_le_corpus(self):
        # Un modèle de langue ne cite pas « l'article 9 000 » : il cite de
        # mémoire un article réel qui ne répond pas. C'est ce cas-là qu'il faut
        # attraper, et il est plus difficile.
        for question in ("congé", "préavis", "salaire minimum"):
            if self.factice.famille(question) != "inventee":
                continue
            citations = bbb.extraire_citations(
                self.factice.rediger(question, self.articles), _NUMEROS)
            self.assertTrue(citations)
            self.assertTrue(set(citations) <= _NUMEROS)

    def test_fidele_sans_article_retombe_sur_muette(self):
        # Fabriquer une citation à partir de rien serait exactement la faute
        # que ce banc traque.
        loyal = bbb.RedacteurFactice(self.numeros, ("fidele",))
        self.assertEqual(
            bbb.extraire_citations(loyal.rediger("question", ()), _NUMEROS), ())

    def test_famille_inconnue_refusee(self):
        with self.assertRaises(SystemExit):
            bbb.RedacteurFactice(self.numeros, ("optimiste",))


class GardeDuRepondeurTemoin(unittest.TestCase):
    """Les trois sorties que la chaîne doit refuser, et celle qu'elle doit rendre."""

    def setUp(self):
        self.moteur = _moteur_idf()
        # Un seuil de marge nul force la rédaction sur toutes les questions :
        # on teste ici la garde, pas l'abstention par la marge.
        self.moteur_bavard = _moteur_idf(0.0)

    def _temoin(self, redacteur, moteur=None):
        return bbb.RepondeurTemoin(moteur or self.moteur_bavard, redacteur,
                                   _NUMEROS)

    def test_rend_une_redaction_loyale(self):
        class Loyal:
            def rediger(self, question, articles):
                return f"D'après l'article {articles[0].numero} du Code."

        reponse = self._temoin(Loyal()).repondre("congé annuel payé")
        self.assertFalse(reponse.abstenu)
        self.assertEqual(len(reponse.citations), 1)
        self.assertTrue(set(reponse.citations) <= {a.numero for a in reponse.articles})
        self.assertTrue(reponse.avertissement.strip())

    def test_rejette_une_citation_hors_ensemble(self):
        class Menteur:
            def rediger(self, question, articles):
                intrus = next(iter(_NUMEROS - {a.numero for a in articles}))
                return f"L'article {intrus} du Code règle ce point."

        reponse = self._temoin(Menteur()).repondre("congé annuel payé")
        self.assertTrue(reponse.abstenu)
        self.assertIsNone(reponse.texte)
        self.assertEqual(reponse.citations, ())
        self.assertIn("récupér", reponse.raison)

    def test_rejette_la_reponse_entiere_et_pas_la_seule_citation(self):
        # Une réponse dont on retire un article cesse de dire ce que son texte
        # dit : la garde ne filtre pas, elle rejette.
        class Melange:
            def rediger(self, question, articles):
                intrus = next(iter(_NUMEROS - {a.numero for a in articles}))
                return f"Les articles {articles[0].numero} et {intrus} du Code."

        reponse = self._temoin(Melange()).repondre("congé annuel payé")
        self.assertTrue(reponse.abstenu)
        self.assertEqual(reponse.citations, ())

    def test_rejette_une_redaction_sans_citation(self):
        class Muet:
            def rediger(self, question, articles):
                return "Le Code traite de cette question, sans aucun doute."

        reponse = self._temoin(Muet()).repondre("congé annuel payé")
        self.assertTrue(reponse.abstenu)
        self.assertIn("cite aucun article", reponse.raison)

    def test_sous_le_seuil_le_temoin_se_tait_sans_rediger(self):
        appels = []

        class Compteur:
            def rediger(self, question, articles):
                appels.append(question)
                return f"L'article {articles[0].numero} du Code."

        # Un seuil de marge inatteignable : la récupération doute toujours, et
        # aucune rédaction ne doit être demandée — ni payée, le jour où elle
        # coûtera une requête à un fournisseur.
        temoin = bbb.RepondeurTemoin(_moteur_idf(1.1), Compteur(), _NUMEROS)
        reponse = temoin.repondre("congé annuel payé")
        self.assertTrue(reponse.abstenu)
        self.assertEqual(appels, [])
        # Les candidats restent, pour que le produit puisse les montrer sans
        # les présenter comme la réponse.
        self.assertTrue(reponse.articles)


class MesuresDuBanc(unittest.TestCase):

    def setUp(self):
        self.jeu = banc.charger_questions()
        self.modes = {
            "generation": "(test)", "familles": "(test)", "recuperation": "idf",
            "repondeur": "(test)", "observe": True, "production": False,
            "seuil_marge": 0.0, "k": 5,
        }

    def _executer(self, redacteur, seuil=0.0):
        observateur = bbb.RedacteurObserve(redacteur, _NUMEROS)
        temoin = bbb.RepondeurTemoin(_moteur_idf(seuil), observateur, _NUMEROS)
        return bbb.executer(temoin.repondre, self.jeu, _NUMEROS, observateur,
                            dict(self.modes, seuil_marge=seuil))

    def test_le_temoin_loyal_ne_fait_rejeter_personne(self):
        loyal = bbb.RedacteurFactice(sorted(_NUMEROS, key=bbb._ordre_numero),
                                     ("fidele",))
        res = self._executer(loyal)
        self.assertEqual(res.taux_rejet(), 0.0)
        self.assertEqual(res.hallucinations(), [])
        self.assertEqual(res.fuites(), [])
        self.assertEqual(res.rejets_a_tort(), [])

    def test_le_temoin_menteur_fait_tout_rejeter(self):
        menteur = bbb.RedacteurFactice(sorted(_NUMEROS, key=bbb._ordre_numero),
                                       ("inventee",))
        res = self._executer(menteur)
        self.assertEqual(res.taux_rejet(), 1.0)
        self.assertEqual(res.taux_hallucination(), 1.0)
        self.assertEqual(res.fuites(), [])
        self.assertEqual(res.derobade(), 1.0)
        self.assertEqual(res.abstention_correcte(), 1.0)

    def test_le_banc_predit_ses_propres_rejets(self):
        # Le contrôle du banc sur lui-même : le nombre d'hallucinations mesuré
        # doit être exactement celui que le factice a fabriqué. Un écart dirait
        # que la garde, l'extraction ou le comptage ne font pas ce qu'ils
        # disent.
        mixte = bbb.RedacteurFactice(sorted(_NUMEROS, key=bbb._ordre_numero))
        res = self._executer(mixte)
        self.assertIsNotNone(res.hallucinations_attendues())
        self.assertEqual(res.hallucinations_attendues(), len(res.hallucinations()))
        self.assertEqual(len(res.rejets_hallucination()), len(res.hallucinations()))

    def test_une_fuite_est_vue(self):
        """Le test le plus important : le banc sait-il voir l'échec qu'il traque ?

        Un répondeur SANS garde, branché sur le modèle menteur, doit produire
        autant de fuites que de rédactions. Si ce test passait à zéro fuite, le
        banc imprimerait « 0 fuite » sur une chaîne entièrement cassée.
        """
        class RepondeurSansGarde:
            def __init__(self, moteur, redacteur):
                self._moteur, self._redacteur = moteur, redacteur

            def repondre(self, question):
                resultat = self._moteur.chercher(question, k=5)
                texte = self._redacteur.rediger(question, resultat.articles)
                citations = bbb.extraire_citations(texte, _NUMEROS)
                return bbb.Reponse(
                    texte=texte, citations=citations, articles=resultat.articles,
                    abstenu=False, raison="", avertissement=resultat.avertissement,
                )

        menteur = bbb.RedacteurFactice(sorted(_NUMEROS, key=bbb._ordre_numero),
                                       ("inventee",))
        observateur = bbb.RedacteurObserve(menteur, _NUMEROS)
        sans_garde = RepondeurSansGarde(_moteur_idf(0.0), observateur)
        res = bbb.executer(sans_garde.repondre, self.jeu, _NUMEROS, observateur,
                           self.modes)
        self.assertEqual(len(res.fuites()), len(res.lignes))
        self.assertEqual(res.abstention_correcte(), 0.0)

    def test_un_rejet_a_tort_est_vu(self):
        """Une garde trop zélée doit se voir aussi : du rappel perdu pour rien."""
        class RepondeurMuet:
            def __init__(self, moteur, redacteur):
                self._moteur, self._redacteur = moteur, redacteur

            def repondre(self, question):
                resultat = self._moteur.chercher(question, k=5)
                self._redacteur.rediger(question, resultat.articles)
                return bbb.Reponse(
                    texte=None, citations=(), articles=resultat.articles,
                    abstenu=True, raison="par excès de prudence",
                    avertissement=resultat.avertissement,
                )

        loyal = bbb.RedacteurFactice(sorted(_NUMEROS, key=bbb._ordre_numero),
                                     ("fidele",))
        observateur = bbb.RedacteurObserve(loyal, _NUMEROS)
        zele = RepondeurMuet(_moteur_idf(0.0), observateur)
        res = bbb.executer(zele.repondre, self.jeu, _NUMEROS, observateur, self.modes)
        self.assertEqual(len(res.rejets_a_tort()), len(res.lignes))
        self.assertEqual(res.derobade(), 1.0)

    def test_les_toleres_ne_comptent_ni_en_reussite_ni_en_faute(self):
        ligne = bbb.Ligne(
            identifiant="Q01", question="q", etiquettes=[],
            attendus={"205"}, toleres={"207"}, recuperes={"205", "207"},
            abstenu=False, citations=("205", "207"), raison="",
        )
        self.assertEqual(ligne.citations_justes, {"205"})
        self.assertEqual(ligne.citations_fautives, set())
        self.assertEqual(ligne.precision(), 1.0)
        self.assertEqual(ligne.couverture(), 1.0)

    def test_le_plafond_separe_la_recuperation_de_la_redaction(self):
        hors_portee = bbb.Ligne(
            identifiant="Q02", question="q", etiquettes=[],
            attendus={"205"}, toleres=set(), recuperes={"231", "238"},
            abstenu=False, citations=("231",), raison="",
        )
        self.assertFalse(hors_portee.plafond)
        self.assertEqual(hors_portee.precision(), 0.0)


class RedacteurLoyalDEssai:
    """Un modèle loyal, pour les trois formes de branchement testées plus bas."""

    def rediger(self, question, articles):
        if not articles:
            return "Le Code ne dit rien ici."
        return f"D'après l'article {articles[0].numero} du Code."


class RepondeurClasseDEssai:
    """Forme 1 : une CLASSE, que le banc doit construire avant de l'appeler."""

    def __init__(self, redacteur, moteur, k=5):
        self._temoin = bbb.RepondeurTemoin(moteur, redacteur, _NUMEROS, k)

    def repondre(self, question):
        return self._temoin.repondre(question)


def fabrique_d_essai(redacteur, k=5):
    """Forme 2 : une FABRIQUE, qui prend le modèle du banc et son propre moteur."""
    return bbb.RepondeurTemoin(_moteur_idf(0.0), redacteur, _NUMEROS, k)


def repondre_nu_d_essai(question):
    """Forme 3 : la fonction du contrat, qui ne prend aucune pièce du banc."""
    temoin = bbb.RepondeurTemoin(_moteur_idf(0.0), RedacteurLoyalDEssai(), _NUMEROS)
    return temoin.repondre(question)


class BranchementDUnRepondeurExterieur(unittest.TestCase):
    """Les trois formes acceptées, et le piège de la classe non construite.

    Une classe porte un `repondre` NON LIÉ : la prendre pour une instance donne
    un appelable qui passe tous les contrôles du banc et n'échoue qu'au premier
    appel. Ce test existe parce que le banc est tombé exactement dans ce piège.
    """

    def _brancher(self, nom_attribut):
        return bbb.construire_repondeur(
            f"{__name__}:{nom_attribut}", _moteur_idf(0.0),
            bbb.RedacteurObserve(RedacteurLoyalDEssai(), _NUMEROS), _NUMEROS, 5)

    def test_une_classe_est_construite(self):
        repondre, _, observe, moteur_remis = self._brancher("RepondeurClasseDEssai")
        reponse = repondre("congé annuel payé")
        self.assertFalse(reponse.abstenu)
        self.assertTrue(observe)
        self.assertTrue(moteur_remis)

    def test_une_fabrique_recoit_le_modele_du_banc(self):
        repondre, _, observe, moteur_remis = self._brancher("fabrique_d_essai")
        self.assertFalse(repondre("congé annuel payé").abstenu)
        self.assertTrue(observe)
        self.assertFalse(moteur_remis)

    def test_une_fonction_nue_est_prise_telle_quelle(self):
        # Elle ne prend pas le modèle du banc : la mesure est donc en aveugle,
        # et le banc doit le dire plutôt que d'imprimer des zéros.
        repondre, _, observe, moteur_remis = self._brancher("repondre_nu_d_essai")
        self.assertFalse(repondre("congé annuel payé").abstenu)
        self.assertFalse(observe)
        self.assertFalse(moteur_remis)

    def test_la_mesure_en_aveugle_est_annoncee(self):
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = bbb.principal(["--recuperation", "idf", "--repondeur",
                                  f"{__name__}:repondre_nu_d_essai"])
        self.assertEqual(code, 0)
        self.assertIn("MESURE EN AVEUGLE", tampon.getvalue())
        self.assertIn("inconnus du banc", tampon.getvalue())

    def test_un_attribut_sans_repondre_est_refuse(self):
        with self.assertRaises(SystemExit):
            bbb.construire_repondeur(f"{__name__}:_NUMEROS", _moteur_idf(0.0),
                                     None, _NUMEROS, 5)


class EntreeEnLigneDeCommande(unittest.TestCase):
    """Le banc doit tourner et sortir en 0 sans clé, sans paquet, sans index."""

    def _lancer(self, *arguments) -> tuple[int, str]:
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = bbb.principal(["--recuperation", "idf", *arguments])
        return code, tampon.getvalue()

    def test_le_mode_factice_est_annonce(self):
        code, sortie_texte = self._lancer()
        self.assertEqual(code, 0)
        self.assertIn("AUCUNE CLÉ", sortie_texte)
        self.assertIn("ne mesurent PAS un modèle de production", sortie_texte)
        self.assertIn("FACTICE (plancher idf)", sortie_texte)
        self.assertIn("CONCORDENT", sortie_texte)

    def test_les_trois_grandeurs_sont_imprimees(self):
        _, sortie_texte = self._lancer()
        self.assertIn("1. EXACTITUDE DES CITATIONS", sortie_texte)
        self.assertIn("2. REJET PAR LA GARDE", sortie_texte)
        self.assertIn("3. ABSTENTION", sortie_texte)

    def test_le_detail_tient(self):
        code, _ = self._lancer("--detail")
        self.assertEqual(code, 0)

    def test_les_trois_redacteurs_factices_tournent(self):
        for redacteur in ("mixte", "fidele", "menteur"):
            with self.subTest(redacteur=redacteur):
                code, _ = self._lancer("--redacteur", redacteur)
                self.assertEqual(code, 0)

    def test_un_seuil_non_tenu_sort_en_1(self):
        # Le modèle menteur ne rend aucune réponse : l'exactitude est nulle.
        code, _ = self._lancer("--redacteur", "menteur", "--seuil-exactitude", "0.5")
        self.assertEqual(code, 1)

    def test_le_json_porte_le_drapeau_de_production(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "rapport.json"
            code, _ = self._lancer("--json", str(chemin))
            self.assertEqual(code, 0)
            rapport = json.loads(chemin.read_text(encoding="utf-8"))
            self.assertIs(rapport["production"], False)
            self.assertEqual(rapport["questions"], 64)
            self.assertEqual(rapport["invariants"]["fuites"], [])

    def test_une_recuperation_inconnue_est_refusee(self):
        with self.assertRaises(SystemExit):
            bbb.principal(["--recuperation", "magique"])


try:
    import moteur.repondre as _module_produit  # noqa: F401
    from moteur import garde as module_garde  # noqa: F401
    _PRODUIT_ABSENT = ""
except Exception as _manque:  # pragma: no cover
    _module_produit = None
    module_garde = None
    _PRODUIT_ABSENT = (
        f"l'étage de réponse du produit n'est pas importable ({_manque}) ; "
        f"ce contrôle croisé est sauté."
    )


@unittest.skipIf(_PRODUIT_ABSENT, _PRODUIT_ABSENT or "disponible")
class ControleCroiseAvecLeProduit(unittest.TestCase):
    """Le témoin du banc et le répondeur du produit doivent mesurer pareil.

    Deux gardes écrites séparément, deux lecteurs de citations écrits
    séparément. S'ils rendent les mêmes rejets sur les mêmes rédactions, aucun
    des deux n'est cru sur parole : ils se contrôlent. S'ils divergeaient, le
    banc le dirait par ses deux compteurs — une citation que seul le banc lit
    apparaît en fuite, une citation que seul le produit lit apparaît en rejet à
    tort.

    Ce contrôle est sauté si l'étage de réponse n'est pas là : le banc doit
    rester mesurable seul.
    """

    def _mesurer(self, repondeur, redacteur):
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = bbb.principal(["--recuperation", "idf", "--redacteur", redacteur,
                                  "--repondeur", repondeur])
        self.assertEqual(code, 0)
        return tampon.getvalue()

    def test_les_deux_gardes_rejettent_la_meme_chose(self):
        for redacteur in ("mixte", "fidele", "menteur"):
            with self.subTest(redacteur=redacteur):
                temoin = self._mesurer("temoin", redacteur)
                produit = self._mesurer("moteur.repondre:Mizan", redacteur)
                # La ligne du répondeur diffère par construction ; tout le
                # reste du rapport doit se superposer.
                depart = temoin.index("1. EXACTITUDE")
                self.assertEqual(temoin[depart:], produit[produit.index("1. EXACTITUDE"):])

    def test_les_deux_lecteurs_couvrent_le_meme_perimetre(self):
        """L'indépendance porte sur l'écriture, jamais sur le périmètre.

        Deux lecteurs qui ne déclarent pas lire la même chose ne se contrôlent
        pas l'un l'autre : ils se contredisent, et c'est le banc qui perd. Le
        désaccord allait dans les deux sens et les deux étaient graves — une
        forme que seul le produit lit faisait compter zéro une hallucination
        réellement servie, et une forme que seul le banc lit faisait déclarer
        une fuite sur un comportement correct, avec sortie en code 1.

        Les six formes ci-dessous sont celles qui divergeaient. Aucune n'est
        une copie du code de la garde : c'est son PÉRIMÈTRE DÉCLARÉ qui est
        verrouillé, pas son implémentation.
        """
        cas = [
            "D'après l'art 45 du Code.",
            "D'après l'article n° 45 du Code.",
            "l'article 32 a 2 alinéas",
            "l'article 5 - 10 jours de congé",
            "D'après l'article 231, soit 1,5 jour par mois.",
            "Selon l'article 238, 18 jours ouvrables sont dus.",
        ]
        for texte in cas:
            with self.subTest(texte=texte):
                du_banc = bbb.extraire_citations(texte, _NUMEROS)
                du_produit = tuple(
                    n for n in module_garde.extraire_citations(texte)
                    if n in _NUMEROS
                )
                self.assertEqual(du_banc, du_produit)

    def test_une_fuite_declaree_se_voit_sans_lire_aucun_texte(self):
        """L'invariant du projet, calculé sur les champs de la réponse.

        C'est le contrôle qui ne dépend d'aucune expression régulière : une
        réponse rendue qui déclare citer un article qu'elle ne déclare pas
        avoir récupéré EST une fuite, quelle que soit la forme du texte. Tant
        qu'il manquait, le banc restait vert à travers une régression de la
        garde dès que le texte employait une écriture que son lecteur ignore.
        """
        ligne = bbb.Ligne(
            identifiant="Q01", question="q", etiquettes=[], attendus=set(),
            toleres=set(), recuperes={"231"}, abstenu=False,
            citations=("231", "350"), raison="", rediction=None,
        )
        self.assertTrue(ligne.fuite)
        self.assertEqual(ligne.hors_recuperes, {"350"})

    def test_un_avertissement_absent_est_un_invariant_et_non_un_defaut_de_forme(self):
        """Code 1 (« l'invariant est brisé »), pas code 2 (« je n'ai pas mesuré »).

        `controler_reponse` ne doit plus le signaler : toute anomalie rendue
        par cette fonction sort en code 2 avant le rapport, ce qui rendait
        inatteignable le code 1 annoncé en tête du fichier et faisait afficher
        zéro à la ligne d'invariant, par construction.
        """
        class SansAvertissement:
            texte, citations, articles = "L'article 231 le prévoit.", ("231",), ()
            abstenu, raison, avertissement = False, "", "   "

        self.assertEqual(
            bbb.controler_reponse("Q01", SansAvertissement(), _NUMEROS), []
        )
        ligne = bbb.Ligne(
            identifiant="Q01", question="q", etiquettes=[], attendus=set(),
            toleres=set(), recuperes={"231"}, abstenu=False, citations=("231",),
            raison="", rediction=None, avertissement_absent=True,
        )
        self.assertEqual(
            bbb.Resultats([ligne], {}).avertissements_absents(), ["Q01"]
        )

    def test_le_repondeur_par_defaut_est_le_produit_et_non_le_temoin(self):
        """Un banc qui mesure sa propre reconstitution ne mesure rien de livré."""
        self.assertEqual(bbb.PRODUIT, "moteur.repondre:Mizan")
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            self.assertEqual(bbb.principal(["--recuperation", "idf"]), 0)
        self.assertIn(f"RÉPONDEUR     {bbb.PRODUIT}", tampon.getvalue())

    def test_le_produit_prend_bien_les_pieces_du_banc(self):
        _, _, observe, moteur_remis = bbb.construire_repondeur(
            "moteur.repondre:Mizan", _moteur_idf(0.0),
            bbb.RedacteurObserve(RedacteurLoyalDEssai(), _NUMEROS), _NUMEROS, 5)
        self.assertTrue(observe, "sans le modèle du banc, la mesure est aveugle")
        self.assertTrue(moteur_remis, "le produit doit chercher avec le moteur du banc")


if __name__ == "__main__":
    unittest.main(verbosity=2)
