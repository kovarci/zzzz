/* Paris·Académique — front. `npm run build` dans web/ produit ../app.js + ../app.css. */
import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { motion, AnimatePresence } from "framer-motion";
import L from "leaflet";
import * as lib from "./lib.js";
import { SITE, REPO, DISC, SRC_LABEL, MAIN_INST, WD, WDS, MO, TODAY, TOMORROW, WEEK_END, WE, today, iso, parse, addDays, norm, cn, dc, kindOf, isFree, isOnline, isNew, fmtDay, fmtShort, relDay, when, thumb, haversine, fmtDist, relTime, EMPTY_FILTERS, matches, filtersFromURL, urlFromState, buildIcs, download, googleCalUrl, store } from "./lib.js";
import { NumberTicker, AnimatedShinyText, Marquee, BlurFade, BorderBeam, DotPattern, BentoGrid, BentoCard, Dock, DockIcon, DockSep, HoverEffect, MovingBorderButton, Spotlight, Button, LinkButton, Badge, Kbd, Tabs, Popover, CheckList, Icon, ICONS } from "./ui.jsx";

const PAGE = 48;

/* ═════════════════════ Couverture / carte ═════════════════════ */
function Cover({ e, className = "", eager }) {
  const [broken, setBroken] = useState(false);
  const pos = className.split(" ").includes("absolute") ? "" : "relative";
  const badge = <Badge className="absolute top-2.5 left-2.5 bg-background/90 text-foreground backdrop-blur border-0 shadow-sm z-[1]">{kindOf(e)}</Badge>;
  if (e.image && !broken) return <div className={cn(pos, "overflow-hidden bg-muted", className)}>
    <img src={thumb(e.image)} alt="" loading={eager ? "eager" : "lazy"} decoding="async" onError={() => setBroken(true)} className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]" />{badge}</div>;
  return <div className={cn(pos, "overflow-hidden flex items-end p-4 text-white", className)} style={{ background: `linear-gradient(135deg, ${dc(e)}, color-mix(in srgb, ${dc(e)} 55%, #000))` }}>
    <DotPattern className="[mask-image:radial-gradient(ellipse_at_top_right,#000,transparent_70%)]" />{badge}
    <div className="relative font-semibold text-lg leading-tight tracking-tight [text-wrap:balance] drop-shadow line-clamp-3">{e.institution}</div></div>;
}
function EventCard({ e, fav, onFav, onOpen, selectMode, selected, onSelect, distance, past }) {
  return <div onClick={() => selectMode ? onSelect(e.id) : onOpen(e)} className={cn("group relative flex h-full flex-col overflow-hidden rounded-xl border bg-card shadow-sm cursor-pointer", selected && "ring-2 ring-primary", past && "opacity-80")}>
    {selectMode
      ? <span className={cn("absolute top-2.5 right-2.5 z-10 inline-flex h-7 w-7 items-center justify-center rounded-md border-2 bg-background/90 backdrop-blur", selected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40")}>{selected && <Icon d={ICONS.check} size={14} />}</span>
      : <button onClick={ev => { ev.stopPropagation(); onFav(e.id); }} aria-label="Favori" className={cn("absolute top-2.5 right-2.5 z-10 inline-flex h-8 w-8 items-center justify-center rounded-md bg-background/80 backdrop-blur transition", fav ? "text-amber-500" : "text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-foreground")}>{fav ? "★" : "☆"}</button>}
    <Cover e={e} className="aspect-[16/10]" />
    <div className="p-4 flex flex-col gap-1.5 flex-1">
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><span className="h-2 w-2 rounded-full shrink-0" style={{ background: dc(e) }} /><span className="tabular-nums font-medium text-foreground">{when(e)}</span><span className="truncate">· {e.discipline}</span>
        {distance !== undefined ? <Badge className="ml-auto tabular-nums">{fmtDist(distance)}</Badge> : isNew(e) && !past ? <Badge className="ml-auto border-sky-500/30 text-sky-600 dark:text-sky-400">Nouveau</Badge> : isFree(e) ? <Badge className="ml-auto border-emerald-500/30 text-emerald-600 dark:text-emerald-400">Gratuit</Badge> : null}</div>
      <h3 className="font-semibold leading-snug tracking-tight line-clamp-3">{e.title}</h3>
      {e.speaker && <p className="text-sm text-muted-foreground line-clamp-1">{e.speaker}</p>}
      <p className="mt-auto pt-2 text-xs text-muted-foreground truncate">{isOnline(e) && "En ligne · "}{e.institution}{e.location ? " · " + e.location.split(",")[0] : ""}</p>
    </div></div>;
}

/* ═════════════════════ Fiche (sheet) ═════════════════════ */
function Sheet({ e, onClose, fav, onFav, onToast }) {
  useEffect(() => { if (!e) return; const h = ev => ev.key === "Escape" && onClose(); document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h); }, [e]);
  const share = async () => {
    const url = `${SITE}/e/${e.id}.html`;
    if (navigator.share && /android|iphone|ipad|mobile/i.test(navigator.userAgent)) { try { await navigator.share({ title: e.title, url }); return; } catch (err) { return; } }
    try { await navigator.clipboard.writeText(url); onToast("Lien copié"); } catch (err) { prompt("Copie ce lien :", url); }
  };
  return <AnimatePresence>{e && <React.Fragment key={e.id}>
    <motion.div className="fixed inset-0 z-50 bg-black/50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
    <motion.aside className="fixed inset-y-0 right-0 z-50 w-full sm:max-w-lg bg-background border-l shadow-2xl flex flex-col overflow-auto" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 380, damping: 40 }} aria-modal="true" role="dialog">
      {(() => { const d = parse(e.date), days = Math.round((d - today) / 864e5); return <>
        <div className="relative aspect-[16/10] shrink-0 group"><Cover e={e} className="absolute inset-0" eager /><button onClick={onClose} className="absolute top-3 right-3 z-[2] inline-flex h-8 w-8 items-center justify-center rounded-md bg-background/90 shadow hover:bg-background" aria-label="Fermer"><Icon d={ICONS.x} size={16} /></button></div>
        <div className="p-6 flex flex-col gap-4">
          <div className="flex flex-wrap gap-2"><Badge style={{ borderColor: dc(e), color: dc(e) }}>{e.discipline}</Badge><Badge>{kindOf(e)}</Badge>{isFree(e) && <Badge className="border-emerald-500/30 text-emerald-600 dark:text-emerald-400">Entrée libre</Badge>}{isOnline(e) && <Badge>En ligne</Badge>}<Badge>{SRC_LABEL[e.source_type] || "Universités & instituts"}</Badge></div>
          <h2 className="text-2xl font-semibold tracking-tight leading-tight [text-wrap:balance]">{e.title}</h2>
          <div className="flex items-center gap-3 rounded-lg border bg-card p-3">
            <div className="flex flex-col items-center justify-center rounded-md bg-muted px-3 py-1.5 min-w-14"><span className="text-[10px] uppercase tracking-wide text-muted-foreground">{WDS[d.getDay()]}</span><span className="text-xl font-bold leading-none tabular-nums">{d.getDate()}</span><span className="text-[10px] text-muted-foreground">{MO[d.getMonth()].slice(0, 4)}</span></div>
            <div className="text-sm"><div className="font-medium capitalize">{fmtDay(e.date)} {d.getFullYear()}</div><div className="text-muted-foreground">{e.time ? `${when(e)} · ` : ""}{days < 0 ? "terminé" : days === 0 ? "c'est aujourd'hui" : days === 1 ? "c'est demain" : `dans ${days} jours`}</div></div>
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">{[["Organisé par", e.institution], ["Avec", e.speaker], ["Lieu", e.location], ["Tarif", e.price ? (isFree(e) ? "Entrée libre" : e.price) : null]].filter(r => r[1]).map(([k, v]) => <React.Fragment key={k}><dt className="text-muted-foreground">{k}</dt><dd className="break-words">{v}</dd></React.Fragment>)}</dl>
          {e.description && e.description.length > 60 && <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-line">{e.description}</p>}
          <div className="grid gap-2 pt-2">
            {e.url && <LinkButton href={e.url} target="_blank" rel="noopener">Page officielle · inscription ↗</LinkButton>}
            <div className="grid grid-cols-3 gap-2">
              <Button variant="outline" onClick={() => onFav(e.id)} className="px-2">{fav ? "★ Favori" : "☆ Favori"}</Button>
              <Popover label="Agenda" align="left">{close => <div className="p-1 min-w-[200px]">
                <a className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent" href={googleCalUrl(e)} target="_blank" rel="noopener" onClick={close}>Google Agenda ↗</a>
                <button className="w-full text-left flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent" onClick={() => { download(`${e.id}.ics`, buildIcs([e])); close(); }}>Fichier .ics (Apple, Outlook…)</button></div>}</Popover>
              <Button variant="outline" onClick={share} className="px-2"><Icon d={ICONS.share} size={14} />Partager</Button>
            </div>
          </div>
        </div>
        <p className="mt-auto p-6 pt-0 text-xs text-muted-foreground">Vérifie les horaires sur la page officielle avant de te déplacer.</p></>; })()}
    </motion.aside></React.Fragment>}</AnimatePresence>;
}

