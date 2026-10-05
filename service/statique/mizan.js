/* ══════════════════════════════════════════════════════════════════════════
   Mizan — l'écran de consultation.

   Deux routes, et rien d'autre : `GET /api/etat` au chargement de la page,
   `POST /api/question` à chaque question.

   TROIS RÉSULTATS QUI SORTENT EN 200 ET NE SONT PAS DES ERREURS, et que ce
   fichier dessine comme trois écrans du produit :
     • « reponse » — un texte servi, avec ses citations vérifiées ;
     • « doute »   — la récupération n'est pas sûre : rien n'est rédigé, et
                     les cinq candidats sont montrés SANS être la réponse ;
     • « rejet »   — la rédaction a cité un article non récupéré, la garde a
                     refusé la réponse entière.

   TOUT CE QUI VIENT DU SERVEUR EST POSÉ EN `textContent`, JAMAIS EN
   `innerHTML`. Ce n'est pas une précaution générique : cet écran affiche
   `signalement.traces[].extrait`, c'est-à-dire un fragment EXACT de la
   question — donc d'un texte potentiellement hostile. Un produit dont le
   sujet est l'injection ne peut pas se permettre d'en rouvrir une par son
   affichage.

   CE QUE CE FICHIER NE FAIT JAMAIS : afficher un score comme une confiance.
   Le contrat n'expose aucun score d'article, et quand il parle de `bras`,
   c'est pour dire qu'un cosinus et un BM25 ne se comparent pas. Le seul
   `score` du contrat est le barème de la détection d'injection, et il est
   étiqueté comme tel.
   ══════════════════════════════════════════════════════════════════════════ */
'use strict';

/* Pas de LIMITE_PAR_DEFAUT. La limite de caractères a UNE source,
   `limites.question_caracteres` de `/api/etat`, qui la tient de
   `service.contrat.LIMITE_CARACTERES_QUESTION`. Un repli chiffré ici serait
   une deuxième source : il resterait juste un moment, puis se décalerait de
   celle que le serveur applique, et c'est l'usager qui paierait l'écart en
   voyant sa question refusée par un serveur qu'un compteur disait d'accord.
   Tant que l'API n'a pas répondu, le compteur affiche le nombre de signes
   sans dénominateur, et c'est le serveur qui refuse, avec son message. */
const ATTENTE_SONDAGE_MS = 2500;

/* Au delà de ce nombre de signes, le texte d'un article est replié derrière un
   bouton. Le seuil est haut exprès : il ne vise que les articles-fleuves du
   Code, pas les articles ordinaires, qui doivent rester lisibles d'un coup. */
const SEUIL_REPLI = 700;

/* L'état de la page. `etatService` est le dernier `/api/etat` connu ; il sert
   à savoir si l'on est en chargement à froid, et à remplir le pied de page. */
let etatService = null;
let requeteEnVol = false;
let sondage = null;
let questionEnAttente = null;
let compteARebours = null;
let tentatives = 0;

const sortie = document.getElementById('sortie');
const champ = document.getElementById('question');
const bouton = document.getElementById('envoyer');
const formulaire = document.getElementById('formulaire');

/* ══ Fabrique de nœuds ════════════════════════════════════════════════════ */

function elt(balise, classe, texte) {
  const noeud = document.createElement(balise);
  if (classe) noeud.className = classe;
  if (texte !== undefined && texte !== null) noeud.textContent = texte;
  return noeud;
}

/* Azeret Mono est réservée aux nombres par la charte : tout nombre affiché
   passe par ici, et rien d'autre ne passe par ici. */
function nombre(valeur) {
  return elt('span', 'nb', String(valeur));
}

function icone(chemins, classe) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  if (classe) svg.setAttribute('class', classe);
  for (const d of chemins) {
    const trait = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    trait.setAttribute('d', d);
    svg.appendChild(trait);
  }
  return svg;
}

const ICONE_OK = ['M20 6 9 17l-5-5'];
const ICONE_SILENCE = ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M8 12h8'];
const ICONE_GARDE = ['M12 3l8 3v6c0 4.4-3.1 8.3-8 9-4.9-.7-8-4.6-8-9V6l8-3z', 'M9.2 12.4l1.9 1.9 3.7-3.7'];
const ICONE_LOUPE = ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z', 'M20 20l-4.2-4.2'];

/* ══ Mise en forme des nombres et des dates ═══════════════════════════════ */

function pourcent(valeur) {
  if (typeof valeur !== 'number' || !isFinite(valeur)) return null;
  return (valeur * 100).toFixed(1).replace('.', ',') + ' %';
}

/* Un cosinus, affiché au centième. Pas au millième : le seuil est lu sur
   dix-huit questions étrangères et rapporté sur dix-huit autres, et trois
   décimales promettraient une précision que ce jeu ne porte pas. */
