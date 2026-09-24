# Lotent

Un site qui rassemble toutes les conférences et séminaires académiques de Paris
dans un seul calendrier filtrable, mis à jour chaque jour.

- Site : <https://lotent.fr>
- Dépôt : <https://github.com/kovarci/zzzz>

## Fonctionnement

Une GitHub Action s'exécute chaque matin (4h UTC). Elle lance un scraper Python
qui récupère les événements sur les sites des sources, écrit `data/events.json`
+ fichiers annexes, et committe le tout. La page `index.html` lit ces JSON et
les affiche.

Pour deux sources (Collège de France, pages Luma par thème) le robot GitHub est
bloqué par géolocalisation IP : un rafraîchissement complémentaire est lancé
chaque semaine depuis une connexion française (voir [Rafraîchissement local](#rafraîchissement-local)).

L'hébergement (GitHub Pages) et l'automatisation (GitHub Actions) sont gratuits
pour un dépôt public. Le domaine `lotent.fr` est branché via le fichier `CNAME`.

## Sources

| Source                              | Méthode                              | Type           |
|-------------------------------------|--------------------------------------|----------------|
| Institut Henri Poincaré             | API Indico                           | Institution    |
| Collège de France                   | requests + headers navigateur        | Institution    |
| Paris School of Economics           | scraping HTML paginé                 | Institution    |
| Université PSL                      | scraping HTML paginé                 | Institution    |
| EHESS                               | parseur dédié (Playwright)           | Institution    |
| Sciences Po                         | scraping HTML paginé                 | Institution    |
| ENS Paris                           | scraping HTML paginé                 | Institution    |
| Sorbonne Université                 | parseur dédié                        | Institution    |
| Université Paris Cité               | cartes HTML (All-in-One Calendar)    | Institution    |
| Paris 1 Panthéon-Sorbonne (agenda + recherche), Paris-Panthéon-Assas, Paris-Saclay | cartes HTML | Institution |
| Campus Condorcet, IEA de Paris, FMSH | cartes HTML                         | Recherche      |
| Musée du quai Branly (colloques + salon de lecture) | cartes HTML          | Musée          |
| Musée du Louvre (conférences, colloques) | données Next.js, mois par mois | Musée          |
| Centre Pompidou (rencontres hors les murs) | cartes HTML               | Musée          |
| ENS : maths (API The Events Calendar), ITEM, CIENS, CERES | cartes HTML / pages séminaires | Institution |
| HEC Paris                           | cartes HTML paginées (hors webinaires) | École       |
| Hi! PARIS, PR[AI]RIE                | API The Events Calendar / cartes HTML | Recherche IA |
| Université Ouverte (Paris Cité)     | articles « Conférences gratuites »   | Institution    |
| Les Mardis de la Philo              | programme des cycles (Webflow)       | Conférences    |
| HEC IA                              | cartes HTML                          | Association    |
| INHA, Institut du monde arabe, Beaux-Arts de Paris, École des chartes | cartes HTML | Culture / Institution |
| Ifri (« Sur invitation » → 🔒), IRIS, Institut Jacques Delors, Fondation Jean-Jaurès | cartes HTML | Think tanks |
| Institut Louis Bachelier, Citéco, ESCP | cartes HTML (Webflow / Drupal) | Économie & finance |
| ENS Paris-Saclay                    | cartes HTML (Scène de recherche)     | Institution    |
| Université Sorbonne Paris Nord      | JSON-LD schema.org (`scrape_jsonld`) | Institution    |
| Université Sorbonne Nouvelle        | listes annuelles des colloques       | Institution    |
| Université Paris 8                  | frise de la page d'accueil (~1 mois) | Institution    |
| Université Paris Nanterre           | export iCal de l'agenda              | Institution    |
| EPHE, Inalco, Cnam                  | cartes HTML                          | Institution    |
| Académie des sciences               | cartes HTML                          | Institution    |
| Institut Pasteur, Institut Curie, Institut du Cerveau | cartes HTML        | Recherche      |
| Muséum (MNHN), Cité des sciences    | cartes HTML, conférences seulement   | Musée          |
| BnF                                 | agenda filtré « Conférences »        | Bibliothèque   |
| Collège des Bernardins              | cartes HTML (Webflow)                | Lieu de débat  |
| Luma (Paris + 8 pages thématiques)  | interception des appels JSON         | Plateforme     |
| Article 1                           | capture remoting Salesforce          | Association    |
| Sciences et Cultures / Citoy.ENS    | Linktree → Framaforms (date dans l'URL) | Association |
| Que faire à Paris (Ville de Paris)  | API open data, tag « Conférence »    | Ville (`source_type: ville`) |
| IJCLab, IN2P3 (LPNHE, APC…), Observatoire de Paris | API Indico (tranches de 60 j, sans réunions internes) | Laboratoire |
| Sciencesconf.org                    | liste des colloques à venir (~3 semaines) + fiche, filtre Île-de-France | Plateforme |

Les **soutenances** de thèse / HDR (repérées au titre, toutes sources) portent `kind: "soutenance"` :
masquées du fil principal, affichées par le bouton « 🎓 Soutenances » (`?soutenances=1`).

**Carrières** (`kind: "carriere"`, bouton « 💼 Carrières », `?carrieres=1`) : événements de
recrutement étudiants à Paris, façon Trackr.
- `scraper/carrieres.json` : ~55 recruteurs suivis (banque, conseil, audit, luxe, industrie, tech)
  et les événements **vérifiés sur une page officielle** (salons, ateliers, soirées…).
- Portails **Eightfold** (BCG, Kering, Morgan Stanley, HSBC, Accenture, EY, Citi) lus chaque jour
  par l'API publique (`/api/events/open/list`, autorisée par leur robots.txt), filtrés Île-de-France.
- Une recherche hebdomadaire (tâche Claude planifiée) ajoute les nouveaux événements au fichier.

**Réservé aux membres** : `members: true` (Article 1 hors public « Extérieur », rencontres de membres des
Jeunes IHEDN, phrases « réservé aux adhérents / membres only… » repérées sur toutes les sources, champ
`"membres": true` des fichiers vérifiés) → badge 🔒 et filtre « Accès » (`?acces=public|membres`).

**Associations étudiantes** (source_type `association`) : Article 1 et Sciences et Cultures (scrapers
dédiés), Jeunes IHEDN (agenda de leur site ; bloque les IP de data-center → lu par le
rafraîchissement local), et `scraper/associations.json` pour celles qui ne
publient que sur Instagram / LinkedIn / Eventbrite (Taureaux du Panthéon…) ou sur leur site
(Open Diplomacy…) : liste suivie + événements publics vérifiés, enrichis par la même recherche
hebdomadaire.

Plus de 1 500 événements indexés depuis avril 2026.

## Le site

Front **React 18 + Tailwind + Framer Motion** (dossier `web/`), compilé en deux fichiers statiques
commités à la racine : `app.js` et `app.css`. GitHub Pages ne build rien.

- **Hero** : compteurs animés (aujourd'hui / semaine / week-end), marquee des institutions.
- **À la une** : bento avec la sélection éditoriale de la semaine (`data/digest.json`), « Ce soir »
  et le graphique des 7 prochains jours.
- **Filtres** : période (dont « Nouveautés » = ajoutés depuis 48 h), discipline, institution,
  source + thèmes Luma, favoris, « En ligne ». L'état est dans l'URL (`?date=…&discipline=…`),
  mêmes clés que l'ancien site : les liens partagés restent valides.
- **3 vues** : Liste (groupée par jour), Semaine (lun→dim), Carte (Leaflet + OSM).
- **Historique** : bouton central du dock, archive chargée à la demande, filtre par mois.
- **Dock** flottant : haut de page, aujourd'hui, historique, au hasard, favoris, recherche.
- **Recherche ⌘K / Ctrl+K** avec navigation clavier.
- **Fiche** latérale : page officielle / inscription, favori, ajout à l'agenda (Google ou .ics),
  partage (lien `e/<id>.html`).
- **Sélection** : coche plusieurs événements, exporte un `.ics` personnalisé.
- **Près de moi** : tri par distance (géolocalisation navigateur), position sur la carte.
- Favoris et thème mémorisés (`paf_favs`, `paf_theme`), lien profond `?event=<id>`.
- Installable comme application (PWA), consultable hors-ligne.

### Modifier le front

```
cd web
npm install          # une seule fois
npm run build        # → ../app.js + ../app.css (à commiter)
npm run watch        # rebuild à chaque modification
```

Après un build, incrémente `?v=` sur `app.js` / `app.css` dans `index.html` et la constante
`CACHE` de `sw.js`, sinon les visiteurs gardent l'ancienne version en cache.

## SEO & partage

- `sitemap.xml` (1 500+ URLs) et `robots.txt`.
- Une page par événement (`e/<id>.html`) avec **JSON-LD schema.org Event** complet
  → résultats enrichis Google (date + lieu + intervenant directement visibles).
- Balises **Open Graph** + image de partage `og.png` (1200×630).
- Liens de partage stables (`?event=<id>`).
- Flux **iCal** global et **par institution** (`data/cal/<slug>.ics`).
- Flux **RSS** des immanquables (`data/digest.xml`).
- Hashes **SRI** sur Leaflet.

## Limites connues

- Université Paris Dauphine : aucun événement (page en carrousels, sans dates exploitables).
- Muséum (MNHN) et Académie des sciences : comme le Collège de France, ils refusent les IP de
  data-center (403). Récupérés par le rafraîchissement local ; le filet de sécurité les garde
  entre deux passages.
- Inria Paris : non intégré, le site est protégé par un anti-robot (Anubis) qu'on ne contourne pas.
- Cnam : son agenda public ne liste que très peu d'événements (souvent 0 ou 1).
- Université Paris 8 : pas d'agenda central, seule la frise de la page d'accueil (~1 mois) est lue.
- EHESS et Sorbonne : peu d'événements (pages d'agenda courtes).
- Collège de France : son CDN (BunnyCDN) bloque les IP de data-center. Le robot GitHub
  reçoit 0 événement ; les conférences sont récupérées depuis une connexion française.
  Entre deux rafraîchissements, le filet de sécurité conserve les événements déjà connus.
- Luma : depuis le serveur GitHub, seule la page « Paris » donne des résultats. Les pages
  par thème sont géolocalisées par IP et renvoient des événements américains. Depuis une
  connexion française, le rafraîchissement local récupère aussi ces pages.
- Le classement par discipline repose sur des mots-clés ; il est approximatif.
- Un événement n'apparaît sur la carte que si son adresse a pu être géocodée.

## Rafraîchissement local

Le Collège de France et les pages Luma par thème sont bloqués ou faussés depuis le
serveur GitHub. Un script les récupère depuis une connexion française, à lancer environ
une fois par semaine.

Le plus simple : **double-cliquer sur `maj.bat`** (il enchaîne les étapes ci-dessous,
puis ouvre GitHub pour confirmer la connexion). Sinon, à la main :

```
git pull
python scraper/refresh_local.py
git add data/ e/ sitemap.xml
git commit -m "maj manuelle (College de France + Luma)"
git push
```

Le tout peut être planifié via le **Planificateur de tâches Windows** (déjà configuré
chaque dimanche 10h sur la machine du mainteneur). La première fois seulement, installer
le navigateur utilisé par Luma :

```
python -m playwright install chromium
```

Si une source ne répond pas, le script conserve les données précédentes au lieu de les
effacer. Les autres sources ne sont pas touchées : le robot GitHub continue de les
mettre à jour chaque jour.

## Utilisation

Le scrape est automatique, tous les jours à 4h UTC. Pour le lancer à la main :
onglet **Actions** → « Daily Conference Scrape » → « Run workflow ».

Pour modifier le site, éditer `index.html` et pousser : GitHub Pages redéploie
automatiquement.

Pour ajouter une source, écrire une fonction dans `scraper/scrape.py` et l'ajouter à
la liste dans `main()`. Le filet de sécurité couvre automatiquement les sources `KNOWN_SOURCES`,
`source_type == "luma"` et `source_type == "association"`.

## Structure

```
index.html              coquille SEO + contenu de secours, charge app.js
app.js, app.css         front compilé (ne pas éditer : voir web/)
web/                    sources du front (React) — src/main.jsx, ui.jsx, lib.js
                        legacy-index.html = ancien site, conservé pour référence
apropos.html            page « À propos » (bilingue FR/EN, stats vivantes)
manifest.json, sw.js    configuration de l'application installable
icon.svg, og.png        icônes et image de partage
maj.bat                 rafraîchissement manuel en un double-clic (Windows)
sitemap.xml             généré par le scraper
robots.txt              renvoie vers sitemap.xml
CNAME                   domaine personnalisé (lotent.fr)
data/
  events.json           événements à venir (minifié)
  events-archive.json   événements passés (1 an, minifié)
  geocache.json         cache des coordonnées géographiques
  meta.json             dernières dates d'exécution (auto / Windows)
  calendar.ics          flux iCal global
  cal/<slug>.ics        flux iCal par institution
  digest.json           top 10 « immanquables » de la semaine
  digest.xml            même chose en RSS
e/
  <id>.html             page de partage par événement (1 500+, JSON-LD)
scraper/
  scrape.py             scraper principal (sources + helpers)
  refresh_local.py      rafraîchissement manuel (Collège de France + Luma)
  check_health.py       contrôle des sources après le scrape
  requirements.txt
.github/workflows/
  daily-scrape.yml      tâche quotidienne
```

## Coût

Aucun. GitHub Pages, GitHub Actions et le domaine `.fr` (renouvelable) sont les seuls
coûts ; le reste est gratuit pour un dépôt public.
