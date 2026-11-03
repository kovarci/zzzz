// Applique une variante comme logo du site : écrit web/src/logo.json, lu par l'en-tête (logo.jsx),
// par web/scripts/brand.mjs (icônes, image de partage) et par scraper/scrape.py (pages générées),
// et réécrit le logo de l'écran de chargement dans index.html (entre <!--logo:start--> et <!--logo:end-->).
// Usage : node logo-ideas/apply.mjs [id]      (sans argument : logo-ideas/active.json)
// Puis :  cd web && npm run brand && npm run build, et régénérer les pages (scraper).
import { readFileSync, writeFileSync } from "node:fs";
import { variants } from "./gen.mjs";

const here = (p) => new URL(p, import.meta.url);
const id = process.argv[2] || JSON.parse(readFileSync(here("./active.json"), "utf8")).id;
const v = variants.find((x) => x.id === id);
if (!v) { console.error("Variante inconnue :", id, "— choix :", variants.map((x) => x.id).join(", ")); process.exit(1); }
const { ink, dot, spine } = v.build();
const nums = [...[...ink, ...dot].join(" ").matchAll(/(-?\d+\.?\d*),(-?\d+\.?\d*)/g)].map((m) => [+m[1], +m[2]]);
const bbox = { x0: Math.min(...nums.map((n) => n[0])), x1: Math.max(...nums.map((n) => n[0])), y0: Math.min(...nums.map((n) => n[1])), y1: Math.max(...nums.map((n) => n[1])) };
// cadre carré centré sur le dessin, avec une marge de 2 unités
const size = Math.max(bbox.x1 - bbox.x0, bbox.y1 - bbox.y0) + 4;
const view = [+((bbox.x0 + bbox.x1) / 2 - size / 2).toFixed(1), +((bbox.y0 + bbox.y1) / 2 - size / 2).toFixed(1), +size.toFixed(1)];
writeFileSync(here("../web/src/logo.json"), JSON.stringify({ id, name: v.name, ink, dot, spine: spine || null, bbox, view }) + "\n");
writeFileSync(here("./active.json"), JSON.stringify({ id }) + "\n");

// Écran de chargement : si la variante a une ligne médiane (spine), la spirale se « dessine » (masque animé) ; sinon elle apparaît d'un bloc.
const [vx, vy, vs] = view;
const mask = spine ? `<defs><mask id="sp-m" maskUnits="userSpaceOnUse" x="${vx}" y="${vy}" width="${vs}" height="${vs}"><path class="drawp" d="${spine}" pathLength="1" fill="none" stroke="#fff" stroke-width="11" stroke-linecap="round"/></mask></defs>` : "";
const svg = `<svg class="sp-logo" viewBox="${vx} ${vy} ${vs} ${vs}" width="84" height="84" aria-hidden="true">${mask}<g fill="currentColor"${spine ? ' mask="url(#sp-m)"' : ""}>${ink.map((d) => `<path d="${d}"/>`).join("")}</g><g class="dot" fill="hsl(var(--brand))">${dot.map((d) => `<path d="${d}"/>`).join("")}</g></svg>`;
const f = here("../index.html");
const html = readFileSync(f, "utf8");
const re = /<!--logo:start-->[\s\S]*?<!--logo:end-->/;
if (re.test(html)) { writeFileSync(f, html.replace(re, () => `<!--logo:start-->${svg}<!--logo:end-->`)); console.log("écran de chargement mis à jour"); }
else console.log("index.html : repères <!--logo:start--> / <!--logo:end--> absents, écran de chargement inchangé");
console.log("Logo actif :", id, "—", v.name, "— cadre", JSON.stringify(view));