function cosinus(valeur) {
  if (typeof valeur !== 'number' || !isFinite(valeur)) return null;
  return valeur.toFixed(2).replace('.', ',');
}

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
];

function dateFr(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
  if (!m) return String(iso || '');
  return Number(m[3]) + ' ' + MOIS[Number(m[2]) - 1] + ' ' + m[1];
}

/* ══ La position hiérarchique ═════════════════════════════════════════════
   `position` COMMENCE DÉJÀ par « article 269, », suivi de la hiérarchie
   complète. Le numéro est affiché juste au-dessus, en or : le répéter ici
   serait le préfixer une seconde fois. On retire donc ce préfixe — et si la
   forme attendue n'est pas là, on affiche la chaîne du serveur telle quelle
   plutôt que de la découper au jugé. ═════════════════════════════════════ */

const COUPURE = /,\s+(?=(?:Livre|Titre|Chapitre|Section|Sous-section|Partie|Annexe)\b)/;

function echapper(texte) {
  return String(texte).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function hierarchie(position, numero) {
  const brut = String(position || '').trim();
  if (!brut) return [];
  const prefixe = new RegExp('^article\\s+' + echapper(numero) + '\\s*,\\s*', 'i');
  const sans = brut.replace(prefixe, '').trim();
  const utile = sans || brut;
  return utile.split(COUPURE).map((s) => s.trim()).filter(Boolean);
}

/* ══ Les bandeaux permanents ══════════════════════════════════════════════ */

function appliquerAvertissement(texte) {
  const propre = String(texte || '').trim();
  if (!propre) return;      // garanti non vide par le cœur ; on ne l'efface jamais
  document.getElementById('avertissement-corpus').textContent = propre;
}

/* Appelée au chargement ET à CHAQUE réponse. Le contrat répète le bloc
   `redaction` dans chaque réponse précisément pour ça : une page qui n'aurait
   lu l'état qu'au chargement continuerait d'annoncer une vraie rédaction
   après l'expiration d'une clé. */
function appliquerRedaction(redaction) {
  const bandeau = document.getElementById('bandeau-factice');
  if (!redaction) return;
  if (redaction.factice) {
    // `pourquoi` est affichée TELLE QUELLE : elle dit à la fois ce qui est
    // faux (la rédaction) et ce qui marche quand même (la recherche, qui est
    // mesurée). La résumer en « mode démo » tromperait dans les deux sens.
    document.getElementById('pourquoi-factice').textContent =
      String(redaction.pourquoi || '');
    bandeau.hidden = false;
  } else {
    bandeau.hidden = true;
  }
}

function appliquerEtat(etat) {
  etatService = etat;
  appliquerRedaction(etat.redaction);

  const corpus = etat.corpus || {};
  appliquerAvertissement(corpus.avertissement);
  document.getElementById('corpus-intitule').textContent = corpus.intitule || '—';
  document.getElementById('corpus-portail').textContent = corpus.portail || '—';
  document.getElementById('corpus-articles').textContent =
    corpus.articles != null ? String(corpus.articles) : '—';
  document.getElementById('corpus-date').textContent =
    corpus.date_consolidation ? dateFr(corpus.date_consolidation) : '—';

  /* L'état vide du HTML est écrit sans aucun nombre pour rester vrai sans
     script. Dès que l'API a parlé, on y pose le compte d'articles — même
     source que le pied de page, et une seule. */
  const videArticles = document.getElementById('vide-articles');
  if (videArticles && corpus.articles != null) {
    document.getElementById('vide-articles-n').textContent = String(corpus.articles);
    videArticles.hidden = false;
  }

  /* La `meta description` ne porte pas la date de consolidation : une date
     fausse y partirait dans les moteurs et les aperçus de partage. On l'y
     ajoute une fois, depuis l'API. `dataset` sert de garde : `/api/etat` est
     relu à chaque sondage du démarrage à froid, et sans elle la phrase se
     répéterait à chaque passe. */
  const meta = document.querySelector('meta[name="description"]');
  if (meta && corpus.date_consolidation && !meta.dataset.dateCorpus) {
    meta.dataset.dateCorpus = corpus.date_consolidation;
    meta.setAttribute('content',
      meta.getAttribute('content')
      + ' Corpus consolidé au ' + dateFr(corpus.date_consolidation) + '.');
  }

  const limites = etat.limites || {};
  const max = limites.question_caracteres;
  if (typeof max === 'number' && max > 0) {
    champ.setAttribute('maxlength', String(max));
    document.getElementById('compteur-max').textContent = String(max);
  }
  majCompteur();
}

/* ══ Les écrans ═══════════════════════════════════════════════════════════ */

function vider() {
  sortie.textContent = '';
}

function ajouter(noeud) {
  sortie.appendChild(noeud);
  return noeud;
}

function carte(titre, texte) {
  const bloc = elt('div', 'carte verre');
  if (titre) bloc.appendChild(elt('h2', 'carte__titre', titre));
  if (texte) bloc.appendChild(elt('p', 'doux', texte));
  return bloc;
}

/* L'attente du chargement à froid. Sur un Space qui démarre, l'index met
   quelques secondes à se lire : c'est une attente qui réessaie, jamais une
   panne — et l'avertissement de date est DÉJÀ affiché à ce moment-là. */
function ecranAttente(titre, detail) {
  vider();
  const bloc = elt('div', 'carte verre');
  const ligne = elt('div', 'attente');
  ligne.appendChild(elt('span', 'pastille'));
  const corps = elt('div');
  corps.appendChild(elt('h2', 'carte__titre', titre));
  corps.appendChild(elt('p', 'doux', detail));
  ligne.appendChild(corps);
  bloc.appendChild(ligne);
  ajouter(bloc);
}

function ecranRecherche() {
  const n = etatService && etatService.corpus ? etatService.corpus.articles : null;
  ecranAttente(
    'Recherche en cours',
    n
      ? 'Mizan parcourt les ' + n + ' articles du Code. La première question '
        + 'de la session peut demander quelques secondes : l\'index n\'est lu '
        + 'qu\'une fois.'
      : 'Mizan parcourt le Code. La première question de la session peut '
        + 'demander quelques secondes.'
  );
}

/* ══ Les erreurs ══════════════════════════════════════════════════════════ */

const TITRES_ERREUR = {
  question_vide: 'Il n\'y a rien à chercher',
  question_trop_longue: 'Question trop longue',
  corps_illisible: 'Requête mal formée',
  trop_de_requetes: 'Trop de questions d\'affilée',
  index_absent: 'L\'index de recherche est absent',
  modele_absent: 'Le modèle de plongement est absent',
  redaction_en_panne: 'La rédaction est indisponible'
};

function ecranErreur(erreur, secondesAttente) {
  vider();
  const bloc = elt('div', 'erreur');
  const code = String(erreur.code || 'inconnu');
  bloc.appendChild(elt('h2', 'erreur__titre', TITRES_ERREUR[code] || 'Erreur'));
  bloc.appendChild(elt('p', 'erreur__code', code));

  // Le message du cœur arrive parfois sur plusieurs lignes et dit déjà quoi
  // faire. Il est affiché tel quel : le résumer perdrait l'information, le
  // réécrire le ferait dériver de ce que le programme imprime.
  bloc.appendChild(elt('p', 'erreur__message', String(erreur.message || '')));

  // La commande apparaît déjà DANS le message, puisque le service l'y relève
  // au lieu de la recopier. Elle est répétée ici pour une raison précise :
  // c'est la seule ligne qu'on doit pouvoir prendre telle quelle, et un bouton
  // qui la copie vaut mieux qu'une sélection à la souris dans un paragraphe.
  if (erreur.commande) {
    bloc.appendChild(elt('p', 'commande__titre', 'La commande à lancer'));
    bloc.appendChild(elt('pre', 'commande', String(erreur.commande)));
    if (navigator.clipboard) {
      const copier = elt('button', 'deplier', 'Copier la commande');
      copier.type = 'button';
      copier.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(String(erreur.commande));
          copier.textContent = 'Copiée';
        } catch (echec) {
          copier.textContent = 'Copie refusée par le navigateur';
        }
      });
      bloc.appendChild(copier);
    }
  }

  if (secondesAttente) {
    const attente = elt('p', 'doux');
    attente.appendChild(document.createTextNode('Réessayez dans '));
    const n = nombre(secondesAttente);
    attente.appendChild(n);
    attente.appendChild(document.createTextNode(' secondes.'));
    bloc.appendChild(attente);
    lancerCompteARebours(secondesAttente, n);
  }
  ajouter(bloc);
}

