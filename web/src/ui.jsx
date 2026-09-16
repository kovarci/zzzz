/* Composants d'interface : ports de Magic UI (magicui.design), d'Aceternity
   (ui.aceternity.com) et primitives façon shadcn/ui. Aucune logique métier. */
import React, { useState, useEffect, useRef, useMemo } from "react";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform, useInView, useAnimationFrame } from "framer-motion";
import { cn } from "./lib.js";

/* ═══════════════════ Magic UI ═══════════════════ */
// magicui.design/docs/components/number-ticker
export function NumberTicker({ value, className, delay = 0 }) {
  const ref = useRef(null);
  const mv = useMotionValue(0);
  const spring = useSpring(mv, { damping: 60, stiffness: 100 });
  const inView = useInView(ref, { once: true, margin: "0px" });
  useEffect(() => { if (inView) { const t = setTimeout(() => mv.set(value), delay * 1000); return () => clearTimeout(t); } }, [inView, value]);
  useEffect(() => spring.on("change", v => { if (ref.current) ref.current.textContent = Intl.NumberFormat("fr-FR").format(Math.round(v)); }), [spring]);
  return <span ref={ref} className={cn("inline-block tabular-nums tracking-tight", className)}>0</span>;
}
// magicui.design/docs/components/animated-shiny-text
export function AnimatedShinyText({ children, className, shimmerWidth = 100 }) {
  return <span style={{ "--shiny-width": `${shimmerWidth}px` }} className={cn("mx-auto max-w-md text-neutral-600/70 dark:text-neutral-400/70 animate-shimmer bg-clip-text bg-no-repeat [background-position:0_0] [background-size:var(--shiny-width)_100%] [transition:background-position_1s_cubic-bezier(.6,.6,0,1)_infinite] bg-gradient-to-r from-transparent via-black/80 via-50% to-transparent dark:via-white/80", className)}>{children}</span>;
}
// magicui.design/docs/components/marquee
export function Marquee({ children, className, pauseOnHover = true, repeat = 3 }) {
  return <div className={cn("group flex overflow-hidden p-2 [--duration:60s] [--gap:1rem] [gap:var(--gap)]", className)}>
    {Array.from({ length: repeat }).map((_, i) => <div key={i} className={cn("flex shrink-0 justify-around [gap:var(--gap)] animate-marquee flex-row", pauseOnHover && "group-hover:[animation-play-state:paused]")}>{children}</div>)}
  </div>;
}
// magicui.design/docs/components/blur-fade
export function BlurFade({ children, className, delay = 0, inView = true, yOffset = 6 }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-40px" });
  return <motion.div ref={ref} initial="hidden" animate={(inView ? isInView : true) ? "visible" : "hidden"}
    variants={{ hidden: { y: yOffset, opacity: 0, filter: "blur(6px)" }, visible: { y: 0, opacity: 1, filter: "blur(0px)" } }}
    transition={{ delay: 0.04 + delay, duration: 0.4, ease: "easeOut" }} className={className}>{children}</motion.div>;
}
// magicui.design/docs/components/border-beam
export function BorderBeam({ size = 200, duration = 15, colorFrom = "#ffaa40", colorTo = "#9c40ff", delay = 0 }) {
  return <div style={{ "--size": size, "--duration": duration, "--color-from": colorFrom, "--color-to": colorTo, "--delay": `-${delay}s` }}
    className="pointer-events-none absolute inset-0 rounded-[inherit] [border:1px_solid_transparent] ![mask-clip:padding-box,border-box] ![mask-composite:intersect] [mask:linear-gradient(transparent,transparent),linear-gradient(white,white)] after:absolute after:aspect-square after:w-[calc(var(--size)*1px)] after:animate-border-beam after:[animation-delay:var(--delay)] after:[background:linear-gradient(to_left,var(--color-from),var(--color-to),transparent)] after:[offset-anchor:90%_50%] after:[offset-path:rect(0_auto_auto_0_round_calc(var(--size)*1px))]" />;
}
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
  return <div onClick={onClick} className={cn("group relative col-span-1 flex flex-col justify-end overflow-hidden rounded-xl cursor-pointer",
    "bg-card [box-shadow:0_0_0_1px_rgba(0,0,0,.03),0_2px_4px_rgba(0,0,0,.05),0_12px_24px_rgba(0,0,0,.05)]",
    "dark:[border:1px_solid_rgba(255,255,255,.1)] dark:[box-shadow:0_-20px_80px_-20px_#ffffff1f_inset]", className)}>
    <div className="absolute inset-0">{background}</div>
    <div className="pointer-events-none z-10 flex transform-gpu flex-col gap-1 p-5 transition-all duration-300 group-hover:-translate-y-8">
      {meta && <div className="text-xs font-medium text-white/85 drop-shadow">{meta}</div>}
      <h3 className="text-lg font-semibold leading-snug text-white drop-shadow line-clamp-2 [text-wrap:balance]">{name}</h3>
      {description && <p className="max-w-lg text-sm text-white/80 line-clamp-1 drop-shadow">{description}</p>}
    </div>
    <div className="pointer-events-none absolute bottom-0 flex w-full translate-y-10 transform-gpu flex-row items-center p-4 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100">
      <span className="inline-flex h-8 items-center rounded-md bg-white/90 px-3 text-xs font-semibold text-black">{cta} →</span>
    </div>
    <div className="pointer-events-none absolute inset-0 transform-gpu transition-all duration-300 group-hover:bg-black/[.04] dark:group-hover:bg-white/[.04]" />
  </div>;
}
// magicui.design/docs/components/dock — magnification par motion values
export function Dock({ children, className }) {
  const mouseX = useMotionValue(Infinity);
  return <motion.div onMouseMove={e => mouseX.set(e.pageX)} onMouseLeave={() => mouseX.set(Infinity)}
    className={cn("mx-auto flex h-[58px] w-max items-end gap-1 sm:gap-2 rounded-2xl border bg-background/70 backdrop-blur-md p-2 shadow-lg supports-[backdrop-filter]:bg-background/60", className)}>
    {React.Children.map(children, c => React.isValidElement(c) && c.type === DockIcon ? React.cloneElement(c, { mouseX }) : c)}
  </motion.div>;
}
export function DockIcon({ mouseX, children, title, onClick, active, size = 40, magnification = 60, distance = 140 }) {
  const ref = useRef(null);
  const dist = useTransform(mouseX, val => { const b = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 }; return val - b.x - b.width / 2; });
  const w = useTransform(dist, [-distance, 0, distance], [size, magnification, size]);
  const width = useSpring(w, { mass: 0.1, stiffness: 150, damping: 12 });
  return <motion.button ref={ref} style={{ width, height: width }} onClick={onClick} title={title} aria-label={title} aria-pressed={active}
    className={cn("relative flex aspect-square items-center justify-center rounded-full hover:bg-accent", active ? "text-amber-500" : "text-foreground/80")}>{children}</motion.button>;
}
export const DockSep = () => <span className="w-px h-6 bg-border mx-0.5 self-center" />;

