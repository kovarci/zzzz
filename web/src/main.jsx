/* Lotent — front. `npm run build` dans web/ produit ../app.js + ../app.css. */
import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { motion, AnimatePresence } from "framer-motion";
import L from "leaflet";
import { SITE, REPO, PROPOSE_URL, DISC, MAIN_INST, TODAY, TOMORROW, WEEK_END, WE, today, iso, parse, addDays, norm, cn, dc, kindOf, SIDE_KINDS, isSide, isMembers, accessOf, titleOf, isFree, isOnline, isNew, when, thumb, haversine, fmtDist, slugify, EMPTY_FILTERS, matches, filtersFromURL, urlFromState, buildIcs, download, googleCalUrl, store } from "./lib.js";
import { NumberTicker, AnimatedShinyText, Marquee, BlurFade, BorderBeam, DotPattern, BentoGrid, BentoCard, Dock, DockIcon, DockSep, HoverEffect, MovingBorderButton, Spotlight, Button, LinkButton, Badge, Kbd, Tabs, Popover, CheckList, Icon, ICONS } from "./ui.jsx";
import { LangProvider, useI18n } from "./i18n.jsx";

const PAGE = 48;
// Couleur CSS résolue d'une discipline (var(--c-xxx) → couleur réelle), pour Leaflet qui ne lit pas les custom properties.
const discColor = disc => getComputedStyle(document.documentElement).getPropertyValue(DISC[disc] || "--c-aut").trim();

/* ═════════════════════ Couverture / carte ═════════════════════ */
function Cover({ e, className = "", eager }) {
  const [broken, setBroken] = useState(false);
  const pos = className.split(" ").includes("absolute") ? "" : "relative";
  const { t } = useI18n();
  const badge = <div className="absolute top-2.5 left-2.5 z-[1] flex flex-wrap gap-1.5">
    <Badge className="bg-background/90 text-foreground backdrop-blur border-0 shadow-sm">{kindOf(e)}</Badge>
    {isMembers(e) && <Badge className="bg-background/90 text-foreground backdrop-blur border-0 shadow-sm" title={t("access_members_hint")}>🔒 {t("badge_members")}</Badge>}</div>;
  if (e.image && !broken) return <div className={cn(pos, "overflow-hidden bg-muted", className)}>
    <img src={thumb(e.image)} alt="" loading={eager ? "eager" : "lazy"} decoding="async" onError={() => setBroken(true)} className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]" />{badge}</div>;
  return <div className={cn(pos, "overflow-hidden flex items-end p-4 text-white", className)} style={{ background: `linear-gradient(135deg, ${dc(e)}, color-mix(in srgb, ${dc(e)} 55%, #000))` }}>
    <DotPattern className="[mask-image:radial-gradient(ellipse_at_top_right,#000,transparent_70%)]" />{badge}
    <div className="relative font-semibold text-lg leading-tight tracking-tight [text-wrap:balance] drop-shadow line-clamp-3">{e.institution}</div></div>;
}
function EventCard({ e, fav, onFav, onOpen, selectMode, selected, onSelect, distance, past }) {
  const { t } = useI18n();
  return <div onClick={() => selectMode ? onSelect(e.id) : onOpen(e)} className={cn("group relative flex h-full flex-col overflow-hidden rounded-xl border bg-card shadow-sm cursor-pointer", selected && "ring-2 ring-primary", past && "opacity-80")}>
    {selectMode
      ? <span className={cn("absolute top-2.5 right-2.5 z-10 inline-flex h-7 w-7 items-center justify-center rounded-md border-2 bg-background/90 backdrop-blur", selected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40")}>{selected && <Icon d={ICONS.check} size={14} />}</span>
      : <button onClick={ev => { ev.stopPropagation(); onFav(e.id); }} aria-label={t("favori")} className={cn("absolute top-2.5 right-2.5 z-10 inline-flex h-8 w-8 items-center justify-center rounded-md bg-background/80 backdrop-blur transition", fav ? "text-amber-500" : "text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-foreground")}>{fav ? "★" : "☆"}</button>}
    <Cover e={e} className="aspect-[16/10]" />
    <div className="p-4 flex flex-col gap-1.5 flex-1">
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><span className="h-2 w-2 rounded-full shrink-0" style={{ background: dc(e) }} /><span className="tabular-nums font-medium text-foreground">{e.time ? `${e.time}${e.end_time ? " – " + e.end_time : ""}` : t("time_tbd")}</span><span className="truncate">· {e.discipline}</span>
        {distance !== undefined ? <Badge className="ml-auto tabular-nums">{fmtDist(distance)}</Badge> : isNew(e) && !past ? <Badge className="ml-auto border-sky-500/30 text-sky-600 dark:text-sky-400">{t("badge_new")}</Badge> : isFree(e) ? <Badge className="ml-auto border-emerald-500/30 text-emerald-600 dark:text-emerald-400">{t("badge_free")}</Badge> : null}</div>
      <h3 className="font-semibold leading-snug tracking-tight line-clamp-3">{e.title}</h3>
      {e.speaker && <p className="text-sm text-muted-foreground line-clamp-1">{e.speaker}</p>}
      <p className="mt-auto pt-2 text-xs text-muted-foreground truncate">{isOnline(e) && (t("online_prefix") || "")}{e.institution}{e.location ? " · " + e.location.split(",")[0] : ""}</p>
    </div></div>;
}

/* ═════════════════════ Fiche (sheet) ═════════════════════ */
function Sheet({ e, onClose, fav, onFav, onToast, following, onFollow }) {
  const { t, fmtDay } = useI18n();
  useEffect(() => { if (!e) return; const h = ev => ev.key === "Escape" && onClose(); document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h); }, [e]);
  const share = async () => {
    const url = `${SITE}/e/${e.id}.html`;
    if (navigator.share && /android|iphone|ipad|mobile/i.test(navigator.userAgent)) { try { await navigator.share({ title: e.title, url }); return; } catch (err) { return; } }
    try { await navigator.clipboard.writeText(url); onToast(t("toast_link_copied")); } catch (err) { prompt("", url); }
  };
  return <AnimatePresence>{e && <React.Fragment key={e.id}>
    <motion.div className="fixed inset-0 z-50 bg-black/50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
    <motion.aside className="fixed inset-y-0 right-0 z-50 w-full sm:max-w-lg bg-background border-l shadow-2xl flex flex-col overflow-auto" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 380, damping: 40 }} aria-modal="true" role="dialog">
      {(() => { const d = parse(e.date), days = Math.round((d - today) / 864e5); return <>
        <div className="relative aspect-[16/10] shrink-0 group"><Cover e={e} className="absolute inset-0" eager /><button onClick={onClose} className="absolute top-3 right-3 z-[2] inline-flex h-8 w-8 items-center justify-center rounded-md bg-background/90 shadow hover:bg-background" aria-label={t("fermer")}><Icon d={ICONS.x} size={16} /></button></div>
        <div className="p-6 flex flex-col gap-4">
          <div className="flex flex-wrap gap-2"><Badge style={{ borderColor: dc(e), color: dc(e) }}>{e.discipline}</Badge><Badge>{kindOf(e)}</Badge>{isMembers(e) && <Badge title={t("access_members_hint")}>🔒 {t("access_members")}</Badge>}{isFree(e) && <Badge className="border-emerald-500/30 text-emerald-600 dark:text-emerald-400">{t("sheet_free")}</Badge>}{isOnline(e) && <Badge>{t("sheet_online")}</Badge>}<Badge>{t("src_" + e.source_type) || t("org_default")}</Badge></div>
          <h2 className="text-2xl font-semibold tracking-tight leading-tight [text-wrap:balance]">{e.title}</h2>
          <div className="flex items-center gap-3 rounded-lg border bg-card p-3">
            <div className="flex flex-col items-center justify-center rounded-md bg-muted px-3 py-1.5 min-w-14"><span className="text-xl font-bold leading-none tabular-nums">{d.getDate()}</span></div>
            <div className="text-sm"><div className="font-medium capitalize">{fmtDay(e.date)} {d.getFullYear()}</div><div className="text-muted-foreground">{e.time ? `${e.time}${e.end_time ? " – " + e.end_time : ""} · ` : ""}{days < 0 ? t("sheet_terminated") : days === 0 ? t("sheet_today") : days === 1 ? t("sheet_tomorrow") : t("sheet_in_days", { n: days })}</div></div>
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">{[[t("sheet_organizer"), e.institution, null], [t("sheet_with"), e.speaker, "speaker"], [t("sheet_place"), e.location, null], [t("sheet_price"), e.price ? (isFree(e) ? t("sheet_free") : e.price) : null, null]].filter(r => r[1]).map(([k, v, kind]) => <React.Fragment key={k}><dt className="text-muted-foreground">{k}</dt><dd className="break-words">{kind === "speaker" ? <span className="inline-flex items-center gap-1.5">{v}<button onClick={() => onFollow(v)} aria-label={following ? t("unfollow_speaker") : t("follow_speaker")} title={following ? t("unfollow_speaker") : t("follow_speaker")} className={cn("inline-flex h-5 w-5 items-center justify-center rounded", following ? "text-amber-500" : "text-muted-foreground hover:text-foreground")}><Icon d={following ? ICONS.bell : ICONS.bellOff} size={13} /></button></span> : v}</dd></React.Fragment>)}</dl>
          {e.description && e.description.length > 60 && <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-line">{e.description}</p>}
          <div className="grid gap-2 pt-2">
            {e.url && <LinkButton href={e.url} target="_blank" rel="noopener">{t("sheet_official")}</LinkButton>}
            <div className="grid grid-cols-3 gap-2">
              <Button variant="outline" onClick={() => onFav(e.id)} className="px-2">{fav ? t("sheet_fav_on") : t("sheet_fav_off")}</Button>
              <Popover label={t("sheet_agenda")} align="left">{close => <div className="p-1 min-w-[200px]">
                <a className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent" href={googleCalUrl(e)} target="_blank" rel="noopener" onClick={close}>{t("sheet_google_cal")}</a>
                <button className="w-full text-left flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent" onClick={() => { download(`${e.id}.ics`, buildIcs([e])); close(); }}>{t("sheet_ics_file")}</button></div>}</Popover>
              <Button variant="outline" onClick={share} className="px-2"><Icon d={ICONS.share} size={14} />{t("sheet_share")}</Button>
            </div>
          </div>
        </div>
        <p className="mt-auto p-6 pt-0 text-xs text-muted-foreground">{t("sheet_footer_note")}</p></>; })()}
    </motion.aside></React.Fragment>}</AnimatePresence>;
}