function lancerCompteARebours(secondes, cible) {
  clearInterval(compteARebours);
  let reste = secondes;
  bouton.disabled = true;
  compteARebours = setInterval(() => {
    reste -= 1;
    if (reste <= 0) {
      clearInterval(compteARebours);
      compteARebours = null;
      cible.textContent = '0';
      majCompteur();
      return;
    }
    cible.textContent = String(reste);
  }, 1000);
}

/* ══ Le verdict ═══════════════════════════════════════════════════════════ */

const VERDICTS = {
  reponse: {
    classe: 'verdict--repond',
    icone: ICONE_OK,
    titre: 'Le Code répond',
    dit: 'La recherche s\'est prononcée, et chaque article cité ci-dessous a '
       + 'été vérifié contre ce qu\'elle a réellement récupéré.'
  },
  doute: {
    classe: 'verdict--doute',
    icone: ICONE_SILENCE,
    titre: 'Mizan ne se prononce pas',
    dit: 'Aucun texte n\'a été rédigé : quand la recherche doute, le modèle '
       + 'n\'est jamais appelé — on ne peut pas inventer ce qu\'on n\'a pas '
       + 'demandé.'
  },
  rejet: {
    classe: 'verdict--rejet',
    icone: ICONE_GARDE,
    titre: 'La garde a refusé cette rédaction',
    dit: 'La recherche avait trouvé, un texte a été écrit — mais il citait un '
       + 'article hors de ceux récupérés. La réponse entière est rejetée, pas '
       + 'rapiécée : une réponse à moitié inventée ne se distingue plus d\'une '
       + 'réponse vérifiée.'
  }
};

