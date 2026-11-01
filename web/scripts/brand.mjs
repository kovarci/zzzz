/* Régénère l'identité visuelle depuis la géométrie de la marque (src/logo-geometry.mjs) :
   ../icon.svg, apple-touch-icon.png, icon-192/512.png, icon-maskable-512.png, og.png.
   Usage : npm run brand   (télécharge Newsreader et Instrument Sans dans .cache/ la première fois) */
import fs from "node:fs";
import path from "node:path";
import { Resvg } from "@resvg/resvg-js";
import { SPIRAL, END } from "../src/logo-geometry.mjs";

const root = path.resolve(import.meta.dirname, "..", "..");
const cache = path.resolve(import.meta.dirname, "..", ".cache", "fonts");
fs.mkdirSync(cache, { recursive: true });

// ── polices (Google Fonts, TTF) ──────────────────────────────────────────
async function font(family, weight, file) {
  const f = path.join(cache, file);
  if (fs.existsSync(f)) return f;
  const css = await (await fetch(`https://fonts.googleapis.com/css2?family=${family}:wght@${weight}`)).text();
  const url = [...css.matchAll(/url\((https:[^)]+\.ttf)\)/g)].pop()?.[1];
  if (!url) throw new Error("police introuvable : " + family);
  fs.writeFileSync(f, Buffer.from(await (await fetch(url)).arrayBuffer()));
  return f;
}
const fontFiles = [await font("Newsreader", 500, "Newsreader-500.ttf"), await font("Instrument+Sans", 400, "InstrumentSans-400.ttf")];

const INK = "#f4f4f5", DOT = "#8CA7FF";
const png = (svg, w, out, opts = {}) => fs.writeFileSync(path.join(root, out),
  new Resvg(svg, { fitTo: { mode: "width", value: w }, font: { fontFiles, loadSystemFonts: false, defaultFontFamily: "Instrument Sans" }, ...opts }).render().asPng());

// ── icône carrée : spirale centrée sur fond sombre ───────────────────────
const icon = (size, { round, scale }) => {
  const s = size * scale / 48.6, cx = 34.4, cy = 29.6;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
<rect width="${size}" height="${size}" ${round ? `rx="${size * 0.22}"` : ""} fill="#111113"/>
<g transform="translate(${size / 2} ${size / 2}) scale(${s}) translate(${-cx} ${-cy})">
<path d="${SPIRAL}" fill="none" stroke="${INK}" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="${END[0]}" cy="${END[1]}" r="5.2" fill="${DOT}"/></g></svg>`;
};
png(icon(512, { round: true, scale: 0.62 }), 180, "apple-touch-icon.png");
png(icon(512, { round: true, scale: 0.62 }), 192, "icon-192.png");
png(icon(512, { round: true, scale: 0.62 }), 512, "icon-512.png");
png(icon(512, { round: false, scale: 0.48 }), 512, "icon-maskable-512.png");   // zone de sécurité du « maskable »

// ── favicon SVG : sans fond, clair ou sombre selon l'onglet ──────────────
fs.writeFileSync(path.join(root, "icon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="7.5 3.5 54 54">
  <style>.s{stroke:#111113}.d{fill:#2B4DB5}@media (prefers-color-scheme:dark){.s{stroke:${INK}}.d{fill:${DOT}}}</style>
  <path class="s" d="${SPIRAL}" fill="none" stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round"/>
  <circle class="d" cx="${END[0]}" cy="${END[1]}" r="5.4"/>
</svg>
`);

// ── image de partage 1200×630 ────────────────────────────────────────────
const total = JSON.parse(fs.readFileSync(path.join(root, "data", "m", "index.json"), "utf8")).total;
const label = total >= 200 ? `Plus de ${Math.floor(total / 100) * 100}`.replace(/\B(?=(\d{3})+(?!\d))/g, " ") : String(total);
const og = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#111113"/>
<g transform="translate(90 80) scale(1.25) translate(-8 -4)">
<path d="${SPIRAL}" fill="none" stroke="${INK}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="${END[0]}" cy="${END[1]}" r="4.6" fill="${DOT}"/></g>
<text x="170" y="136" font-family="Newsreader" font-size="52" fill="${INK}">Lotent</text>
<text x="90" y="318" font-family="Newsreader" font-size="86" fill="${INK}">Toutes les conférences</text>
<text x="90" y="412" font-family="Newsreader" font-size="86" fill="${INK}">académiques de Paris.</text>
<text x="90" y="486" font-family="Instrument Sans" font-size="27" fill="#a1a1aa">Collège de France · ENS · EHESS · Sorbonne · Sciences Po · IHP · PSE · PSL</text>
<line x1="90" y1="528" x2="1110" y2="528" stroke="#2a2a2e" stroke-width="1.5"/>
<text x="90" y="572" font-family="Instrument Sans" font-size="26" fill="${INK}">${label} événements à venir <tspan fill="#a1a1aa">· gratuit, sans compte · mis à jour chaque jour</tspan></text>
</svg>`;
png(og, 1200, "og.png");
console.log("OK :", label, "événements");