/* ═════════════════════ Palette ⌘K ═════════════════════ */
function CommandDialog({ open, onClose, onPick, pool }) {
  const { t, fmtShort } = useI18n();
  const [q, setQ] = useState(""); const [sel, setSel] = useState(0); const inputRef = useRef(null);
  const res = useMemo(() => { const n = norm(q.trim()); return (n ? pool.filter(e => { const hay = norm([e.title, e.speaker, e.institution, e.location].join(" ")); return n.split(/\s+/).every(w => hay.includes(w)); }) : pool.filter(e => e.date === TODAY || e.date === TOMORROW)).slice(0, 30); }, [q, pool]);
  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => inputRef.current?.focus(), 30); } }, [open]);
  useEffect(() => setSel(0), [q]);
  const onKey = ev => { if (ev.key === "ArrowDown") { ev.preventDefault(); setSel(s => (s + 1) % Math.max(1, res.length)); } else if (ev.key === "ArrowUp") { ev.preventDefault(); setSel(s => (s - 1 + res.length) % Math.max(1, res.length)); } else if (ev.key === "Enter" && res[sel]) onPick(res[sel]); };
  return <AnimatePresence>{open && <motion.div key="cmd" className="fixed inset-0 z-[60]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .12 }}>
    <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
    <motion.div initial={{ scale: .97, y: -8 }} animate={{ scale: 1, y: 0 }} exit={{ scale: .97, y: -8 }} className="absolute left-1/2 top-[12vh] w-[min(640px,calc(100%-2rem))] -translate-x-1/2 rounded-xl border bg-popover shadow-2xl overflow-hidden" role="dialog" aria-modal="true">
      <div className="flex items-center gap-2 border-b px-3"><Icon d={ICONS.search} size={16} className="text-muted-foreground" />
        <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" placeholder={t("cmd_ph")} /><Kbd>ESC</Kbd></div>
      <div className="max-h-[50vh] overflow-auto p-1">{res.length ? res.map((e, i) => <button key={e.id} onMouseEnter={() => setSel(i)} onClick={() => onPick(e)} className={cn("w-full flex items-center gap-3 rounded-md px-2 py-2 text-left text-sm", i === sel && "bg-accent")}>
        <span className="h-2 w-2 rounded-full shrink-0" style={{ background: dc(e) }} /><span className="flex-1 min-w-0"><span className="block truncate">{titleOf(e)}</span><span className="block text-xs text-muted-foreground truncate">{e.institution}{e.speaker ? " · " + e.speaker : ""}</span></span><span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">{fmtShort(e.date)}{e.time ? " " + e.time : ""}</span></button>)
        : <p className="p-6 text-center text-sm text-muted-foreground">{t("cmd_none")}</p>}</div>
      <div className="flex items-center gap-3 border-t px-3 py-2 text-[11px] text-muted-foreground"><span><kbd className="font-mono">↑↓</kbd> {t("cmd_nav")}</span><span><kbd className="font-mono">↵</kbd> {t("cmd_open")}</span><span className="ml-auto">{q ? t("cmd_n_results", { n: res.length }) : t("cmd_today_tomorrow")}</span></div>
    </motion.div></motion.div>}</AnimatePresence>;
}