function ecranVerdict(registre) {
  const v = VERDICTS[registre] || VERDICTS.rejet;
  const bloc = elt('div', 'verdict verre ' + v.classe);
  bloc.appendChild(icone(v.icone, 'verdict__icone'));
  const corps = elt('div', 'verdict__corps');
  corps.appendChild(elt('h2', 'verdict__titre', v.titre));
  corps.appendChild(elt('p', 'verdict__dit', v.dit));
  bloc.appendChild(corps);
  return bloc;
}

/* ══ Le texte rédigé, et sa marque quand il est factice ═══════════════════ */

function ecranTexte(texte, redaction) {
  const factice = !!(redaction && redaction.factice);
  const bloc = elt('div', 'redige verre' + (factice ? ' redige--factice' : ''));

  if (factice) {
    // Marqué SUR le texte, et pas seulement en haut de page : c'est la zone
    // qu'on lit, et c'est la seule qui soit fausse. Personne ne relit le haut
    // d'une page en lisant un paragraphe.
    bloc.appendChild(elt('span', 'marque-factice', 'Rédaction factice'));
  }

  bloc.appendChild(elt('p', 'redige__texte', String(texte)));

  if (factice) {
    bloc.appendChild(elt('p', 'redige__note',
      'Ce paragraphe n\'a pas été écrit par un modèle de langue : un modèle '
      + 'factice déterministe nomme les articles trouvés, et c\'est tout. Les '
      + 'articles ci-dessous, leur position hiérarchique et le verdict de la '
      + 'recherche sont réels — c\'est eux qui sont mesurés.'));
  }
  return bloc;
}

function ecranCitations(citations) {
  // L'OR PORTE LES CITATIONS. C'est la décision de charte du projet : une
  // réponse sans or à l'écran est une réponse sans source, et l'anomalie doit
  // se voir avant d'être lue.
  const bloc = elt('div', 'citations');
  bloc.appendChild(elt('p', 'citations__titre', 'Articles cités et vérifiés'));
  for (const numero of citations) {
    const puce = elt('a', 'citation');
    puce.href = '#article-' + encodeURIComponent(numero);
    puce.appendChild(document.createTextNode('article'));
    puce.appendChild(nombre(numero));
    bloc.appendChild(puce);
  }
  return bloc;
}

/* ══ Les articles ═════════════════════════════════════════════════════════ */

const NOMS_BRAS = {
  dense: 'bras dense (plongements)',
  lexical: 'bras lexical (BM25)'
};

const EXPLICATION_BRAS =
  'Le bras qui a remonté cet article. Son score n\'est pas affiché : un '
  + 'cosinus et un BM25 ne se comparent pas, et aucun des deux n\'est une '
  + 'mesure de confiance.';

