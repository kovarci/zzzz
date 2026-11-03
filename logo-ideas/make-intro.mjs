// Maquettes des animations de lancement du site : node logo-ideas/make-intro.mjs → logo-ideas/intro.html
// Le logo vient de la variante « pinceau » (gen.mjs) ; chaque carte se rejoue avec son bouton.
import { writeFileSync, readFileSync } from "node:fs";
import { variants } from "./gen.mjs";

const logo = JSON.parse(readFileSync(new URL("../web/src/logo.json", import.meta.url), "utf8"));
const v = variants.find((x) => x.id === "pinceau").build();
const [vx, vy, vs] = logo.view;
const cx = (((v.center[0] - vx) / vs) * 100).toFixed(1), cy = (((v.center[1] - vy) / vs) * 100).toFixed(1);

const mark = (id, withMask) => {
  const ink = logo.ink.map((d) => `<path d="${d}"${withMask ? ` mask="url(#m-${id})"` : ""}/>`).join("");
  const dot = logo.dot.map((d) => `<path d="${d}"/>`).join("");
  const mask = withMask ? `<defs><mask id="m-${id}" maskUnits="userSpaceOnUse" x="${vx}" y="${vy}" width="${vs}" height="${vs}"><path class="drawp" d="${v.spine}" pathLength="1" fill="none" stroke="#fff" stroke-width="11" stroke-linecap="round"/></mask></defs>` : "";
  return `<svg viewBox="${vx} ${vy} ${vs} ${vs}" aria-hidden="true">${mask}<g fill="currentColor">${ink}</g><g class="dot" fill="#8CA7FF">${dot}</g></svg>`;
};
const page = `<div class="page"><div class="hd"><b>Lotent</b><i></i><i></i></div><h3>Les conférences ouvertes au public à Paris, en un seul agenda.</h3><div class="srch"></div><div class="chips"><i></i><i></i><i></i></div></div>`;
const card = (k, title, text, meta, withMask = false) => `<article><h2>${k}. ${title}</h2><p>${text}</p>
<div class="stage s-${k.toLowerCase()}" data-k="${k}">${page}<div class="splash"><div class="inner"><div class="mark">${mark(k.toLowerCase(), withMask)}</div><div class="name">Lotent</div></div></div></div>
<div class="row"><button type="button" class="replay">Rejouer</button><span>${meta}</span></div></article>`;

