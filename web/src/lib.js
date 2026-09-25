/* Données, dates, filtres — pas de React ici. */

export const SITE = "https://lotent.fr";
export const REPO = "https://github.com/kovarci/zzzz";
// Formulaire « Proposer un événement » (.github/ISSUE_TEMPLATE/proposer-evenement.yml)
export const PROPOSE_URL = "https://github.com/kovarci/zzzz/issues/new?template=proposer-evenement.yml";

export const DISC = {
  "Mathématiques": "--c-math", "Sciences": "--c-sci", "Économie": "--c-eco", "Histoire": "--c-his",
  "Philosophie": "--c-phi", "Littérature": "--c-lit", "Sociologie & Anthropologie": "--c-soc",
  "Droit & Sciences politiques": "--c-dro", "Arts & Culture": "--c-art", "Autre": "--c-aut",
};
export const SRC_LABEL = { institution: "Universités & instituts", luma: "Luma", association: "Associations", ville: "Que faire à Paris" };
// Doit rester aligné sur SHARE_INSTITUTIONS dans scraper/scrape.py (hubs i/<slug>.html)
export const MAIN_INST = ["Collège de France", "Institut Henri Poincaré", "Université PSL", "Paris School of Economics",
  "Sciences Po", "Sorbonne Université", "ENS Paris", "Université Paris Dauphine", "EHESS", "Article 1", "Sciences et Cultures",
  // NEW_INSTITUTIONS dans scraper/scrape.py
  "Université Paris Cité", "Cnam", "Muséum national d'Histoire naturelle", "BnF", "Institut Pasteur", "Institut Curie",
  "Institut du Cerveau", "Inalco", "EPHE", "Collège des Bernardins", "Académie des sciences", "Cité des sciences",
  "Université Sorbonne Nouvelle", "Université Paris 8", "Université Paris Nanterre",
  "IJCLab", "IN2P3", "Observatoire de Paris", "Sciencesconf.org",
  "Université Paris 1 Panthéon-Sorbonne", "Université Paris-Panthéon-Assas", "Université Paris-Saclay", "Campus Condorcet", "Institut d'études avancées de Paris", "Fondation Maison des Sciences de l'Homme", "Musée du quai Branly",
  "Hi! PARIS", "PR[AI]RIE", "HEC Paris", "Musée du Louvre", "Centre Pompidou",
  "INHA", "Ifri", "IRIS", "Institut Jacques Delors", "Fondation Jean-Jaurès",
  "Institut Louis Bachelier", "Citéco", "Institut du monde arabe", "Beaux-Arts de Paris", "ENS Paris-Saclay",
  "ESCP Business School", "Université Sorbonne Paris Nord", "École nationale des chartes",
  "Institut des actuaires", "École polytechnique",
  "IHES", "Labos de maths d'Île-de-France", "IPGP", "Maison de l'Amérique latine", "Institut culturel italien", "Maison de la culture du Japon"];