function ecranArticle(article, citee, registre) {
  const bloc = elt('article', 'article verre');
  bloc.id = 'article-' + encodeURIComponent(article.numero);

  const tete = elt('div', 'article__tete');
  const numero = elt('span', 'article__numero');
  numero.appendChild(document.createTextNode('article'));
  numero.appendChild(nombre(article.numero));
  tete.appendChild(numero);
  // « candidat » n'a de sens que sur une abstention — là où rien n'a été
  // départagé. Sur un rejet, ces articles ONT été retrouvés et retenus : les
  // appeler candidats sous-estimerait ce que la recherche avait fait.
  tete.appendChild(
    citee
      ? elt('span', 'etiquette etiquette--citee', 'cité')
      : elt('span', 'etiquette', registre === 'doute' ? 'candidat' : 'récupéré')
  );
  bloc.appendChild(tete);

  // La position hiérarchique complète. En droit, un article sans son chapitre
  // ne veut pas dire la même chose : c'est de la matière juridique, donc de
  // l'or.
  const chaine = hierarchie(article.position, article.numero);
  if (chaine.length) {
    const liste = elt('ol', 'hierarchie');
    for (const segment of chaine) liste.appendChild(elt('li', null, segment));
    bloc.appendChild(liste);
  }

  // Le texte de l'article. Replié au delà d'un seuil, jamais tronqué : le
  // bouton dit ce qu'il déplie, et un article juridique rendu à moitié sans
  // le dire serait exactement le genre de demi-vérité que ce produit refuse.
  const brut = String(article.texte || '');
  const texte = elt('p', 'article__texte', brut);
  bloc.appendChild(texte);
  if (brut.length > SEUIL_REPLI) {
    texte.classList.add('article__texte--plie');
    const bascule = elt('button', 'deplier');
    bascule.type = 'button';
    bascule.setAttribute('aria-expanded', 'false');
    const etiqueter = (plie) => {
      bascule.textContent = '';
      if (plie) {
        bascule.appendChild(document.createTextNode('Afficher l\'article entier — '));
        bascule.appendChild(nombre(brut.length));   // mono : c'est un nombre
        bascule.appendChild(document.createTextNode(' signes'));
      } else {
        bascule.appendChild(document.createTextNode('Replier l\'article'));
      }
      bascule.setAttribute('aria-expanded', plie ? 'false' : 'true');
    };
    etiqueter(true);
    bascule.addEventListener('click', () => {
      const plie = texte.classList.toggle('article__texte--plie');
      etiqueter(plie);
    });
    bloc.appendChild(bascule);
  }

  const pied = elt('p', 'article__pied');
  const bras = elt('span', null, NOMS_BRAS[article.bras] || String(article.bras || ''));
  bras.title = EXPLICATION_BRAS;
  pied.appendChild(bras);
  if (article.page_pdf) {
    const page = elt('span');
    page.appendChild(document.createTextNode('page'));
    page.appendChild(nombre(article.page_pdf));
    page.appendChild(document.createTextNode('du PDF source'));
    pied.appendChild(page);
  }
  bloc.appendChild(pied);
  return bloc;
}

function ecranArticles(donnees) {
  const fragment = document.createDocumentFragment();
  const candidats = donnees.registre === 'doute';

  const entete = elt('div',
    'articles__entete verre' + (candidats ? ' articles__entete--candidats' : ''));
  if (candidats) {
    entete.appendChild(elt('h2', 'articles__titre',
      'Ces articles ne sont pas la réponse'));
    entete.appendChild(elt('p', 'articles__avis',
      'Ce sont les textes les plus proches de votre question. Ils sont '
      + 'affichés parce qu\'ils peuvent servir de point de départ, mais la '
      + 'recherche ne les a pas départagés : les lire comme une réponse '
      + 'serait exactement l\'erreur que cette abstention évite.'));
  } else if (donnees.registre === 'rejet') {
    entete.appendChild(elt('h2', 'articles__titre',
      'Les articles récupérés, eux, sont réels'));
    entete.appendChild(elt('p', 'articles__avis',
      'La recherche les a bien trouvés et ils sont dans le Code. C\'est le '
      + 'texte rédigé par-dessus qui a été refusé.'));
  } else {
    entete.appendChild(elt('h2', 'articles__titre', 'Les articles du Code'));
    entete.appendChild(elt('p', 'articles__avis',
      'Les cinq textes récupérés pour cette question, avec leur position '
      + 'complète. Ceux marqués « cité » sont ceux sur lesquels la réponse '
      + 's\'appuie.'));
  }
  fragment.appendChild(entete);

  const citees = new Set((donnees.citations || []).map(String));
  for (const article of donnees.articles || []) {
    fragment.appendChild(
      ecranArticle(article, citees.has(String(article.numero)), donnees.registre)
    );
  }
  return fragment;
}

/* ══ Mots inconnus du Code ════════════════════════════════════════════════
   Souvent l'explication d'une mauvaise réponse : un mot que le législateur
   n'emploie pas ne peut pas être retrouvé par le bras lexical. ═══════════ */

function ecranInconnus(mots) {
  const bloc = elt('div', 'carte verre');
  bloc.appendChild(elt('h2', 'carte__titre', 'Des mots que le Code n\'emploie pas'));
  bloc.appendChild(elt('p', 'doux',
    'Ces mots de votre question n\'apparaissent nulle part dans les articles. '
    + 'C\'est souvent ce qui explique une recherche qui doute ou qui se '
    + 'trompe : le Code dit la même chose avec d\'autres termes.'));
  const liste = elt('div', 'inconnus');
  for (const mot of mots) liste.appendChild(elt('span', 'mot-inconnu', mot));
  bloc.appendChild(liste);
  return bloc;
}

