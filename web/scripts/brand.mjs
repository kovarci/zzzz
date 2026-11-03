/* Régénère l'identité visuelle depuis le logo actif (src/logo.json, posé par logo-ideas/apply.mjs) :
   ../icon.svg, apple-touch-icon.png, icon-192/512.png, icon-maskable-512.png, og.png.
   Usage : npm run brand   (télécharge Newsreader et Instrument Sans dans .cache/ la première fois) */
import fs from "node:fs";
import path from "node:path";
import { Resvg } from "@resvg/resvg-js";
const logo = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, "..", "src", "logo.json"), "utf8"));
const [VX, VY, VS] = logo.view;
// Le dessin (contours remplis) dans un repère de 64 unités, centré dans sa case carrée
const mark = (ink, dot) => `<g fill="${ink}">${logo.ink.map((d) => `<path d="${d}"/>`).join("")}</g><g fill="${dot}">${logo.dot.map((d) => `<path d="${d}"/>`).join("")}</g>`;

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

// ── icône carrée : le logo centré sur fond sombre ────────────────────────
const icon = (size, { round, scale }) => {
  const k = size * scale / VS;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
<rect width="${size}" height="${size}" ${round ? `rx="${size * 0.22}"` : ""} fill="#111113"/>
<g transform="translate(${size / 2} ${size / 2}) scale(${k}) translate(${-(VX + VS / 2)} ${-(VY + VS / 2)})">${mark(INK, DOT)}</g></svg>`;
};
png(icon(512, { round: true, scale: 0.66 }), 180, "apple-touch-icon.png");
png(icon(512, { round: true, scale: 0.66 }), 192, "icon-192.png");
png(icon(512, { round: true, scale: 0.66 }), 512, "icon-512.png");
png(icon(512, { round: false, scale: 0.5 }), 512, "icon-maskable-512.png");   // zone de sécurité du « maskable »

// ── favicon SVG : sans fond, clair ou sombre selon l'onglet ──────────────
fs.writeFileSync(path.join(root, "icon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${VX} ${VY} ${VS} ${VS}">
  <style>.s{fill:#111113}.d{fill:#2B4DB5}@media (prefers-color-scheme:dark){.s{fill:${INK}}.d{fill:${DOT}}}</style>
  <g class="s">${logo.ink.map((d) => `<path d="${d}"/>`).join("")}</g><g class="d">${logo.dot.map((d) => `<path d="${d}"/>`).join("")}</g>
</svg>
`);

// ── image de partage 1200×630 ────────────────────────────────────────────
const total = JSON.parse(fs.readFileSync(path.join(root, "data", "m", "index.json"), "utf8")).total;
const label = total >= 200 ? `Plus de ${Math.floor(total / 100) * 100}`.replace(/\B(?=(\d{3})+(?!\d))/g, " ") : String(total);
const og = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#111113"/>
<g transform="translate(84 54) scale(1.4) translate(${-VX} ${-VY})">${mark(INK, DOT)}</g>
<text x="176" y="136" font-family="Newsreader" font-size="52" fill="${INK}">Lotent</text>
<text x="90" y="318" font-family="Newsreader" font-size="86" fill="${INK}">Les conférences ouvertes</text>
<text x="90" y="412" font-family="Newsreader" font-size="86" fill="${INK}">au public à Paris.</text>
<text x="90" y="486" font-family="Instrument Sans" font-size="27" fill="#a1a1aa">Collège de France · ENS · EHESS · Sorbonne · Sciences Po · IHP · PSE · PSL</text>
<line x1="90" y1="528" x2="1110" y2="528" stroke="#2a2a2e" stroke-width="1.5"/>
<text x="90" y="572" font-family="Instrument Sans" font-size="26" fill="${INK}">${label} événements à venir <tspan fill="#a1a1aa">· gratuit, sans compte · mis à jour chaque jour</tspan></text>
</svg>`;
png(og, 1200, "og.png");
console.log("OK :", label, "événements");
