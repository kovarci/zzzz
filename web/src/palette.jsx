/* Recherche ⌘K : texte + choix d'un jour ou d'une période (calendrier).
   Les résultats suivent la frappe avec un léger délai (140 ms) : la liste ne
   clignote plus à chaque lettre, et la sélection ne saute plus quand la
   souris est immobile sous la liste. */
import React, { useState, useEffect, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { DayPicker } from "react-day-picker";
import { fr, enUS } from "react-day-picker/locale";
import { TODAY, TOMORROW, WEEK_END, WE, today, iso, parse, addDays, norm, cn, dc, titleOf } from "./lib.js";
import { Icon, ICONS, Kbd, Button, useFocusTrap } from "./ui.jsx";
import { useI18n } from "./i18n.jsx";

// Le mot w commence-t-il un mot de h (début, ou précédé d'un caractère non alphanumérique) ?
const wordStart = (h, w) => { for (let i = h.indexOf(w); i >= 0; i = h.indexOf(w, i + 1)) if (i === 0 || !/[a-z0-9]/.test(h[i - 1])) return true; return false; };
const byDate = (a, b) => (a.date + (a.time || "")).localeCompare(b.date + (b.time || ""));
const mondayOf = d => addDays(d, -((d.getDay() + 6) % 7));

function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}

/* ── « 9 novembre », « 09/11 », « semaine du 9 nov », « demain »… → période ── */
const MONTHS = { janvier: 0, janv: 0, jan: 0, january: 0, fevrier: 1, fevr: 1, fev: 1, feb: 1, february: 1, mars: 2, mar: 2, march: 2, avril: 3, avr: 3, apr: 3, april: 3,
  mai: 4, may: 4, juin: 5, jun: 5, june: 5, juillet: 6, juil: 6, jul: 6, july: 6, aout: 7, aug: 7, august: 7, septembre: 8, sept: 8, sep: 8, september: 8,
  octobre: 9, oct: 9, october: 9, novembre: 10, nov: 10, november: 10, decembre: 11, dec: 11, december: 11 };
const mkDate = (y, m, d) => { const x = new Date(y, m, d); return x.getFullYear() === y && x.getMonth() === m && x.getDate() === d ? x : null; };
function parseDay(s, future) {
  s = s.replace(/^le /, "");
  let d, m, y, x;
  if ((x = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s))) return mkDate(+x[1], +x[2] - 1, +x[3]);
  if ((x = /^(\d{1,2})(?:er)? ([a-z]+)\.?(?: (\d{4}))?$/.exec(s))) { if (!(x[2] in MONTHS)) return null; d = +x[1]; m = MONTHS[x[2]]; y = x[3] && +x[3]; }
  else if ((x = /^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2}|\d{4}))?$/.exec(s))) { d = +x[1]; m = +x[2] - 1; y = x[3] && (x[3].length === 2 ? 2000 + +x[3] : +x[3]); }
  else return null;
  if (y) return mkDate(y, m, d);
  const a = mkDate(today.getFullYear(), m, d);
  return a && future && a < today ? mkDate(today.getFullYear() + 1, m, d) : a;
}
export function parseDateQuery(raw, future = true) {
  const s = norm(raw).replace(/,/g, " ").replace(/\s+/g, " ").trim();
  if (!s) return null;
  const one = d => d && { from: iso(d), to: iso(d) };
  const week = d => d && { from: iso(mondayOf(d)), to: iso(addDays(mondayOf(d), 6)) };
  if (/^(aujourd ?hui|today)$/.test(s)) return one(today);
  if (/^(demain|tomorrow)$/.test(s)) return one(addDays(today, 1));
  if (/^(ce )?(this )?week[- ]?end$/.test(s)) return { from: WE[0], to: WE[1] };
  if (/^(cette semaine|this week)$/.test(s)) return { from: TODAY, to: WEEK_END };
  if (/^(semaine prochaine|next week)$/.test(s)) return week(addDays(today, 7));
  const wk = /^(?:semaine du|semaine|week of|week) (.+)$/.exec(s);
  return wk ? week(parseDay(wk[1], future)) : one(parseDay(s, future));
}

