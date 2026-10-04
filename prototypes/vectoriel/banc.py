"""Banc de questions pour juger la récupération, construit À LA MAIN en lisant le corpus.

Chaque question est posée dans la langue d'un usager, pas dans celle du législateur :
c'est tout l'enjeu du vectoriel et ce serait tricher que de recopier les mots de
l'article dans la question.

`attendu` est la liste des articles qu'un juriste citerait pour répondre. Elle est
tenue au plus COURT possible : accepter trois articles « voisins » gonflerait le
rappel sans que la réponse rendue soit meilleure. Quand deux articles se partagent
réellement la réponse (le droit et son montant), les deux sont listés et le
commentaire dit pourquoi.

`piege` nomme l'article dont la question est volontairement proche, quand elle a été
écrite pour mettre l'approche en difficulté. Les paires (6, 7), (8, 9), (19, 20) et
(24) existent pour cette raison : sans elles le banc ne mesurerait que la facilité.
"""

QUESTIONS = [
    # --- congés -------------------------------------------------------------
    dict(id=1, q="combien de jours de congés payés après deux ans dans la même boîte ?",
         attendu=["231"],
         note="art. 231 : 1,5 jour par mois de service après 6 mois. L'art. 232 ne joue qu'à partir de 5 ans."),
    dict(id=2, q="mon patron choisit tout seul la date de mes vacances ?",
         attendu=["245"],
         note="art. 245 : dates fixées par l'employeur après consultation des délégués et des intéressés."),
    dict(id=3, q="est-ce que je peux garder mes congés pour les prendre l'année suivante ?",
         attendu=["240"],
         note="art. 240 : fractionnement ou cumul sur deux années consécutives, après accord."),

    # --- naissance / maternité : paire piège -------------------------------
    dict(id=4, q="ma femme accouche la semaine prochaine, j'ai droit à des jours ?",
         attendu=["269"], piege="152",
         note="art. 269 : 3 jours pour le salarié à chaque naissance. Le piège est le congé de maternité (152), qui ne concerne que la salariée."),
    dict(id=5, q="je suis enceinte, j'ai combien de semaines d'arrêt pour l'accouchement ?",
         attendu=["152"], piege="269",
         note="art. 152 : 14 semaines de congé de maternité."),
    dict(id=6, q="est-ce qu'on peut me licencier pendant que je suis enceinte ?",
         attendu=["159"],
         note="art. 159 : interdiction de rompre pendant la grossesse et les 14 semaines suivant l'accouchement."),
    dict(id=7, q="je veux allaiter mon bébé, j'ai droit à des pauses dans la journée ?",
         attendu=["161"],
         note="art. 161 : une demi-heure matin et après-midi pendant douze mois, payée."),

    # --- absences familiales ------------------------------------------------
    dict(id=8, q="je me marie le mois prochain, combien de jours je peux prendre ?",
         attendu=["274"],
         note="art. 274 : 4 jours pour le mariage du salarié."),
    dict(id=9, q="mon père est décédé, est-ce que j'ai le droit de m'absenter ?",
         attendu=["274"],
         note="art. 274 : 3 jours pour le décès d'un ascendant."),

    # --- maladie ------------------------------------------------------------
    dict(id=10, q="je suis malade, dans quel délai je dois prévenir le travail ?",
         attendu=["271"],
         note="art. 271 : aviser dans les 48 heures, certificat au-delà de 4 jours."),
    dict(id=11, q="je suis en arrêt depuis sept mois, mon employeur peut me remplacer ?",
         attendu=["272"],
         note="art. 272 : au-delà de 180 jours sur 365, l'employeur peut le considérer comme démissionnaire."),

    # --- licenciement -------------------------------------------------------
    dict(id=12, q="on m'a viré sans rien me dire, est-ce que c'est permis ?",
         attendu=["35"],
         note="art. 35 : licenciement sans motif valable interdit. C'est le cas d'école du vectoriel : « viré » n'apparaît nulle part dans le code."),
    dict(id=13, q="avant de me renvoyer, est-ce qu'il doit m'écouter ?",
         attendu=["62"],
         note="art. 62 : audition du salarié dans les 8 jours, en présence d'un délégué, procès-verbal."),
    dict(id=14, q="j'ai été licencié après huit ans, on me doit combien ?",
         attendu=["53"],
         note="art. 53 : barème en heures de salaire par année d'ancienneté (144 h pour 6 à 10 ans)."),
    dict(id=15, q="est-ce que j'ai droit à quelque chose si on me renvoie après quatre mois ?",
         attendu=["52"],
         note="art. 52 : l'indemnité suppose six mois de travail dans la même entreprise."),
    dict(id=16, q="combien de temps j'ai pour attaquer mon licenciement devant le tribunal ?",
         attendu=["65"], piege="395",
         note="art. 65 : 90 jours sous peine de déchéance. Le piège est l'art. 395 (prescription de deux ans), qui parle du même sujet dans des mots très proches."),
    dict(id=17, q="mon ancien employeur ne m'a jamais payé mes derniers mois, c'est trop tard pour réclamer ?",
         attendu=["395"], piege="65",
         note="art. 395 : les droits découlant du contrat se prescrivent par deux années."),
    dict(id=18, q="le vol dans l'entreprise, ça justifie un renvoi immédiat ?",
         attendu=["39"],
         note="art. 39 : liste des fautes graves du salarié, dont le vol."),
    dict(id=19, q="mon chef m'a insulté et m'a frappé, qu'est-ce que la loi en dit ?",
         attendu=["40"],
         note="art. 40 : fautes graves de l'employeur, départ assimilé à un licenciement abusif."),
    dict(id=20, q="j'ai donné ma démission, il y a une forme à respecter ?",
         attendu=["34"],
         note="art. 34 : démission avec signature légalisée."),
    dict(id=21, q="combien de temps de préavis mon employeur doit-il me laisser ?",
         attendu=["43"],
         note="art. 43 : principe du préavis et plancher de huit jours. Les durées elles-mêmes sont renvoyées au réglementaire : la bonne réponse est l'article, pas un nombre."),

    # --- temps de travail ---------------------------------------------------
    dict(id=22, q="combien d'heures par semaine au maximum peut-on me faire travailler ?",
         attendu=["184"],
         note="art. 184 : 2288 heures par an ou 44 heures par semaine, 10 heures par jour au plus."),
    dict(id=23, q="mes heures en plus le soir, elles sont majorées de combien ?",
         attendu=["201"],
         note="art. 201 : 25 % de 6 h à 21 h, 50 % de 21 h à 6 h (non agricole)."),
    dict(id=24, q="j'ai droit à un jour de congé par semaine ?",
         attendu=["205"],
         note="art. 205 : repos hebdomadaire de 24 heures au moins. Volontairement formulé avec « congé », le mot du chapitre voisin."),

    # --- âges : paire piège -------------------------------------------------
    dict(id=25, q="à partir de quel âge on peut travailler au Maroc ?",
         attendu=["143"], piege="526",
         note="art. 143 : quinze ans révolus."),
    dict(id=26, q="à quel âge est-ce que je serai mis à la retraite ?",
         attendu=["526"], piege="143",
         note="art. 526 : soixante ans, cinquante-cinq pour le fond des mines."),

    # --- salaire ------------------------------------------------------------
    dict(id=27, q="une femme peut-elle être payée moins qu'un homme au même poste ?",
         attendu=["346"],
         note="art. 346 : interdiction de toute discrimination de salaire entre les sexes à travail de valeur égale."),
    dict(id=28, q="mon patron me retient de l'argent chaque mois pour un prêt qu'il m'a fait, il peut ?",
         attendu=["386"],
         note="art. 386 : retenues limitées au dixième du salaire échu."),
    dict(id=29, q="est-ce qu'on peut me payer en bons d'achat utilisables au magasin de l'usine ?",
         attendu=["362"], piege="392",
         note="art. 362 : paiement en monnaie marocaine. Les économats sont au chapitre V (392 et suivants), qui est le piège."),

    # --- seuils d'effectif : famille de pièges ------------------------------
    dict(id=30, q="on est douze salariés, faut-il élire des représentants du personnel ?",
         attendu=["430"], piege="336",
         note="art. 430 : délégués obligatoires à partir de dix salariés permanents. Pièges : l'art. 138 (règlement intérieur, dix salariés aussi) et l'art. 336 (comité de sécurité, cinquante)."),
    dict(id=31, q="à partir de combien de salariés faut-il un comité de sécurité ?",
         attendu=["336"], piege="430",
         note="art. 336 : cinquante salariés."),

    # --- divers -------------------------------------------------------------
    dict(id=32, q="je suis sénégalais, ai-je besoin d'un papier pour être embauché ici ?",
         attendu=["516"],
         note="art. 516 : autorisation de l'autorité gouvernementale, visa sur le contrat."),
    dict(id=33, q="on m'a mis à pied huit jours, c'est une sanction prévue ?",
         attendu=["37"],
         note="art. 37 : échelle des sanctions pour faute non grave, mise à pied de huit jours au plus."),
    dict(id=34, q="combien de temps peut durer ma période d'essai comme cadre ?",
         attendu=["14"],
         note="art. 14 : trois mois pour les cadres, renouvelable une fois."),
]

# Questions dont la réponse N'EST PAS dans le corpus, ou n'y est qu'en creux.
# Elles ne comptent pas dans le rappel : elles servent à voir si l'approche
# sait se taire. Une approche qui rend un article confiant ici est dangereuse.
QUESTIONS_SANS_REPONSE = [
    dict(id=101, q="combien de jours de télétravail par semaine ai-je le droit de demander ?",
         note="Rien sur le télétravail dans un texte consolidé en 2011. Aucune réponse n'est correcte."),
    dict(id=102, q="quel est le montant du SMIG en dirhams par heure ?",
         note="Le code (art. 356) renvoie le montant au réglementaire : le chiffre n'est PAS dans le corpus. Rendre l'art. 356 est honnête à condition de dire que le montant manque."),
    dict(id=103, q="est-ce que je peux cumuler mon emploi avec une activité d'auto-entrepreneur ?",
         note="Le statut d'auto-entrepreneur marocain date de 2015, postérieur à la consolidation."),
]
