# Logo : pistes et logo actif

Le logo de Lotent est une **spirale qui s'enroule vers un point bleu** (le temps, et l'événement au bout).
Ce dossier garde toutes les pistes explorées, **dont le logo d'origine**, pour pouvoir changer d'avis.

| N° | Id | Idée |
|----|----|------|
| 00 | `original` | Le logo d'origine, « l'escargot de Paris » : trait régulier de 3,6, point rond |
| 01 | `crayon` | Crayon de cire : trait fin et tremblé |
| 02 | `argile` | Boudin d'argile : un gros colombin, bords irréguliers |
| 03 | `enfant` | Dessin d'enfant : plus de tours, traits inégaux, point gribouillé |
| 04 | `pinceau` | **Coup de pinceau (actif)** : fin au centre, gras à l'extérieur |
| 05 | `pate` | Pâte à modeler : ramassé et épais |
| 06 | `escargot` | Petit escargot : coquille, corps qui rampe, le point bleu fait la tête |

`index.html` est la planche de comparaison (clair, sombre, 28 px et 16 px). Les `.svg` sont les mêmes
logos, un par thème. Le logo d'origine exact (tracé Bézier) est dans `original-geometry.mjs`.

## Changer de logo

```bash
node logo-ideas/apply.mjs escargot     # écrit web/src/logo.json (le logo actif)
cd web && npm run brand                # icône, icônes mobiles, image de partage (og.png)
npm run build                          # en-tête de l'application (app.js)
```

Puis régénérer les pages statiques (le scraper le fait au prochain passage ; en local :
`python scraper/refresh_local.py` ou les fonctions `write_*_pages`) et mettre à jour `404.html` et
`apropos.html` (logo en ligne). Changer `OG_INST_VERSION` dans `scraper/scrape.py` refait les images
de partage des organisateurs.

## Retoucher une piste

Les formes sont calculées (bruit à graine fixe) dans `gen.mjs` : nombre de tours, rayon, épaisseur,
tremblement (`wr`, `wa`), graine (`seed`). `node logo-ideas/make.mjs` réécrit les SVG et la planche.

Le logo d'avant les pistes (spirale régulière) est aussi dans l'historique Git :
`git show 376ed0b11:web/src/logo-geometry.mjs`.
