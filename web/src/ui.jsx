/* Composants d'interface : ports de Magic UI (magicui.design), d'Aceternity
   (ui.aceternity.com) et primitives façon shadcn/ui. Aucune logique métier. */
import React, { useState, useEffect, useLayoutEffect, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform, useInView } from "framer-motion";
import { cn } from "./lib.js";

/* ═══════════════════ Accessibilité ═══════════════════ */
// Fenêtre modale : focus déplacé dedans à l'ouverture, Tab et Maj+Tab restent
// dedans, focus rendu à l'élément qui l'a ouverte à la fermeture.
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea,[tabindex]:not([tabindex="-1"])';
// Page derrière figée tant qu'une fenêtre est ouverte (compteur : fenêtres
// empilées) ; la largeur de la barre de défilement est compensée.
let scrollLocks = 0;
function lockScroll() {
  if (scrollLocks++) return;
  const root = document.documentElement, bar = window.innerWidth - root.clientWidth;
  root.style.overflow = "hidden";
  if (bar > 0) root.style.paddingRight = `${bar}px`;
}
function unlockScroll() {
  if (--scrollLocks > 0) return;
  scrollLocks = 0;
  document.documentElement.style.overflow = ""; document.documentElement.style.paddingRight = "";
}
export function useFocusTrap(active) {
  const ref = useRef(null);
  useEffect(() => {
    if (!active) return;
    lockScroll();
    const opener = document.activeElement;
    const items = () => [...(ref.current?.querySelectorAll(FOCUSABLE) || [])].filter(el => el.getClientRects().length);
    const t = setTimeout(() => {
      const el = ref.current;
      if (!el || el.contains(document.activeElement)) return;
      const first = items()[0];
      (first || el).focus?.({ preventScroll: true });
    }, 40);
    const onKey = ev => {
      if (ev.key !== "Tab" || !ref.current) return;
      const f = items(); if (!f.length) return;
      const first = f[0], last = f[f.length - 1], cur = document.activeElement;
      if (!ref.current.contains(cur)) { ev.preventDefault(); first.focus(); }
      else if (ev.shiftKey && cur === first) { ev.preventDefault(); last.focus(); }
      else if (!ev.shiftKey && cur === last) { ev.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t); document.removeEventListener("keydown", onKey); unlockScroll();
      if (opener && opener !== document.body && opener.isConnected) setTimeout(() => opener.focus?.({ preventScroll: true }), 0);
    };
  }, [active]);
  return ref;
}

/* ═══════════════════ Magic UI ═══════════════════ */
// magicui.design/docs/components/number-ticker
// Chiffre affiché tel quel : le compteur qui monte depuis 0 était un effet de démonstration
export function NumberTicker({ value, className, locale = "fr-FR" }) {
  return <span className={cn("inline-block tabular-nums tracking-tight", className)}>{Intl.NumberFormat(locale).format(value)}</span>;
}
// Texte simple (l'ancien effet « brillance » et le défilement continu des
// institutions, le fondu flouté à l'arrivée, le faisceau lumineux sur les
// bordures : retirés, c'est ce qui donnait l'air « template »)
export function AnimatedShinyText({ children, className }) {
  return <span className={cn("text-muted-foreground", className)}>{children}</span>;
}
// Rangée d'institutions : défilement manuel, rien ne bouge seul
export function Marquee({ children, className }) {
  return <div className={cn("flex gap-2 overflow-x-auto py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden", className)}>{children}</div>;
}
export function BlurFade({ children, className }) { return <div className={className}>{children}</div>; }
export function BorderBeam() { return null; }
// magicui.design/docs/components/dot-pattern
export function DotPattern({ width = 16, height = 16, cr = 1, className }) {
  const id = useMemo(() => "dp" + Math.random().toString(36).slice(2), []);
  return <svg aria-hidden="true" className={cn("pointer-events-none absolute inset-0 h-full w-full fill-white/30", className)}>
    <defs><pattern id={id} width={width} height={height} patternUnits="userSpaceOnUse"><circle cx={cr} cy={cr} r={cr} /></pattern></defs>
    <rect width="100%" height="100%" fill={`url(#${id})`} /></svg>;
}
// magicui.design/docs/components/bento-grid
export function BentoGrid({ children, className }) { return <div className={cn("grid w-full auto-rows-[190px] grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4", className)}>{children}</div>; }
export function BentoCard({ name, className, background, description, cta = "Ouvrir", onClick, meta }) {
  return <div role="button" tabIndex={0} aria-label={name} onClick={onClick} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick?.(); } }} className={cn("group relative col-span-1 flex flex-col justify-end overflow-hidden rounded-xl cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-ring",
    "bg-card",
    "border", className)}>
    <div className="absolute inset-0">{background}</div>
    <div className="pointer-events-none z-10 flex transform-gpu flex-col gap-1 p-5 transition-all duration-300 group-hover:-translate-y-8">
      {meta && <div className="text-xs font-medium text-white/85 drop-shadow">{meta}</div>}
      <h3 className="font-serif text-xl font-medium leading-snug text-white drop-shadow line-clamp-2 [text-wrap:balance]">{name}</h3>
      {description && <p className="max-w-lg text-sm text-white/80 line-clamp-1 drop-shadow">{description}</p>}
    </div>
    <div className="pointer-events-none absolute bottom-0 flex w-full translate-y-10 transform-gpu flex-row items-center p-4 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100">
      <span className="inline-flex h-8 items-center rounded-md bg-white/90 px-3 text-xs font-semibold text-black">{cta} →</span>
    </div>
    <div className="pointer-events-none absolute inset-0 transform-gpu transition-all duration-300 group-hover:bg-black/[.04] dark:group-hover:bg-white/[.04]" />
  </div>;
}
// Barre d'icônes flottante, sans l'effet de loupe du Dock macOS
export function Dock({ children, className }) {
  return <div className={cn("mx-auto flex h-[52px] w-max items-center gap-1 rounded-xl border bg-background/90 p-1.5 shadow-md", className)}>{children}</div>;
}
export function DockIcon({ children, title, onClick, active, size = 40 }) {
  return <button onClick={onClick} title={title} aria-label={title} aria-pressed={active} style={{ width: size, height: size }}
    className={cn("relative flex items-center justify-center rounded-lg hover:bg-accent", active ? "text-amber-500" : "text-foreground/80")}>{children}</button>;
}
export const DockSep = () => <span className="w-px h-6 bg-border mx-0.5 self-center" />;

