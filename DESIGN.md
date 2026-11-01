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
Pas de couleur d'accent de marque tant qu'aucune n'est choisie.

## Formes
- Rayon : 8 px sur les conteneurs, 6 px sur les contrôles.
- Pas d'ombres (`boxShadow` désactivé dans `tailwind.config.js`).
- Vignette d'un événement sans image : aplat teinté par la discipline, institution en serif.

## À éviter (signes d'une page générée)
Fond aurore, spotlight, bordures animées, marquee, compteurs qui montent, dock à loupe,
cartes identiques avec ombre douce, badges pilule partout, dégradé violet / bleu / rose.
Ces composants viennent de Magic UI / Aceternity : ne pas les réintroduire.

## Pas encore fait
- Les pages de partage `e/<id>.html` et `s/*.html` (générées par `scraper/scrape.py`) utilisent encore Geist.
- Choisir une couleur d'accent propre à Lotent.
