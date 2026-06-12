# Paris·Académique

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
| Luma (Paris + 8 pages thématiques)  | interception des appels JSON         | Plateforme     |
| Article 1                           | capture remoting Salesforce          | Association    |
| Sciences et Cultures / Citoy.ENS    | Linktree → Framaforms (date dans l'URL) | Association |

Plus de 1 500 événements indexés depuis avril 2026.

## Le site

- Recherche tolérante aux accents et multi-mots, avec autocomplétion intervenants.
- Filtres : discipline, institution, format, date (« En ce moment », aujourd'hui, semaine, week-end).
- 4 onglets : **Tout / Universités / Luma / Association** + **Historique** (changement d'ambiance sépia).
- 3 vues : **Liste**, **Semaine** (grille lun→dim avec navigation), **Carte** (Leaflet).
- Bandeau **« Les immanquables de la semaine »** (sélection automatique pondérée).
- Bouton **dé** pour découvrir un événement au hasard parmi la sélection filtrée.
- Pastille **« N nouveaux »** depuis ta dernière visite (localStorage).
- Favoris, **partage natif mobile** (`navigator.share`), bouton « Près de moi ».
- En-tête dédié quand une seule institution est filtrée (lien officiel + iCal filtré).
- Bilingue **FR/EN**, raccourcis clavier (`/` pour chercher, `Échap` pour fermer).
- Page **À propos** avec stats publiques en temps réel.
- Installable comme application (PWA), consultable hors-ligne.

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
index.html              interface et logique du site
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