/* ═════════════════════ Vue semaine ═════════════════════ */
function WeekView({ events, onOpen, favs }) {
  const { t, WDS, MO } = useI18n();
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const h = ev => {
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "")) return;
      if (ev.key === "ArrowLeft") setOffset(o => o - 1);
      if (ev.key === "ArrowRight") setOffset(o => o + 1);
    };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, []);
  const monday = addDays(today, -((today.getDay() + 6) % 7) + offset * 7);
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  const from = iso(days[0]), to = iso(days[6]);
  const inWeek = events.filter(e => e.date >= from && e.date <= to);
  return <div className="pt-6">
    <div className="flex items-center justify-between mb-4">
      <Button variant="outline" size="sm" onClick={() => setOffset(o => o - 1)}>{t("week_prev")}</Button>
      <div className="text-center"><div className="font-semibold capitalize">{days[0].getDate()} {MO[days[0].getMonth()]} → {days[6].getDate()} {MO[days[6].getMonth()]} {days[6].getFullYear()}</div><div className="text-xs text-muted-foreground">{inWeek.length} {t("noun_event", { n: inWeek.length })}{offset !== 0 && <button className="ml-2 underline" onClick={() => setOffset(0)}>{t("week_this")}</button>}</div></div>
      <Button variant="outline" size="sm" onClick={() => setOffset(o => o + 1)}>{t("week_next")}</Button>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-7 gap-2 overflow-x-auto">
      {days.map(d => { const k = iso(d), evs = inWeek.filter(e => e.date === k); return <div key={k} className={cn("rounded-xl border bg-card min-h-[120px] flex flex-col", k === TODAY && "ring-2 ring-primary")}>
        <div className={cn("px-3 py-2 border-b text-xs font-semibold capitalize flex items-baseline justify-between", k < TODAY && "text-muted-foreground")}><span>{WDS[d.getDay()]} {d.getDate()}</span><span className="text-muted-foreground font-normal tabular-nums">{evs.length || ""}</span></div>
        <div className="flex flex-col divide-y overflow-auto max-h-[60vh]">{evs.map(e => <button key={e.id} onClick={() => onOpen(e)} className="text-left px-3 py-2 hover:bg-accent text-xs flex flex-col gap-0.5">
          <span className="flex items-center gap-1.5 text-muted-foreground tabular-nums"><span className="h-1.5 w-1.5 rounded-full" style={{ background: dc(e) }} />{e.time || "—"}{favs.has(e.id) && <span className="text-amber-500">★</span>}</span>
          <span className="font-medium leading-snug line-clamp-3">{titleOf(e)}</span><span className="text-muted-foreground truncate">{e.institution}</span></button>)}</div>
      </div>; })}
    </div></div>;
}

/* ═════════════════════ Carte Leaflet (pleine) ═════════════════════ */
function MapView({ events, onOpen, userPos }) {
  const { t, fmtShort } = useI18n();
  const ref = useRef(null), mapRef = useRef(null), layerRef = useRef(null), live = useRef({ events, onOpen });
  live.current = { events, onOpen };
  useEffect(() => {
    const map = L.map(ref.current, { scrollWheelZoom: true }).setView(userPos ? [userPos.lat, userPos.lng] : [48.8566, 2.349], userPos ? 13 : 12);
    // OSM (CARTO exige désormais une clé) ; en sombre, les tuiles sont inversées en CSS (.leaflet-tile)
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19 }).addTo(map);
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
      const icon = L.divIcon({ className: "", html: `<div class="pin" style="background:${discColor(first.discipline)}"></div>`, iconSize: [12, 12], iconAnchor: [6, 6] });
      const html = `<div style="max-width:240px"><div style="font-weight:600;margin-bottom:6px">${first.location ? first.location.split(",")[0].replace(/</g, "&lt;") : first.institution}</div>` +
        evs.slice(0, 6).map(e => `<div style="margin:4px 0"><span style="opacity:.7">${fmtShort(e.date)}${e.time ? " " + e.time : ""}</span> · <a href="#" data-open="${e.id}" onclick="return false">${e.title.replace(/</g, "&lt;")}</a></div>`).join("") +
        (evs.length > 6 ? `<div style="opacity:.7">+ ${evs.length - 6}</div>` : "") + "</div>";
      L.marker([lat, lng], { icon }).bindPopup(html).addTo(layer);
    });
    if (userPos) L.marker([userPos.lat, userPos.lng], { icon: L.divIcon({ className: "", html: '<div class="pin-me"></div>', iconSize: [14, 14], iconAnchor: [7, 7] }) }).bindPopup(t("you_are_here")).addTo(layer);
  }, [events, userPos]);
  return <div className="pt-6"><div ref={ref} className="h-[70vh] rounded-xl border overflow-hidden z-0" /><p className="text-xs text-muted-foreground mt-2">{t("map_note", { n: events.filter(e => typeof e.lat === "number").length })}</p></div>;
}

/* ═════════════════════ Mini-carte (bento, aperçu) ═════════════════════ */
function MiniMap({ events, onGoMap }) {
  const { t } = useI18n();
  const ref = useRef(null), mapRef = useRef(null), layerRef = useRef(null);
  useEffect(() => {
    const map = L.map(ref.current, { zoomControl: false, attributionControl: false, dragging: false, scrollWheelZoom: false, doubleClickZoom: false, touchZoom: false, boxZoom: false, keyboard: false, tap: false }).setView([48.8566, 2.349], 11.6);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map); mapRef.current = map;
    const t0 = setTimeout(() => map.invalidateSize(), 60);
    return () => { clearTimeout(t0); map.remove(); };
  }, []);
  const geo = useMemo(() => events.filter(e => typeof e.lat === "number"), [events]);
  useEffect(() => {
    const layer = layerRef.current; if (!layer) return; layer.clearLayers();
    geo.slice(0, 200).forEach(e => { L.circleMarker([e.lat, e.lng], { radius: 4, weight: 0, fillOpacity: .85, fillColor: discColor(e.discipline) }).addTo(layer); });
  }, [geo]);
  return <button onClick={onGoMap} className="group relative col-span-1 lg:col-span-2 rounded-xl border bg-card shadow-sm overflow-hidden text-left">
    <div ref={ref} className="absolute inset-0 pointer-events-none [&_.leaflet-control-attribution]:hidden" />
    <div className="absolute inset-0 bg-gradient-to-t from-background via-background/20 to-transparent transition-opacity group-hover:opacity-90" />
    <div className="absolute inset-x-0 bottom-0 flex items-end justify-between p-4">
      <div><h3 className="text-sm font-semibold">{t("map_title")}</h3><p className="text-xs text-muted-foreground">{t("n_events", { n: geo.length })}</p></div>
      <span className="text-sm font-medium shrink-0 group-hover:underline">{t("map_cta")}</span>
    </div>
  </button>;
}

/* ═════════════════════ Bandeau institution (filtre unique) ═════════════════════ */
function InstitutionBanner({ name, events, onClear }) {
  const { t } = useI18n();
  const evs = useMemo(() => events.filter(e => e.institution === name), [events, name]);
  const slug = slugify(name);
  const isMain = MAIN_INST.includes(name);
  return <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 my-3 shadow-sm">
    <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-semibold text-white" style={{ background: evs[0] ? discColor(evs[0].discipline) : "var(--c-aut)" }}>{name[0]}</span>
    <div className="flex-1 min-w-0"><div className="font-semibold text-sm truncate">{name}</div><div className="text-xs text-muted-foreground">{t("inst_events_count", { n: evs.length })}</div></div>
    <div className="flex items-center gap-3 shrink-0 ml-auto">
      {isMain && <a href={`i/${slug}.html`} className="text-xs font-medium text-muted-foreground hover:text-foreground hover:underline hidden sm:inline">{t("inst_site")}</a>}
      {isMain && <a href={`data/cal/${slug}.ics`} className="text-xs font-medium text-muted-foreground hover:text-foreground hover:underline hidden sm:inline">{t("inst_ics")}</a>}
      <Button variant="outline" size="sm" onClick={onClear}>{t("inst_clear")}</Button>
    </div>
  </div>;
}

