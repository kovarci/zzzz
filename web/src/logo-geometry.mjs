/* Géométrie de la marque Lotent : l'escargot de Paris (la spirale des arrondissements).
   Partagée par le logo de l'en-tête (logo.jsx) et par scripts/brand.mjs (icônes, image de partage). */
const TURNS = 4.6 * Math.PI, R0 = 2.5, R1 = 27, N = 64;

export const points = Array.from({ length: N + 1 }, (_, i) => {
  const th = TURNS * i / N, r = R0 + (R1 - R0) * Math.pow(th / TURNS, 0.9), a = th - Math.PI / 2;
  return [32 + r * Math.cos(a), 32 + r * Math.sin(a)];
});

// Spline de Catmull-Rom → courbes de Bézier : un tracé lisse, pas une ligne brisée
export const SPIRAL = (() => {
  const f = n => +n.toFixed(2), p = points;
  let d = `M${f(p[0][0])} ${f(p[0][1])}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] || p[i], p1 = p[i], p2 = p[i + 1], p3 = p[i + 2] || p2;
    d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return d;
})();
export const END = points[N].map(n => +n.toFixed(2));
