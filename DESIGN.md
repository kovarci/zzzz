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

## Pages statiques (e/, i/, d/, s/, p/, 404)
Générées chaque jour par `scraper/scrape.py` (`_hub_page`, `write_event_pages`), sans JavaScript sauf le filtre par
discipline et la recherche de l'annuaire. Même charte que l'application, dans **`pages.css`** (un seul fichier, versionné
par un hachage dans l'URL) : mêmes jetons zinc clair / sombre, thème mémorisé (`paf_theme`), Newsreader + Instrument Sans.
- **Un programme, pas des cartes** : les événements sont groupés par jour (titre en serif), une ligne par événement
  (heure, titre, organisateur · lieu, discipline), vignette à droite si elle existe. Pas d'aplat vide quand il n'y a pas d'image.
- **À la une** (3 événements avec image, organisateurs différents) et **barre des jours** (liens d'ancre, sans JavaScript)
  au-dessus des listes de 12 événements ou plus ; puces de discipline pour filtrer (JavaScript).
- **Par organisateur** sur les sélections et les disciplines : maillage vers les pages `i/`.
- La page `s/gratuites.html` est la plus visitée : ne pas la surcharger, la garder rapide (≈ 190 Ko pour 400 événements).
- Cibles de 44 px au tactile, bordure de contrôle à 3:1 (`--control`), lien « Aller au contenu », un seul `<h1>`.
- Le lien officiel d'une page événement porte la classe `ext` : `write_event_pages` s'en sert pour rediriger un événement renommé.
- **Jamais de 404 pour un ancien événement** : une fiche de plus d'un an (ou retirée par sa source) devient une page
  « Événement passé » (`_past_stub`, `noindex`, sans redirection automatique, avec « Voir l'agenda » et une recherche
  préremplie) au lieu d'être supprimée. `404.html` dit la même chose pour les liens `/e/…` restants.
- **`apropos.html`** (+ `apropos.css`, `apropos.js`) est la démonstration technique du site : pipeline en cinq étapes,
  carte des lieux, répartitions, générateur d'abonnement `.ics`, poids du premier affichage, pile. Aucun chiffre n'y est
  écrit à la main : tout vient de `data/meta.json` et `data/site.json` (`write_site_stats`, à chaque passage du scraper).