export const WD = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
export const WDS = ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"];
export const MO = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const ONLINE_RE = /\b(online|en ligne|visio|distanciel|webinaire|webinar|zoom|teams|à distance|hybride|streaming)\b/i;
const KIND_RE = /^(Cours|Séminaire|Colloque|Conférence|Leçon inaugurale|Journée d'étude|Atelier|Workshop|Table ronde|Rencontre|Lecture)\b/i;

export const pad = n => String(n).padStart(2, "0");
export const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const parse = s => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
export const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
export const today = new Date(); today.setHours(0, 0, 0, 0);
export const TODAY = iso(today), TOMORROW = iso(addDays(today, 1));
const dow = today.getDay();
export const WEEK_END = iso(addDays(today, (7 - dow) % 7 || 7));
// Le dimanche, « ce week-end » est celui en cours (hier + aujourd'hui), pas le suivant
const SAT = addDays(today, dow === 0 ? -1 : 6 - dow);
export const WE = [iso(SAT), iso(addDays(SAT, 1))];
export const NEW_CUTOFF = new Date(Date.now() - 48 * 3600 * 1000).toISOString().slice(0, 10);

export const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
// Texte ins\u00e9r\u00e9 en HTML brut (popups Leaflet) : les noms d'h\u00f4tes Luma sont saisis librement
export const escHtml = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
// Liens venus des sources : http(s) seulement (pas de javascript:\u2026)
export const safeUrl = u => /^https?:\/\//i.test(u || "") ? u : "";
export const cn = (...a) => a.filter(Boolean).join(" ");
export const dc = e => `var(${DISC[e.discipline] || "--c-aut"})`;
// Catégories à part : masquées du fil principal, un bouton chacune les affiche.
// param = clé d'URL (?soutenances=1), label/hint = clés i18n.
export const SIDE_KINDS = {
  soutenance: { param: "soutenances", icon: "🎓", label: "btn_theses", hint: "btn_theses_hint", kind: "Soutenance" },
  carriere: { param: "carrieres", icon: "💼", label: "btn_careers", hint: "btn_careers_hint", kind: "Recrutement" },
};
export const isSide = e => !!SIDE_KINDS[e.kind];
// Réservé aux membres (adhérents, bénéficiaires, élèves d'une école…) : 🔒
export const isMembers = e => !!e.members;
export const accessOf = e => isMembers(e) ? "membres" : "public";
export const titleOf = e => (isMembers(e) ? "🔒 " : "") + e.title;
export const kindOf = e => { if (isSide(e)) return SIDE_KINDS[e.kind].kind; const m =KIND_RE.exec(e.description || "") || KIND_RE.exec(e.title || ""); return m ? m[1][0].toUpperCase() + m[1].slice(1).toLowerCase() : (e.source_type === "luma" ? "Rencontre" : "Conférence"); };
export const isFree = e => e.price === "0" || e.price === 0 || /gratuit|free/i.test(e.price || "");
export const isOnline = e => ONLINE_RE.test(e.location || "");
export const isNew = e => e.added_at && e.added_at >= NEW_CUTOFF;
export const fmtDay = s => { const d = parse(s); return `${WD[d.getDay()]} ${d.getDate()} ${MO[d.getMonth()]}`; };
export const fmtShort = s => { const d = parse(s); return `${WDS[d.getDay()]} ${d.getDate()} ${MO[d.getMonth()].slice(0, 4)}`; };
export const relDay = s => s === TODAY ? "Aujourd'hui" : s === TOMORROW ? "Demain" : "";
export const when = e => e.time ? `${e.time}${e.end_time ? " – " + e.end_time : ""}` : "Horaire à confirmer";
// Vignette Luma redimensionnée par leur CDN (600px, webp) plutôt que l'original
export const thumb = url => !url || url.indexOf("images.lumacdn.com/") < 0 || url.indexOf("/cdn-cgi/") >= 0 ? url
  : url.replace("images.lumacdn.com/", "images.lumacdn.com/cdn-cgi/image/width=600,quality=72,format=auto/");

export function haversine(a, b) {
  const R = 6371, dLat = (b.lat - a.lat) * Math.PI / 180, dLng = (b.lng - a.lng) * Math.PI / 180;
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
export const fmtDist = km => km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`;

// Identique à slugify() dans scraper/scrape.py (mêmes règles : NFD, minuscules,
// non-alphanumériques -> "-") — sert à retrouver i/<slug>.html et data/cal/<slug>.ics.
export function slugify(name) {
  return (name || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

export const relTime = ts => {
  if (!ts) return "jamais"; const m = Math.round((Date.now() - new Date(ts)) / 60000);
  if (m < 1) return "à l'instant"; if (m < 60) return `il y a ${m} min`; if (m < 48 * 60) return `il y a ${Math.round(m / 60)} h`; return `il y a ${Math.round(m / 1440)} j`;
};

/* ── Filtrage ──────────────────────────────────────────────────── */
export const EMPTY_FILTERS = { when: "all", disc: new Set(), inst: new Set(), src: new Set(), theme: new Set(), fav: false, online: false, cat: new Set(), access: new Set(), q: "" };

// Filtre « Source » : les sources (src) et les catégories à part (cat :
// soutenances, carrières) sont des cases d'une même liste, cumulables (« Luma
// + Carrières »). Rien de coché : le fil normal, sans les catégories à part —
// sauf favori ou recherche (un nom de doctorant doit rester trouvable).
export function inSource(e, f) {
  if (f.src.size || f.cat.size) return isSide(e) ? f.cat.has(e.kind) : f.src.has(e.source_type);
  return !isSide(e) || !!f.q || f.fav;
}

export function matches(e, f, favs) {
  if (f.fav && !favs.has(e.id)) return false;
  if (!inSource(e, f)) return false;
  if (f.online && !isOnline(e)) return false;
  if (f.when === "today" && e.date !== TODAY) return false;
  if (f.when === "tonight" && !(e.date === TODAY && (e.time || "") >= "17:30")) return false;
  if (f.when === "week" && e.date > WEEK_END) return false;
  if (f.when === "weekend" && !WE.includes(e.date)) return false;
  if (f.when === "new" && !isNew(e)) return false;
  if (f.disc.size && !f.disc.has(e.discipline)) return false;
  if (f.inst.size && !f.inst.has(e.institution)) return false;
  if (f.access.size && !f.access.has(accessOf(e))) return false;
  if (f.theme.size && !(e.luma_categories || []).some(c => f.theme.has(c))) return false;
  if (f.q) { const hay = norm([e.title, e.speaker, e.institution, e.description, e.location].join(" ")); if (!f.q.split(/\s+/).every(w => hay.includes(w))) return false; }
  return true;
}

/* ── URL ⇄ état (mêmes clés que l'ancien site : les liens partagés et les
   hubs i/*.html?institution=… continuent de fonctionner) ─────────────── */
export function filtersFromURL() {
  const p = new URLSearchParams(location.search), f = { ...EMPTY_FILTERS, disc: new Set(), inst: new Set(), src: new Set(), theme: new Set(), access: new Set(), cat: new Set() };
  const list = k => (p.get(k) || "").split(",").filter(Boolean);
  if (p.get("date")) f.when = p.get("date");
  list("acces").forEach(v => f.access.add(v));
  list("discipline").forEach(v => f.disc.add(v)); list("institution").forEach(v => f.inst.add(v)); list("theme").forEach(v => f.theme.add(v));
  const src = p.get("source"); if (src && src !== "all" && src !== "history") f.src.add(src);
  if (p.get("favoris") === "1") f.fav = true;
  if (p.get("format") === "online") f.online = true;
  Object.entries(SIDE_KINDS).forEach(([k, s]) => { if (p.get(s.param) === "1") f.cat.add(k); });
  if (p.get("q")) f.q = norm(p.get("q"));
  return { filters: f, view: p.get("vue") || "list", history: src === "history", event: p.get("event") || null, rawQ: p.get("q") || "" };
}
export function urlFromState({ filters: f, view, history, rawQ }) {
  const p = new URLSearchParams();
  if (history) p.set("source", "history"); else if (f.src.size === 1) p.set("source", [...f.src][0]);
  if (view !== "list") p.set("vue", view);
  if (rawQ.trim()) p.set("q", rawQ.trim());
  if (f.when !== "all") p.set("date", f.when);
  if (f.online) p.set("format", "online");
  if (f.disc.size) p.set("discipline", [...f.disc].join(","));
  if (f.inst.size) p.set("institution", [...f.inst].join(","));
  if (f.theme.size) p.set("theme", [...f.theme].join(","));
  if (f.access.size) p.set("acces", [...f.access].join(","));
  if (f.fav) p.set("favoris", "1");
  f.cat.forEach(k => SIDE_KINDS[k] && p.set(SIDE_KINDS[k].param, "1"));
  const qs = p.toString(); return qs ? "?" + qs : location.pathname;
}

/* ── ICS (export de la sélection) — même format que l'ancien site ─── */
const icsEsc = s => String(s || "").replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/[,;]/g, m => "\\" + m);
function icsDt(date, time) {
  if (!date) return { start: "", allDay: true };
  const d = date.replace(/-/g, "");
  if (!time) return { start: d, allDay: true, h: 0, m: 0 };
  const [h, m] = time.split(":").map(Number);
  return { start: `${d}T${pad(h)}${pad(m)}00`, allDay: false, h, m };
}
export function buildIcs(events) {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Lotent//Selection//FR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    "X-WR-CALNAME:Ma sélection · Lotent", "X-WR-TIMEZONE:Europe/Paris"];
  for (const ev of events) {
    const s = icsDt(ev.date, ev.time); let dtstart, dtend;
    if (s.allDay) { dtstart = `DTSTART;VALUE=DATE:${s.start}`; dtend = `DTEND;VALUE=DATE:${iso(addDays(parse(ev.date), 1)).replace(/-/g, "")}`; }
    else { dtstart = `DTSTART:${s.start}`; const e = icsDt(ev.date, ev.end_time); dtend = e.start && !e.allDay ? `DTEND:${e.start}` : `DTEND:${ev.date.replace(/-/g, "")}T${pad(Math.min(s.h + 2, 23))}${pad(s.m)}00`; }
    out.push("BEGIN:VEVENT", `UID:${ev.id}@lotent.fr`, `DTSTAMP:${stamp}`, dtstart, dtend, `SUMMARY:${icsEsc(ev.title)}`,
      `LOCATION:${icsEsc(ev.location || "Paris")}`, `DESCRIPTION:${icsEsc((ev.description || "") + (ev.url ? "\n" + ev.url : ""))}`,
      ev.url ? `URL:${ev.url}` : "", `CATEGORIES:${icsEsc(ev.discipline || "")}`, "END:VEVENT");
  }
  out.push("END:VCALENDAR");
  return out.filter(Boolean).join("\r\n");
}
export function download(name, text, type = "text/calendar") {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
export function googleCalUrl(ev) {
  const s = icsDt(ev.date, ev.time), e = icsDt(ev.date, ev.end_time);
  const dates = s.allDay ? `${s.start}/${iso(addDays(parse(ev.date), 1)).replace(/-/g, "")}` : `${s.start}/${e.start && !e.allDay ? e.start : ev.date.replace(/-/g, "") + "T" + pad(Math.min(s.h + 2, 23)) + pad(s.m) + "00"}`;
  const p = new URLSearchParams({ action: "TEMPLATE", text: ev.title, dates, details: (ev.description || "") + (ev.url ? "\n" + ev.url : ""), location: ev.location || "Paris", ctz: "Europe/Paris" });
  return "https://calendar.google.com/calendar/render?" + p.toString();
}

/* ── Stockage local ─────────────────────────────────────────────── */
export const store = {
  // paf_theme était stocké en chaîne brute par l'ancien site : on tolère les deux formes
  get(k, d) { let v = null; try { v = localStorage.getItem(k); } catch (e) { return d; } if (v === null) return d; try { return JSON.parse(v); } catch (e) { return v; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};
