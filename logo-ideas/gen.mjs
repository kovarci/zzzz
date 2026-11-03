// Pistes de logo « spirale + point bleu », moins parfaites : tracé à la main, argile, pinceau.
// Chaque variante est calculée (bruit à graine fixe) : les mêmes fichiers sortent à chaque fois.
import { points as ORIGINAL_POINTS, END as ORIGINAL_END } from "./original-geometry.mjs";
const TAU = Math.PI * 2;
const rng = (s) => () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
const wob = (seed, amp, freq) => { const r = rng(seed), p = [r() * TAU, r() * TAU, r() * TAU];
  return (t) => amp * (0.6 * Math.sin(t * freq + p[0]) + 0.3 * Math.sin(t * freq * 2.3 + p[1]) + 0.1 * Math.sin(t * freq * 4.1 + p[2])); };
const f = (p) => p[0].toFixed(1) + "," + p[1].toFixed(1);

function spine(o) {
  const n = o.n || 90, fr = wob(o.seed, o.wr, 7), fa = wob(o.seed + 11, o.wa, 4), start = o.end - o.turns * TAU, pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, th = start + t * o.turns * TAU + fa(t), r = o.r0 + (o.r1 - o.r0) * Math.pow(t, o.pow || 0.85) + fr(t);
    pts.push([o.cx + Math.cos(th) * r, o.cy + Math.sin(th) * r * (o.sq || 1)]);
  }
  return pts;
}
function outline(pts, wfn) {
  const n = pts.length, L = [], R = [], nrm = [];
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    let tx = b[0] - a[0], ty = b[1] - a[1]; const m = Math.hypot(tx, ty) || 1; tx /= m; ty /= m;
    const w = wfn(i / (n - 1)) / 2; nrm.push([tx, ty, w]);
    L.push([pts[i][0] - ty * w, pts[i][1] + tx * w]); R.push([pts[i][0] + ty * w, pts[i][1] - tx * w]);
  }
  const cap = (c, tx, ty, w, from, steps = 7) => { const a0 = Math.atan2(tx, -ty), out = [];
    for (let k = 1; k < steps; k++) { const a = a0 - from * (k / steps) * Math.PI; out.push([c[0] + Math.cos(a) * w, c[1] + Math.sin(a) * w]); } return out; };
  const e = nrm[n - 1], s = nrm[0];
  const endCap = cap(pts[n - 1], e[0], e[1], e[2], 1);
  const sa = Math.atan2(s[0], -s[1]) - Math.PI, sc = [];
  for (let k = 1; k < 7; k++) { const a = sa - (k / 7) * Math.PI; sc.push([pts[0][0] + Math.cos(a) * s[2], pts[0][1] + Math.sin(a) * s[2]]); }
  return [...L, ...endCap, ...R.reverse(), ...sc];
}
function smooth(poly) {
  const n = poly.length; let d = "M" + f(poly[0]);
  for (let i = 0; i < n; i++) {
    const p0 = poly[(i - 1 + n) % n], p1 = poly[i], p2 = poly[(i + 1) % n], p3 = poly[(i + 2) % n];
    d += "C" + f([p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]) + " " + f([p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]) + " " + f(p2);
  }
  return d + "Z";
}
function blob(cx, cy, r, seed, amp = 0.14, k = 9) {
  const rd = rng(seed), poly = [];
  for (let i = 0; i < k; i++) { const a = (i / k) * TAU, rr = r * (1 + (rd() - 0.5) * 2 * amp); poly.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); }
  return smooth(poly);
}
const last = (a) => a[a.length - 1];
export function openPath(pts) {
  let d = "M" + f(pts[0]);
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
    d += "C" + f([p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]) + " " + f([p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]) + " " + f(p2);
  }
  return d;
}

