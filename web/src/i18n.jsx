/* Bilingue FR/EN. Clé courte -> [fr, en]. "{n}" est remplacé par la valeur
   fournie, "{s}" devient "s" si n > 1 (accord singulier/pluriel commun aux
   deux langues). Persisté dans localStorage sous la même clé que l'ancien
   site (paf_lang), donc un visiteur qui revient garde sa langue. */
import React, { createContext, useContext, useState, useCallback, useMemo, useEffect } from "react";
import { store } from "./lib.js";

const TR = {
  nav_agenda: ["Agenda", "Agenda"], nav_history: ["Historique", "History"], nav_about: ["À propos", "About"], nav_propose: ["Proposer un événement", "Submit an event"],
  search_ph: ["Rechercher…", "Search…"], subscribe: ["S'abonner", "Subscribe"], theme_aria: ["Changer de thème", "Toggle theme"],
  lang_aria: ["Passer en anglais", "Switch to French"],

  live_updated: ["Mis à jour {rel}", "Updated {rel}"], live_fallback: ["Mis à jour chaque matin", "Updated every morning"],
  live_events_suffix: [" · {n} événement{s} à venir", " · {n} upcoming event{s}"],
  hero_title_1: ["Toutes les conférences de Paris,", "All the conferences in Paris,"],
  hero_title_2: ["en un seul agenda.", "in one single agenda."],
  hero_loading: ["chargement…", "loading…"],
  hero_lede: ["Cours du Collège de France, séminaires de l'IHP et de PSE, rencontres Luma : {n} organisateurs réunis, {f} événements en entrée libre.",
              "Lectures from the Collège de France, seminars from IHP and PSE, Luma meetups: {n} organisers gathered, {f} free events."],
  btn_today: ["Voir aujourd'hui", "See today"], btn_week: ["Cette semaine", "This week"],
  stat_today: ["aujourd'hui", "today"], stat_week: ["cette semaine", "this week"], stat_weekend: ["ce week-end", "this weekend"],

  featured_title: ["À la une", "Featured"],
  featured_sub_digest: ["Sélection de la semaine — {period}", "This week's picks — {period}"],
  featured_sub_auto: ["Aujourd'hui et demain, sélection automatique.", "Today and tomorrow, automatic pick."],
  tonight_title: ["Ce soir", "Tonight"], tonight_empty: ["Rien après 17h30 aujourd'hui. Regarde demain.", "Nothing after 5:30pm today. Check tomorrow."],
  days7_title: ["Les 7 prochains jours", "Next 7 days"], n_events: ["{n} événement{s}", "{n} event{s}"],
  map_title: ["Carte", "Map"], map_cta: ["Voir la carte →", "View map →"],

  tab_all: ["Tout", "All"], tab_today: ["Aujourd'hui", "Today"], tab_tonight: ["Ce soir", "Tonight"],
  tab_week: ["Semaine", "Week"], tab_weekend: ["Week-end", "Weekend"], tab_new: ["Nouveautés", "New"],
  history_badge: ["Historique", "History"], history_all_period: ["Toute la période", "Whole period"],
  history_back: ["← Retour à l'agenda", "← Back to agenda"], history_loading: ["Chargement de l'historique…", "Loading history…"],
  history_kicker: ["Archives", "Archives"], history_title: ["Les conférences passées.", "Past conferences."],
  history_lede: ["{n} conférence{s} archivée{s} — la mémoire de l'agenda, pour retrouver un intervenant ou une séance.",
                 "{n} archived event{s} — the agenda's memory, to find a past speaker or session again."],

  pop_discipline: ["Discipline", "Discipline"], pop_institution: ["Institution", "Institution"], pop_source: ["Source", "Source"],
  group_establishments: ["Établissements", "Institutions"], group_others: ["Autres organisateurs", "Other organisers"],
  group_luma_themes: ["Thèmes Luma", "Luma themes"], clear_all: ["Tout effacer", "Clear all"],
  group_side: ["Masqués du fil par défaut", "Hidden from the feed by default"], group_format: ["Format", "Format"],
  group_price: ["Tarif", "Price"], group_lang: ["Langue", "Language"], filter_en: ["En anglais", "In English"],
  filter_en_hint: ["Repéré automatiquement d'après le titre et la description", "Detected automatically from the title and description"],
  btn_fav: ["Favoris", "Favourites"], btn_online: ["En ligne", "Online"],
  pop_access: ["Accès", "Access"], access_public: ["Ouvert à tous", "Open to all"], access_members: ["Réservé aux membres", "Members only"],
  badge_members: ["Membres", "Members"], access_members_hint: ["Réservé aux membres de l'organisation (adhérents, bénéficiaires, élèves…)", "Reserved for the organisation's members (members, beneficiaries, students…)"],
  btn_theses: ["Soutenances", "PhD defences"], btn_theses_hint: ["Soutenances de thèse et HDR, masquées du fil principal", "PhD and habilitation defences, hidden from the main feed"],
  btn_careers: ["Carrières", "Careers"], btn_careers_hint: ["Événements de recrutement des entreprises (banques, conseil, tech…), masqués du fil principal", "Company recruiting events (banks, consulting, tech…), hidden from the main feed"],
  view_list: ["Liste", "List"], view_week: ["Semaine", "Week"], view_map: ["Carte", "Map"],
  near_locate: ["Localisation…", "Locating…"], near_sorted: ["Tri par distance", "Sorted by distance"], near_label: ["Près de moi", "Near me"],
  noun_event: ["événement{s}", "event{s}"],
  src_institution: ["Universités & instituts", "Universities & institutes"], src_luma: ["Luma", "Luma"], src_association: ["Associations", "Associations"], src_ville: ["Que faire à Paris", "Que faire à Paris (City of Paris)"], src_entreprise: ["Entreprise", "Company"],

  badge_new: ["Nouveau", "New"], badge_free: ["Gratuit", "Free"], online_prefix: ["En ligne · ", "Online · "],
  time_tbd: ["Horaire à confirmer", "Time TBC"],

  empty_fav_title: ["Aucun favori", "No favourites"], empty_fav_sub: ["Clique sur l'étoile d'un événement pour le retrouver ici.", "Click an event's star to find it here."],
  empty_generic_title: ["Rien ne correspond", "Nothing matches"], empty_generic_sub: ["Élargis la période ou retire un filtre.", "Widen the period or remove a filter."],
  sorted_by_distance: ["Triés par distance depuis ta position.", "Sorted by distance from your location."],
  show_more: ["Afficher la suite · {n} restant{s}", "Show more · {n} left"],

  sheet_free: ["Entrée libre", "Free entry"], sheet_online: ["En ligne", "Online"], sheet_organizer: ["Organisé par", "Organised by"], sheet_also: ["Co-organisé avec", "Co-organised with"],
  sheet_with: ["Avec", "With"], sheet_place: ["Lieu", "Venue"], sheet_price: ["Tarif", "Price"],
  sheet_official: ["Page officielle · inscription ↗", "Official page · registration ↗"],
  sheet_fav_on: ["★ Favori", "★ Favourite"], sheet_fav_off: ["☆ Favori", "☆ Favourite"],
  sheet_agenda: ["Agenda", "Calendar"], sheet_google_cal: ["Google Agenda ↗", "Google Calendar ↗"],
  sheet_ics_file: ["Fichier .ics (Apple, Outlook…)", ".ics file (Apple, Outlook…)"], sheet_share: ["Partager", "Share"],
  sheet_footer_note: ["Vérifie les horaires sur la page officielle avant de te déplacer.", "Double-check the time on the official page before heading out."],
  sheet_terminated: ["terminé", "past"], sheet_today: ["c'est aujourd'hui", "it's today"], sheet_tomorrow: ["c'est demain", "it's tomorrow"],
  sheet_in_days: ["dans {n} jours", "in {n} days"], org_default: ["Universités & instituts", "Universities & institutes"],
  fermer: ["Fermer", "Close"], favori: ["Favori", "Favourite"],
  rel_cycle: ["Autres séances du cycle", "Other sessions in this series"], rel_speaker: ["Du même intervenant", "Same speaker"],
  rel_place: ["Au même endroit ce jour-là", "Same place, same day"], rel_more: ["Voir {n} autre{s}", "Show {n} more"],

  cmd_ph: ["Un titre, un intervenant, un sujet…", "A title, a speaker, a topic…"], cmd_nav: ["naviguer", "navigate"],
  cmd_open: ["ouvrir", "open"], cmd_none: ["Aucun résultat.", "No results."], cmd_today_tomorrow: ["Aujourd'hui et demain", "Today and tomorrow"],
  cmd_n_results: ["{n} résultat{s}", "{n} result{s}"],

  week_prev: ["← Semaine préc.", "← Prev week"], week_next: ["Semaine suiv. →", "Next week →"], week_this: ["cette semaine", "this week"],

  map_note: ["{n} événement{s} localisé{s} · clique un point pour voir les conférences du lieu.", "{n} located event{s} · click a point to see the conferences there."],

  toast_fav_added: ["Ajouté aux favoris", "Added to favourites"], toast_fav_removed: ["Retiré des favoris", "Removed from favourites"],
  toast_link_copied: ["Lien copié", "Link copied"],
  sub_title: ["S'abonner à l'agenda", "Subscribe to the calendar"], sub_all: ["Toutes les conférences", "All conferences"],
  sub_apple: ["Apple Calendrier, Outlook, Thunderbird", "Apple Calendar, Outlook, Thunderbird"],
  sub_google: ["Google Agenda", "Google Calendar"], sub_copy: ["Copier le lien", "Copy link"],
  sub_hint: ["Un abonnement se met à jour tout seul chaque jour : rien à retélécharger. Autre application : collez le lien dans « Ajouter un agenda par URL ».",
    "A subscription updates itself every day: nothing to download again. Other apps: paste the link into “Add calendar from URL”."],
  toast_geoloc_unavailable: ["Géolocalisation indisponible sur ce navigateur.", "Geolocation unavailable on this browser."],
  toast_locate_error: ["Localisation impossible : {msg}", "Location failed: {msg}"],
  toast_not_found: ["Événement introuvable — il est peut-être terminé.", "Event not found — it may be over."],


  dock_top: ["Haut de page", "Back to top"], dock_today: ["Aujourd'hui", "Today"], dock_history: ["Historique", "History"],
  dock_random: ["Au hasard", "Random"], dock_fav: ["Favoris", "Favourites"], dock_search: ["Rechercher (⌘K)", "Search (⌘K)"],

  footer_tagline: ["Toutes les conférences, cours et séminaires ouverts au public à Paris, réunis chaque matin en un seul agenda.",
                   "All public conferences, lectures and seminars in Paris, gathered every morning into one agenda."],
  footer_updated: ["Dernière mise à jour automatique : {auto}", "Last automatic update: {auto}"],
  footer_manual_suffix: [" · manuelle : {t}", " · manual: {t}"],
  footer_subscribe: ["S'abonner", "Subscribe"], footer_ics: ["Calendrier complet (.ics)", "Full calendar (.ics)"],
  footer_rss: ["Flux RSS de la semaine", "This week's RSS feed"], footer_sitemap: ["Plan du site", "Sitemap"],
  footer_contact_title: ["Une question, une idée ?", "A question, an idea?"],
  footer_contact_body: ["Le code est ouvert : signale une source manquante, un bug, ou propose une amélioration.",
                         "The code is open: report a missing source, a bug, or suggest an improvement."],
  footer_repo_desc: ["Agrégateur des conférences académiques de Paris.", "Aggregator for Paris academic conferences."],
  footer_open_issue: ["Ouvrir une discussion", "Open a discussion"], footer_source: ["Code source", "Source code"],

  follow_speaker: ["Suivre cet intervenant", "Follow this speaker"], unfollow_speaker: ["Ne plus suivre", "Unfollow"],
  my_speakers: ["Mes intervenants", "My speakers"], no_speakers: ["Aucun intervenant suivi.", "No speakers followed yet."],
  no_speakers_sub: ["Clique sur la cloche à côté d'un intervenant pour le suivre ici.", "Click the bell next to a speaker to follow them here."],
  upcoming_from: ["À venir", "Upcoming"], no_upcoming: ["Plus rien de prévu pour l'instant.", "Nothing scheduled for now."],
  notify_enable: ["Activer les notifications", "Enable notifications"], notify_enabled: ["Notifications activées ✓", "Notifications enabled ✓"],
  notify_denied: ["Notifications bloquées par le navigateur.", "Notifications blocked by the browser."],
  notify_title: ["Tes intervenants reviennent", "Your speakers are back"],
  inst_events_count: ["{n} événement{s} à venir", "{n} upcoming event{s}"], inst_site: ["Fiche institution ↗", "Institution page ↗"],
  inst_ics: ["S'abonner à son agenda", "Subscribe to its calendar"], inst_clear: ["Voir toutes les institutions", "See all institutions"],
  disc_site: ["Page de la discipline ↗", "Discipline page ↗"], disc_clear: ["Toutes les disciplines", "All disciplines"],
  search_hint: ["Appuie sur / pour rechercher", "Press / to search"],

  you_are_here: ["Vous êtes ici", "You are here"],
  speaker_followed: ["Intervenant suivi ✓", "Speaker followed ✓"], speaker_unfollowed: ["Ne suit plus cet intervenant", "No longer following"],
  rel_never: ["jamais", "never"], rel_now: ["à l'instant", "just now"],
  rel_min: ["il y a {n} min", "{n} min ago"], rel_h: ["il y a {n} h", "{n} h ago"], rel_d: ["il y a {n} j", "{n} d ago"],
  rel_today: ["Aujourd'hui", "Today"], rel_tomorrow: ["Demain", "Tomorrow"],
};