const html = `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Animations de lancement</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{margin:0;padding:2rem;background:#0a0a0b;color:#f4f4f5;font:16px/1.5 system-ui,sans-serif}h1{font:500 2rem Georgia,serif;margin:0 0 .25rem}p.lead{color:#a1a1aa;margin:0 0 2rem;max-width:44rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(22rem,1fr));gap:2.25rem 2rem}article h2{font:500 1.25rem Georgia,serif;margin:0}article p{margin:.25rem 0 .75rem;color:#a1a1aa;font-size:.9rem;min-height:2.7em}
.stage{position:relative;aspect-ratio:16/10;border:1px solid #27272a;border-radius:8px;overflow:hidden;background:#0a0a0b}
.page{position:absolute;inset:0;padding:12px 16px;background:#0a0a0b;z-index:1}.hd{display:flex;gap:8px;align-items:center;font:500 15px Georgia,serif;margin-bottom:22px}.hd i{width:26px;height:8px;border-radius:3px;background:#27272a}.hd i:first-of-type{margin-left:auto}
.page h3{font:500 22px/1.1 Georgia,serif;margin:0 0 14px;max-width:16em}.srch{height:26px;border:1px solid #3f3f46;border-radius:6px}.chips{display:flex;gap:6px;margin-top:10px}.chips i{width:54px;height:20px;border:1px solid #27272a;border-radius:6px}
.splash{position:absolute;inset:0;display:grid;place-items:center;background:#0a0a0b;z-index:2}.inner{display:flex;flex-direction:column;align-items:center}
.mark{width:86px;height:86px;color:#f4f4f5}.mark svg{width:100%;height:100%;overflow:visible}.name{font:500 21px Georgia,serif;margin-top:10px}
.row{display:flex;align-items:center;gap:.75rem;margin-top:.6rem;color:#a1a1aa;font-size:.8rem}button{font:inherit;color:#f4f4f5;background:#18181b;border:1px solid #52525b;border-radius:6px;padding:.4rem .8rem;cursor:pointer}button:hover{background:#27272a}
.all{margin:0 0 1.5rem}
@keyframes a-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes fadeout{to{opacity:0;visibility:hidden}}
.s-a.go .inner{animation:a-in .5s ease both}.s-a.go .splash{animation:fadeout .45s 1.1s ease forwards}
@keyframes b-spin{0%{transform:rotate(-120deg) scale(.5);opacity:0}20%{opacity:1}65%{transform:rotate(360deg) scale(1.1)}100%{transform:rotate(420deg) scale(2.6);opacity:0}}
@keyframes b-name{0%{opacity:0}20%,55%{opacity:1}70%,100%{opacity:0}}
@keyframes b-bg{0%,60%{opacity:1}100%{opacity:0;visibility:hidden}}
.s-b.go .mark{animation:b-spin 1.6s cubic-bezier(.65,0,.35,1) both}.s-b.go .name{animation:b-name 1.6s ease both}.s-b.go .splash{animation:b-bg 1.6s linear both}
.s-c .mark{transform-origin:${cx}% ${cy}%}
@keyframes c-dive{0%{transform:scale(.7) rotate(-20deg);opacity:0}18%{transform:scale(1) rotate(0);opacity:1}45%{transform:scale(1.04) rotate(12deg)}100%{transform:scale(46) rotate(140deg)}}
@keyframes c-bg{0%,55%{opacity:1}100%{opacity:0;visibility:hidden}}
.s-c.go .mark{animation:c-dive 1.7s cubic-bezier(.7,0,.3,1) both}.s-c.go .name{animation:b-name 1.7s ease both}.s-c.go .splash{animation:c-bg 1.7s linear both}
.s-d .drawp{stroke-dasharray:1;stroke-dashoffset:1}.s-d .dot{transform-box:fill-box;transform-origin:center;opacity:0}.s-d .name{opacity:0}
@keyframes d-draw{to{stroke-dashoffset:0}}@keyframes d-pop{from{transform:scale(0);opacity:1}to{transform:scale(1);opacity:1}}@keyframes d-name{to{opacity:1}}
.s-d.go .drawp{animation:d-draw 1.2s cubic-bezier(.5,0,.25,1) .2s both}.s-d.go .dot{animation:d-pop .5s 1.3s cubic-bezier(.3,1.7,.5,1) both}.s-d.go .name{animation:d-name .5s 1.5s ease both}.s-d.go .splash{animation:fadeout .5s 2.3s ease forwards}
.s-e .page{z-index:3;clip-path:circle(0% at 50% 50%)}
@keyframes e-iris{to{clip-path:circle(85% at 50% 50%)}}@keyframes e-pulse{0%{transform:scale(.8);opacity:0}30%{transform:scale(1);opacity:1}60%{transform:scale(1.06)}100%{transform:scale(1)}}
.s-e.go .page{animation:e-iris 1s 1.2s cubic-bezier(.6,0,.2,1) forwards}.s-e.go .inner{animation:e-pulse 1.4s ease both}
.rm{display:none;margin:0 0 1.25rem;padding:.6rem .9rem;border:1px solid #52525b;border-radius:8px;color:#d4d4d8;font-size:.9rem}.rm.on{display:block}
</style></head><body><h1>Animations de lancement</h1>
<p class="lead">Ce qu'on verrait à l'ouverture du site, pendant que l'agenda se charge. Chaque maquette se rejoue. Une animation à la fois : cliquez « Rejouer » sous chaque carte. Durées réelles : entre 1,4 et 2,8 secondes ; l'animation ne retarderait jamais l'agenda, elle prendrait le temps du chargement et finirait ensuite.</p>
<p class="rm" id="rm">Votre système demande de réduire les animations : le vrai site les respecterait (le logo apparaîtrait simplement). Cette page joue quand même les maquettes, pour que vous puissiez les juger.</p>
<p class="all"><button type="button" id="all">Tout rejouer</button></p>
<div class="grid">
${card("A", "Sobre : apparition puis fondu", "Le logo et le mot arrivent doucement, puis l'écran se dissout. Presque rien à voir : c'est ce que fait déjà le site, en plus propre.", "1,6 s · très discret · aucun risque", false)}
${card("B", "Tourne, grossit, s'efface", "Votre idée : le logo fait un tour sur lui-même en grossissant, puis passe devant l'écran en s'effaçant, et la page apparaît.", "1,6 s · dynamique · classique d'appli mobile", false)}
${card("C", "Plongée dans la spirale", "Le logo se pose, puis la caméra plonge au centre de la spirale : les bras défilent et la page apparaît derrière. La plus « signature ».", "1,7 s · spectaculaire · propre à Lotent", false)}
${card("D", "Tracé à la plume", "La spirale se dessine d'un trait, du centre vers l'extérieur, puis le point bleu tombe au bout. Le mot apparaît, puis fondu.", "2,8 s · poétique · demande de la patience", true)}
${card("E", "Ouverture en iris", "Le logo respire au centre ; la page s'ouvre en un cercle qui grandit depuis le logo, comme un objectif d'appareil photo.", "2,2 s · élégant · sans rotation", false)}
</div>
<script>
function play(s){s.classList.remove('go');void s.offsetWidth;s.classList.add('go')}
document.querySelectorAll('.stage').forEach(function(s){var b=s.parentElement.querySelector('.replay');b.addEventListener('click',function(){play(s)});});
setTimeout(function(){play(document.querySelector('.stage'))},400);
if(matchMedia('(prefers-reduced-motion:reduce)').matches)document.getElementById('rm').classList.add('on');document.getElementById('all').addEventListener('click',function(){document.querySelectorAll('.stage').forEach(play)});
</script></body></html>`;
writeFileSync(new URL("./intro.html", import.meta.url), html);
console.log("intro.html écrit", Math.round(html.length / 1024), "Ko");
