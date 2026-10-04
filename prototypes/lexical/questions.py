"""
Banc de questions. Chaque réponse attendue a été établie EN LISANT l'article
dans le corpus, pas en interrogeant le prototype.

Règle de composition, et c'est la seule qui protège la mesure : le banc est
écrit AVANT d'avoir vu les scores, et il contient délibérément des questions
dont on attend qu'elles échouent — celles du registre « ordinaire », posées
sans aucun terme du texte de loi. Un banc où toutes les questions emploient le
vocabulaire du Code mesurerait la capacité de BM25 à retrouver des mots qu'on
lui a soufflés, ce qui n'est pas la question posée au projet.

`registre` :
  technique — la question emploie au moins un terme du Code (« préavis »,
              « indemnité de licenciement », « période d'essai »).
  ordinaire — la question est formulée comme le ferait quelqu'un qui n'a pas
              lu le Code (« on m'a viré », « fiche de paie », « être payé
              pareil »).
"""

# (identifiant, question, articles attendus, registre, ce que dit l'article)
BANC: list[tuple[str, str, set[str], str, str]] = [
    (
        "conges-deux-ans",
        "Combien de jours de congés payés ai-je après deux ans de travail ?",
        {"231"},
        "technique",
        "art. 231 : un jour et demi par mois de service après six mois continus.",
    ),
    (
        "conges-ouverture",
        "Au bout de combien de temps de service ai-je droit au congé annuel payé ?",
        {"231"},
        "technique",
        "art. 231 : après six mois de service continu.",
    ),
    (
        "conges-plafond",
        "La durée du congé annuel peut-elle dépasser trente jours ?",
        {"232"},
        "technique",
        "art. 232 : majoration d'ancienneté plafonnée à trente jours.",
    ),
    (
        "essai-cadre",
        "Quelle est la durée de la période d'essai pour un cadre ?",
        {"14"},
        "technique",
        "art. 14 : trois mois pour les cadres et assimilés.",
    ),
    (
        "essai-renouvellement",
        "La période d'essai peut-elle être renouvelée ?",
        {"14"},
        "technique",
        "art. 14 : renouvelable une seule fois.",
    ),
    (
        "indemnite-montant",
        "Quel est le montant de l'indemnité de licenciement par année d'ancienneté ?",
        {"53"},
        "technique",
        "art. 53 : 96 h de salaire pour les cinq premières années, puis 144, 192, 240.",
    ),
    (
        "indemnite-ouverture",
        "À partir de combien de mois de travail l'indemnité de licenciement est-elle due ?",
        {"52"},
        "technique",
        "art. 52 : après six mois de travail dans la même entreprise.",
    ),
    (
        "faute-employeur",
        "Le harcèlement sexuel commis par l'employeur est-il une faute grave ?",
        {"40"},
        "technique",
        "art. 40 : liste des fautes graves de l'employeur, dont le harcèlement sexuel.",
    ),
    (
        "vire-sans-rien",
        "On m'a viré du jour au lendemain sans rien me dire, j'ai droit à quoi ?",
        {"41", "51", "59"},
        "ordinaire",
        "art. 59 (dommages-intérêts + indemnité de préavis + perte d'emploi), "
        "art. 51 (indemnité de préavis), art. 41 (droit aux dommages-intérêts). "
        "Seule question du banc à réponse multiple, parce qu'elle est vague.",
    ),
    (
        "delai-contester",
        "Combien de temps ai-je pour contester mon licenciement devant le tribunal ?",
        {"65"},
        "technique",
        "art. 65 : 90 jours à compter de la réception de la décision, sous peine "
        "de déchéance.",
    ),
    (
        "duree-hebdo",
        "Quelle est la durée normale du travail par semaine ?",
        {"184"},
        "technique",
        "art. 184 : 2288 heures par an ou 44 heures par semaine (non agricole).",
    ),
    (
        "heures-sup-nuit",
        "De combien sont majorées les heures supplémentaires faites la nuit ?",
        {"201"},
        "technique",
        "art. 201 : 50 % entre 21 h et 6 h (non agricole).",
    ),
    (
        "maternite-duree",
        "Combien de semaines de congé de maternité ?",
        {"152"},
        "technique",
        "art. 152 : quatorze semaines.",
    ),
    (
        "enceinte-licenciement",
        "Mon employeur peut-il me licencier alors que je suis enceinte ?",
        {"159"},
        "technique",
        "art. 159 : rupture interdite pendant la grossesse et les quatorze "
        "semaines suivant l'accouchement.",
    ),
    (
        "bebe-jours-pere",
        "Je viens d'avoir un bébé, est-ce que mon mari a droit à des jours ?",
        {"269"},
        "ordinaire",
        "art. 269 : congé de trois jours à l'occasion de chaque naissance.",
    ),
    (
        "mariage-absence",
        "Combien de jours d'absence pour le mariage du salarié ?",
        {"274"},
        "technique",
        "art. 274 : quatre jours pour le mariage du salarié.",
    ),
    (
        "age-travail",
        "À quel âge est-ce qu'on peut commencer à travailler ?",
        {"143"},
        "ordinaire",
        "art. 143 : pas avant quinze ans révolus.",
    ),
    (
        "delegues-seuil",
        "À partir de combien de salariés faut-il élire des délégués des salariés ?",
        {"430"},
        "technique",
        "art. 430 : au moins dix salariés permanents.",
    ),
    (
        "delegues-nombre",
        "Combien de délégués des salariés dans une entreprise de trente personnes ?",
        {"433"},
        "technique",
        "art. 433 : de 26 à 50 salariés, deux titulaires et deux suppléants.",
    ),
    (
        "reglement-interieur-seuil",
        "À partir de combien de salariés faut-il un règlement intérieur ?",
        {"138"},
        "technique",
        "art. 138 : au minimum dix salariés habituellement occupés.",
    ),
    (
        "fiche-de-paie",
        "Mon patron ne me donne jamais de fiche de paie, est-ce qu'il y est obligé ?",
        {"370"},
        "ordinaire",
        "art. 370 : obligation de délivrer un bulletin de paye. Le Code écrit "
        "« bulletin de paye » et jamais « fiche de paie ».",
    ),
    (
        "repos-hebdo",
        "Combien d'heures de repos par semaine au minimum ?",
        {"205"},
        "technique",
        "art. 205 : au moins vingt-quatre heures, de minuit à minuit.",
    ),
    (
        "arret-long",
        "Je suis en arrêt depuis six mois, mon employeur peut-il me considérer "
        "comme démissionnaire ?",
        {"272"},
        "ordinaire",
        "art. 272 : au-delà de 180 jours consécutifs sur 365, l'employeur peut "
        "le considérer comme démissionnaire.",
    ),
    (
        "paye-pareil",
        "Est-ce qu'un homme et une femme doivent être payés pareil pour le même travail ?",
        {"346"},
        "ordinaire",
        "art. 346 : interdiction de toute discrimination de salaire entre les "
        "deux sexes pour un travail de valeur égale.",
    ),
    (
        "papier-fin-contrat",
        "En partant, mon employeur doit-il me remettre un papier prouvant que "
        "j'ai travaillé chez lui ?",
        {"72"},
        "ordinaire",
        "art. 72 : certificat de travail dans un délai maximum de huit jours.",
    ),
]