/* ═════════════════════ Palette ⌘K ═════════════════════ */
function CommandDialog({ open, onClose, onPick, pool }) {
  const [q, setQ] = useState(""); const [sel, setSel] = useState(0); const inputRef = useRef(null);
  const res = useMemo(() => { const n = norm(q.trim()); return (n ? pool.filter(e => { const hay = norm([e.title, e.speaker, e.institution, e.location].join(" ")); return n.split(/\s+/).every(w => hay.includes(w)); }) : pool.filter(e => e.date === TODAY || e.date === TOMORROW)).slice(0, 30); }, [q, pool]);
  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => inputRef.current?.focus(), 30); } }, [open]);
  useEffect(() => setSel(0), [q]);
  const onKey = ev => { if (ev.key === "ArrowDown") { ev.preventDefault(); setSel(s => (s + 1) % Math.max(1, res.length)); } else if (ev.key === "ArrowUp") { ev.preventDefault(); setSel(s => (s - 1 + res.length) % Math.max(1, res.length)); } else if (ev.key === "Enter" && res[sel]) onPick(res[sel]); };
  return <AnimatePresence>{open && <motion.div key="cmd" className="fixed inset-0 z-[60]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .12 }}>
    <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
    <motion.div initial={{ scale: .97, y: -8 }} animate={{ scale: 1, y: 0 }} exit={{ scale: .97, y: -8 }} className="absolute left-1/2 top-[12vh] w-[min(640px,calc(100%-2rem))] -translate-x-1/2 rounded-xl border bg-popover shadow-2xl overflow-hidden" role="dialog" aria-modal="true">
      <div className="flex items-center gap-2 border-b px-3"><Icon d={ICONS.search} size={16} className="text-muted-foreground" />
        <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" placeholder="Un titre, un intervenant, un sujet…" /><Kbd>ESC</Kbd></div>
      <div className="max-h-[50vh] overflow-auto p-1">{res.length ? res.map((e, i) => <button key={e.id} onMouseEnter={() => setSel(i)} onClick={() => onPick(e)} className={cn("w-full flex items-center gap-3 rounded-md px-2 py-2 text-left text-sm", i === sel && "bg-accent")}>
        <span className="h-2 w-2 rounded-full shrink-0" style={{ background: dc(e) }} /><span className="flex-1 min-w-0"><span className="block truncate">{e.title}</span><span className="block text-xs text-muted-foreground truncate">{e.institution}{e.speaker ? " · " + e.speaker : ""}</span></span><span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">{fmtShort(e.date)}{e.time ? " " + e.time : ""}</span></button>)
        : <p className="p-6 text-center text-sm text-muted-foreground">Aucun résultat.</p>}</div>
      <div className="flex items-center gap-3 border-t px-3 py-2 text-[11px] text-muted-foreground"><span><kbd className="font-mono">↑↓</kbd> naviguer</span><span><kbd className="font-mono">↵</kbd> ouvrir</span><span className="ml-auto">{q ? `${res.length} résultat${res.length > 1 ? "s" : ""}` : "Aujourd'hui et demain"}</span></div>
    </motion.div></motion.div>}</AnimatePresence>;
}