/* ══ Le signalement d'injection ═══════════════════════════════════════════
   Il SIGNALE, il ne bloque pas : la réponse est rendue dans le même objet, et
   elle est affichée. Cet encart dit ce qui a été repéré, fragment exact
   compris — une défense qui signale sans montrer n'est pas contestable, donc
   pas améliorable. ══════════════════════════════════════════════════════ */

function ecranSignalement(signalement) {
  const bloc = elt('div', 'signalement verre');
  bloc.appendChild(elt('h2', 'signalement__titre',
    'Une consigne adressée à l\'assistant a été repérée'));
  bloc.appendChild(elt('p', 'doux',
    'Votre question a quand même été traitée, et le résultat ci-dessus est '
    + 'celui du produit : la détection signale, elle ne refuse jamais. '
    + 'Quelqu\'un peut très bien demander si son employeur peut ignorer le '
    + 'règlement intérieur sans attaquer personne.'));
  bloc.appendChild(elt('p', 'doux', String(signalement.pourquoi || '')));

  if ((signalement.familles || []).length) {
    const liste = elt('ul', 'familles');
    for (const famille of signalement.familles) {
      liste.appendChild(elt('li', 'famille', famille));
    }
    bloc.appendChild(liste);
  }

  if ((signalement.traces || []).length) {
    const traces = elt('div', 'traces');
    for (const trace of signalement.traces) {
      const bulle = elt('div', 'trace');
      bulle.appendChild(elt('p', 'trace__extrait', String(trace.extrait || '')));
      const meta = elt('p', 'trace__meta');
      meta.appendChild(document.createTextNode(
        'famille « ' + String(trace.famille || '') + ' », motif '
        + String(trace.motif || '')));
      bulle.appendChild(meta);
      traces.appendChild(bulle);
    }
    bloc.appendChild(traces);
  }

  const bareme = elt('p', 'faible');
  bareme.appendChild(document.createTextNode('Barème de la détection : '));
  bareme.appendChild(nombre(signalement.score));
  bareme.appendChild(document.createTextNode(' pour un seuil de '));
  bareme.appendChild(nombre(signalement.seuil));
  bareme.appendChild(document.createTextNode(
    '. Ce barème est un compte pondéré de motifs, pas une confiance.'));
  bloc.appendChild(bareme);
  return bloc;
}

/* ══ Le détail de la décision ═════════════════════════════════════════════ */

function mesure(nom, valeurNoeud) {
  const ligne = elt('div', 'mesure');
  ligne.appendChild(elt('span', 'mesure__nom', nom));
  const valeur = elt('span', 'mesure__valeur');
  valeur.appendChild(valeurNoeud);
  ligne.appendChild(valeur);
  return ligne;
}

function ecranDetail(donnees) {
  const bloc = elt('details', 'technique verre');
  bloc.appendChild(elt('summary', null, 'Détail de la décision'));
  const corps = elt('div', 'technique__corps');
  const mesures = elt('div', 'mesures');

  mesures.appendChild(mesure('Verdict de la récupération',
    document.createTextNode(donnees.sur ? 'sûre' : 'pas sûre')));

  /* CE QUI DÉCIDE vient d'abord, et son seuil juste après : la décision
     affichée et le nombre qui l'a prise ne se séparent pas. */
  const proche = cosinus(donnees.proximite);
  if (proche) {
    mesures.appendChild(mesure(
      'Ressemblance de la question au Code', nombre(proche)));
  }
  const seuil = cosinus(donnees.seuil_proximite);
  if (seuil) {
    mesures.appendChild(mesure('Seuil en dessous duquel Mizan se tait',
      nombre(seuil)));
  }
  /* La marge s'affiche SANS seuil, et c'est tout le point : elle a décidé
     jusqu'au banc d'abstention, elle ne décide plus rien. Lui remettre un
     seuil à l'écran réinstallerait la décision qu'on vient de lui retirer. */
  const pct = pourcent(donnees.marge);
  if (pct) {
    mesures.appendChild(mesure(
      'Écart au candidat suivant (n\'entre plus dans la décision)',
      nombre(pct)));
  }
  mesures.appendChild(mesure('Registre et cause',
    document.createTextNode(String(donnees.registre) + ' / ' + String(donnees.cause))));
  corps.appendChild(mesures);

  if (donnees.pourquoi) {
    corps.appendChild(elt('p', 'doux', String(donnees.pourquoi)));
  }

  corps.appendChild(elt('p', 'faible',
    'Aucun score par article n\'est affiché, et ce n\'est pas un oubli : le '
    + 'bras dense note en cosinus, le bras lexical en BM25, les deux échelles '
    + 'ne se comparent pas, et le score dense sépare mal une bonne réponse '
    + 'd\'une mauvaise. Un pourcentage de certitude par article serait une '
    + 'invention. Le seul score qui sorte est celui du premier article, parce '
    + 'que c\'est lui qui a décidé du silence : il dit à quel point la '
    + 'question ressemble au Code, pas à quel point la réponse est juste.'));

  const signalement = donnees.signalement;
  if (signalement && !signalement.signale) {
    const ligne = elt('p', 'faible');
    ligne.appendChild(document.createTextNode(
      'Détection d\'injection : ' + String(signalement.pourquoi || '') + ' Barème '));
    ligne.appendChild(nombre(signalement.score));
    ligne.appendChild(document.createTextNode(' pour un seuil de '));
    ligne.appendChild(nombre(signalement.seuil));
    ligne.appendChild(document.createTextNode('.'));
    corps.appendChild(ligne);
  }

  bloc.appendChild(corps);
  return bloc;
}

