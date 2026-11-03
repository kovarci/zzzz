// Applique une variante comme logo du site : écrit web/src/logo.json, lu par l'en-tête (logo.jsx),
// par web/scripts/brand.mjs (icônes, image de partage) et par scraper/scrape.py (pages générées).
// Usage : node logo-ideas/apply.mjs [id]      (sans argument : logo-ideas/active.json)
// Puis :  cd web && npm run brand && npm run build, et régénérer les pages (scraper).
import { readFileSync, writeFileSync } from "node:fs";
import { variants } from "./gen.mjs";

const here = (p) => new URL(p, import.meta.url);
const id = process.argv[2] || JSON.parse(readFileSync(here("./active.json"), "utf8")).id;
const v = variants.find((x) => x.id === id);
if (!v) { console.error("Variante inconnue :", id, "— choix :", variants.map((x) => x.id).join(", ")); process.exit(1); }
const { ink, dot } = v.build();
const nums = [...[...ink, ...dot].join(" ").matchAll(/(-?\d+\.?\d*),(-?\d+\.?\d*)/g)].map((m) => [+m[1], +m[2]]);
const bbox = { x0: Math.min(...nums.map((n) => n[0])), x1: Math.max(...nums.map((n) => n[0])), y0: Math.min(...nums.map((n) => n[1])), y1: Math.max(...nums.map((n) => n[1])) };
// cadre carré centré sur le dessin, avec une marge de 2 unités
const size = Math.max(bbox.x1 - bbox.x0, bbox.y1 - bbox.y0) + 4;
const view = [+((bbox.x0 + bbox.x1) / 2 - size / 2).toFixed(1), +((bbox.y0 + bbox.y1) / 2 - size / 2).toFixed(1), +size.toFixed(1)];
writeFileSync(here("../web/src/logo.json"), JSON.stringify({ id, name: v.name, ink, dot, bbox, view }) + "\n");
writeFileSync(here("./active.json"), JSON.stringify({ id }) + "\n");
console.log("Logo actif :", id, "—", v.name, "— cadre", JSON.stringify(view));
