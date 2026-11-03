// Écrit un SVG par variante et par thème, et une planche de comparaison (index.html).
import { writeFileSync } from "node:fs";
import { variants, svg } from "./gen.mjs";

const cards = variants.map((v, i) => {
  const num = v.num ?? i;
  writeFileSync(`${String(num).padStart(2, "0")}-${v.id}-sombre.svg`, svg(v, "dark"));
  writeFileSync(`${String(num).padStart(2, "0")}-${v.id}-clair.svg`, svg(v, "light"));
  const small = (m, px) => svg(v, m).replace('width="64" height="64"', `width="${px}" height="${px}"`);
  return `<article><h2>${num}. ${v.name}</h2><p>${v.note}</p>
  <div class="row"><div class="tile dark">${small("dark", 128)}</div><div class="tile light">${small("light", 128)}</div></div>
  <div class="row sm"><div class="tile dark"><span>${small("dark", 28)}<b>Lotent</b></span><span>${small("dark", 16)}</span></div><div class="tile light"><span>${small("light", 28)}<b>Lotent</b></span><span>${small("light", 16)}</span></div></div></article>`;
}).join("\n");
writeFileSync("index.html", `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Pistes de logo</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;padding:2rem;background:#0a0a0b;color:#f4f4f5;font:16px/1.5 system-ui,sans-serif}h1{font:500 2rem Georgia,serif;margin:0 0 .25rem}p.lead{color:#a1a1aa;margin:0 0 2rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(22rem,1fr));gap:2rem}article h2{font:500 1.25rem Georgia,serif;margin:0}article p{margin:.25rem 0 .75rem;color:#a1a1aa;font-size:.9rem}
.row{display:grid;grid-template-columns:1fr 1fr;gap:.5rem;margin-bottom:.5rem}.tile{display:flex;align-items:center;justify-content:center;gap:1rem;border-radius:8px;padding:1.25rem}
.tile.dark{background:#111113;border:1px solid #27272a}.tile.light{background:#fff;border:1px solid #e4e4e7;color:#09090b}.sm .tile{padding:.75rem}.tile span{display:inline-flex;align-items:center;gap:.5rem}
.tile b{font:500 1.5rem Georgia,serif}.dark b{color:#f4f4f5}</style></head><body><h1>Pistes de logo</h1><p class="lead">Même idée (une spirale, un point bleu), tracé moins parfait. Clair, sombre, et tailles d’icône.</p><div class="grid">${cards}</div></body></html>`);
console.log(variants.length + " variantes écrites");