/* ═════════════════════ Vue semaine ═════════════════════ */
function WeekView({ events, onOpen, favs }) {
  const [offset, setOffset] = useState(0);
  const monday = addDays(today, -((today.getDay() + 6) % 7) + offset * 7);
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  const from = iso(days[0]), to = iso(days[6]);
  const inWeek = events.filter(e => e.date >= from && e.date <= to);
  return <div className="pt-6">
    <div className="flex items-center justify-between mb-4">
      <Button variant="outline" size="sm" onClick={() => setOffset(o => o - 1)}>← Semaine préc.</Button>
      <div className="text-center"><div className="font-semibold capitalize">{days[0].getDate()} {MO[days[0].getMonth()]} → {days[6].getDate()} {MO[days[6].getMonth()]} {days[6].getFullYear()}</div><div className="text-xs text-muted-foreground">{inWeek.length} événement{inWeek.length > 1 ? "s" : ""}{offset !== 0 && <button className="ml-2 underline" onClick={() => setOffset(0)}>cette semaine</button>}</div></div>
      <Button variant="outline" size="sm" onClick={() => setOffset(o => o + 1)}>Semaine suiv. →</Button>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-7 gap-2 overflow-x-auto">
      {days.map(d => { const k = iso(d), evs = inWeek.filter(e => e.date === k); return <div key={k} className={cn("rounded-xl border bg-card min-h-[120px] flex flex-col", k === TODAY && "ring-2 ring-primary")}>
        <div className={cn("px-3 py-2 border-b text-xs font-semibold capitalize flex items-baseline justify-between", k < TODAY && "text-muted-foreground")}><span>{WDS[d.getDay()]} {d.getDate()}</span><span className="text-muted-foreground font-normal tabular-nums">{evs.length || ""}</span></div>
        <div className="flex flex-col divide-y overflow-auto max-h-[60vh]">{evs.map(e => <button key={e.id} onClick={() => onOpen(e)} className="text-left px-3 py-2 hover:bg-accent text-xs flex flex-col gap-0.5">
          <span className="flex items-center gap-1.5 text-muted-foreground tabular-nums"><span className="h-1.5 w-1.5 rounded-full" style={{ background: dc(e) }} />{e.time || "—"}{favs.has(e.id) && <span className="text-amber-500">★</span>}</span>
          <span className="font-medium leading-snug line-clamp-3">{e.title}</span><span className="text-muted-foreground truncate">{e.institution}</span></button>)}</div>
      </div>; })}
    </div></div>;
}

/* ═════════════════════ Carte Leaflet ═════════════════════ */
function MapView({ events, onOpen, userPos }) {
  const ref = useRef(null), mapRef = useRef(null), layerRef = useRef(null), tileRef = useRef(null), live = useRef({ events, onOpen });
  live.current = { events, onOpen };
  useEffect(() => {
    const map = L.map(ref.current, { scrollWheelZoom: true }).setView(userPos ? [userPos.lat, userPos.lng] : [48.8566, 2.349], userPos ? 13 : 12);
    // OSM (CARTO exige désormais une clé) ; en sombre, les tuiles sont inversées en CSS (.leaflet-tile)
    tileRef.current = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19 }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map); mapRef.current = map;
    map.on("popupopen", ev => { ev.popup.getElement().querySelectorAll("[data-open]").forEach(b => b.addEventListener("click", () => { const e = live.current.events.find(x => x.id === b.dataset.open); if (e) live.current.onOpen(e); })); });
    return () => map.remove();
  }, []);
  useEffect(() => {
    const layer = layerRef.current; if (!layer) return; layer.clearLayers();
    const byLoc = new Map();
    events.forEach(e => { if (typeof e.lat !== "number") return; const k = `${e.lat.toFixed(4)},${e.lng.toFixed(4)}`; if (!byLoc.has(k)) byLoc.set(k, []); byLoc.get(k).push(e); });
    byLoc.forEach((evs, k) => {
      const [lat, lng] = k.split(",").map(Number), first = evs[0];
      const icon = L.divIcon({ className: "", html: `<div class="pin" style="background:${getComputedStyle(document.documentElement).getPropertyValue(DISC[first.discipline] || "--c-aut").trim()}"></div>`, iconSize: [12, 12], iconAnchor: [6, 6] });
      const html = `<div style="max-width:240px"><div style="font-weight:600;margin-bottom:6px">${first.location ? first.location.split(",")[0].replace(/</g, "&lt;") : first.institution}</div>` +
        evs.slice(0, 6).map(e => `<div style="margin:4px 0"><span style="opacity:.7">${fmtShort(e.date)}${e.time ? " " + e.time : ""}</span> · <a href="#" data-open="${e.id}" onclick="return false">${e.title.replace(/</g, "&lt;")}</a></div>`).join("") +
        (evs.length > 6 ? `<div style="opacity:.7">+ ${evs.length - 6} autres</div>` : "") + "</div>";
      L.marker([lat, lng], { icon }).bindPopup(html).addTo(layer);
    });
    if (userPos) L.marker([userPos.lat, userPos.lng], { icon: L.divIcon({ className: "", html: '<div class="pin-me"></div>', iconSize: [14, 14], iconAnchor: [7, 7] }) }).bindPopup("Vous êtes ici").addTo(layer);
  }, [events, userPos]);
  return <div className="pt-6"><div ref={ref} className="h-[70vh] rounded-xl border overflow-hidden z-0" /><p className="text-xs text-muted-foreground mt-2">{events.filter(e => typeof e.lat === "number").length} événements localisés · clique un point pour voir les conférences du lieu.</p></div>;
}

