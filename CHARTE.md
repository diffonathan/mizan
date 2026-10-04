# Charte de Mizan

Dérivée de la **charte maison des 24 palettes**
(`Documents/Projet/charte/CHARTE-24-PALETTES.md`). Source unique des couleurs
du projet : aucune valeur de couleur ne s'écrit ailleurs qu'en `var(--…)`
pointant sur un jeton défini ici.

---

## La palette : 19 — Violet profond `#7c3aed`

Palettes déjà attribuées : 13 Bleu FTMO (Hope Traders), 01 Vert Hope (RDV
Santé), 08 Or antique (Factura), 03 Sarcelle (Artisans.ma). Deux projets ne
portent jamais la même.

**Pourquoi le violet profond.** Le violet est la couleur de l'autorité
judiciaire — la robe, le sceau — sans être le rouge de l'alarme. Mais la
raison qui a tranché n'est pas symbolique, elle est structurelle : c'est la
seule teinte profonde non attribuée qui laisse **les trois autres rôles
libres pour ce que cette application doit dire**.

**Ce qui a été écarté, et pourquoi.**

*24 — Bordeaux `#b91c3c`* était le candidat évident : c'est le rouge des
robes de magistrat. Il est refusé parce que la charte réserve le rouge à la
baisse et à la perte. Un accent rouge obligerait à déplacer la couleur de
direction, et sur une application qui doit distinguer « le Code répond » de
« le Code ne répond pas », perdre le rouge pour le décor serait payer une
métaphore avec une information.

*18 — Violet royal `#a855f7`* est le même registre en plus clair. Trop clair :
sur un socle nuit, il tire vers le décoratif, et cet outil parle de droit du
travail à des gens qui s'en servent pour décider.

*17 — Indigo `#635bff`* aurait convenu, mais la famille bleue est déjà
occupée par le projet 13, et deux outils bleus dans une même série de
démonstrations se confondent dans une page de portfolio.

---

## Les jetons

Calculés par les formules exactes de la charte, pas à l'estime :

```
assombrir(hex, t) = mélange(hex, #000000, t)
eclaircir(hex, t) = mélange(hex, #ffffff, t)
```

| Jeton | Valeur | Origine |
|---|---|---|
| `--primary` | `#7c3aed` | l'accent |
| `--primary-dim` | `#6630c2` | `assombrir(accent, 0.18)` |
| `--accent-texte` | `#b793f5` | `eclaircir(accent, 0.45)` |
| `--accent-soft` | `rgba(124, 58, 237, 0.10)` | |
| `--accent-border` | `rgba(124, 58, 237, 0.30)` | |
| `--accent-glow` | `rgba(124, 58, 237, 0.18)` | |
| `--glass-border-hover` | `rgba(124, 58, 237, 0.35)` | |
| `--grad-accent` | `linear-gradient(-15deg, #b793f5, #612db9)` | `eclaircir(…, 0.45)` → `assombrir(…, 0.22)` |

`--accent-texte` n'est pas un cinquième rôle : c'est le rôle *action* à la
graduation que le socle nuit impose. La leçon a été payée sur Artisans.ma —
`--primary` est une teinte moyenne, et du corps de texte écrit avec elle
tombe sous le seuil de contraste dès qu'il se pose sur du verre. Six endroits
avaient dû être corrigés après coup.

Les trois halos de `body::before` utilisent `rgba(124, 58, 237, …)` aux
opacités 0.12, 0.06 et 0.05, sur le dégradé nuit de la charte.

---

## Les quatre rôles — et ce qu'ils portent ICI

| Rôle | Jeton | Ce qu'il porte dans Mizan |
|---|---|---|
| **action** | `--primary` | la zone de question, les boutons, le focus |
| **action, en texte** | `--accent-texte` | libellés d'accent, liens |
| **valeur** | `--or` `#f9a825` | **les citations d'articles** |
| **réponse trouvée** | `--vert` `#4ade80` | le Code répond, et l'assistant est sûr |
| **pas de réponse** | `--rouge` `#f87171` | le Code ne traite pas la question |

**L'or porte les citations, et c'est la décision de charte la plus importante
du projet.** Sur Factura l'or portait les montants, sur Artisans.ma les
dirhams. Ici, l'objet de valeur est la **référence d'article** : c'est elle
qui transforme une phrase plausible en affirmation vérifiable, et c'est la
seule chose que le lecteur doit pouvoir repérer sans lire.

Une réponse sans or à l'écran est une réponse sans source. L'anomalie doit se
voir d'un coup d'œil, avant même d'être lue.

**Le vert et le rouge ne disent pas « bien » et « mal ».** Ils disent « le
Code répond » et « le Code ne traite pas cette question ». Un rouge ici n'est
pas un échec de l'outil : c'est son comportement correct, et le plus difficile
à obtenir — les mesures des fondations donnent une abstention de 0 % pour
l'approche la plus performante. Que le refus porte une couleur franche plutôt
qu'un gris d'erreur est un choix de produit, pas d'esthétique.

---

## Le socle, qui ne change pas

- **nuit uniquement** — aucun thème clair, aucun `prefers-color-scheme` ;
- **glassmorphism** — `backdrop-filter: blur(12px) saturate(140%)`, bordures
  fines, liseré interne haut ;
- **DM Sans** pour le texte, **Azeret Mono** réservée aux nombres — numéros
  d'articles, scores de confiance, délais légaux. Jamais pour de la prose ;
- courbe d'animation signature `cubic-bezier(0.22, 1, 0.36, 1)`.

## Ce qui est interdit

- une couleur écrite en dur dans un composant ;
- une teinte absente des 24 palettes ;
- `prefers-color-scheme` ou tout thème clair ;
- un `<select>` restylé en ligne — `background:` en raccourci efface le
  chevron, utiliser `background-color` ;
- Azeret Mono sur autre chose que des nombres ;
- **une citation d'article qui ne serait pas en or**, ou un élément doré qui
  ne serait pas une citation.

---

## Une contrainte propre à ce projet

Le corpus est consolidé au **26 octobre 2011**. L'interface doit le dire, de
façon visible et permanente — pas dans un pied de page, pas dans une page
« à propos ».

Ce n'est pas une mention légale, c'est le garde-fou central du produit : un
assistant juridique qui laisse croire qu'il connaît le droit en vigueur
aujourd'hui est dangereux pour celui qui s'en sert. La charte lui réserve donc
un emplacement, et ce bandeau ne se ferme pas.