/* ═══════════════════ Aceternity ═══════════════════ */
// ui.aceternity.com/components/card-hover-effect
export function HoverEffect({ items, render, className, layoutId = "hoverBackground" }) {
  const [hovered, setHovered] = useState(null);
  return <div className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4", className)}>
    {items.map((it, idx) => <div key={it.id} className="relative group block p-2 h-full w-full" onMouseEnter={() => setHovered(idx)} onMouseLeave={() => setHovered(null)}>
      <AnimatePresence>{hovered === idx && <motion.span layoutId={layoutId} className="absolute inset-0 h-full w-full bg-accent block rounded-2xl"
        initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { duration: 0.15 } }} exit={{ opacity: 0, transition: { duration: 0.15, delay: 0.2 } }} />}</AnimatePresence>
      <div className="relative z-20 h-full">{render(it)}</div>
    </div>)}
  </div>;
}
// ui.aceternity.com/components/moving-border
export function MovingBorderButton({ children, onClick, href, duration = 3000, className }) {
  const Tag = href ? "a" : "button";
  return <Tag href={href} onClick={onClick} className={cn("relative h-11 w-auto overflow-hidden bg-transparent p-[1px] text-sm rounded-[1.75rem] inline-flex", className)}>
    <div className="absolute inset-0 rounded-[1.75rem]"><MovingBorder duration={duration} rx="30%" ry="30%"><div className="h-20 w-20 bg-[radial-gradient(#3B82F6_40%,transparent_60%)] opacity-[0.8]" /></MovingBorder></div>
    <div className="relative flex h-full w-full items-center justify-center border border-border bg-background/90 backdrop-blur-xl px-6 font-medium rounded-[1.75rem] antialiased">{children}</div>
  </Tag>;
}
function MovingBorder({ children, duration, rx, ry }) {
  const pathRef = useRef(null); const progress = useMotionValue(0);
  useAnimationFrame(time => { const len = pathRef.current?.getTotalLength(); if (len) progress.set((time * (len / duration)) % len); });
  const x = useTransform(progress, v => pathRef.current?.getPointAtLength(v).x);
  const y = useTransform(progress, v => pathRef.current?.getPointAtLength(v).y);
  const transform = useTransform([x, y], ([a, b]) => `translateX(${a}px) translateY(${b}px) translateX(-50%) translateY(-50%)`);
  return <>
    <svg xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none" className="absolute h-full w-full" width="100%" height="100%"><rect fill="none" width="100%" height="100%" rx={rx} ry={ry} ref={pathRef} /></svg>
    <motion.div style={{ position: "absolute", top: 0, left: 0, display: "inline-block", transform }}>{children}</motion.div>
  </>;
}
// ui.aceternity.com/components/spotlight (fond sombre uniquement, cf. app.css .spot)
export function Spotlight({ className, fill = "white" }) {
  return <svg className={cn("spot animate-spotlight pointer-events-none absolute z-[1] h-[169%] w-[138%] lg:w-[84%] opacity-0", className)} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3787 2842" fill="none">
    <g filter="url(#spot)"><ellipse cx="1924.71" cy="273.501" rx="1924.71" ry="273.501" transform="matrix(-0.822377 -0.568943 -0.568943 0.822377 3631.88 2291.09)" fill={fill} fillOpacity="0.21" /></g>
    <defs><filter id="spot" x="0.86" y="0.84" width="3785.16" height="2840.26" filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB"><feFlood floodOpacity="0" result="BackgroundImageFix" /><feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" /><feGaussianBlur stdDeviation="151" result="effect1_foregroundBlur" /></filter></defs>
  </svg>;
}

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
    {items.map(([v, l]) => <button key={v} onClick={() => onChange(v)} className={cn("relative z-10 inline-flex h-7 items-center rounded-md px-3 text-sm font-medium transition-colors whitespace-nowrap", value === v && "text-foreground")}>
      {value === v && <motion.span layoutId={layoutId} className="absolute inset-0 rounded-md bg-background shadow-sm" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
      <span className="relative">{l}</span></button>)}
  </div>;
}
export function Popover({ label, count, children, align = "left" }) {
  const [open, setOpen] = useState(false); const ref = useRef(null);
  useEffect(() => { const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  return <div ref={ref} className="relative">
    <Button variant="outline" size="sm" className={cn("h-9", open && "bg-accent")} onClick={() => setOpen(o => !o)} aria-expanded={open}>{label}{count > 0 && <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[11px] text-primary-foreground">{count}</span>}
      <svg className="opacity-50" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6" /></svg></Button>
    <AnimatePresence>{open && <motion.div initial={{ opacity: 0, y: -4, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -4, scale: .98 }} transition={{ duration: .12 }}
      className={cn("absolute top-[calc(100%+6px)] z-40 min-w-[280px] max-h-[60vh] overflow-auto rounded-lg border bg-popover p-1 shadow-lg", align === "right" ? "right-0" : "left-0")}>{children(() => setOpen(false))}</motion.div>}</AnimatePresence>
  </div>;
}
export function CheckList({ values, set, onToggle, swatch, labelFn, onClear, colorOf }) {
  return <>
    {values.map(([v, n, hd]) => <React.Fragment key={v}>{hd && <div className="px-2 pt-2 pb-1 text-xs font-medium text-muted-foreground">{hd}</div>}
      <label className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm cursor-pointer hover:bg-accent"><input type="checkbox" className="accent-[hsl(var(--primary))]" checked={set.has(v)} onChange={() => onToggle(v)} />
        {swatch && <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: colorOf(v) }} />}<span className="truncate">{labelFn ? labelFn(v) : v}</span><span className="ml-auto text-xs text-muted-foreground tabular-nums">{n}</span></label></React.Fragment>)}
    <button onClick={onClear} className="w-full text-left rounded-b-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent mt-1 border-t">Tout effacer</button>
  </>;
}
export const Icon = ({ d, size = 18, ...p }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}>{Array.isArray(d) ? d.map((x, i) => <path key={i} d={x} />) : <path d={d} />}</svg>;
export const ICONS = {
  up: "m18 15-6-6-6 6", search: ["M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14z", "m20 20-3.5-3.5"], cal: ["M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M16 2v4M8 2v4M3 10h18"],
  random: "M2 18h1.4c1.3 0 2.5-.6 3.3-1.7l6.1-8.6c.7-1.1 2-1.7 3.3-1.7H22M18 2l4 4-4 4M2 6h1.9c1.5 0 2.9.9 3.6 2.2M22 18h-5.9c-1.3 0-2.6-.7-3.3-1.8l-.5-.8M18 14l4 4-4 4",
  star: "m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z", history: ["M3 12a9 9 0 1 0 3-6.7", "M3 3v5h5", "M12 7v5l3 2"], map: ["M9 20 3 17V4l6 3 6-3 6 3v13l-6-3-6 3z", "M9 7v13M15 4v13"],
  week: ["M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M3 10h18M9 4v18M15 4v18"], list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01", pin: ["M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z", "M12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"],
  moon: "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z", sun: ["M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4", "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z"],
  check: "M20 6 9 17l-5-5", share: ["M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8", "M16 6l-4-4-4 4M12 2v13"], download: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M7 10l5 5 5-5M12 15V3"], x: "M18 6 6 18M6 6l12 12", github: "M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 0 0-.9-2.6c3.1-.3 6.4-1.5 6.4-7A5.4 5.4 0 0 0 20 4.8 5 5 0 0 0 19.9 1s-1.2-.4-3.9 1.5a13.4 13.4 0 0 0-7 0C6.3.6 5.1 1 5.1 1A5 5 0 0 0 5 4.8a5.4 5.4 0 0 0-1.5 3.7c0 5.5 3.3 6.7 6.4 7A3.4 3.4 0 0 0 9 18v4",
};
