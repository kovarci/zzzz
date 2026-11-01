# Direction visuelle de Lotent

Lotent est un agenda : on le consulte pour trouver une conférence, pas pour être impressionné.
L'interface s'efface devant le contenu, comme un programme imprimé.

## Principes
- **Un seul élément marquant** : le titre en serif. Tout le reste est calme.
- **La structure passe par les filets** (bordures fines), pas par le relief : aucune ombre portée.
- **Pas de mouvement décoratif** : rien ne bouge seul. Les animations répondent à une action (ouvrir une fiche, une recherche).
- **Pas d'accent sur un seul mot** d'un titre, pas de dégradés, pas de lueurs, pas d'étincelles.

## Typographie
- Titres, titres d'événements, logotype : **Newsreader** (serif, graisse 500).
- Interface, texte courant, libellés : **Instrument Sans**.
- Lignes de moins de 80 caractères. Pas de capitales espacées au-dessus des titres.
- Remplace Geist (la police par défaut des projets Tailwind / shadcn).

## Couleurs
Neutres zinc (tokens `--background`, `--foreground`, `--muted`, `--border` dans `web/src/app.css`),
clair et sombre. La couleur ne sert qu'à **coder la discipline** (`--c-*`) : point, vignette sans image.
Un seul accent de marque, `--brand` (bleu, `224 64% 42%` en clair, `224 100% 78%` en sombre) : réservé au **point du logo**.
Ne pas l'étendre aux boutons ou aux liens sans décision explicite.

## Logo : l'escargot de Paris
Une spirale (la disposition des arrondissements de Paris) qui s'enroule vers un point : le temps, et l'événement au bout.
Le mot « Lotent » en Newsreader à côté. La spirale suit la couleur du texte ; le point est `--brand`.
- Géométrie unique : `web/src/logo-geometry.mjs` (utilisée par `web/src/logo.jsx` et par le script de marque).
- `cd web && npm run brand` régénère `icon.svg` (favicon clair/sombre), `apple-touch-icon.png`, `icon-192/512.png`, `icon-maskable-512.png` et `og.png`.
- Les images de partage générées chaque jour (`scraper/scrape.py`, accueil et institutions) utilisent le même dessin ; changer `OG_INST_VERSION` les refait toutes.

## Formes
- Rayon : 8 px sur les conteneurs, 6 px sur les contrôles.
- Pas d'ombres (`boxShadow` désactivé dans `tailwind.config.js`).
- Vignette d'un événement sans image : aplat teinté par la discipline, institution en serif.

## À éviter (signes d'une page générée)
Fond aurore, spotlight, bordures animées, marquee, compteurs qui montent, dock à loupe,
cartes identiques avec ombre douce, badges pilule partout, dégradé violet / bleu / rose.
Ces composants viennent de Magic UI / Aceternity : ne pas les réintroduire.

## Textes
Tutoiement, phrases courtes, rien de promotionnel. Un bouton dit ce qu'il fait (« Ajouter aux favoris », pas « Favori »).
Une panne ou un résultat vide dit ce qui s'est passé et propose une sortie (« Effacer les filtres », « Recharger »).

Un seul mot par notion :
- **Organisateur** (pas institution, établissement) pour qui organise ; **événement** pour ce qu'on compte, « conférence » seulement dans les accroches.
- **Gratuit** (pas « entrée libre »).
- **Agenda** = le site Lotent ; **calendrier** = l'application de la personne (« Ajouter à mon calendrier »).
- Nombres avec séparateur de milliers (« 2 480 » / « 2,480 »), via `t()` ou `fmtNum`, jamais bruts.
- Raccourci de recherche : `SHORTCUT` (`lib.js`), « ⌘K » sur Mac, « Ctrl K » ailleurs.
- Flèches ← → ↗ dans un libellé : passer par `<Arr text={…} />`, elles sont décoratives.
- Un bouton dont le mot disparaît sur téléphone garde un `aria-label`.

## Pas encore fait
- Les pages de partage `e/<id>.html` et `s/*.html` (générées par `scraper/scrape.py`) utilisent encore Geist.
