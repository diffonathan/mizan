"""Fusion des deux classements par rang reciproque (RRF), et refus de repondre.

Pourquoi RRF et pas une somme ponderee des scores : un score BM25 vaut entre
0 et 40 selon la question, un cosinus entre -1 et 1 selon le modele. Les
mettre dans la meme addition demande de les recalibrer, donc de regler deux
constantes sur un jeu de questions — exactement ce qu'on ne peut pas faire
honnetement avec vingt-cinq questions ecrites par l'auteur du banc. RRF
n'utilise que les rangs : il n'y a rien a regler sauf k, et on mesure ce que
k change au lieu de l'affirmer.
"""

from dataclasses import dataclass

K_RRF = 60  # valeur de l'article d'origine (Cormack 2009), non reglee ici
PROFONDEUR = 50  # nombre de candidats pris a chaque bras avant fusion


@dataclass
class Resultat:
    indice: int
    score_rrf: float
    rang_lexical: int | None
    rang_dense: int | None


@dataclass
class Verdict:
    """Ce que le systeme sait dire de sa propre incertitude.

    Aucun de ces trois signaux ne mesure une probabilite d'avoir raison : ce
    sont des indices, et leur taux de fausse alarme est mesure dans banc.py.
    """

    couverture: float            # part des mots de la question presents dans le corpus
    mots_inconnus: list[str]
    accord: int                  # articles communs aux cinq premiers des deux bras
    marge: float                 # ecart relatif entre le 1er et le 2e score fusionne
    refus: bool
    raison: str


def fusionner(
    lexical: list[tuple[int, float]],
    dense: list[tuple[int, float]],
    k_rrf: int = K_RRF,
) -> list[Resultat]:
    rang_lex = {i: r for r, (i, _) in enumerate(lexical, start=1)}
    rang_den = {i: r for r, (i, _) in enumerate(dense, start=1)}
    scores: dict[int, float] = {}
    for rangs in (rang_lex, rang_den):
        for i, r in rangs.items():
            scores[i] = scores.get(i, 0.0) + 1.0 / (k_rrf + r)
    ordre = sorted(scores.items(), key=lambda kv: (-kv[1], rang_lex.get(kv[0], 10**6)))
    return [
        Resultat(i, s, rang_lex.get(i), rang_den.get(i)) for i, s in ordre
    ]


# Seuils fixes AVANT la premiere mesure, et non retouches apres : un seuil
# choisi en regardant les resultats ne mesure plus rien.
SEUIL_COUVERTURE = 0.6
SEUIL_MARGE = 0.02


def juger(
    resultats: list[Resultat],
    couverture: float,
    mots_inconnus: list[str],
) -> Verdict:
    lex5 = {r.indice for r in resultats if r.rang_lexical and r.rang_lexical <= 5}
    den5 = {r.indice for r in resultats if r.rang_dense and r.rang_dense <= 5}
    accord = len(lex5 & den5)

    if len(resultats) >= 2 and resultats[0].score_rrf > 0:
        marge = (resultats[0].score_rrf - resultats[1].score_rrf) / resultats[0].score_rrf
    else:
        marge = 1.0

    raisons = []
    if couverture < SEUIL_COUVERTURE:
        raisons.append(
            "mots absents du Code du travail : " + ", ".join(mots_inconnus)
        )
    if accord == 0:
        raisons.append(
            "les deux methodes de recherche ne designent aucun article commun"
        )
    return Verdict(
        couverture=couverture,
        mots_inconnus=mots_inconnus,
        accord=accord,
        marge=marge,
        refus=bool(raisons),
        raison=" ; ".join(raisons),
    )


def fusionner_par_scores(
    lexical: list[tuple[int, float]],
    dense: list[tuple[int, float]],
) -> list[Resultat]:
    """Variante de comparaison : somme des scores remis a l'echelle [0, 1].

    Elle ne demande pas plus de reglage que RRF (la mise a l'echelle est faite
    par requete, sur le minimum et le maximum observes), mais elle garde
    l'information que RRF jette : l'ECART entre le premier et le deuxieme.
    Elle est mesuree pour savoir si cette information valait d'etre gardee.
    """
    rang_lex = {i: r for r, (i, _) in enumerate(lexical, start=1)}
    rang_den = {i: r for r, (i, _) in enumerate(dense, start=1)}

    def echelle(liste):
        if not liste:
            return {}
        valeurs = [s for _, s in liste]
        bas, haut = min(valeurs), max(valeurs)
        etendue = haut - bas
        if etendue <= 0:
            return {i: 1.0 for i, _ in liste}
        return {i: (s - bas) / etendue for i, s in liste}

    e_lex, e_den = echelle(lexical), echelle(dense)
    scores: dict[int, float] = {}
    for table in (e_lex, e_den):
        for i, v in table.items():
            scores[i] = scores.get(i, 0.0) + v
    ordre = sorted(scores.items(), key=lambda kv: (-kv[1], rang_lex.get(kv[0], 10**6)))
    return [Resultat(i, s, rang_lex.get(i), rang_den.get(i)) for i, s in ordre]


def fusionner_n(
    classements: list[list[tuple[int, float]]],
    k_rrf: int = K_RRF,
) -> list[Resultat]:
    """RRF sur un nombre quelconque de bras.

    Sert a repondre a la question centrale de cette piste : le mecanisme
    gagne-t-il quelque chose a chaque bras ajoute, ou seulement au premier ?
    Les champs rang_lexical et rang_dense gardent les deux premiers bras de la
    liste, les seuls que l'interface affiche.
    """
    rangs = [
        {i: r for r, (i, _) in enumerate(c, start=1)} for c in classements
    ]
    scores: dict[int, float] = {}
    for table in rangs:
        for i, r in table.items():
            scores[i] = scores.get(i, 0.0) + 1.0 / (k_rrf + r)
    premier = rangs[0] if rangs else {}
    second = rangs[1] if len(rangs) > 1 else {}
    ordre = sorted(scores.items(), key=lambda kv: (-kv[1], premier.get(kv[0], 10**6)))
    return [Resultat(i, s, premier.get(i), second.get(i)) for i, s in ordre]