/* ═══════════════════ Aceternity ═══════════════════ */
// ui.aceternity.com/components/card-hover-effect
// Fond « aurore » du mode sombre (l'ancien site l'avait ; la refonte React
// l'avait perdu : le sombre n'était plus qu'un aplat). Taches de couleur en
// dégradés radiaux — pas de filter: blur(110px), qui coûtait cher à chaque
// image — qui dérivent lentement, plus un halo qui suit la souris. Tout passe
// par transform (compositeur, sans relayout) ; la position de la souris est
// lue au plus une fois par image. Rien en mode clair, ni avec « réduire les
// animations » ; sur écran tactile, pas de suivi.
export function Ambient() { return null; }

export function HoverEffect({ items, render, className }) {
  return <div className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4", className)}>
    {items.map(it => <div key={it.id} className="relative group/hover block p-2 h-full w-full">
      <span aria-hidden="true" className="absolute inset-0 h-full w-full bg-accent block rounded-2xl opacity-0 scale-[.97] transition duration-200 group-hover/hover:opacity-100 group-hover/hover:scale-100 [@media(hover:none)]:hidden" />
      <div className="relative z-20 h-full">{render(it)}</div>
    </div>)}
  </div>;
}
export function MovingBorderButton({ children, onClick, href, className }) {
  const Tag = href ? "a" : "button";
  return <Tag href={href} onClick={onClick} className={cn("inline-flex h-9 items-center justify-center rounded-md border bg-background px-4 text-sm font-medium shadow-sm hover:bg-accent", className)}>{children}</Tag>;
}
export function Spotlight() { return null; }

/* ═══════════════════ shadcn-style ═══════════════════ */
export const Button = ({ variant = "default", size = "md", className, ...p }) => <button className={cn("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
  size === "sm" ? "h-8 px-3" : size === "icon" ? "h-9 w-9" : "h-10 px-4",
  variant === "default" ? "bg-primary text-primary-foreground shadow hover:bg-primary/90" : variant === "outline" ? "border bg-background shadow-sm hover:bg-accent" : variant === "ghost" ? "hover:bg-accent" : "", className)} {...p} />;
export const LinkButton = ({ variant = "default", className, ...p }) => <a className={cn("inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition-colors",
  variant === "default" ? "bg-primary text-primary-foreground shadow hover:bg-primary/90" : "border bg-background shadow-sm hover:bg-accent", className)} {...p} />;
export const Badge = ({ variant = "outline", className, style, children, title }) => <span title={title} style={style} className={cn("inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold", variant === "outline" ? "border" : "bg-primary text-primary-foreground", className)}>{children}</span>;
export const Kbd = ({ children, className }) => <kbd className={cn("inline-flex h-5 items-center rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground", className)}>{children}</kbd>;