export function CommandDialog({ open, onClose, onPick, pool }) {
  const { t, lang, fmtShort, fmtDay, discName } = useI18n();
  const [q, setQ] = useState(""); const [sel, setSel] = useState(0);
  const [range, setRange] = useState(null);        // { from, to } en AAAA-MM-JJ, to = from pour un seul jour
  const [picking, setPicking] = useState(false);   // premier clic fait, on attend le second
  const [cal, setCal] = useState(false);
  const inputRef = useRef(null), listRef = useRef(null), byKey = useRef(false), calRef = useRef(false);
  calRef.current = cal;
  const trap = useFocusTrap(open);
  const dq = useDebounced(q, q ? 140 : 0);
  const future = useMemo(() => pool.some(e => e.date >= TODAY), [pool]);

  // Textes normalisés une fois par ouverture : titre, qui (intervenant,
  // organisateurs), reste (lieu, discipline)
  const idx = useMemo(() => open ? pool.map(e => [e, norm(e.title), norm([e.speaker, e.institution, ...(e.also || [])].join(" ")), norm([e.location, e.discipline, discName(e.discipline)].join(" "))]) : [], [open, pool, discName]);
  const perDay = useMemo(() => { const m = new Map(); if (open) for (const e of pool) m.set(e.date, (m.get(e.date) || 0) + 1); return m; }, [open, pool]);
  const bounds = useMemo(() => { const k = [...perDay.keys()].sort(); return k.length ? { from: parse(k[0]), to: parse(k[k.length - 1]) } : null; }, [perDay]);
  const hasEv = useMemo(() => [...perDay.keys()].map(parse), [perDay]);

  const hint = useMemo(() => dq ? parseDateQuery(dq, future) : null, [dq, future]);
  const words = useMemo(() => norm(dq.trim()).split(/\s+/).filter(Boolean), [dq]);
  const res = useMemo(() => {
    const base = range ? idx.filter(([e]) => e.date >= range.from && e.date <= range.to) : idx;
    if (!words.length) return range ? base.map(x => x[0]).sort(byDate).slice(0, 400) : pool.filter(e => e.date === TODAY || e.date === TOMORROW).slice(0, 30);
    // Chaque mot doit apparaître ; ceux d'une ou deux lettres en début de mot
    // seulement (« IA », le « po » de Sciences Po trouvaient « pour », « Gaïas »).
    // Classement : titre, puis intervenant / organisateur, puis le reste ; à
    // égalité, l'ordre chronologique.
    const out = [];
    for (const [e, ...fields] of base) {
      let score = 0;
      for (const w of words) {
        let best = 0;
        fields.forEach((h, k) => { const at = wordStart(h, w); if (at || (w.length > 2 && h.includes(w))) best = Math.max(best, [6, 3, 1][k] * (at ? 1.5 : 1)); });
        if (!best) { score = 0; break; }
        score += best;
      }
      // Expression entière dans le titre ou chez l'organisateur : devant les mots trouvés un à un
      if (score && words.length > 1) { const ph = words.join(" "); fields.forEach((h, k) => { if (wordStart(h, ph)) score += [30, 30, 5][k]; }); }
      if (score) out.push([score, e]);
    }
    return out.sort((a, b) => b[0] - a[0]).slice(0, range ? 400 : 30).map(x => x[1]);
  }, [words, idx, pool, range]);

  // Ligne 0 : « Voir le 9 novembre » quand la saisie est une date
  const items = useMemo(() => [...(hint ? [{ date: hint }] : []), ...res.map(e => ({ e }))], [hint, res]);

  useEffect(() => { if (open) { setQ(""); setSel(0); setRange(null); setPicking(false); setCal(false); setTimeout(() => inputRef.current?.focus(), 30); } }, [open]);
  useEffect(() => { setSel(0); if (listRef.current) listRef.current.scrollTop = 0; }, [dq, range]);
  useEffect(() => {   // le clavier fait défiler la liste ; la souris, non
    if (!byKey.current) return; byKey.current = false;
    listRef.current?.querySelector('[data-sel="true"]')?.scrollIntoView({ block: "nearest" });
  }, [sel]);
  // Ouverte par-dessus une fiche (« / » ou ⌘K) : Échap ne ferme que la palette ; calendrier ouvert : que lui
  useEffect(() => {
    if (!open) return;
    const k = ev => { if (ev.key === "Escape") { ev.preventDefault(); calRef.current ? setCal(false) : onClose(); } };
    document.addEventListener("keydown", k, true); return () => document.removeEventListener("keydown", k, true);
  }, [open]);

  const dayFmt = Intl.DateTimeFormat(lang === "en" ? "en-GB" : "fr-FR", { day: "numeric", month: "short" });
  const label = r => r.from === r.to ? dayFmt.format(parse(r.from)) : `${dayFmt.format(parse(r.from))} → ${dayFmt.format(parse(r.to))}`;
  const long = r => r.from === r.to ? fmtDay(r.from) : `${fmtDay(r.from)} ${t("cmd_to")} ${fmtDay(r.to)}`;
  const apply = r => { setRange(r); setPicking(false); setQ(""); setCal(false); inputRef.current?.focus(); };
  const clearRange = () => { setRange(null); setPicking(false); inputRef.current?.focus(); };
  const onDay = d => {
    const k = iso(d);
    if (!range || !picking) { setRange({ from: k, to: k }); setPicking(true); }
    else { setRange(range.from <= k ? { from: range.from, to: k } : { from: k, to: range.from }); setPicking(false); }
  };
  const go = it => it?.date ? apply(it.date) : it?.e && onPick(it.e);
  const onKey = ev => {
    const n = Math.max(1, items.length);
    if (ev.key === "ArrowDown") { ev.preventDefault(); byKey.current = true; setSel(s => (s + 1) % n); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); byKey.current = true; setSel(s => (s - 1 + n) % n); }
    else if (ev.key === "Enter") { ev.preventDefault(); if (cal) setCal(false); else go(items[sel]); }
  };

  const presets = [
    [t("cmd_p_today"), { from: TODAY, to: TODAY }], [t("cmd_p_tomorrow"), { from: TOMORROW, to: TOMORROW }],
    [t("cmd_p_week"), { from: TODAY, to: WEEK_END }], [t("cmd_p_weekend"), { from: WE[0], to: WE[1] }],
    [t("cmd_p_next"), { from: iso(addDays(mondayOf(today), 7)), to: iso(addDays(mondayOf(today), 13)) }],
    [t("cmd_p_month"), { from: TODAY, to: iso(new Date(today.getFullYear(), today.getMonth() + 1, 0)) }],
  ];
  const same = (a, b) => a && a.from === b.from && a.to === b.to;
  // Vrai nombre d'événements de la période (la liste, elle, est plafonnée à 400)
  const nIn = range ? [...perDay].reduce((n, [d, c]) => n + (d >= range.from && d <= range.to ? c : 0), 0) : 0;
  const grouped = !words.length && !!range;
  let rows = [], lastDay = "";
  items.forEach((it, i) => {
    if (grouped && it.e.date !== lastDay) { lastDay = it.e.date; rows.push(<div key={"d" + lastDay} className="px-2 pb-1 pt-3 text-xs font-medium text-muted-foreground first:pt-1.5">{fmtDay(lastDay)}<span className="font-normal tabular-nums"> · {res.filter(x => x.date === lastDay).length}</span></div>); }
    const on = i === sel;
    rows.push(it.date
      ? <button key="hint" id="cmd-o-hint" role="option" aria-selected={on} data-sel={on} onMouseMove={() => !on && setSel(i)} onClick={() => go(it)} className={cn("w-full flex items-center gap-3 rounded-md px-2 py-2 text-left text-sm", on && "bg-accent")}>
          <Icon d={ICONS.cal} size={14} className="shrink-0 text-muted-foreground" /><span className="flex-1 first-letter:uppercase">{t("cmd_see", { d: long(it.date).toLowerCase() })}</span><Kbd>↵</Kbd></button>
      : <button key={it.e.id} id={"cmd-o-" + i} role="option" aria-selected={on} data-sel={on} onMouseMove={() => !on && setSel(i)} onClick={() => go(it)} className={cn("w-full flex items-center gap-3 rounded-md px-2 py-2 text-left text-sm", on && "bg-accent")}>
          <span className="h-2 w-2 rounded-full shrink-0" style={{ background: dc(it.e) }} /><span className="flex-1 min-w-0"><span className="block truncate">{titleOf(it.e)}</span><span className="block text-xs text-muted-foreground truncate">{it.e.institution}{it.e.speaker ? " · " + it.e.speaker : ""}</span></span>
          <span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">{grouped ? (it.e.time || "") : fmtShort(it.e.date)}</span></button>);
  });

  return <AnimatePresence>{open && <motion.div key="cmd" className="fixed inset-0 z-[60]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: "easeOut" }}>
    <div className="absolute inset-0 bg-black/60" onClick={onClose} />
    <motion.div initial={{ x: "-50%", y: -6 }} animate={{ x: "-50%", y: 0 }} exit={{ x: "-50%", y: -6 }} transition={{ duration: .18, ease: "easeOut" }} ref={trap} className="absolute left-1/2 top-[10vh] w-[min(640px,calc(100%-2rem))] max-h-[82vh] flex flex-col rounded-xl border bg-popover shadow-2xl overflow-hidden" role="dialog" aria-modal="true" aria-label={t("dock_search")}>
      <div className="flex shrink-0 items-center gap-2 border-b px-3">
        <Icon d={ICONS.search} size={16} className="shrink-0 text-muted-foreground" />
        <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} role="combobox" aria-expanded={!cal && items.length > 0} aria-controls="cmd-list" aria-autocomplete="list" aria-label={t("dock_search")} aria-activedescendant={!cal && items[sel] ? (items[sel].date ? "cmd-o-hint" : "cmd-o-" + sel) : undefined} className="h-12 min-w-0 flex-1 bg-transparent text-sm outline-none focus-visible:shadow-none placeholder:text-muted-foreground" placeholder={t("cmd_ph")} />
        <span className={cn("inline-flex h-8 shrink-0 items-center rounded-md border text-xs", range ? "bg-accent" : "")}>
          <button onClick={() => setCal(c => !c)} aria-expanded={cal} aria-label={t("cmd_pick")} className="inline-flex h-full items-center gap-1.5 rounded-md px-2 hover:bg-accent"><Icon d={ICONS.cal} size={14} /><span className={cn(!range && "hidden sm:inline")}>{range ? label(range) : t("cmd_date")}</span></button>
          {range && <button onClick={clearRange} aria-label={t("cmd_clear_date")} title={t("cmd_clear_date")} className="inline-flex h-full w-7 items-center justify-center rounded-r-md text-muted-foreground hover:bg-accent hover:text-foreground"><Icon d={ICONS.x} size={13} /></button>}
        </span>
        <Kbd className="hidden sm:inline-flex">ESC</Kbd></div>

      {cal ? <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-3 sm:flex-row">
          <div className="flex flex-wrap gap-1.5 sm:w-40 sm:shrink-0 sm:flex-col sm:gap-1 sm:border-r sm:pr-3">
            {presets.map(([l, r]) => <button key={l} onClick={() => apply(r)} className={cn("rounded-md border px-2.5 py-1.5 text-left text-xs font-medium hover:bg-accent sm:border-0", same(range, r) && "bg-accent")}>{l}</button>)}</div>
          <div className="lotent-cal flex flex-1 justify-center">
            <DayPicker mode="range" selected={range ? { from: parse(range.from), to: parse(range.to) } : undefined} onDayClick={onDay}
              locale={lang === "en" ? enUS : fr} weekStartsOn={1} showOutsideDays defaultMonth={range ? parse(range.from) : today}
              startMonth={bounds ? new Date(Math.min(bounds.from, today)) : undefined} endMonth={bounds?.to}
              modifiers={{ has: hasEv }} modifiersClassNames={{ has: "has-ev" }} /></div></div>
        <div className="flex shrink-0 items-center gap-2 border-t px-3 py-2">
          <span className="flex-1 text-xs text-muted-foreground">{range ? <><span className="font-medium text-foreground first-letter:uppercase">{long(range)}</span> · {t("cmd_in_range", { n: nIn })}</> : t("cmd_hint")}{range && picking ? " · " + t("cmd_hint") : ""}</span>
          <Button size="sm" onClick={() => { setCal(false); setPicking(false); inputRef.current?.focus(); }}>{t("cmd_done")}</Button></div>
      </div>
      : <>
        <div ref={listRef} id="cmd-list" role="listbox" aria-label={t("dock_search")} className="min-h-0 flex-1 overflow-auto p-1">{items.length ? rows
          : words.length ? <div className="p-6 text-center">
              <p className="text-sm font-medium">{t("cmd_none_q", { q: dq.trim() })}</p>
              <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground [text-wrap:balance]">{t("cmd_none_hint")}</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {[presets[2], presets[3]].map(([l, r]) => <button key={l} onClick={() => apply(r)} className="inline-flex h-10 items-center rounded-md border px-3 text-sm font-medium hover:bg-accent">{l}</button>)}
                <button onClick={() => { setQ(""); inputRef.current?.focus(); }} className="inline-flex h-10 items-center rounded-md px-3 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">{t("cmd_clear_q")}</button></div></div>
          : <p className="p-6 text-center text-sm text-muted-foreground">{range ? t("cmd_empty_range") : t("cmd_none")}</p>}</div>
        <div className="flex shrink-0 items-center gap-3 border-t px-3 py-2 text-xs text-muted-foreground"><span><kbd className="font-mono">↑↓</kbd> {t("cmd_nav")}</span><span><kbd className="font-mono">↵</kbd> {t("cmd_open")}</span><span className="ml-auto" role="status" aria-live="polite">{dq || range ? t("cmd_n_results", { n: !words.length && range ? nIn : res.length }) : t("cmd_today_tomorrow")}</span></div></>}
    </motion.div></motion.div>}</AnimatePresence>;
}