/* ══ L'assemblage d'une réponse ═══════════════════════════════════════════ */

function ecranReponse(donnees) {
  vider();

  // Repris de chaque réponse, pas seulement de `/api/etat` : une clé peut
  // expirer en cours de session.
  appliquerRedaction(donnees.redaction);
  appliquerAvertissement(donnees.avertissement);

  const rappel = elt('p', 'rappel-question');
  rappel.appendChild(document.createTextNode('Question posée : '));
  rappel.appendChild(elt('q', null, String(donnees.question || '')));
  ajouter(rappel);

  ajouter(ecranVerdict(donnees.registre));

  // `raison` est la phrase française du cœur, et elle nomme les articles
  // fautifs sur un rejet. Elle est affichée telle quelle.
  if (donnees.raison) {
    const bloc = elt('div', 'carte verre');
    bloc.appendChild(elt('h2', 'carte__titre',
      donnees.registre === 'rejet'
        ? 'Ce que la garde a refusé'
        : 'Pourquoi Mizan ne répond pas'));
    bloc.appendChild(elt('p', null, String(donnees.raison)));
    // Sur une abstention, `raison` EST la phrase de la récupération : le cœur
    // la reprend telle quelle. L'afficher deux fois ferait croire à deux
    // motifs distincts.
    if (donnees.pourquoi && donnees.pourquoi !== donnees.raison) {
      bloc.appendChild(elt('p', 'doux', String(donnees.pourquoi)));
    }
    ajouter(bloc);
  }

  if (donnees.texte) {
    const bloc = ecranTexte(donnees.texte, donnees.redaction);
    if ((donnees.citations || []).length) {
      bloc.appendChild(ecranCitations(donnees.citations));
    }
    ajouter(bloc);
  }

  if ((donnees.termes_inconnus || []).length) {
    ajouter(ecranInconnus(donnees.termes_inconnus));
  }

  if (donnees.signalement && donnees.signalement.signale) {
    ajouter(ecranSignalement(donnees.signalement));
  }

  if ((donnees.articles || []).length) {
    sortie.appendChild(ecranArticles(donnees));
  }

  ajouter(ecranDetail(donnees));
}

/* ══ Le réseau ════════════════════════════════════════════════════════════ */

async function lireEtat() {
  try {
    const reponse = await fetch('api/etat', { headers: { Accept: 'application/json' } });
    const corps = await reponse.json();
    appliquerEtat(corps);
    return corps;
  } catch (echec) {
    return null;
  }
}

/* `etape === "chargement"` au premier chargement de la page : une attente qui
   réessaie, pas une panne. Le sondage s'arrête de lui-même dès que la
   recherche est prête, et il relance la question mise de côté s'il y en a
   une. */
function sonder() {
  clearTimeout(sondage);
  sondage = setTimeout(async () => {
    tentatives += 1;
    const etat = await lireEtat();
    // Au delà d'une demi-minute, l'écran le DIT au lieu de faire tourner une
    // pastille indéfiniment : une attente muette finit par ressembler à une
    // panne, et c'est précisément la confusion qu'on voulait éviter.
    if (tentatives === 12) {
      const detail = sortie.querySelector('.attente .doux');
      if (detail) {
        detail.textContent =
          'Le chargement dure plus longtemps que prévu. L\'écran continue de '
          + 'réessayer tout seul ; si rien ne vient, le service est peut-être '
          + 'en train de reconstruire son index.';
      }
    }
    if (!etat) { sonder(); return; }
    if (etat.etape === 'chargement') { sonder(); return; }
    if (etat.etape === 'panne') {
      const recherche = etat.recherche || {};
      ecranErreur({
        code: 'index_absent',
        message: recherche.pourquoi || 'La recherche n\'a pas pu être chargée.',
        commande: recherche.commande
      });
      return;
    }
    if (questionEnAttente) {
      const question = questionEnAttente;
      questionEnAttente = null;
      poser(question);
    } else {
      ecranVide();
    }
  }, ATTENTE_SONDAGE_MS);
}