export function Tabs({ value, onChange, items, layoutId = "tab-pill" }) {
  return <div className="inline-flex h-9 items-center rounded-lg bg-muted p-1 text-muted-foreground relative">
    {items.map(([v, l, label]) => <button key={v} onClick={() => onChange(v)} aria-label={label} title={label} aria-pressed={value === v} className={cn("relative z-10 inline-flex h-7 items-center rounded-md px-3 text-sm font-medium transition-colors whitespace-nowrap", value === v && "text-foreground")}>
      {value === v && <motion.span layoutId={layoutId} className="absolute inset-0 rounded-md bg-background shadow-sm" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
      <span className="relative">{l}</span></button>)}
  </div>;
}
// block : bouton pleine largeur, hauteur des boutons voisins (fiche détail).
// Sur téléphone (< 640 px), le menu s'ouvre en panneau depuis le bas de
// l'écran (rendu dans <body>) : la rangée de filtres y défile à l'horizontale,
// un menu positionné sous son bouton y serait coupé.
const narrow = () => typeof window !== "undefined" && window.matchMedia("(max-width: 639px)").matches;
export function Popover({ label, count, children, align = "left", minW = "min-w-[280px]", block, closeLabel = "Fermer" }) {
  const [open, setOpen] = useState(false), [sheet, setSheet] = useState(false);
  const ref = useRef(null), popRef = useRef(null), openRef = useRef(false);
  openRef.current = open;
  // Panneau du bas (téléphone) = fenêtre modale : même gestion du focus
  const trap = useFocusTrap(open && sheet);
  const sheetRef = el => { popRef.current = el; trap.current = el; };
  const close = () => setOpen(false);
  // Menu déroulant : recalé dans la fenêtre s'il en dépasse (8 px de marge)
  const [dx, setDx] = useState(0), [maxH, setMaxH] = useState(0);
  useLayoutEffect(() => {
    if (!open || sheet) { setDx(0); return; }
    const r = popRef.current?.getBoundingClientRect(); if (!r) return;
    const over = r.right - (window.innerWidth - 8);          // dépasse à droite
    if (over > 0) setDx(-Math.min(over, r.left - 8));        // vers la gauche, sans sortir à gauche
    else if (r.left < 8) setDx(8 - r.left);
  }, [open, sheet]);
  // Hauteur bornée à la place restante sous le bouton : sur un écran de
  // portable (~650 px), la fin de la liste Institution passait sous le bas de
  // la fenêtre. Recalculée au défilement (la barre de filtres est collante).
  // 84 px : la barre d'outils flottante du bas de l'écran, qui passe au-dessus.
  useLayoutEffect(() => {
    if (!open || sheet) return;
    const upd = () => { const r = ref.current?.getBoundingClientRect(); if (r) setMaxH(Math.max(200, window.innerHeight - r.bottom - 84)); };
    upd(); window.addEventListener("scroll", upd, { passive: true }); window.addEventListener("resize", upd);
    return () => { window.removeEventListener("scroll", upd); window.removeEventListener("resize", upd); };
  }, [open, sheet]);
  useEffect(() => {
    const h = e => { if (!ref.current?.contains(e.target) && !popRef.current?.contains(e.target)) setOpen(false); };
    // Échap ferme le menu seulement : en phase de capture, avant la fiche
    // (menu « Agenda ») qui, sinon, se fermait avec lui.
    // Focus rendu au bouton du menu : il retombait en haut de la page (clavier,
    // lecteur d'écran). Le panneau du bas (téléphone) le fait déjà via useFocusTrap.
    const k = e => { if (e.key === "Escape" && openRef.current) { e.preventDefault(); setOpen(false); ref.current?.querySelector("button")?.focus({ preventScroll: true }); } };
    document.addEventListener("mousedown", h); document.addEventListener("keydown", k, true);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("keydown", k, true); };
  }, []);
  const panel = sheet
    ? createPortal(<AnimatePresence>{open && <motion.div key="sheet" className="fixed inset-0 z-[70]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }}>
        <div className="absolute inset-0 bg-black/50" />
        <motion.div ref={sheetRef} role="dialog" aria-modal="true" aria-label={typeof label === "string" ? label : undefined} initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }} transition={{ type: "spring", stiffness: 420, damping: 40 }}
          className="absolute inset-x-0 bottom-0 flex max-h-[75vh] flex-col rounded-t-2xl border-t bg-popover shadow-2xl">
          <div className="flex items-center justify-between border-b px-4 py-3"><span className="text-sm font-semibold">{label}</span>
            <button onClick={close} aria-label={closeLabel} className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg></button></div>
          <div className="overflow-auto p-2 pb-[max(1rem,env(safe-area-inset-bottom))]">{children(close)}</div>
        </motion.div></motion.div>}</AnimatePresence>, document.body)
    // align="center" : centré sous le bouton (le décalage passe par framer, qui écrit lui-même `transform`)
    : <AnimatePresence>{open && <motion.div ref={popRef} style={{ ...(align === "right" ? { marginRight: -dx } : { marginLeft: dx }), ...(maxH ? { maxHeight: `min(60vh, ${maxH}px)` } : null) }} initial={{ opacity: 0, y: -4, scale: .98, x: align === "center" ? "-50%" : 0 }} animate={{ opacity: 1, y: 0, scale: 1, x: align === "center" ? "-50%" : 0 }} exit={{ opacity: 0, y: -4, scale: .98 }} transition={{ duration: .12 }}
        className={cn("absolute top-[calc(100%+6px)] z-40 max-h-[60vh] overflow-auto rounded-lg border bg-popover p-1 shadow-lg", minW, align === "right" ? "right-0" : align === "center" ? "left-1/2" : "left-0")}>{children(close)}</motion.div>}</AnimatePresence>;
  return <div ref={ref} className={cn("relative shrink-0", block && "w-full")}>
    <Button variant="outline" size={block ? "md" : "sm"} className={cn(block ? "w-full px-2" : "h-9", open && "bg-accent")} onClick={() => { setSheet(narrow()); setOpen(o => !o); }} aria-expanded={open}>{label}{count > 0 && <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[11px] text-primary-foreground">{count}</span>}
      <svg className="opacity-50" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6" /></svg></Button>
    {panel}
  </div>;
}
export function CheckList({ values, set, onToggle, swatch, labelFn, titleFn, onClear, colorOf, clearLabel = "Tout effacer" }) {
  return <>
    {values.map(([v, n, hd]) => <React.Fragment key={v}>{hd && <div className="px-2 pt-2 pb-1 text-xs font-medium text-muted-foreground">{hd}</div>}
      <label title={titleFn?.(v)} className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm cursor-pointer hover:bg-accent"><input type="checkbox" className="accent-[hsl(var(--primary))]" checked={set.has(v)} onChange={() => onToggle(v)} />
        {swatch && <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: colorOf(v) }} />}<span className="truncate">{labelFn ? labelFn(v) : v}</span><span className="ml-auto text-xs text-muted-foreground tabular-nums">{n}</span></label></React.Fragment>)}
    {onClear && <button onClick={onClear} className="w-full text-left rounded-b-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent mt-1 border-t">{clearLabel}</button>}
  </>;
}
export const Icon = ({ d, size = 18, ...p }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}>{Array.isArray(d) ? d.map((x, i) => <path key={i} d={x} />) : <path d={d} />}</svg>;
export const ICONS = {
  up: "m18 15-6-6-6 6", search: ["M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14z", "m20 20-3.5-3.5"], cal: ["M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M16 2v4M8 2v4M3 10h18"],
  random: "M2 18h1.4c1.3 0 2.5-.6 3.3-1.7l6.1-8.6c.7-1.1 2-1.7 3.3-1.7H22M18 2l4 4-4 4M2 6h1.9c1.5 0 2.9.9 3.6 2.2M22 18h-5.9c-1.3 0-2.6-.7-3.3-1.8l-.5-.8M18 14l4 4-4 4",
  star: "m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z", history: ["M3 12a9 9 0 1 0 3-6.7", "M3 3v5h5", "M12 7v5l3 2"], map: ["M9 20 3 17V4l6 3 6-3 6 3v13l-6-3-6 3z", "M9 7v13M15 4v13"],
  week: ["M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M3 10h18M9 4v18M15 4v18"], list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01", pin: ["M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z", "M12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"],
  moon: "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z", sun: ["M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4", "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z"],
  bell: ["M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9", "M13.73 21a2 2 0 0 1-3.46 0"], bellOff: ["M13.73 21a2 2 0 0 1-3.46 0", "M18.63 13A17.89 17.89 0 0 1 18 8", "M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14", "M18 8a6 6 0 0 0-9.33-5", "M1 1l22 22"], external: ["M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6", "M15 3h6v6", "M10 14 21 3"],
  check: "M20 6 9 17l-5-5", share: ["M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8", "M16 6l-4-4-4 4M12 2v13"], download: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M7 10l5 5 5-5M12 15V3"], x: "M18 6 6 18M6 6l12 12", github: "M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 0 0-.9-2.6c3.1-.3 6.4-1.5 6.4-7A5.4 5.4 0 0 0 20 4.8 5 5 0 0 0 19.9 1s-1.2-.4-3.9 1.5a13.4 13.4 0 0 0-7 0C6.3.6 5.1 1 5.1 1A5 5 0 0 0 5 4.8a5.4 5.4 0 0 0-1.5 3.7c0 5.5 3.3 6.7 6.4 7A3.4 3.4 0 0 0 9 18v4",
};