/* ═════════════════════ App ═════════════════════ */
function useFavs() {
  const [favs, setFavs] = useState(() => new Set(store.get("paf_favs", [])));
  const toggle = useCallback(id => setFavs(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); store.set("paf_favs", [...n]); return n; }), []);
  return [favs, toggle];
}
function App() {
  const init = useMemo(filtersFromURL, []);
  const [events, setEvents] = useState(null); const [loadErr, setLoadErr] = useState(null);
  const [archive, setArchive] = useState(null); const [meta, setMeta] = useState({}); const [digest, setDigest] = useState(null);
  const [filters, setFilters] = useState(init.filters); const [rawQ, setRawQ] = useState(init.rawQ);
  const [view, setView] = useState(init.view); const [history, setHistory] = useState(init.history); const [histMonth, setHistMonth] = useState("all");
  const [favs, toggleFav] = useFavs(); const [open, setOpen] = useState(null); const [cmd, setCmd] = useState(false); const [shown, setShown] = useState(PAGE); const [toast, setToast] = useState(null);
  const [selectMode, setSelectMode] = useState(false); const [selected, setSelected] = useState(new Set());
  const [near, setNear] = useState(false); const [userPos, setUserPos] = useState(null); const [locating, setLocating] = useState(false);
  const agendaRef = useRef(null), moreRef = useRef(null), pendingEvent = useRef(init.event);
  const setF = patch => setFilters(f => ({ ...f, ...patch }));
  const toggleIn = key => v => setFilters(f => { const n = new Set(f[key]); n.has(v) ? n.delete(v) : n.add(v); return { ...f, [key]: n }; });
  const notify = msg => { setToast(msg); setTimeout(() => setToast(null), 1500); };
  const goAgenda = () => agendaRef.current?.scrollIntoView({ behavior: "smooth" });

  /* données */
  useEffect(() => {
    fetch("data/events.json?" + Date.now()).then(r => r.json()).then(list => {
      list.forEach(e => { if (!e.source_type) e.source_type = "institution"; });
      list.sort((a, b) => (a.date + (a.time || "")).localeCompare(b.date + (b.time || "")));
      setEvents(list);
    }).catch(e => setLoadErr(e.message));
    fetch("data/meta.json?" + Date.now()).then(r => r.json()).then(setMeta).catch(() => {});
    fetch("data/digest.json?" + Date.now()).then(r => r.json()).then(d => d?.events?.length && setDigest(d)).catch(() => {});
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  }, []);
  const ensureArchive = useCallback(() => archive ? Promise.resolve(archive) : fetch("data/events-archive.json?" + Date.now()).then(r => r.json()).catch(() => []).then(a => { a.sort((x, y) => (y.date + (y.time || "")).localeCompare(x.date + (x.time || ""))); setArchive(a); return a; }), [archive]);
  useEffect(() => { if (history) ensureArchive(); }, [history]);
  // ?event=<id> (pages e/*.html) : ouvre la fiche, dans les événements à venir ou l'archive
  useEffect(() => {
    if (!events || !pendingEvent.current) return; const id = pendingEvent.current; pendingEvent.current = null;
    const e = events.find(x => x.id === id); if (e) { setOpen(e); return; }
    ensureArchive().then(a => { const p = a.find(x => x.id === id); p ? setOpen(p) : notify("Événement introuvable — il est peut-être terminé."); });
  }, [events]);
  useEffect(() => { window.history.replaceState(null, "", urlFromState({ filters, view, history, rawQ })); }, [filters, view, history, rawQ]);
  useEffect(() => { const h = ev => { if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); setCmd(c => !c); } if (ev.key === "Escape") setCmd(false); }; document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h); }, []);

  /* dérivés */
  const UP = useMemo(() => (events || []).filter(e => e.date >= TODAY), [events]);
  const pool = history ? (archive || []) : UP;
  const filtered = useMemo(() => {
    let list = pool.filter(e => matches(e, history ? { ...filters, when: "all" } : filters, favs));
    if (history && histMonth !== "all") list = list.filter(e => e.date.startsWith(histMonth));
    if (near && userPos) list = list.filter(e => typeof e.lat === "number").map(e => ({ ...e, _d: haversine(userPos, { lat: e.lat, lng: e.lng }) })).sort((a, b) => a._d - b._d);
    return list;
  }, [pool, filters, favs, history, histMonth, near, userPos]);
  useEffect(() => setShown(PAGE), [filtered]);
  useEffect(() => { const el = moreRef.current; if (!el) return; const io = new IntersectionObserver(es => es[0].isIntersecting && setShown(s => s + PAGE), { rootMargin: "800px" }); io.observe(el); return () => io.disconnect(); }, [shown, filtered, view]);
  const counts = useMemo(() => { const c = k => { const m = {}; UP.forEach(e => m[e[k]] = (m[e[k]] || 0) + 1); return m; }; const th = {}; UP.forEach(e => (e.luma_categories || []).forEach(t => th[t] = (th[t] || 0) + 1)); return { disc: c("discipline"), inst: c("institution"), src: c("source_type"), theme: th }; }, [UP]);
  const nToday = UP.filter(e => e.date === TODAY).length, nWeek = UP.filter(e => e.date <= WEEK_END).length, nWe = UP.filter(e => WE.includes(e.date)).length, nNew = UP.filter(isNew).length;
  const topInst = useMemo(() => Object.entries(counts.inst).sort((a, b) => b[1] - a[1]).slice(0, 18), [counts]);
  const featured = useMemo(() => {
    // Le digest (data/digest.json) est la sélection éditoriale de la semaine ; sinon sélection automatique
    const fromDigest = digest ? digest.events.map(d => UP.find(e => e.id === d.id)).filter(Boolean).filter(e => e.date <= WEEK_END) : [];
    const pool = fromDigest.length >= 3 ? fromDigest : UP.filter(e => e.date === TODAY || e.date === TOMORROW);
    const score = e => (e.image ? 2 : 0) + (MAIN_INST.includes(e.institution) ? 1.5 : 0) + (e.speaker ? .5 : 0) + ((e.description || "").length > 80 ? .5 : 0);
    return [...pool].sort((a, b) => score(b) - score(a)).slice(0, 3);
  }, [UP, digest]);
  const tonight = UP.filter(e => e.date === TODAY && (e.time || "") >= "17:30");
  const days7 = useMemo(() => [...Array(7)].map((_, i) => { const d = addDays(today, i), k = iso(d); return { k, d, n: UP.filter(e => e.date === k).length }; }), [UP]);
  const max7 = Math.max(1, ...days7.map(x => x.n));
  const groups = useMemo(() => { const g = []; filtered.slice(0, shown).forEach(e => { if (!g.length || g[g.length - 1].date !== e.date) g.push({ date: e.date, items: [] }); g[g.length - 1].items.push(e); }); return g; }, [filtered, shown]);
  const histMonths = useMemo(() => [...new Set((archive || []).map(e => e.date.slice(0, 7)))].sort().reverse(), [archive]);
  const activeTags = [...[...filters.disc].map(v => [v, () => toggleIn("disc")(v)]), ...[...filters.inst].map(v => [v, () => toggleIn("inst")(v)]), ...[...filters.src].map(v => [SRC_LABEL[v], () => toggleIn("src")(v)]), ...[...filters.theme].map(v => ["Luma · " + v, () => toggleIn("theme")(v)]), ...(filters.online ? [["En ligne", () => setF({ online: false })]] : [])];

  /* actions */
  const onFav = id => { toggleFav(id); notify(favs.has(id) ? "Retiré des favoris" : "Ajouté aux favoris"); };
  const onSelect = id => setSelected(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const exportSel = () => { const evs = pool.filter(e => selected.has(e.id)); if (!evs.length) return; download("ma-selection-paris-academique.ics", buildIcs(evs)); notify(`${evs.length} événement${evs.length > 1 ? "s" : ""} exporté${evs.length > 1 ? "s" : ""}`); };
  const toggleNear = () => {
    if (near) { setNear(false); return; }
    if (userPos) { setNear(true); return; }
    if (!navigator.geolocation) { notify("Géolocalisation indisponible sur ce navigateur."); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(p => { setUserPos({ lat: p.coords.latitude, lng: p.coords.longitude }); setNear(true); setLocating(false); }, err => { setLocating(false); notify("Localisation impossible : " + err.message); });
  };
  const toggleHistory = () => { setHistory(h => !h); setView("list"); setNear(false); goAgenda(); };
  const toggleTheme = () => { const r = document.documentElement, dark = r.dataset.theme === "dark" || (!r.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches); r.dataset.theme = dark ? "light" : "dark"; store.set("paf_theme", dark ? "light" : "dark"); };
  const pickRandom = () => { const p = filtered.length ? filtered : pool; if (p.length) setOpen(p[Math.floor(Math.random() * p.length)]); };

  if (loadErr) return <div className="mx-auto max-w-lg p-10 text-center"><p className="font-semibold">Erreur de chargement</p><p className="text-sm text-muted-foreground mt-1">{loadErr}</p></div>;

  return <>
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-14 flex items-center gap-4">
        <a href="/" className="flex items-center gap-2 font-semibold tracking-tight"><span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-sm font-bold">P</span><span>Paris·Académique</span></a>
        <nav className="hidden md:flex items-center gap-1 text-sm text-muted-foreground ml-4"><button onClick={() => { setHistory(false); goAgenda(); }} className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-accent">Agenda</button><button onClick={toggleHistory} className={cn("px-3 py-1.5 rounded-md hover:text-foreground hover:bg-accent", history && "text-foreground bg-accent")}>Historique</button><a href="apropos.html" className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-accent">À propos</a></nav>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setCmd(true)} className="inline-flex items-center gap-2 h-9 rounded-md border bg-background px-3 text-sm text-muted-foreground shadow-sm hover:bg-accent hover:text-foreground w-10 sm:w-64 justify-center sm:justify-between" aria-label="Rechercher"><Icon d={ICONS.search} size={15} className="sm:hidden" /><span className="hidden sm:inline">Rechercher…</span><Kbd className="hidden sm:inline-flex">⌘K</Kbd></button>
          <Button variant="outline" size="icon" onClick={toggleTheme} aria-label="Changer de thème"><Icon d={ICONS.moon} size={16} className="dark:hidden" /><Icon d={ICONS.sun} size={16} className="hidden dark:block" /></Button>
          <MovingBorderButton href="data/calendar.ics" className="hidden sm:inline-flex h-9">S'abonner</MovingBorderButton>
        </div></div></header>

    <main className="mx-auto max-w-7xl px-4 sm:px-6">
      <section className="relative pt-14 pb-8 text-center">
        <Spotlight className="-top-40 left-0 md:left-60 md:-top-20" />
        <BlurFade inView={false}><div className="inline-flex items-center rounded-full border bg-background/60 px-4 py-1 text-sm shadow-sm"><AnimatedShinyText>✦ {meta.last_workflow_run ? `Mis à jour ${relTime(meta.last_workflow_run)}` : "Mis à jour chaque matin"}{events ? ` · ${UP.length} événements à venir` : ""}</AnimatedShinyText></div></BlurFade>
        <BlurFade inView={false} delay={.1}><h1 className="mt-6 text-4xl sm:text-6xl font-bold tracking-tight [text-wrap:balance] max-w-4xl mx-auto leading-[1.05]">Toutes les conférences de Paris, <span className="bg-gradient-to-r from-[#3B82F6] via-[#8B5CF6] to-[#EC4899] bg-clip-text text-transparent">en un seul agenda.</span></h1></BlurFade>
        <BlurFade inView={false} delay={.2}><p className="mt-5 text-lg text-muted-foreground max-w-2xl mx-auto [text-wrap:balance]">Cours du Collège de France, séminaires de l'IHP et de PSE, rencontres Luma : {events ? `${Object.keys(counts.inst).length} organisateurs réunis, ${UP.filter(isFree).length} événements en entrée libre.` : "chargement…"}</p></BlurFade>
        <BlurFade inView={false} delay={.3}><div className="mt-8 flex flex-wrap justify-center gap-3"><Button onClick={() => { setHistory(false); setF({ when: "today" }); goAgenda(); }} className="h-11 px-6">Voir aujourd'hui</Button><Button variant="outline" onClick={() => { setHistory(false); setF({ when: "week" }); goAgenda(); }} className="h-11 px-6">Cette semaine</Button></div></BlurFade>
        <BlurFade inView={false} delay={.4}><div className="relative mt-12 grid grid-cols-3 max-w-xl mx-auto divide-x rounded-xl border bg-card shadow-sm">
          {[[nToday, "aujourd'hui", "today"], [nWeek, "cette semaine", "week"], [nWe, "ce week-end", "weekend"]].map(([n, l, w], i) => <button key={w} onClick={() => { setHistory(false); setF({ when: w }); goAgenda(); }} className="flex flex-col items-center py-4 hover:bg-accent first:rounded-l-xl last:rounded-r-xl"><span className="text-3xl font-bold"><NumberTicker value={n} delay={.2 + i * .1} /></span><span className="text-xs text-muted-foreground mt-1">{l}</span></button>)}
          <BorderBeam size={200} duration={12} colorFrom="#3B82F6" colorTo="#EC4899" /></div></BlurFade>
      </section>

      {topInst.length > 0 && <section className="py-2 relative [mask-image:linear-gradient(to_right,transparent,#000_10%,#000_90%,transparent)]">
        <Marquee pauseOnHover>{topInst.map(([i, n]) => <button key={i} onClick={() => { setHistory(false); setF({ inst: new Set([i]) }); goAgenda(); }} className="inline-flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm shadow-sm hover:bg-accent whitespace-nowrap"><span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-muted text-xs font-semibold">{i[0]}</span>{i}<span className="text-xs text-muted-foreground tabular-nums">{n}</span></button>)}</Marquee>
      </section>}

      {events && <section className="py-10">
        <BlurFade><div className="mb-5 flex items-end justify-between gap-4"><div><h2 className="text-2xl font-semibold tracking-tight">À la une</h2><p className="text-sm text-muted-foreground mt-1">{digest && featured.length >= 3 ? `Sélection de la semaine — ${digest.period}` : "Aujourd'hui et demain, sélection automatique."}</p></div></div></BlurFade>
        <BentoGrid>
          {featured[0] && <BentoCard className="lg:col-span-2 lg:row-span-2" name={featured[0].title} meta={`${relDay(featured[0].date) || fmtShort(featured[0].date)}${featured[0].time ? " · " + featured[0].time : ""} · ${featured[0].institution}`} description={featured[0].speaker} onClick={() => setOpen(featured[0])}
            background={<div className="group h-full"><Cover e={featured[0]} className="absolute inset-0" eager /><div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" /></div>} />}
          {featured.slice(1, 3).map(e => <BentoCard key={e.id} name={e.title} meta={`${relDay(e.date) || fmtShort(e.date)}${e.time ? " · " + e.time : ""}`} onClick={() => setOpen(e)}
            background={<div className="group h-full"><Cover e={e} className="absolute inset-0" eager /><div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" /></div>} />)}
          <div className="col-span-1 flex flex-col gap-2 rounded-xl border bg-card p-4 shadow-sm overflow-hidden"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Ce soir</h3><Badge>{tonight.length}</Badge></div>
            {tonight.length ? <ul className="flex flex-col divide-y text-sm overflow-hidden">{tonight.slice(0, 4).map(e => <li key={e.id}><button onClick={() => setOpen(e)} className="w-full text-left py-1.5 flex gap-2 text-muted-foreground hover:text-foreground"><span className="font-mono text-xs pt-0.5 tabular-nums text-foreground">{e.time}</span><span className="truncate">{e.title}</span></button></li>)}</ul> : <p className="text-sm text-muted-foreground">Rien après 17h30 aujourd'hui. Regarde demain.</p>}</div>
          <div className="col-span-1 lg:col-span-2 flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Les 7 prochains jours</h3><span className="text-xs text-muted-foreground">{days7.reduce((s, x) => s + x.n, 0)} événements</span></div>
            <div className="flex items-end gap-2 flex-1 min-h-[80px]">{days7.map(x => <button key={x.k} onClick={() => { setHistory(false); setF({ when: "all" }); setView("list"); setTimeout(() => document.querySelector(`[data-date="${x.k}"]`)?.scrollIntoView({ behavior: "smooth" }), 60); }} className="flex-1 flex flex-col items-center gap-1 group/bar"><span className="text-[11px] tabular-nums text-muted-foreground">{x.n}</span><motion.span initial={{ height: 6 }} whileInView={{ height: Math.max(6, x.n / max7 * 64) }} viewport={{ once: true }} transition={{ type: "spring", stiffness: 120, damping: 18 }} className="w-full rounded-md bg-primary/80 group-hover/bar:bg-primary" /><span className={cn("text-[11px]", x.k === TODAY ? "font-semibold" : "text-muted-foreground")}>{WDS[x.d.getDay()]} {x.d.getDate()}</span></button>)}</div></div>
        </BentoGrid>
      </section>}

      <div ref={agendaRef} className="scroll-mt-14" />
      <div className="sticky top-14 z-30 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 bg-background/80 backdrop-blur border-b">
        <div className="flex flex-wrap items-center gap-2">
          {history
            ? <><Badge variant="solid" className="h-9 px-3 text-sm">Historique</Badge><select value={histMonth} onChange={e => setHistMonth(e.target.value)} className="h-9 rounded-md border bg-background px-2 text-sm"><option value="all">Toute la période</option>{histMonths.map(m => <option key={m} value={m}>{MO[+m.slice(5, 7) - 1]} {m.slice(0, 4)}</option>)}</select><Button variant="outline" size="sm" className="h-9" onClick={toggleHistory}>← Retour à l'agenda</Button></>
            : <div className="overflow-x-auto max-w-full"><Tabs value={filters.when} onChange={w => setF({ when: w })} items={[["all", "Tout"], ["today", "Aujourd'hui"], ["tonight", "Ce soir"], ["week", "Semaine"], ["weekend", "Week-end"], ...(nNew ? [["new", `Nouveautés · ${nNew}`]] : [])]} /></div>}
          <Popover label="Discipline" count={filters.disc.size}>{() => <CheckList values={Object.keys(DISC).filter(d => counts.disc[d]).map(d => [d, counts.disc[d]])} set={filters.disc} onToggle={toggleIn("disc")} swatch colorOf={v => `var(${DISC[v] || "--c-aut"})`} onClear={() => setF({ disc: new Set() })} />}</Popover>
          <Popover label="Institution" count={filters.inst.size}>{() => <CheckList values={[...MAIN_INST.filter(i => counts.inst[i]).map((i, k) => [i, counts.inst[i], k === 0 ? "Établissements" : null]), ...Object.entries(counts.inst).filter(([i]) => !MAIN_INST.includes(i)).sort((a, b) => b[1] - a[1]).slice(0, 30).map(([i, n], k) => [i, n, k === 0 ? "Autres organisateurs" : null])]} set={filters.inst} onToggle={toggleIn("inst")} onClear={() => setF({ inst: new Set() })} />}</Popover>
          <Popover label="Source" count={filters.src.size + filters.theme.size}>{() => <>
            <CheckList values={Object.keys(SRC_LABEL).filter(s => counts.src[s]).map(s => [s, counts.src[s]])} set={filters.src} onToggle={toggleIn("src")} labelFn={v => SRC_LABEL[v]} onClear={() => setF({ src: new Set(), theme: new Set() })} />
            {Object.keys(counts.theme).length > 0 && <CheckList values={Object.entries(counts.theme).sort((a, b) => b[1] - a[1]).map(([t, n], k) => [t, n, k === 0 ? "Thèmes Luma" : null])} set={filters.theme} onToggle={toggleIn("theme")} onClear={() => setF({ theme: new Set() })} />}</>}</Popover>
          <Button variant={filters.fav ? "default" : "outline"} size="sm" className="h-9" onClick={() => setF({ fav: !filters.fav })} aria-pressed={filters.fav}>★<span className="hidden sm:inline"> Favoris</span>{favs.size > 0 && <span className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px]", filters.fav ? "bg-primary-foreground text-primary" : "bg-primary text-primary-foreground")}>{favs.size}</span>}</Button>
          <Button variant={filters.online ? "default" : "outline"} size="sm" className="h-9" onClick={() => setF({ online: !filters.online })} aria-pressed={filters.online}>En ligne</Button>
          <div className="ml-auto flex items-center gap-2">
            {!history && <Tabs value={view} onChange={setView} layoutId="view-pill" items={[["list", <Icon d={ICONS.list} size={15} />], ["week", <Icon d={ICONS.week} size={15} />], ["map", <Icon d={ICONS.map} size={15} />]]} />}
            {!history && <Button variant={near ? "default" : "outline"} size="sm" className="h-9" onClick={toggleNear} aria-pressed={near} disabled={locating}><Icon d={ICONS.pin} size={14} /><span className="hidden lg:inline">{locating ? "Localisation…" : near ? "Tri par distance" : "Près de moi"}</span></Button>}
            <Button variant={selectMode ? "default" : "outline"} size="sm" className="h-9" onClick={() => { setSelectMode(m => !m); setSelected(new Set()); }} aria-pressed={selectMode}><Icon d={ICONS.check} size={14} /><span className="hidden lg:inline">Sélection</span></Button>
            <span className="text-sm text-muted-foreground tabular-nums whitespace-nowrap"><b className="text-foreground font-medium">{filtered.length}</b><span className="hidden sm:inline"> événement{filtered.length > 1 ? "s" : ""}</span></span>
          </div>
        </div>
        {(activeTags.length > 0 || rawQ) && <div className="flex flex-wrap gap-1.5 mt-2">{rawQ && <span className="inline-flex items-center gap-1 rounded-md border bg-background pl-2 pr-1 py-0.5 text-xs font-medium">« {rawQ} »<button onClick={() => { setRawQ(""); setF({ q: "" }); }} className="inline-flex h-4 w-4 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground">×</button></span>}{activeTags.map(([l, rm]) => <span key={l} className="inline-flex items-center gap-1 rounded-md border bg-background pl-2 pr-1 py-0.5 text-xs font-medium">{l}<button onClick={rm} className="inline-flex h-4 w-4 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground">×</button></span>)}</div>}
      </div>

      <section className="py-4 pb-36">
        {!events && <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 pt-6">{[...Array(8)].map((_, i) => <div key={i} className="rounded-xl border bg-card overflow-hidden animate-pulse"><div className="aspect-[16/10] bg-muted" /><div className="p-4 space-y-2"><div className="h-3 w-1/3 bg-muted rounded" /><div className="h-4 w-4/5 bg-muted rounded" /><div className="h-3 w-1/2 bg-muted rounded" /></div></div>)}</div>}
        {events && history && !archive && <p className="pt-6 text-sm text-muted-foreground">Chargement de l'historique…</p>}
        {events && !filtered.length && (!history || archive) && <div className="mt-6 rounded-xl border border-dashed p-12 text-center"><p className="font-medium">{filters.fav && !favs.size ? "Aucun favori" : "Rien ne correspond"}</p><p className="text-sm text-muted-foreground mt-1">{filters.fav && !favs.size ? "Clique sur l'étoile d'un événement pour le retrouver ici." : "Élargis la période ou retire un filtre."}</p></div>}
        {events && view === "week" && !history && <WeekView events={filtered} onOpen={setOpen} favs={favs} />}
        {events && view === "map" && !history && <MapView events={filtered} onOpen={setOpen} userPos={userPos} />}
        {events && (view === "list" || history) && (near && userPos
          ? <div className="pt-6"><p className="text-sm text-muted-foreground mb-2 px-2">Triés par distance depuis ta position.</p><HoverEffect items={filtered.slice(0, shown)} render={e => <EventCard e={e} fav={favs.has(e.id)} onFav={onFav} onOpen={setOpen} selectMode={selectMode} selected={selected.has(e.id)} onSelect={onSelect} distance={e._d} />} /></div>
          : groups.map(g => { const d = parse(g.date), n = filtered.filter(x => x.date === g.date).length; return <section key={g.date} data-date={g.date} className="pt-8 scroll-mt-32">
            <div className="flex items-baseline gap-3 mb-2 px-2"><h2 className="text-xl font-semibold tracking-tight capitalize">{fmtDay(g.date)}{d.getFullYear() !== today.getFullYear() ? " " + d.getFullYear() : ""}</h2>{relDay(g.date) && <Badge variant="solid">{relDay(g.date)}</Badge>}<span className="ml-auto text-sm text-muted-foreground tabular-nums">{n}</span></div>
            <HoverEffect items={g.items} render={e => <EventCard e={e} fav={favs.has(e.id)} onFav={onFav} onOpen={setOpen} selectMode={selectMode} selected={selected.has(e.id)} onSelect={onSelect} past={history} />} />
          </section>; }))}
        {events && (view === "list" || history) && shown < filtered.length && <div ref={moreRef} className="flex justify-center pt-10"><Button variant="outline" onClick={() => setShown(s => s + PAGE)}>Afficher la suite · {filtered.length - shown} restants</Button></div>}
      </section>
    </main>

    <footer className="border-t">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-10 grid gap-8 md:grid-cols-3 text-sm">
        <div><div className="font-semibold">Paris·Académique</div><p className="text-muted-foreground mt-2 max-w-xs">Toutes les conférences, cours et séminaires ouverts au public à Paris, réunis chaque matin en un seul agenda.</p><p className="text-xs text-muted-foreground mt-3">Dernière mise à jour automatique : {relTime(meta.last_workflow_run)}{meta.last_manual_run && ` · manuelle : ${relTime(meta.last_manual_run)}`}</p></div>
        <div><div className="font-semibold">S'abonner</div><ul className="mt-2 space-y-1.5 text-muted-foreground"><li><a className="hover:text-foreground" href="data/calendar.ics">Calendrier complet (.ics)</a></li><li><a className="hover:text-foreground" href="data/digest.xml">Flux RSS de la semaine</a></li><li><a className="hover:text-foreground" href="sitemap.xml">Plan du site</a></li><li><a className="hover:text-foreground" href="apropos.html">À propos</a></li></ul></div>
        <div><div className="font-semibold">Une question, une idée ?</div><p className="text-muted-foreground mt-2">Le site est open source. Une source manquante, un bug, une suggestion : ouvre un ticket sur GitHub.</p>
          <a href={`${REPO}/issues`} target="_blank" rel="noopener" className="mt-3 inline-flex h-10 items-center gap-2 rounded-md border bg-background px-4 font-medium shadow-sm hover:bg-accent"><Icon d={ICONS.github} size={16} />Questions & recommandations</a>
          <p className="text-xs text-muted-foreground mt-2"><a className="hover:text-foreground underline underline-offset-2" href={REPO} target="_blank" rel="noopener">Code source du projet</a></p></div>
      </div>
    </footer>

    <AnimatePresence>{selectMode && <motion.div initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }} className="fixed bottom-24 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 rounded-xl border bg-popover px-3 py-2 shadow-lg text-sm"><span className="tabular-nums"><b>{selected.size}</b> sélectionné{selected.size > 1 ? "s" : ""}</span><Button size="sm" onClick={exportSel} disabled={!selected.size}><Icon d={ICONS.download} size={14} />Exporter .ics</Button><Button size="sm" variant="ghost" onClick={() => { setSelectMode(false); setSelected(new Set()); }}>Terminer</Button></motion.div>}</AnimatePresence>

    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40">
      <Dock>
        <DockIcon title="Haut de page" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}><Icon d={ICONS.up} /></DockIcon>
        <DockIcon title="Aujourd'hui" active={!history && filters.when === "today"} onClick={() => { setHistory(false); setF({ when: "today" }); goAgenda(); }}><Icon d={ICONS.cal} /></DockIcon>
        <DockIcon title="Historique" active={history} onClick={toggleHistory}><Icon d={ICONS.history} /></DockIcon>
        <DockIcon title="Au hasard" onClick={pickRandom}><Icon d={ICONS.random} /></DockIcon>
        <DockIcon title="Favoris" active={filters.fav} onClick={() => { setF({ fav: !filters.fav }); goAgenda(); }}><Icon d={ICONS.star} />{favs.size > 0 && <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 rounded-full bg-primary text-primary-foreground text-[10px] font-bold px-1 leading-4">{favs.size}</span>}</DockIcon>
        <DockSep />
        <DockIcon title="Rechercher (⌘K)" onClick={() => setCmd(true)}><Icon d={ICONS.search} /></DockIcon>
      </Dock>
    </div>

    <Sheet e={open} onClose={() => setOpen(null)} fav={open ? favs.has(open.id) : false} onFav={onFav} onToast={notify} />
    <CommandDialog open={cmd} onClose={() => setCmd(false)} onPick={e => { setCmd(false); setOpen(e); }} pool={pool} />
    <AnimatePresence>{toast && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 rounded-md border bg-popover px-3 py-2 text-sm shadow-lg">{toast}</motion.div>}</AnimatePresence>
  </>;
}

// Thème mémorisé par l'ancien site (paf_theme) : appliqué avant le premier rendu
const savedTheme = store.get("paf_theme", null);
if (savedTheme === "dark" || savedTheme === "light") document.documentElement.dataset.theme = savedTheme;
createRoot(document.getElementById("root")).render(<App />);