/* ═════════════════════ Mes intervenants ═════════════════════ */
function SpeakersPanel({ open, onClose, speakers, onUnfollow, pool, onOpenEvent, notifyPerm, onEnableNotify }) {
  const { t, fmtShort } = useI18n();
  const list = useMemo(() => [...speakers].sort((a, b) => a.localeCompare(b)), [speakers]);
  return <AnimatePresence>{open && <motion.div key="speakers" className="fixed inset-0 z-[60]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .12 }}>
    <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
    <motion.div initial={{ scale: .97, y: -8 }} animate={{ scale: 1, y: 0 }} exit={{ scale: .97, y: -8 }} className="absolute left-1/2 top-[10vh] w-[min(480px,calc(100%-2rem))] max-h-[78vh] -translate-x-1/2 rounded-xl border bg-popover shadow-2xl overflow-hidden flex flex-col" role="dialog" aria-modal="true">
      <div className="flex items-center justify-between border-b px-4 py-3"><h2 className="font-semibold text-sm">{t("my_speakers")}</h2><button onClick={onClose} className="inline-flex h-7 w-7 items-center justify-center rounded-md hover:bg-accent" aria-label={t("fermer")}><Icon d={ICONS.x} size={15} /></button></div>
      {notifyPerm !== "unsupported" && <div className="px-4 py-2 border-b bg-muted/40 text-xs">
        {notifyPerm === "granted" ? <span className="text-emerald-600 dark:text-emerald-400 font-medium">{t("notify_enabled")}</span>
          : notifyPerm === "denied" ? <span className="text-muted-foreground">{t("notify_denied")}</span>
          : <button onClick={onEnableNotify} className="font-medium underline underline-offset-2 hover:text-foreground">{t("notify_enable")}</button>}
      </div>}
      <div className="overflow-auto flex-1">
        {!list.length ? <div className="p-8 text-center"><p className="text-sm font-medium">{t("no_speakers")}</p><p className="text-xs text-muted-foreground mt-1">{t("no_speakers_sub")}</p></div>
          : <ul className="divide-y">{list.map(name => {
            const talks = pool.filter(e => e.speaker && e.speaker.toLowerCase().includes(name.toLowerCase())).slice(0, 3);
            return <li key={name} className="px-4 py-3">
              <div className="flex items-center justify-between gap-2"><span className="font-medium text-sm truncate">{name}</span><button onClick={() => onUnfollow(name)} className="text-xs text-muted-foreground hover:text-foreground shrink-0">{t("unfollow_speaker")}</button></div>
              {talks.length ? <ul className="mt-1.5 flex flex-col gap-1">{talks.map(e => <li key={e.id}><button onClick={() => onOpenEvent(e)} className="w-full text-left text-xs text-muted-foreground hover:text-foreground flex gap-2"><span className="tabular-nums shrink-0">{fmtShort(e.date)}</span><span className="truncate">{e.title}</span></button></li>)}</ul>
                : <p className="mt-1 text-xs text-muted-foreground">{t("no_upcoming")}</p>}
            </li>; })}</ul>}
      </div>
    </motion.div></motion.div>}</AnimatePresence>;
}

/* ═════════════════════ Carte GitHub (contact) ═════════════════════ */
function GithubCard() {
  const { t } = useI18n();
  return <div className="flex flex-col gap-3">
    <div><div className="font-semibold">{t("footer_contact_title")}</div><p className="text-muted-foreground mt-2">{t("footer_contact_body")}</p></div>
    <a href={`${REPO}/issues`} target="_blank" rel="noopener" className="group flex items-center gap-3 rounded-xl border bg-card p-3 shadow-sm hover:border-foreground/25 hover:bg-accent transition">
      <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-foreground text-background"><Icon d={ICONS.github} size={18} /></span>
      <span className="flex-1 min-w-0"><span className="block font-semibold text-sm">kovarci/zzzz</span><span className="block text-xs text-muted-foreground truncate">{t("footer_repo_desc")}</span></span>
      <span className="text-xs font-medium text-muted-foreground shrink-0 group-hover:text-foreground">{t("footer_open_issue")} ↗</span>
    </a>
    <p className="text-xs text-muted-foreground"><a className="hover:text-foreground underline underline-offset-2" href={REPO} target="_blank" rel="noopener">{t("footer_source")}</a></p>
  </div>;
}