export const variants = [
  { id: "original", num: 0, name: "Spirale actuelle (l’escargot de Paris)", note: "Le logo d’origine : trait régulier de 3,6, point rond. Reconstruit à l’identique en contour.",
    build() { return { ink: [smooth(outline(ORIGINAL_POINTS, () => 3.6))], dot: [blob(ORIGINAL_END[0], ORIGINAL_END[1], 4.6, 1, 0, 24)] }; } },
  { id: "crayon", name: "Crayon de cire", note: "Trait fin et tremblé, comme une spirale tracée sans lever la main.",
    build() { const p = spine({ turns: 2.5, r0: 2.5, r1: 23, cx: 31, cy: 31, wr: 1.5, wa: 0.1, seed: 3, end: 0.4 }), w = wob(5, 0.7, 9), e = last(p);
      return { ink: [smooth(outline(p, (t) => 3.4 + w(t * 6)))], dot: [blob(e[0] + 1, e[1] + 1, 5.2, 21, 0.12)] }; } },
  { id: "argile", name: "Boudin d’argile", note: "Un gros colombin roulé entre les mains, bords irréguliers.",
    build() { const p = spine({ turns: 1.7, r0: 5, r1: 24, cx: 31, cy: 31, wr: 1.0, wa: 0.06, seed: 8, end: 0.35 }), w = wob(9, 0.9, 8), e = last(p);
      return { ink: [smooth(outline(p, (t) => 6.2 + w(t * 6)))], dot: [blob(e[0] + 0.5, e[1] + 0.5, 7, 34, 0.1)] }; } },
  { id: "enfant", name: "Dessin d’enfant", note: "Spirale qui déborde, traits inégaux, point gribouillé deux fois.",
    build() { const p = spine({ turns: 3.1, r0: 1.5, r1: 25, cx: 30, cy: 32, wr: 2.0, wa: 0.12, sq: 0.94, seed: 14, end: 0.3, pow: 0.8 }), w = wob(17, 1.0, 6), e = last(p);
      return { ink: [smooth(outline(p, (t) => Math.max(1.8, 3.1 + w(t * 6))))], dot: [blob(e[0] + 1, e[1] + 0.5, 4.8, 41, 0.18, 8), blob(e[0] - 0.8, e[1] + 1.4, 3.8, 43, 0.2, 7)] }; } },
  { id: "pinceau", name: "Coup de pinceau", note: "Fin au centre, gras à l’extérieur : un seul geste d’encre.",
    build() { const p = spine({ turns: 2.3, r0: 1.5, r1: 23, cx: 31, cy: 31, wr: 0.7, wa: 0.05, seed: 22, end: 0.4, pow: 0.9 }), w = wob(24, 0.5, 8), e = last(p);
      return { ink: [smooth(outline(p, (t) => 1.1 + 5.6 * Math.pow(t, 0.9) + w(t * 6)))], dot: [blob(e[0] + 1, e[1] + 1, 6, 52, 0.1)], spine: openPath(p), end: e, center: [31, 31] }; } },
  { id: "pate", name: "Pâte à modeler", note: "Ramassé et épais, presque un escargot en pâte.",
    build() { const p = spine({ turns: 1.35, r0: 7, r1: 23, cx: 31, cy: 31, wr: 0.8, wa: 0.05, sq: 0.92, seed: 31, end: 0.35 }), w = wob(33, 1.0, 7), e = last(p);
      return { ink: [smooth(outline(p, (t) => 8.2 + w(t * 5)))], dot: [blob(e[0] + 1, e[1] + 1, 7.4, 61, 0.09)] }; } },
  { id: "escargot", name: "Petit escargot", note: "Coquille en spirale, corps qui rampe, le point bleu fait la tête.",
    build() { const sp = spine({ turns: 2.2, r0: 2, r1: 17, cx: 25, cy: 27, wr: 0.7, wa: 0.05, seed: 40, end: Math.PI / 2 + 0.15 }), s = last(sp);
      const body = [[s[0] + 5, s[1] + 2.2], [s[0] + 12, s[1] + 3.2], [s[0] + 19, s[1] + 2], [s[0] + 24, s[1] - 2]], p = sp.concat(body), w = wob(42, 0.5, 9), h = last(p);
      const ant = (dx, dy) => smooth(outline([[h[0] + dx * 0.5, h[1] - 4], [h[0] + dx, h[1] - 9 + dy]], () => 1.8));
      return { ink: [smooth(outline(p, (t) => 3.6 + w(t * 6))), ant(-2.5, 0), ant(3, 0.6)], dot: [blob(h[0] + 1, h[1] - 1, 5.4, 70, 0.1)] }; } },
];

export const DOT = { dark: "#8CA7FF", light: "#274BB0" };
export function svg(v, mode) {
  const { ink, dot } = v.build(), fg = mode === "dark" ? "#f4f4f5" : "#09090b";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="Lotent">` +
    `<g fill="${fg}">${ink.map((d) => `<path d="${d}"/>`).join("")}</g><g fill="${DOT[mode]}">${dot.map((d) => `<path d="${d}"/>`).join("")}</g></svg>`;
}
