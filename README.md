# Conférences académiques à Paris

Un site qui rassemble les conférences et séminaires académiques de Paris sur
une seule page, mis à jour chaque jour.

- Site : https://kovarci.github.io/zzzz
- Dépôt : https://github.com/kovarci/zzzz

## Fonctionnement

Une GitHub Action s'exécute chaque matin. Elle lance un scraper Python qui
récupère les événements sur les sites des institutions, écrit
`data/events.json` et committe le fichier. La page `index.html` lit ce JSON
et l'affiche.

L'hébergement (GitHub Pages) et l'automatisation (GitHub Actions) sont
gratuits pour un dépôt public.

## Sources

| Source                    | Méthode                       |
|---------------------------|-------------------------------|
| Institut Henri Poincaré   | API Indico                    |
| Collège de France         | scraping HTML (requests)      |
| Paris School of Economics | scraping HTML paginé          |
| Université PSL            | scraping HTML paginé          |
| EHESS                     | parseur dédié                 |
| Sciences Po               | scraping HTML paginé          |
| ENS Paris                 | scraping HTML paginé          |
| Sorbonne Université       | parseur dédié                 |
| Luma                      | interception des appels JSON  |

Le total tourne autour de 500 événements à venir ; le détail par source
change à chaque scrape.

## Le site

- Recherche par titre, intervenant ou sujet.
- Filtres : discipline, institution, date, format (présentiel ou en ligne).
- Vue liste et vue carte.
- Favoris, enregistrés dans le navigateur.
- Ajout à un agenda : Google Agenda ou fichier `.ics` par événement.
- Flux d'abonnement iCal (`data/calendar.ics`).
- Les filtres sont conservés dans l'URL, ce qui rend les liens partageables.
- Installable comme application (PWA) et consultable hors-ligne.

## Limites connues

- Université Paris Dauphine : aucun événement. Sa page est construite en
  carrousels, sans dates exploitables par le scraper.
- EHESS et Sorbonne : peu d'événements. Leurs pages d'agenda sont courtes,
  ou contiennent surtout des événements passés.
- Collège de France : son CDN (BunnyCDN) bloque les IP de data-center. Le
  robot GitHub reçoit donc 0 événement ; les conférences sont récupérées
  depuis une connexion française (voir « Rafraîchissement local »). Entre
  deux rafraîchissements, le filet de sécurité conserve les événements déjà
  connus.
- Luma : depuis le serveur GitHub, seule la page « Paris » donne des
  résultats. Les pages par thème sont géolocalisées par IP et renvoient des
  événements américains. Depuis une connexion française, le rafraîchissement
  local récupère aussi ces pages.
- Le classement par discipline repose sur des mots-clés ; il est approximatif.
- Un événement n'apparaît sur la carte que si son adresse a pu être géocodée.

## Rafraîchissement local

Le Collège de France et les pages Luma par thème sont bloqués ou faussés
depuis le serveur GitHub (géolocalisation par IP). Un script les récupère
depuis une connexion française. À lancer environ une fois par semaine :

```
git pull
python scraper/refresh_local.py
git add data/events.json data/calendar.ics
git commit -m "maj manuelle (College de France + Luma)"
git push
```

La première fois seulement, installer le navigateur utilisé par Luma :

```
python -m playwright install chromium
```

Si une source ne répond pas, le script conserve les données précédentes au
lieu de les effacer. Les autres sources ne sont pas touchées : le robot
GitHub continue de les mettre à jour chaque jour.

## Utilisation

Le scrape est automatique, tous les jours à 6h. Pour le lancer à la main :
onglet Actions, puis « Daily Conference Scrape », puis « Run workflow ».

Pour modifier le site, éditer `index.html` et pousser : GitHub Pages
redéploie automatiquement.

Pour ajouter une source, écrire une fonction dans `scraper/scrape.py` et
l'ajouter à la liste dans `main()`.

## Structure

```
index.html              interface et logique du site
manifest.json, sw.js    configuration de l'application installable
icon.svg                icône de l'application
data/
  events.json           données, régénérées par le scraper
  geocache.json         cache des coordonnées géographiques
  calendar.ics          flux d'abonnement
scraper/
  scrape.py             scraper
  refresh_local.py      rafraîchissement manuel (Collège de France + Luma)
  check_health.py       contrôle des sources après le scrape
  requirements.txt
.github/workflows/
  daily-scrape.yml      tâche quotidienne
```

## Coût

Aucun. GitHub Pages et GitHub Actions sont gratuits pour un dépôt public.
