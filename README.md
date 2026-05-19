# Conférences Académiques · Paris

Calendrier agrégé des conférences et séminaires académiques à Paris, mis à jour automatiquement chaque jour.

**Sources scraped :** Collège de France · ENS Paris · EHESS · Institut Henri Poincaré · Sciences Po · Sorbonne

## Mise en ligne (étapes)

### 1. Créer le repo GitHub

```bash
# Dans le dossier paris-conferences
git init
git add .
git commit -m "init: paris academic conferences site"
```

Puis sur [github.com/new](https://github.com/new) → créer un repo public (ex: `paris-conferences`), puis :

```bash
git remote add origin https://github.com/TON_USERNAME/paris-conferences.git
git branch -M main
git push -u origin main
```

### 2. Activer GitHub Pages

- Aller dans **Settings → Pages**
- Source : **Deploy from a branch**
- Branch : `main` / `/ (root)`
- Sauvegarder → le site sera disponible à `https://TON_USERNAME.github.io/paris-conferences`

### 3. Lancer le scraper manuellement (premier run)

- Aller dans **Actions → Daily Conference Scrape → Run workflow**
- Cela va peupler `data/events.json` avec les vraies données

Ensuite le scraper tourne automatiquement tous les jours à 6h (heure de Paris).

## Ajouter une nouvelle source

1. Dans `scraper/scrape.py`, ajouter une fonction `scrape_nom_institution()` en suivant le même pattern
2. L'ajouter à la liste `SCRAPERS`
3. La détection de discipline est automatique par mots-clés

## Structure

```
paris-conferences/
├── index.html              ← Site statique (1 seul fichier)
├── data/
│   └── events.json         ← Données (mises à jour par GitHub Actions)
├── scraper/
│   ├── scrape.py           ← Scraper Python multi-sources
│   └── requirements.txt
└── .github/
    └── workflows/
        └── daily-scrape.yml ← Tâche cron GitHub Actions
```

## Coût

**100 % gratuit** : GitHub Pages (hébergement) + GitHub Actions (2000 min/mois inclus, le scraper prend ~1 min/jour).
