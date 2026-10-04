"""Bras dense : encodeur de phrases multilingue, par passage.

Choix du modele, et ce qu'il coute : sentence-transformers/
paraphrase-multilingual-MiniLM-L12-v2 en ONNX quantifie, servi par fastembed.
C'est le plus petit encodeur VRAIMENT multilingue du catalogue fastembed. Les
modeles anglais (bge-small-en, 67 Mo) sont deux a quatre fois plus legers mais
n'ont rien a dire d'un texte francais ; le seul e5 multilingue du catalogue
pese 2,24 Go. Ce modele est un modele de PARAPHRASE, pas de recuperation
asymetrique : il a ete entraine a rapprocher deux phrases qui se disent
pareil, pas une question de son article de loi. C'est sa faiblesse connue, et
elle se lit dans les echecs mesures.
"""

import chemin_paquets  # noqa: F401  (doit preceder l'import de fastembed)

import numpy as np

from corpus import Corpus, passages, tete

NOM_MODELE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class IndexDense:
    # Lots volontairement petits : le remplissage (padding) de fastembed
    # alloue un masque de la taille du plus long passage du lot, et un lot de
    # 256 passages a fait echouer une allocation de 96 Mio sur cette machine.
    TAILLE_LOT = 32

    def __init__(self, corpus: Corpus, avec_titres: bool = True, taille_max: int = 600) -> None:
        from fastembed import TextEmbedding

        self.corpus = corpus
        kwargs = {}
        if chemin_paquets.MODELE_LOCAL:
            kwargs["specific_model_path"] = chemin_paquets.MODELE_LOCAL
        self.encodeur = TextEmbedding(NOM_MODELE, **kwargs)

        self.passages = passages(corpus, taille_max=taille_max)
        if not avec_titres:
            # Retire la tete "Livre > Titre > Chapitre > article N." pour
            # mesurer ce que le contexte hierarchique apporte au bras dense.
            #
            # On retire la tete EXACTE, reconstruite par corpus.tete(), et non
            # tout ce qui precede le premier ". ". Cette decoupe naive laissait
            # la fin du chemin de titres dans le texte de 28 passages sur 781
            # (19 articles : 217 a 230, 256, 522 a 525), parce que leur
            # intitule de chapitre finit lui-meme par un point — "Du repos des
            # jours de fetes payes et jours feries.". Pour ces articles,
            # l'ablation ne retirait donc PAS ce qu'elle annonce, et son
            # chiffre melangeait les deux conditions qu'elle devait separer.
            sans_tete = []
            for i, t in self.passages:
                debut = tete(corpus.articles[i])
                if t.startswith(debut):
                    sans_tete.append((i, t[len(debut):]))
                else:
                    # Seul cas restant : l'article 256, abroge, dont le passage
                    # ne contient QUE sa tete. Prive de titres il ne reste rien
                    # a encoder ; son numero garde au vecteur une existence.
                    sans_tete.append((i, "article " + corpus.articles[i].numero))
            self.passages = sans_tete
        self.proprietaire = np.array([i for i, _ in self.passages], dtype=np.int32)
        vecteurs = np.asarray(
            list(
                self.encodeur.embed(
                    [t for _, t in self.passages], batch_size=self.TAILLE_LOT
                )
            ),
            dtype=np.float32,
        )
        self.vecteurs = self._normaliser(vecteurs)
        self.dimension = int(self.vecteurs.shape[1])

    @staticmethod
    def _normaliser(v: np.ndarray) -> np.ndarray:
        # On normalise soi-meme : le produit scalaire ne vaut le cosinus que si
        # les deux cotes sont unitaires, et cela ne doit pas dependre de ce que
        # fastembed decide de faire par defaut pour tel ou tel modele.
        normes = np.linalg.norm(v, axis=1, keepdims=True)
        normes[normes == 0] = 1.0
        return v / normes

    def chercher(self, question: str, k: int = 10) -> list[tuple[int, float]]:
        q = self._normaliser(
            np.asarray(list(self.encodeur.query_embed(question)), dtype=np.float32)
        )[0]
        cosinus = self.vecteurs @ q
        # Un article vaut le meilleur de ses passages : une question ne porte
        # jamais sur un article entier, elle porte sur un de ses alineas.
        meilleur: dict[int, float] = {}
        for prop, s in zip(self.proprietaire, cosinus):
            p = int(prop)
            if s > meilleur.get(p, -2.0):
                meilleur[p] = float(s)
        classement = sorted(
            meilleur.items(), key=lambda kv: (-kv[1], self.corpus.articles[kv[0]].rang)
        )
        return classement[:k]