function ecranVide() {
  vider();
  const bloc = carte('Prêt à chercher',
    'Posez une question ci-dessus. Mizan rend au plus cinq articles, avec '
    + 'leur position complète dans le Code — ou une abstention expliquée.');
  ajouter(bloc);
}

async function poser(question) {
  if (requeteEnVol) return;
  requeteEnVol = true;
  bouton.disabled = true;
  sortie.setAttribute('aria-busy', 'true');
  ecranRecherche();

  let reponse;
  let corps;
  try {
    reponse = await fetch('api/question', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ question: question })
    });
    corps = await reponse.json();
  } catch (echec) {
    // Une coupure réseau n'a pas de code du cœur : on le dit sans en inventer
    // un, et surtout sans montrer une commande qui ne réparerait rien.
    ecranErreur({
      code: 'reseau',
      message: 'Le service n\'a pas répondu. Vérifiez votre connexion, puis '
             + 'reposez la question.'
    });
    terminer();
    return;
  }

  if (reponse.ok) {
    tentatives = 0;
    ecranReponse(corps);
    terminer();
    return;
  }

  const erreur = (corps && corps.erreur) || { code: 'inconnu', message: '' };

  // Le seul 503 qui se résout tout seul : on garde la question et on la
  // reposera dès que la recherche sera chaude.
  if (erreur.code === 'chargement_en_cours') {
    questionEnAttente = question;
    ecranAttente(
      'Le moteur de recherche se charge',
      'Votre question est gardée et sera reposée automatiquement dès que '
      + 'l\'index sera lu. L\'avertissement de date ci-dessus est déjà valable.'
    );
    terminer();
    sonder();
    return;
  }

  const retry = Number(reponse.headers.get('Retry-After'));
  ecranErreur(erreur, reponse.status === 429 && retry > 0 ? retry : 0);
  terminer();
}

function terminer() {
  requeteEnVol = false;
  sortie.setAttribute('aria-busy', 'false');
  majCompteur();
}

/* ══ Le formulaire ════════════════════════════════════════════════════════ */

function majCompteur() {
  const n = champ.value.length;
  /* `maxlength` est absent du balisage et posé par `appliquerEtat` : tant
     qu'il manque, il n'y a pas de plafond à annoncer, et le compteur ne doit
     surtout pas se mettre au rouge contre un plafond deviné. */
  const attr = champ.getAttribute('maxlength');
  const max = attr === null ? null : Number(attr);
  document.getElementById('compteur-n').textContent = String(n);
  document.getElementById('compteur').classList.toggle(
    'compteur--plein', max !== null && n >= max);
  if (!compteARebours) {
    bouton.disabled = requeteEnVol || champ.value.trim().length === 0;
  }
}

champ.addEventListener('input', majCompteur);

// Entrée envoie, Maj+Entrée passe à la ligne : une question de droit du
// travail tient en une ligne neuf fois sur dix, et un champ multiligne qui
// n'envoie pas à Entrée fait chercher le bouton.
champ.addEventListener('keydown', (evenement) => {
  if (evenement.key === 'Enter' && !evenement.shiftKey) {
    evenement.preventDefault();
    formulaire.requestSubmit();
  }
});

formulaire.addEventListener('submit', (evenement) => {
  evenement.preventDefault();
  // `bouton.disabled` porte aussi le compte à rebours du débit dépassé : sans
  // ce test, la touche Entrée passerait par-dessus la limite que le bouton
  // affiche.
  if (bouton.disabled) return;
  const question = champ.value.trim();
  if (!question) return;
  poser(question);
});

for (const puce of document.querySelectorAll('.puce')) {
  puce.addEventListener('click', () => {
    champ.value = puce.dataset.question;
    majCompteur();
    champ.focus();
    poser(champ.value.trim());
  });
}

/* ══ Démarrage ════════════════════════════════════════════════════════════ */

(async function demarrer() {
  const etat = await lireEtat();
  if (!etat) return;
  if (etat.etape === 'chargement') {
    ecranAttente(
      'Le moteur de recherche se charge',
      'Mizan lit son index au démarrage ; cela prend quelques secondes sur un '
      + 'service qui vient de s\'éveiller. L\'écran se débloque tout seul — '
      + 'l\'avertissement de date ci-dessus, lui, est déjà valable.'
    );
    sonder();
  } else if (etat.etape === 'panne') {
    const recherche = etat.recherche || {};
    ecranErreur({
      code: 'index_absent',
      message: recherche.pourquoi || 'La recherche n\'a pas pu être chargée.',
      commande: recherche.commande
    });
  }
})();