const WD_FR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
const WD_EN = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const WDS_FR = ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"];
const WDS_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MO_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const MO_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// Noms affichés en anglais. Les clés restent les valeurs françaises des
// données (e.discipline, kindOf(e)) : filtres et URL ne changent pas.
const DISC_EN = {
  "Mathématiques": "Mathematics", "Sciences": "Sciences", "Économie": "Economics", "Histoire": "History",
  "Philosophie": "Philosophy", "Littérature": "Literature", "Sociologie & Anthropologie": "Sociology & Anthropology",
  "Droit & Sciences politiques": "Law & Political science", "Arts & Culture": "Arts & Culture", "Autre": "Other",
};
const KIND_EN = {
  "Cours": "Lecture course", "Séminaire": "Seminar", "Colloque": "Conference", "Conférence": "Talk",
  "Leçon inaugurale": "Inaugural lecture", "Journée d'étude": "Study day", "Atelier": "Workshop",
  "Workshop": "Workshop", "Table ronde": "Round table", "Rencontre": "Meetup", "Lecture": "Reading",
  "Soutenance": "Thesis defence", "Recrutement": "Recruitment",
};

const LangContext = createContext(null);

function parseISO(s) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(() => (store.get("paf_lang", "fr") === "en" ? "en" : "fr"));
  const setLang = useCallback(l => { setLangState(l); store.set("paf_lang", l); }, []);
  const toggleLang = useCallback(() => setLang(lang === "en" ? "fr" : "en"), [lang, setLang]);
  // <html lang> reste sinon figé sur "fr" (valeur statique d'index.html) après
  // un passage en anglais — mauvais pour l'accessibilité et les lecteurs d'écran.
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const t = useCallback((key, vars) => {
    let s = (TR[key] || [key, key])[lang === "en" ? 1 : 0];
    if (vars) {
      // Pluriel : « 0 événement » en français, mais « 0 events » en anglais
      if ("n" in vars) s = s.split("{s}").join((lang === "en" ? vars.n !== 1 : vars.n > 1) ? "s" : "");
      Object.keys(vars).forEach(k => { s = s.split(`{${k}}`).join(vars[k]); });
    }
    return s;
  }, [lang]);

  const value = useMemo(() => {
    const WD = lang === "en" ? WD_EN : WD_FR, WDS = lang === "en" ? WDS_EN : WDS_FR, MO = lang === "en" ? MO_EN : MO_FR;
    const relTime = ts => {
      if (!ts) return t("rel_never");
      const m = Math.round((Date.now() - new Date(ts)) / 60000);
      if (m < 1) return t("rel_now");
      if (m < 60) return t("rel_min", { n: m });
      if (m < 48 * 60) return t("rel_h", { n: Math.round(m / 60) });
      return t("rel_d", { n: Math.round(m / 1440) });
    };
    return {
      lang, setLang, toggleLang, t, WD, WDS, MO,
      discName: d => (lang === "en" && DISC_EN[d]) || d,
      kindName: k => (lang === "en" && KIND_EN[k]) || k,
      fmtDay: s => { const d = parseISO(s); return `${WD[d.getDay()]} ${d.getDate()} ${MO[d.getMonth()]}`; },
      fmtShort: s => { const d = parseISO(s); return `${WDS[d.getDay()]} ${d.getDate()} ${MO[d.getMonth()].slice(0, lang === "en" ? 3 : 4)}`; },
      relDay: (s, TODAY, TOMORROW) => s === TODAY ? t("rel_today") : s === TOMORROW ? t("rel_tomorrow") : "",
      relTime,
    };
  }, [lang, t]);

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useI18n must be used within a LangProvider");
  return ctx;
}