/* ═════════════════════ App ═════════════════════ */
function useFavs() {
  const [favs, setFavs] = useState(() => new Set(store.get("paf_favs", [])));
  const toggle = useCallback(id => setFavs(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); store.set("paf_favs", [...n]); return n; }), []);
  return [favs, toggle];
}
// Intervenants suivis (paf_speakers) + notifications : événements déjà vus
// pour un intervenant suivi (paf_speakers_seen), pour ne notifier qu'une fois.
function useSpeakers() {
  const [speakers, setSpeakers] = useState(() => new Set(store.get("paf_speakers", [])));
  const [seen, setSeen] = useState(() => new Set(store.get("paf_speakers_seen", [])));
  const toggle = useCallback(name => setSpeakers(s => { const n = new Set(s); n.has(name) ? n.delete(name) : n.add(name); store.set("paf_speakers", [...n]); return n; }), []);
  const markSeen = useCallback(ids => setSeen(s => { const n = new Set(s); ids.forEach(id => n.add(id)); store.set("paf_speakers_seen", [...n]); return n; }), []);
  return { speakers, toggle, seen, markSeen };
}
function App() {
  const { t, lang, toggleLang, fmtDay, fmtShort, relDay, relTime, MO } = useI18n();
  const init = useMemo(filtersFromURL, []);
  const [events, setEvents] = useState(null); const [loadErr, setLoadErr] = useState(null);
  const [archive, setArchive] = useState(null); const [meta, setMeta] = useState({}); const [digest, setDigest] = useState(null);
  const [filters, setFilters] = useState(init.filters); const [rawQ, setRawQ] = useState(init.rawQ);
  const [view, setView] = useState(init.view); const [history, setHistory] = useState(init.history); const [histMonth, setHistMonth] = useState("all");
  const [favs, toggleFav] = useFavs(); const [open, setOpen] = useState(null); const [cmd, setCmd] = useState(false); const [shown, setShown] = useState(PAGE); const [toast, setToast] = useState(null);
  const { speakers, toggle: toggleSpeaker, seen: seenSpeakerEvents, markSeen } = useSpeakers();
  const [speakersOpen, setSpeakersOpen] = useState(false);
  const [notifyPerm, setNotifyPerm] = useState(() => (typeof Notification === "undefined" ? "unsupported" : Notification.permission));
  const [selectMode, setSelectMode] = useState(false); const [selected, setSelected] = useState(new Set());
  const [near, setNear] = useState(false); const [userPos, setUserPos] = useState(null); const [locating, setLocating] = useState(false);
  const agendaRef = useRef(null), moreRef = useRef(null), pendingEvent = useRef(init.event);
  const setF = patch => setFilters(f => ({ ...f, ...patch }));
  const toggleIn = key => v => setFilters(f => { const n = new Set(f[key]); n.has(v) ? n.delete(v) : n.add(v); return { ...f, [key]: n }; });
  const notify = msg => { setToast(msg); setTimeout(() => setToast(null), 1500); };
  const goAgenda = () => agendaRef.current?.scrollIntoView({ behavior: "smooth" });
  // Basculer agenda <-> historique ajoute ou retire tout le haut de page (hero,
  // carrousel, bento) : l'ancre mesurée avant le rendu est donc périmée de ~1000px.
  // On note où aller et on scrolle une fois la nouvelle mise en page posée.
  const pendingScroll = useRef(null);
  const SRC_LABEL_T = { institution: t("src_institution"), luma: t("src_luma"), association: t("src_association"), ville: t("src_ville") };

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
  // Agenda rendu (ou erreur affichée) : on efface en fondu l'écran de
  // chargement d'index.html — deux frames, le temps que le rendu soit peint.
  useEffect(() => { if (events || loadErr) requestAnimationFrame(() => requestAnimationFrame(() => window.__lotentReady?.())); }, [events, loadErr]);
  const ensureArchive = useCallback(() => archive ? Promise.resolve(archive) : fetch("data/events-archive.json?" + Date.now()).then(r => r.json()).catch(() => []).then(a => { a.sort((x, y) => (y.date + (y.time || "")).localeCompare(x.date + (x.time || ""))); setArchive(a); return a; }), [archive]);
  useEffect(() => { if (history) ensureArchive(); }, [history]);
  useEffect(() => { document.documentElement.classList.toggle("history-mode", history); }, [history]);
  useEffect(() => {
    const to = pendingScroll.current; if (!to) return; pendingScroll.current = null;
    if (to === "top") window.scrollTo({ top: 0, behavior: "smooth" }); else goAgenda();
  }, [history]);
  // ?event=<id> (pages e/*.html) : ouvre la fiche, dans les événements à venir ou l'archive
  useEffect(() => {
    if (!events || !pendingEvent.current) return; const id = pendingEvent.current; pendingEvent.current = null;
    const e = events.find(x => x.id === id); if (e) { setOpen(e); return; }
    ensureArchive().then(a => { const p = a.find(x => x.id === id); p ? setOpen(p) : notify(t("toast_not_found")); });
  }, [events]);
  useEffect(() => { window.history.replaceState(null, "", urlFromState({ filters, view, history, rawQ })); }, [filters, view, history, rawQ]);
  useEffect(() => { const h = ev => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); setCmd(c => !c); }
    else if (ev.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "")) { ev.preventDefault(); setCmd(true); }
    if (ev.key === "Escape") setCmd(false);
  }; document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h); }, []);

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
  const counts = useMemo(() => { const c = k => { const m = {}; UP.forEach(e => m[e[k]] = (m[e[k]] || 0) + 1); return m; }; const th = {}; UP.forEach(e => (e.luma_categories || []).forEach(t => th[t] = (th[t] || 0) + 1)); const acc = {}; UP.forEach(e => { const a = accessOf(e); acc[a] = (acc[a] || 0) + 1; }); return { disc: c("discipline"), inst: c("institution"), src: c("source_type"), theme: th, access: acc }; }, [UP]);
  // Compteurs sans les catégories à part (soutenances, carrières), masquées par défaut
  const UPc = UP.filter(e => !isSide(e)), nSide = {};
  UP.forEach(e => { if (isSide(e)) nSide[e.kind] = (nSide[e.kind] || 0) + 1; });
  const nToday = UPc.filter(e => e.date === TODAY).length, nWeek = UPc.filter(e => e.date <= WEEK_END).length, nWe = UPc.filter(e => WE.includes(e.date)).length, nNew = UPc.filter(isNew).length;
  const topInst = useMemo(() => Object.entries(counts.inst).sort((a, b) => b[1] - a[1]).slice(0, 18), [counts]);
  const followedNew = useMemo(() => {
    if (!speakers.size) return [];
    const names = [...speakers].map(n => n.toLowerCase());
    return UP.filter(e => e.speaker && !seenSpeakerEvents.has(e.id) && names.some(n => e.speaker.toLowerCase().includes(n)));
  }, [UP, speakers, seenSpeakerEvents]);
  useEffect(() => {
    if (notifyPerm !== "granted" || !followedNew.length) return;
    try {
      if (followedNew.length === 1) new Notification(t("notify_title"), { body: followedNew[0].title });
      else new Notification(t("notify_title"), { body: `${followedNew.length} ${t("noun_event", { n: followedNew.length })}` });
    } catch (err) {}
    markSeen(followedNew.map(x => x.id));
  }, [followedNew, notifyPerm]);
  const enableNotify = () => {
    if (typeof Notification === "undefined") return;
    Notification.requestPermission().then(p => { setNotifyPerm(p); if (p === "granted") notify(t("notify_enabled")); else if (p === "denied") notify(t("notify_denied")); });
  };
  const openSpeakers = () => { setSpeakersOpen(true); if (followedNew.length) markSeen(followedNew.map(x => x.id)); };
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
  const activeTags = [...[...filters.disc].map(v => [v, () => toggleIn("disc")(v)]), ...[...filters.inst].map(v => [v, () => toggleIn("inst")(v)]), ...[...filters.src].map(v => [SRC_LABEL_T[v], () => toggleIn("src")(v)]), ...[...filters.access].map(v => [t(v === "membres" ? "access_members" : "access_public"), () => toggleIn("access")(v)]), ...[...filters.theme].map(v => ["Luma · " + v, () => toggleIn("theme")(v)]), ...(filters.online ? [[t("btn_online"), () => setF({ online: false })]] : []), ...(filters.cat ? [[t(SIDE_KINDS[filters.cat].label), () => setF({ cat: "" })]] : [])];

  /* actions */
  const onFav = id => { toggleFav(id); notify(favs.has(id) ? t("toast_fav_removed") : t("toast_fav_added")); };
  const onSelect = id => setSelected(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const exportSel = () => { const evs = pool.filter(e => selected.has(e.id)); if (!evs.length) return; download("ma-selection-lotent.ics", buildIcs(evs)); notify(t("toast_exported", { n: evs.length })); };
  const toggleNear = () => {
    if (near) { setNear(false); return; }
    if (userPos) { setNear(true); return; }
    if (!navigator.geolocation) { notify(t("toast_geoloc_unavailable")); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(p => { setUserPos({ lat: p.coords.latitude, lng: p.coords.longitude }); setNear(true); setLocating(false); }, err => { setLocating(false); notify(t("toast_locate_error", { msg: err.message })); });
  };
  const toggleHistory = () => { pendingScroll.current = history ? "agenda" : "top"; setHistory(h => !h); setView("list"); setNear(false); };
  const backToAgenda = () => { if (history) { pendingScroll.current = "agenda"; setHistory(false); } else goAgenda(); };
  const toggleTheme = () => { const r = document.documentElement, dark = r.dataset.theme === "dark" || (!r.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches); r.dataset.theme = dark ? "light" : "dark"; store.set("paf_theme", dark ? "light" : "dark"); };
  const pickRandom = () => { const p = filtered.length ? filtered : pool; if (p.length) setOpen(p[Math.floor(Math.random() * p.length)]); };
  const goMap = () => { setHistory(false); setNear(false); setView("map"); goAgenda(); };

  if (loadErr) return <div className="mx-auto max-w-lg p-10 text-center"><p className="font-semibold">{t("empty_generic_title")}</p><p className="text-sm text-muted-foreground mt-1">{loadErr}</p></div>;

  return <>
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-14 flex items-center gap-4">
        <a href="/" className="flex items-center gap-2 font-semibold tracking-tight"><img src="icon.svg" alt="" width="28" height="28" className="h-7 w-7 rounded-md" /><span>Lotent</span></a>
        <nav className="hidden md:flex items-center gap-1 text-sm text-muted-foreground ml-4"><button onClick={backToAgenda} className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-accent">{t("nav_agenda")}</button><button onClick={toggleHistory} className={cn("px-3 py-1.5 rounded-md hover:text-foreground hover:bg-accent", history && "text-foreground bg-accent")}>{t("nav_history")}</button><a href="apropos.html" className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-accent">{t("nav_about")}</a><a href={PROPOSE_URL} target="_blank" rel="noopener" className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-accent">{t("nav_propose")}</a></nav>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setCmd(true)} className="inline-flex items-center gap-2 h-9 rounded-md border bg-background px-3 text-sm text-muted-foreground shadow-sm hover:bg-accent hover:text-foreground w-10 sm:w-64 justify-center sm:justify-between" aria-label={t("search_ph")}><Icon d={ICONS.search} size={15} className="sm:hidden" /><span className="hidden sm:inline">{t("search_ph")}</span><Kbd className="hidden sm:inline-flex">⌘K</Kbd></button>
          <Button variant="outline" size="icon" onClick={toggleLang} aria-label={t("lang_aria")} className="font-semibold text-xs">{lang === "en" ? "FR" : "EN"}</Button>
          <Button variant="outline" size="icon" onClick={toggleTheme} aria-label={t("theme_aria")}><Icon d={ICONS.moon} size={16} className="dark:hidden" /><Icon d={ICONS.sun} size={16} className="hidden dark:block" /></Button>
          <MovingBorderButton href="data/calendar.ics" className="hidden sm:inline-flex h-9">{t("subscribe")}</MovingBorderButton>
        </div></div></header>

    <main className="mx-auto max-w-7xl px-4 sm:px-6">
      {history ? <section className="relative pt-16 pb-10 text-center overflow-hidden">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 [background:radial-gradient(60%_55%_at_50%_-10%,rgba(180,83,9,.22),transparent_70%)]" />
        <BlurFade inView={false}><div className="inline-flex items-center gap-1.5 rounded-full border bg-background/60 px-4 py-1 text-sm shadow-sm"><Icon d={ICONS.history} size={13} />{t("history_kicker")}</div></BlurFade>
        <BlurFade inView={false} delay={.1}><h1 className="mt-6 text-3xl sm:text-5xl font-bold tracking-tight [text-wrap:balance] max-w-3xl mx-auto leading-[1.05]">{t("history_title")}</h1></BlurFade>
        <BlurFade inView={false} delay={.2}><p className="mt-4 text-lg text-muted-foreground max-w-xl mx-auto [text-wrap:balance]">{archive ? t("history_lede", { n: archive.length }) : t("history_loading")}</p></BlurFade>
      </section> : <>
      <section className="relative pt-14 pb-8 text-center">
        <Spotlight className="-top-40 left-0 md:left-60 md:-top-20" />
        <BlurFade inView={false}><div className="inline-flex items-center rounded-full border bg-background/60 px-4 py-1 text-sm shadow-sm"><AnimatedShinyText>✦ {meta.last_workflow_run ? t("live_updated", { rel: relTime(meta.last_workflow_run) }) : t("live_fallback")}{events ? t("live_events_suffix", { n: UP.length }) : ""}</AnimatedShinyText></div></BlurFade>
        <BlurFade inView={false} delay={.1}><h1 className="mt-6 text-4xl sm:text-6xl font-bold tracking-tight [text-wrap:balance] max-w-4xl mx-auto leading-[1.05]">{t("hero_title_1")} <span className="bg-gradient-to-r from-[#3B82F6] via-[#8B5CF6] to-[#EC4899] bg-clip-text text-transparent">{t("hero_title_2")}</span></h1></BlurFade>
        <BlurFade inView={false} delay={.2}><p className="mt-5 text-lg text-muted-foreground max-w-2xl mx-auto [text-wrap:balance]">{events ? t("hero_lede", { n: Object.keys(counts.inst).length, f: UP.filter(isFree).length }) : t("hero_loading")}</p></BlurFade>
        <BlurFade inView={false} delay={.3}><div className="mt-8 flex flex-wrap justify-center gap-3"><Button onClick={() => { setHistory(false); setF({ when: "today" }); goAgenda(); }} className="h-11 px-6">{t("btn_today")}</Button><Button variant="outline" onClick={() => { setHistory(false); setF({ when: "week" }); goAgenda(); }} className="h-11 px-6">{t("btn_week")}</Button></div></BlurFade>
        <BlurFade inView={false} delay={.4}><div className="relative mt-12 grid grid-cols-3 max-w-xl mx-auto divide-x rounded-xl border bg-card shadow-sm">
          {[[nToday, t("stat_today"), "today"], [nWeek, t("stat_week"), "week"], [nWe, t("stat_weekend"), "weekend"]].map(([n, l, w], i) => <button key={w} onClick={() => { setHistory(false); setF({ when: w }); goAgenda(); }} className="flex flex-col items-center py-4 hover:bg-accent first:rounded-l-xl last:rounded-r-xl"><span className="text-3xl font-bold"><NumberTicker value={n} delay={.2 + i * .1} locale={lang === "en" ? "en-US" : "fr-FR"} /></span><span className="text-xs text-muted-foreground mt-1">{l}</span></button>)}
          <BorderBeam size={70} duration={9} colorFrom="#3B82F6" colorTo="#EC4899" /></div></BlurFade>
      </section>

      {topInst.length > 0 && <section className="py-2 relative [mask-image:linear-gradient(to_right,transparent,#000_10%,#000_90%,transparent)]">
        <Marquee pauseOnHover>{topInst.map(([i, n]) => <button key={i} onClick={() => { setHistory(false); setF({ inst: new Set([i]) }); goAgenda(); }} className="inline-flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm shadow-sm hover:bg-accent whitespace-nowrap"><span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-muted text-xs font-semibold">{i[0]}</span>{i}<span className="text-xs text-muted-foreground tabular-nums">{n}</span></button>)}</Marquee>
      </section>}

      {events && <section className="py-10">
        <BlurFade><div className="mb-5 flex items-end justify-between gap-4"><div><h2 className="text-2xl font-semibold tracking-tight">{t("featured_title")}</h2><p className="text-sm text-muted-foreground mt-1">{digest && featured.length >= 3 ? t("featured_sub_digest", { period: digest.period }) : t("featured_sub_auto")}</p></div></div></BlurFade>
        <BentoGrid>
          {featured[0] && <BentoCard className="lg:col-span-2 lg:row-span-2" name={featured[0].title} meta={`${relDay(featured[0].date, TODAY, TOMORROW) || fmtShort(featured[0].date)}${featured[0].time ? " · " + featured[0].time : ""} · ${featured[0].institution}`} description={featured[0].speaker} onClick={() => setOpen(featured[0])}
            background={<div className="group h-full"><Cover e={featured[0]} className="absolute inset-0" eager /><div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" /></div>} />}
          {featured.slice(1, 3).map(e => <BentoCard key={e.id} name={e.title} meta={`${relDay(e.date, TODAY, TOMORROW) || fmtShort(e.date)}${e.time ? " · " + e.time : ""}`} onClick={() => setOpen(e)}
            background={<div className="group h-full"><Cover e={e} className="absolute inset-0" eager /><div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" /></div>} />)}
          <div className="col-span-1 flex flex-col gap-2 rounded-xl border bg-card p-4 shadow-sm overflow-hidden"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">{t("tonight_title")}</h3><Badge>{tonight.length}</Badge></div>
            {tonight.length ? <ul className="flex flex-col divide-y text-sm overflow-hidden">{tonight.slice(0, 4).map(e => <li key={e.id}><button onClick={() => setOpen(e)} className="w-full text-left py-1.5 flex gap-2 text-muted-foreground hover:text-foreground"><span className="font-mono text-xs pt-0.5 tabular-nums text-foreground">{e.time}</span><span className="truncate">{e.title}</span></button></li>)}</ul> : <p className="text-sm text-muted-foreground">{t("tonight_empty")}</p>}</div>
          <div className="col-span-1 lg:col-span-2 flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">{t("days7_title")}</h3><span className="text-xs text-muted-foreground">{t("n_events", { n: days7.reduce((s, x) => s + x.n, 0) })}</span></div>
            <div className="flex items-end gap-2 flex-1 min-h-[80px]">{days7.map(x => <button key={x.k} onClick={() => { setHistory(false); setF({ when: "all" }); setView("list"); setTimeout(() => document.querySelector(`[data-date="${x.k}"]`)?.scrollIntoView({ behavior: "smooth" }), 60); }} className="flex-1 flex flex-col items-center gap-1 group/bar"><span className="text-[11px] tabular-nums text-muted-foreground">{x.n}</span><motion.span initial={{ height: 6 }} whileInView={{ height: Math.max(6, x.n / max7 * 64) }} viewport={{ once: true }} transition={{ type: "spring", stiffness: 120, damping: 18 }} className="w-full rounded-md bg-primary/80 group-hover/bar:bg-primary" /><span className={cn("text-[11px]", x.k === TODAY ? "font-semibold" : "text-muted-foreground")}>{x.d.getDate()}</span></button>)}</div></div>
          <MiniMap events={UP} onGoMap={goMap} />
        </BentoGrid>
      </section>}
      </>}

      <div ref={agendaRef} className="scroll-mt-14" />
      <div className="sticky top-14 z-30 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 bg-background/80 backdrop-blur border-b">
        <div className="flex flex-wrap items-center gap-2">
          {history
            ? <><Badge variant="solid" className="h-9 px-3 text-sm">{t("history_badge")}</Badge><select value={histMonth} onChange={e => setHistMonth(e.target.value)} className="h-9 rounded-md border bg-background px-2 text-sm"><option value="all">{t("history_all_period")}</option>{histMonths.map(m => <option key={m} value={m}>{MO[+m.slice(5, 7) - 1]} {m.slice(0, 4)}</option>)}</select><Button variant="outline" size="sm" className="h-9" onClick={toggleHistory}>{t("history_back")}</Button></>
            : <div className="overflow-x-auto max-w-full"><Tabs value={filters.when} onChange={w => setF({ when: w })} items={[["all", t("tab_all")], ["today", t("tab_today")], ["tonight", t("tab_tonight")], ["week", t("tab_week")], ["weekend", t("tab_weekend")], ...(nNew ? [["new", `${t("tab_new")} · ${nNew}`]] : [])]} /></div>}
          <Popover label={t("pop_discipline")} count={filters.disc.size}>{() => <CheckList values={Object.keys(DISC).filter(d => counts.disc[d]).map(d => [d, counts.disc[d]])} set={filters.disc} onToggle={toggleIn("disc")} swatch colorOf={v => `var(${DISC[v] || "--c-aut"})`} onClear={() => setF({ disc: new Set() })} clearLabel={t("clear_all")} />}</Popover>
          <Popover label={t("pop_institution")} count={filters.inst.size}>{() => <CheckList values={[...MAIN_INST.filter(i => counts.inst[i]).map((i, k) => [i, counts.inst[i], k === 0 ? t("group_establishments") : null]), ...Object.entries(counts.inst).filter(([i]) => !MAIN_INST.includes(i)).sort((a, b) => b[1] - a[1]).slice(0, 30).map(([i, n], k) => [i, n, k === 0 ? t("group_others") : null])]} set={filters.inst} onToggle={toggleIn("inst")} onClear={() => setF({ inst: new Set() })} clearLabel={t("clear_all")} />}</Popover>
          <Popover label={t("pop_source")} count={filters.src.size + filters.theme.size}>{() => <>
            <CheckList values={Object.keys(SRC_LABEL_T).filter(s => counts.src[s]).map(s => [s, counts.src[s]])} set={filters.src} onToggle={toggleIn("src")} labelFn={v => SRC_LABEL_T[v]} onClear={() => setF({ src: new Set(), theme: new Set() })} clearLabel={t("clear_all")} />
            {Object.keys(counts.theme).length > 0 && <CheckList values={Object.entries(counts.theme).sort((a, b) => b[1] - a[1]).map(([tm, n], k) => [tm, n, k === 0 ? t("group_luma_themes") : null])} set={filters.theme} onToggle={toggleIn("theme")} onClear={() => setF({ theme: new Set() })} clearLabel={t("clear_all")} />}</>}</Popover>
          {counts.access.membres > 0 && <Popover label={t("pop_access")} count={filters.access.size}>{() => <CheckList values={["public", "membres"].filter(a => counts.access[a]).map(a => [a, counts.access[a]])} set={filters.access} onToggle={toggleIn("access")} labelFn={v => (v === "membres" ? "🔒 " : "") + t(v === "membres" ? "access_members" : "access_public")} onClear={() => setF({ access: new Set() })} clearLabel={t("clear_all")} />}</Popover>}
          <Button variant={filters.fav ? "default" : "outline"} size="sm" className="h-9" onClick={() => setF({ fav: !filters.fav })} aria-pressed={filters.fav}>★<span className="hidden sm:inline"> {t("btn_fav")}</span>{favs.size > 0 && <span className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px]", filters.fav ? "bg-primary-foreground text-primary" : "bg-primary text-primary-foreground")}>{favs.size}</span>}</Button>
          <Button variant={filters.online ? "default" : "outline"} size="sm" className="h-9" onClick={() => setF({ online: !filters.online })} aria-pressed={filters.online}>{t("btn_online")}</Button>
          {Object.entries(SIDE_KINDS).map(([k, s]) => nSide[k] > 0 && <Button key={k} variant={filters.cat === k ? "default" : "outline"} size="sm" className="h-9" onClick={() => setF({ cat: filters.cat === k ? "" : k })} aria-pressed={filters.cat === k} title={t(s.hint)}>{s.icon}<span className="hidden sm:inline"> {t(s.label)}</span><span className="tabular-nums text-xs opacity-70">{nSide[k]}</span></Button>)}
          <div className="ml-auto flex items-center gap-2">
            {!history && <Tabs value={view} onChange={setView} layoutId="view-pill" items={[["list", <Icon d={ICONS.list} size={15} />], ["week", <Icon d={ICONS.week} size={15} />], ["map", <Icon d={ICONS.map} size={15} />]]} />}
            {!history && <Button variant={near ? "default" : "outline"} size="sm" className="h-9" onClick={toggleNear} aria-pressed={near} disabled={locating}><Icon d={ICONS.pin} size={14} /><span className="hidden lg:inline">{locating ? t("near_locate") : near ? t("near_sorted") : t("near_label")}</span></Button>}
            <Button variant={selectMode ? "default" : "outline"} size="sm" className="h-9" onClick={() => { setSelectMode(m => !m); setSelected(new Set()); }} aria-pressed={selectMode}><Icon d={ICONS.check} size={14} /><span className="hidden lg:inline">{t("select_btn")}</span></Button>
            <span className="text-sm text-muted-foreground tabular-nums whitespace-nowrap"><b className="text-foreground font-medium">{filtered.length}</b><span className="hidden sm:inline"> {t("noun_event", { n: filtered.length })}</span></span>
          </div>
        </div>
        {(activeTags.length > 0 || rawQ) && <div className="flex flex-wrap gap-1.5 mt-2">{rawQ && <span className="inline-flex items-center gap-1 rounded-md border bg-background pl-2 pr-1 py-0.5 text-xs font-medium">« {rawQ} »<button onClick={() => { setRawQ(""); setF({ q: "" }); }} className="inline-flex h-4 w-4 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground">×</button></span>}{activeTags.map(([l, rm]) => <span key={l} className="inline-flex items-center gap-1 rounded-md border bg-background pl-2 pr-1 py-0.5 text-xs font-medium">{l}<button onClick={rm} className="inline-flex h-4 w-4 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground">×</button></span>)}</div>}
      </div>

      {!history && filters.inst.size === 1 && <InstitutionBanner name={[...filters.inst][0]} events={UP} onClear={() => setF({ inst: new Set() })} />}

      <section className="py-4 pb-36">
        {!events && <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 pt-6">{[...Array(8)].map((_, i) => <div key={i} className="rounded-xl border bg-card overflow-hidden animate-pulse"><div className="aspect-[16/10] bg-muted" /><div className="p-4 space-y-2"><div className="h-3 w-1/3 bg-muted rounded" /><div className="h-4 w-4/5 bg-muted rounded" /><div className="h-3 w-1/2 bg-muted rounded" /></div></div>)}</div>}
        {events && history && !archive && <p className="pt-6 text-sm text-muted-foreground">{t("history_loading")}</p>}
        {events && !filtered.length && (!history || archive) && <div className="mt-6 rounded-xl border border-dashed p-12 text-center"><p className="font-medium">{filters.fav && !favs.size ? t("empty_fav_title") : t("empty_generic_title")}</p><p className="text-sm text-muted-foreground mt-1">{filters.fav && !favs.size ? t("empty_fav_sub") : t("empty_generic_sub")}</p></div>}
        {events && view === "week" && !history && <WeekView events={filtered} onOpen={setOpen} favs={favs} />}
        {events && view === "map" && !history && <MapView events={filtered} onOpen={setOpen} userPos={userPos} />}
        {events && (view === "list" || history) && (near && userPos
          ? <div className="pt-6"><p className="text-sm text-muted-foreground mb-2 px-2">{t("sorted_by_distance")}</p><HoverEffect items={filtered.slice(0, shown)} render={e => <EventCard e={e} fav={favs.has(e.id)} onFav={onFav} onOpen={setOpen} selectMode={selectMode} selected={selected.has(e.id)} onSelect={onSelect} distance={e._d} />} /></div>
          : groups.map(g => { const d = parse(g.date), n = filtered.filter(x => x.date === g.date).length; return <section key={g.date} data-date={g.date} className="pt-8 scroll-mt-32">
            <div className="flex items-baseline gap-3 mb-2 px-2"><h2 className="text-xl font-semibold tracking-tight capitalize">{fmtDay(g.date)}{d.getFullYear() !== today.getFullYear() ? " " + d.getFullYear() : ""}</h2>{relDay(g.date, TODAY, TOMORROW) && <Badge variant="solid">{relDay(g.date, TODAY, TOMORROW)}</Badge>}<span className="ml-auto text-sm text-muted-foreground tabular-nums">{n}</span></div>
            <HoverEffect items={g.items} render={e => <EventCard e={e} fav={favs.has(e.id)} onFav={onFav} onOpen={setOpen} selectMode={selectMode} selected={selected.has(e.id)} onSelect={onSelect} past={history} />} />
          </section>; }))}
        {events && (view === "list" || history) && shown < filtered.length && <div ref={moreRef} className="flex justify-center pt-10"><Button variant="outline" onClick={() => setShown(s => s + PAGE)}>{t("show_more", { n: filtered.length - shown })}</Button></div>}
      </section>
    </main>

    <footer className="border-t">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-10 grid gap-8 md:grid-cols-3 text-sm">
        <div><div className="font-semibold">Lotent</div><p className="text-muted-foreground mt-2 max-w-xs">{t("footer_tagline")}</p><p className="text-xs text-muted-foreground mt-3">{t("footer_updated", { auto: relTime(meta.last_workflow_run) })}{meta.last_manual_run && t("footer_manual_suffix", { t: relTime(meta.last_manual_run) })}</p></div>
        <div><div className="font-semibold">{t("footer_subscribe")}</div><ul className="mt-2 space-y-1.5 text-muted-foreground"><li><a className="hover:text-foreground" href="data/calendar.ics">{t("footer_ics")}</a></li><li><a className="hover:text-foreground" href="data/digest.xml">{t("footer_rss")}</a></li><li><a className="hover:text-foreground" href="sitemap.xml">{t("footer_sitemap")}</a></li><li><a className="hover:text-foreground" href="apropos.html">{t("nav_about")}</a></li><li><a className="hover:text-foreground" href={PROPOSE_URL} target="_blank" rel="noopener">{t("nav_propose")}</a></li></ul></div>
        <GithubCard />
      </div>
    </footer>

    <AnimatePresence>{selectMode && <motion.div initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }} className="fixed bottom-24 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 rounded-xl border bg-popover px-3 py-2 shadow-lg text-sm"><span className="tabular-nums"><b>{selected.size}</b> {t("adj_selected", { n: selected.size })}</span><Button size="sm" onClick={exportSel} disabled={!selected.size}><Icon d={ICONS.download} size={14} />{t("sel_export")}</Button><Button size="sm" variant="ghost" onClick={() => { setSelectMode(false); setSelected(new Set()); }}>{t("sel_done")}</Button></motion.div>}</AnimatePresence>

    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40">
      <Dock>
        <DockIcon title={t("dock_top")} onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}><Icon d={ICONS.up} /></DockIcon>
        <DockIcon title={t("dock_today")} active={!history && filters.when === "today"} onClick={() => { setF({ when: "today" }); backToAgenda(); }}><Icon d={ICONS.cal} /></DockIcon>
        <DockIcon title={t("dock_history")} active={history} onClick={toggleHistory}><Icon d={ICONS.history} /></DockIcon>
        <DockIcon title={t("dock_random")} onClick={pickRandom}><Icon d={ICONS.random} /></DockIcon>
        <DockIcon title={t("dock_fav")} active={filters.fav} onClick={() => { setF({ fav: !filters.fav }); goAgenda(); }}><Icon d={ICONS.star} />{favs.size > 0 && <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 rounded-full bg-primary text-primary-foreground text-[10px] font-bold px-1 leading-4">{favs.size}</span>}</DockIcon>
        {speakers.size > 0 && <DockIcon title={t("my_speakers")} active={speakersOpen} onClick={openSpeakers}><Icon d={ICONS.bell} />{followedNew.length > 0 && <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 rounded-full bg-primary text-primary-foreground text-[10px] font-bold px-1 leading-4">{followedNew.length}</span>}</DockIcon>}
        <DockSep />
        <DockIcon title={t("dock_search")} onClick={() => setCmd(true)}><Icon d={ICONS.search} /></DockIcon>
      </Dock>
    </div>

    <Sheet e={open} onClose={() => setOpen(null)} fav={open ? favs.has(open.id) : false} onFav={onFav} onToast={notify} following={open ? speakers.has(open.speaker) : false} onFollow={name => { const willFollow = !speakers.has(name); toggleSpeaker(name); notify(willFollow ? t("speaker_followed") : t("speaker_unfollowed")); }} />
    <CommandDialog open={cmd} onClose={() => setCmd(false)} onPick={e => { setCmd(false); setOpen(e); }} pool={pool} />
    <SpeakersPanel open={speakersOpen} onClose={() => setSpeakersOpen(false)} speakers={speakers} onUnfollow={toggleSpeaker} pool={UP} onOpenEvent={e => { setSpeakersOpen(false); setOpen(e); }} notifyPerm={notifyPerm} onEnableNotify={enableNotify} />
    <AnimatePresence>{toast && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 rounded-md border bg-popover px-3 py-2 text-sm shadow-lg">{toast}</motion.div>}</AnimatePresence>
  </>;
}

// Thème mémorisé par l'ancien site (paf_theme) : appliqué avant le premier rendu
const savedTheme = store.get("paf_theme", null);
if (savedTheme === "dark" || savedTheme === "light") document.documentElement.dataset.theme = savedTheme;
createRoot(document.getElementById("root")).render(<LangProvider><App /></LangProvider>);
