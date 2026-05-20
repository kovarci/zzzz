# Conférences Académiques · Paris

Un site web qui agrège **toutes les conférences et séminaires académiques de Paris**
dans un seul calendrier filtrable, mis à jour **automatiquement chaque jour**.

🔗 **En ligne :** https://kovarci.github.io/zzzz
📦 **Dépôt :** https://github.com/kovarci/zzzz

---

## Comment ça marche

```
┌─────────────────┐   chaque jour à 6h    ┌──────────────────┐
│ GitHub Actions  │ ────────────────────► │  scraper Python  │
│  (cron gratuit) │                       │  (scrape.py)     │
└─────────────────┘                       └────────┬─────────┘
                                                   │ écrit
                                                   ▼
                                          ┌──────────────────┐
┌─────────────────┐    lit le JSON        │ data/events.json │
│  index.html     │ ◄──────────────────── │  (commit auto)   │
│ (GitHub Pages)  │                       └──────────────────┘
└─────────────────┘
```

1. Un **workflow GitHub Actions** se déclenche tout seul chaque matin (`cron`).
2. Le **scraper Python** visite les sites des institutions et écrit `data/events.json`.
3. Le bot **commit** le fichier mis à jour.
4. **GitHub Pages** sert `index.html`, qui lit ce JSON et affiche le calendrier.

Le tout **100 % gratuit** : Pages + Actions sont gratuits pour un dépôt public.

---

## ✅ Ce qui a été fait

### Sources agrégées (8 institutions + Luma)

| Source | Événements | Méthode |
|---|---|---|
| Institut Henri Poincaré | ~180 | API Indico (JSON), filtrée Paris |
| Collège de France | ~113 | Scraping HTML paginé |
| Paris School of Economics | ~95 | Scraping HTML paginé (`/page/N/`) |
| Université PSL | ~38 | Scraping HTML paginé |
| EHESS | ~18 | Parseur dédié (`.jnews-event-card`) |
| Sciences Po | ~16 | Scraping HTML paginé |
| ENS Paris | ~13 | Scraping HTML paginé |
| Sorbonne Université | ~7 | Parseur dédié (`.thumbnail`) |
| Luma | ~37 | Interception JSON + `__NEXT_DATA__`, filtré France |

### Le scraper (`scraper/scrape.py`)

- **Playwright** (navigateur sans interface) pour les sites en JavaScript.
- **Plusieurs stratégies** selon le site : API Indico, interception réseau,
  JSON-LD, balises `<time datetime>`, attributs `data-*`, texte en français.
- **Pagination universelle** : essaie `?page=N` *et* `/page/N/`.
- **Parsing de dates françaises** : « 3 juin 2026 », « 10 Sep. 2026 », « 20/05/26 »…
- **Classement automatique par discipline** (mots-clés) : Mathématiques,
  Philosophie, Littérature, Histoire, Sciences, Économie, Sociologie,
  Droit & Sciences politiques, Arts & Culture.
- **Filtre Paris** : exclut les événements hors région parisienne.
- Filtre les événements passés, déduplique.

### Le site (`index.html`)

- Design **glassmorphism** : thème sombre, fond « aurora » animé, cartes en
  verre translucide, effet **3D au survol** (la carte s'incline + reflet).
- **Recherche** par titre / intervenant / sujet.
- **Filtres** : discipline, institution, période (Aujourd'hui · Cette semaine ·
  Ce week-end), format (en ligne / présentiel).
- **Onglets** : Tout · Universités · Luma.
- **Ajouter à mon agenda** : bouton Google Agenda + fichier `.ics`
  (Apple Calendar / Outlook) sur chaque événement.
- **Favoris** : une étoile pour sauvegarder des événements (gardés dans le
  navigateur via `localStorage`).
- Entièrement **responsive** (mobile/desktop).

### Automatisation

- Scrape quotidien automatique à 6h — **aucun clic nécessaire**.
- Déclenchement manuel possible (Actions → Run workflow).

---

## ❌ Ce qui n'a PAS été fait (et pourquoi)

### Limites de couverture

- **Université Paris Dauphine — 0 événement.** Sa page « événements à venir »
  est construite en **carrousels** sans dates lisibles par une machine.
  Impossible à parser de façon fiable.
- **EHESS — ~18 seulement.** Sa page agenda contient ~500 cartes, mais ~480
  sont des événements **passés** ou des articles. 18 est le vrai nombre
  d'événements *à venir* sur cette page.
- **Sorbonne — ~7 seulement.** Sa page `/evenements` est une page **curée**
  qui n'affiche qu'une quinzaine d'événements au total, pas un agenda complet.
- **ENS / Sciences Po — ~13-16.** Reflète ce que publient leurs pages
  d'agenda principales.

### Luma

- **Catégories Luma (tech, ai, arts…) — non récupérables.** Luma géolocalise
  par **adresse IP**. Le serveur GitHub étant aux États-Unis, ces pages ne
  renvoient que des événements américains. Contournable uniquement avec un
  **proxy français payant** — non rentable pour du contenu non-académique.
- **Événements Luma « non listés » — impossibles.** Par conception, ils
  n'apparaissent dans aucune API ni recherche : accessibles uniquement avec
  le lien direct. Personne ne peut les énumérer.

### Fonctionnalités non incluses

- **Pas de vue calendrier** (grille mensuelle) — retirée car illisible avec
  500+ événements ; la vue liste groupée par jour est plus claire.
- **Pas de pages de détail** — cliquer un événement ouvre le site source.
- **Pas de carte** des événements (géocodage non implémenté).
- **Pas de notifications / newsletter.**
- **Classement par discipline approximatif** — basé sur des mots-clés, donc
  quelques événements peuvent tomber dans « Autre » ou la mauvaise catégorie.

---

## Utilisation

### Mettre à jour le site

Le scrape est **automatique**. Pour forcer une mise à jour :
**Actions → Daily Conference Scrape → Run workflow**.

Modifier le design (`index.html`) : il suffit de pousser le fichier,
GitHub Pages redéploie tout seul.

```bash
git add .
git commit -m "votre message"
git push
```

### Ajouter une source

Dans `scraper/scrape.py` :
- Site avec pagination classique → ajouter une fonction qui appelle
  `scrape_paginated(...)`.
- Site complexe → écrire un parseur dédié (voir `scrape_ehess` / `scrape_sorbonne`).
- Puis ajouter la fonction à la liste dans `main()`.

---

## Structure du projet

```
paris-conferences/
├── index.html               ← Site (design + logique, un seul fichier)
├── data/
│   └── events.json           ← Données (mises à jour par le bot)
├── scraper/
│   ├── scrape.py             ← Scraper multi-sources
│   └── requirements.txt
└── .github/workflows/
    └── daily-scrape.yml      ← Tâche cron quotidienne
```

## Coût

**0 € / mois.** Dépôt public → GitHub Pages (hébergement) et GitHub Actions
(scraper quotidien, ~10 min/jour) sont entièrement gratuits et sans limite.
