#!/usr/bin/env python3
"""
Scraper for Paris academic conferences.

Sources:
- IHP            : Indico JSON API
- Collège de France, EHESS, ENS, Sciences Po, Sorbonne : paginated HTML scrape
- Luma           : network interception of JSON API calls

All HTML sources are scraped page-by-page (?page=N) until no new events appear.
"""

import json
import hashlib
import re
import time
import traceback
from datetime import datetime, date, timedelta
from pathlib import Path

import icalendar
import requests
from bs4 import BeautifulSoup
from dateparser.search import search_dates
from html import unescape as html_unescape
from dateutil import parser as dateparser, tz as dateutil_tz
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "events.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
TODAY = date.today()
CUTOFF = TODAY - timedelta(days=1)
HORIZON = TODAY + timedelta(days=365)

# ── Discipline detection ──────────────────────────────────────────────────────

DISCIPLINE_KEYWORDS = {
    "Mathématiques": [
        # FR
        "mathémat", "algèbre", "géométri", "topologi", "analyse fonction",
        "probabilit", "statistique", "arithmétique", "combinatoire",
        "théorie des nombres", "équation", "logique mathématique", " math ",
        " graphe", "tenseur", "variété", "homologi", "cohomologi",
        "homotopi", "homotop", "espace métrique", "groupe de lie",
        "courbe ellipt", "modulair", "polytope", "fractale",
        # EN
        "theorem", "conjecture", "manifold", "algebra", "geometry", "geometr",
        "topology", "operator", "operad", "homotopy", "homology", "cohomology",
        "motivic", "automorphic", "langlands", "modular form", "galois",
        "perfectoid", "ergodic", "schur", "étale", "etale", "derived",
        "scheme", "sheaf", "fano", "calabi-yau", "hodge", "witt", "k-theory",
        "k-théorie", "lie algebra", "lie group", "lie algebr", " hilbert",
        "banach", "sobolev", " nls", "pde ", " edp", "schrödinger",
        "schrodinger", "hyperbolic equation", "elliptic equation", "lattice",
        "integrable", "dispersive", "ricci", "yamabe", " riemann", "kahler",
        "kähler", "symplectic", "symplectique", "groebner", "gröbner",
        "spectral", "spectrale", "combinatoire", "combinatorics",
        "stochastic", "stochastique", "mathematics", "mathematical",
    ],
    "Philosophie": [
        "philosoph", "éthique", "métaphysique", "épistémologie", "ontologie",
        "phénoménologi", "wittgenstein", "hegel", " kant", "nietzsche",
        "platon", "aristote", "esthétique philosophique", "morale",
        "ricoeur", "deleuze", "foucault", "merleau-ponty", "spinoza",
        # Théologie / spiritualité (Collège des Bernardins…) rangées ici
        "théolog", "theolog", " dieu", "église", "biblique", "bible",
        "chrétien", "christian", "spiritualit", "évangile", "évangél",
        "pensée", "philosophy",
    ],
    "Littérature": [
        "littératur", "roman", "poésie", "poème", "narratologi", "récit",
        "fiction", "écrivain", "stylistique", "rhétorique", "traduction littéraire",
        "linguistique", "philolog", "poétique", "romanesque", "shakespeare",
        "balzac", "proust", "flaubert", "stendhal", "céline", "rimbaud",
        "baudelaire", "verlaine", "molière", "racine", "corneille",
        "une heure, un livre", "écrivaine", "romancier", "romancière",
        "poète", "poésie", "literature", "novel", "poetry",
    ],
    "Histoire": [
        "histoir", "archive", "mémoire collective", "patrimoine", "médiéval",
        "antiquité", "révolution", "colonialism", "esclavage", " guerre",
        "empire", "historiograph", "chronologie", "préhistoir", "néolithi",
        "byzantin", "ottoman", "renaissance", " moyen âge", "égyptolog",
        "assyriolog", "sumeri", " sassanid", "carthag", "vichy", " shoah",
        "siècle", "égypt", "mésopotam", " antique", "archéolog", "papyr",
        "romain", "rome antique", "grec ancien", "pharaon", "médiév",
        "napoléon", "monarchie", "history", "historical", "ancient",
        "medieval", "archaeolog",
    ],
    "Sciences": [
        # FR
        "physique", "chimie", "biologi", "neuroscienc", "génétique", "écologi",
        "astronomi", "astrophysique", "quantique", "thermodynamique", "évolution",
        "darwin", "climat", "environnement", "science cognitiv",
        "intelligence artificielle", "apprentissage automatique",
        "particule", "atomique", "moléculaire", "nucléair", "relativ",
        "supraconduc", "cellulair", "écosystèm", "biodiversit",
        "cosmolog", "exoplanèt", "matière noire", "boson",
        # EN
        "physics", "chemistry", "biology", "ecology", "ecological",
        "climate", "quantum", "particle", "atomic", "molecular",
        "cosmic", "cosmolog", "exoplanet", "stellar",
        "machine learning", "deep learning", "data science", "neural network",
        "artificial intelligence", "computational", "computing",
        "hamiltonian", "lagrangian", "magnetic", "magnetism", "magnétique",
        "semi-classical", "laplacian", "laplacien", "dirac", "gauge",
        "supersymetr", "supersymétri", "conformal", "conforme", "holograph",
        "condensed matter", "matière condensé", "moire", "moiré",
        "josephson", "topological state", "moléculaire", "réaction chimique",
        " josephson",
        # Vivant, santé, numérique, instruments (labos, Pasteur, Curie…)
        "cellule", "cancer", "tumeur", "oncolog", "cerveau", "neuron",
        "génom", "genom", " gène", "protéin", "protein", "immun", "virus",
        "viral", "bactéri", "bacteri", "microbio", "épidémi", "epidemi",
        "vaccin", "médecine", "médical", "medical", "clinique", "clinical",
        "pathogen", "infection", "brain", " cell", "stem cell", "enzym",
        "données", "informatique", "algorithm", "logiciel", "software",
        "robot", " ia ", "(ia)", "entropi", "fluide", "atome", " atom",
        "laser", "plasma", "accélérateur", "accelerator", "détecteur",
        "detector", "neutrino", "photon", "galax", "planét", "planet",
        "astronom", "spectroscop", "matériau", "material", "énergie",
        "energy", "océan", "ocean", "géolog", "geolog", "séisme",
        "chimi", "chemist", "biophys", "cosmic", "supernova",
        "obésité", "traitement", "médicament", "nutrition", "physiolog",
        "plantes", "botani",
    ],
    "Économie": [
        "économi", "economic", "macroéco", "microéco", "macro-", "micro-",
        "marché", "finance", "financ", "monétaire", "monetary",
        "fiscal", "inégalité", "inequality", "croissance", "growth",
        "emploi", "chômage", "unemployment", "salaire", "wage",
        "capitalisme", "capitalism", "économétr", "econometric",
        "pib", "gdp", "inflation", "phillips", "solow", "dsge",
        "consumption", "consommation", "investment", "investissement",
        "trade ", "commerce", "tax", "fiscalit", "banque centrale",
        "central bank", "labor market", "marché du travail",
    ],
    "Sociologie & Anthropologie": [
        "sociologi", "anthropologi", "ethnolog", "terrain", " enquête",
        "société", "classe sociale", "genre ", "racisme", "discrimination",
        "migration", "identité", "rituel", "bourdieu", "durkheim", "famille",
        "ethnograph", "kinship", "parenté", "tribu", "rural", "urbain ",
    ],
    "Droit & Sciences politiques": [
        " droit", " droits ", "juridique", "constitutionnel", "science politique",
        "démocratie", "democracy", "gouvernance", "parlement",
        "élection", "election", "souveraineté", "sovereignty",
        "politique publique", "géopolitique", "geopolitic", "ambassadeur",
        "ambassade", "diplomate", "diplomacy", "diplomatie", "ministre",
        "minister", "ancien premier ministre", "former prime minister",
        "président", "elysée", "elysee",
    ],
    "Arts & Culture": [
        " art ", " arts ", "musique", "music ", "cinéma", "cinema", " film ",
        " films ", "théâtre", "theatre", "peinture", "painting", "sculpture",
        "architecture", "danse", "dance ", "muséolog", "exposition", "exhibit",
        "photographi", "photograph", "design", "musical", "ballet", "opéra",
        "opera", "matisse", "picasso", "monet", "degas", "rodin", "rembrandt",
    ],
}

# Quand le détecteur ne trouve rien, on tombe sur la discipline « phare »
# de l'institution. Les multi-disciplines (Sciences Po, EHESS…) restent en
# « Autre » pour ne pas étiqueter à tort.
_INSTITUTION_DEFAULT = {
    "Université Paris-Panthéon-Assas": "Droit & Sciences politiques",
    "Sciences Po": "Droit & Sciences politiques",
    "Université Paris Dauphine": "Économie",
    "EPHE": "Histoire",
    "Fondation Maison des Sciences de l'Homme": "Sociologie & Anthropologie",
    "Campus Condorcet": "Sociologie & Anthropologie",
    "Musée du quai Branly": "Sociologie & Anthropologie",
    "Musée du Louvre": "Arts & Culture", "Centre Pompidou": "Arts & Culture",
    "Hi! PARIS": "Sciences", "PR[AI]RIE": "Sciences", "HEC IA": "Sciences",
    "HEC Paris": "Économie",
    "INHA": "Arts & Culture", "Beaux-Arts de Paris": "Arts & Culture",
    "Institut du monde arabe": "Arts & Culture", "École nationale des chartes": "Histoire",
    "Ifri": "Droit & Sciences politiques", "IRIS": "Droit & Sciences politiques",
    "Institut Jacques Delors": "Droit & Sciences politiques",
    "Fondation Jean-Jaurès": "Droit & Sciences politiques",
    "Institut Louis Bachelier": "Économie", "Citéco": "Économie", "ESCP Business School": "Économie",
    "ENS Paris-Saclay": "Sciences",
    "EHESS": "Sociologie & Anthropologie",
    "Collège des Bernardins": "Philosophie",
    "Université Sorbonne Nouvelle": "Littérature",
    "IJCLab": "Sciences", "IN2P3": "Sciences", "Observatoire de Paris": "Sciences",
    "Institut Henri Poincaré": "Mathématiques",
    "Paris School of Economics": "Économie",
    "Institut Pasteur": "Sciences",
    "Institut Curie": "Sciences",
    "Institut du Cerveau": "Sciences",
    "Académie des sciences": "Sciences",
    "Muséum national d'Histoire naturelle": "Sciences",
    "Cité des sciences": "Sciences",
}


# Titulaires des chaires du Collège de France (college-de-france.fr/fr/chaires-
# actuelles, sept. 2026). Leurs cours ont des titres sans mot-clé (« Les
# Épouses du dieu à Thèbes (6) ») : le nom du professeur suffit. À mettre à
# jour quand les chaires changent ; le classement par mots-clés reste en secours.
_SPEAKER_DISCIPLINE = {
    "Nalini Anantharaman": "Mathématiques", "Timothy Gowers": "Mathématiques",
    "Laure Saint-Raymond": "Mathématiques",
    **dict.fromkeys([
        "Xavier Leroy", "Stéphane Mallat", "Ioana Manolescu", "Lydéric Bocquet",
        "Jean Dalibard", "Louis Fensterbank", "Marc Fontecave", "Antoine Georges",
        "Marc Henneaux", "Jean-François Joanny", "Jean-Marie Tarascon", "Edouard Bard",
        "Alessandro Morbidelli", "Simon Cauchemez", "Hugues de Thé", "Stanislas Dehaene",
        "Denis Duboule", "Sonia Garel", "Edith Heard", "Olivier Hermine",
        "Jean-Jacques Hublin", "Thomas Lecuit", "Tâm Mignot", "Lluis Quintana-Murci"],
        "Sciences"),
    **dict.fromkeys([
        "Patrick Boucheron", "Dominique Charpin", "Anne Cheng", "Laurent Coulon",
        "François-Xavier Fauvelle", "Jean-Luc Fournet", "Henry Laurens", "Antoine Lilti",
        "Dario Mantovani", "Vinciane Pirenne-Delforge", "Thomas Römer"], "Histoire"),
    "Isabelle Ratié": "Philosophie", "Barbara Cassin": "Philosophie",
    "François Recanati": "Philosophie",
    "Diane Bodart": "Arts & Culture", "Claire Denis": "Arts & Culture",
    "William Marx": "Littérature",
    "Philippe Aghion": "Économie", "Esther Duflo": "Économie", "Marc Fleurbaey": "Économie",
    "Samantha Besson": "Droit & Sciences politiques",
    "Olivier Borraz": "Sociologie & Anthropologie", "Didier Fassin": "Sociologie & Anthropologie",
    "Pierre-Michel Menger": "Sociologie & Anthropologie",
}


def _speaker_discipline(ev):
    hay = f"{ev.get('speaker', '')} {ev.get('title', '')}"
    return next((d for name, d in _SPEAKER_DISCIPLINE.items() if name in hay), None)


def reclassify(ev):
    """Pour les événements restés en « Autre » (y compris ceux reportés des
    jours précédents) : professeur connu, puis mots-clés, puis institution."""
    if ev.get("discipline") not in (None, "", "Autre"):
        return
    ev["discipline"] = _speaker_discipline(ev) or detect_discipline(
        ev.get("title", ""), ev.get("description", ""), ev.get("institution", ""),
        ev.get("luma_categories"))


# Mapping des thèmes Luma vers une discipline « phare » : si aucun mot-clé
# n'attrape un titre Luma (souvent court, ex. « Pocket Party »), on retombe
# au moins sur le thème de la page Luma d'où il vient.
_LUMA_CAT_DISCIPLINE = {
    "ai": "Sciences", "tech": "Sciences", "climate": "Sciences",
    "arts": "Arts & Culture", "crypto": "Économie",
    # paris / wellness / food / fitness → restent "Autre" (vraiment hors champ académique)
}


def detect_discipline(title: str, description: str = "",
                      institution: str = "",
                      luma_categories=None) -> str:
    text = " " + (title + " " + description).lower() + " "
    scores = {}
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score:
            scores[discipline] = score
    if scores:
        return max(scores, key=scores.get)
    # Fallback Luma : la catégorie d'origine sert d'indice
    if luma_categories:
        for cat in luma_categories:
            d = _LUMA_CAT_DISCIPLINE.get(cat)
            if d:
                return d
    return _INSTITUTION_DEFAULT.get(institution, "Autre")


# ── French date parser ────────────────────────────────────────────────────────

FRENCH_MONTHS = {
    "janvier": 1, "janv": 1, "jan": 1,
    "fevrier": 2, "fevr": 2, "fev": 2,
    "mars": 3, "mar": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juill": 7, "juil": 7,
    "aout": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "decembre": 12, "dec": 12,
}

# Regex fragment matching any full OR abbreviated French month (longest first)
_MONTH_PAT = (r"janvier|janv|jan|f[ée]vrier|f[ée]vr|f[ée]v|mars|avril|avr|mai|"
              r"juin|juillet|juill|juil|ao[uû]t|septembre|sept|sep|octobre|oct|"
              r"novembre|nov|d[ée]cembre|d[ée]c")

_FR_DATE_RE = re.compile(
    r"(\d{1,2})(?:er|ère|ème|e)?\s+(" + _MONTH_PAT + r")\.?\s+(\d{4})", re.I)
_FR_NOYEAR_RE = re.compile(
    r"(\d{1,2})(?:er|ère|ème|e)?\s+(" + _MONTH_PAT + r")\b", re.I)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_FR_SLASH_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b")


def _month_num(s):
    """French month name or abbreviation → month number 1-12 (or None)."""
    k = str(s or "").strip().lower().rstrip(".")
    k = (k.replace("é", "e").replace("è", "e").replace("ê", "e")
          .replace("û", "u").replace("ô", "o").replace("à", "a"))
    return FRENCH_MONTHS.get(k)


def parse_french_date_text(text: str):
    """Extract a date object from French text like 'Mardi 3 juin 2026'."""
    m = _FR_DATE_RE.search(text)
    if m:
        month = _month_num(m.group(2))
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                pass
    m = _ISO_DATE_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = _FR_SLASH_RE.search(text)
    if m:
        try:
            y = int(m.group(3))
            if y < 100:
                y += 2000
            return date(y, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # Last resort: day + month without a year — infer the year
    m = _FR_NOYEAR_RE.search(text)
    if m:
        return _day_month_to_date(m.group(1), m.group(2))
    return None


def _day_month_to_date(day_str, month_str):
    """Build a date from a day-number + French month name; infers the year."""
    dm = re.search(r"\d{1,2}", str(day_str or ""))
    if not dm:
        return None
    day = int(dm.group(0))
    month = _month_num(month_str)
    if not month:
        return None
    for yr in (TODAY.year, TODAY.year + 1):
        try:
            d = date(yr, month, day)
        except ValueError:
            return None
        if d >= TODAY - timedelta(days=15):
            return d
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_id(*parts) -> str:
    raw = "-".join(str(p) for p in parts if p)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def slugify(name: str) -> str:
    """ASCII slug, must stay identical to the JS slugify() in index.html
    (used for the per-institution .ics filenames)."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(name or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def clean_text(s) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def strip_html(s) -> str:
    if not s:
        return ""
    if hasattr(s, "get_text"):
        return clean_text(s.get_text(separator=" "))
    try:
        return clean_text(BeautifulSoup(str(s), "lxml").get_text(separator=" "))
    except Exception:
        return clean_text(re.sub(r"<[^>]+>", " ", str(s)))


PARIS_TZ = dateutil_tz.gettz("Europe/Paris")


def to_paris(dt):
    """If dt is timezone-aware, convert to Paris wall-clock time and drop the
    tz. Naive datetimes are returned unchanged. This is what fixes Luma —
    its API returns times in UTC; here we shift them to Paris."""
    if dt is None:
        return None
    if dt.tzinfo is not None and PARIS_TZ is not None:
        dt = dt.astimezone(PARIS_TZ)
    return dt.replace(tzinfo=None)


def parse_date(s):
    """Parse a date/datetime string into a naive Paris-local datetime.
    ISO format (YYYY-MM-DD) is parsed year-first; everything else day-first.
    Falls back to the French text parser."""
    if not s:
        return None
    txt = str(s).strip()
    if not txt:
        return None
    is_iso = bool(re.match(r"\d{4}-\d{2}-\d{2}", txt))
    try:
        return to_paris(dateparser.parse(txt, dayfirst=not is_iso, yearfirst=is_iso, fuzzy=True))
    except Exception:
        pass
    d = parse_french_date_text(txt)
    if d:
        return datetime(d.year, d.month, d.day)
    return None


_JUNK_TITLE = re.compile(
    r"^\s*(acc[eè]s rapides?|aujourd'?hui|cette semaine|ce mois|cette ann[eé]e|"
    r"agenda|programme|calendrier|r[eé]sultats?|tous les|voir tout|voir plus|"
    r"filtrer|affiner( par)?|trier( par)?|recherche[rz]?( par\b.*)?|"
    r"prochains? [eé]v[eé]nements?|[aà] venir|en ce moment|menu|"
    r"[eé]v[eé]nements?|tous les [eé]v[eé]nements?|"
    r"formulaire(\s+de\s+recherche)?|"
    r"param[eè]tres?(\s+d['’e]?\s*accessibilit[eé])?|accessibilit[eé]|"
    r"se connecter|connexion|s['’]inscrire|inscription|"
    r"newsletter|cookies?|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
    r"\d{1,2}\s+\w+\s+\d{4})\s*$",
    re.I,
)

# French cities / venues OUTSIDE the Paris region — to filter the nationwide
# CNRS-math Indico instance down to Paris-area events only.
NON_PARIS = re.compile(
    r"\b(toulouse|lyon|marseille|lille|nice|bordeaux|strasbourg|grenoble|"
    r"nantes|rennes|montpellier|nancy|amiens|caen|dijon|orl[eé]ans|"
    r"clermont|besan[çc]on|reims|rouen|metz|brest|angers|limoges|poitiers|"
    r"pau|avignon|le mans|la rochelle|perpignan|toulon|villeurbanne|"
    r"talence|frumam|upjv|braconnier|ljad|insa toulouse|insa lyon|"
    # Sites du Muséum et partenaires Inalco hors Île-de-France
    r"menton|concarneau|dinard|eyzies|s[ée]rignan|pessac)\b",
    re.I,
)


def is_junk_title(t: str) -> bool:
    """True if the title is a navigation/UI element, not a real event."""
    t = (t or "").strip()
    if len(t) < 6:
        return True
    return bool(_JUNK_TITLE.match(t))


def make_absolute(href: str, base: str) -> str:
    if not href:
        return base
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return base.rstrip("/") + "/" + href


def in_window(d) -> bool:
    if isinstance(d, datetime):
        d = d.date()
    return d is not None and CUTOFF <= d <= HORIZON


def new_event(institution, title, d, time_str="", end_time="", location="",
              desc="", url="", speaker="", source_type="institution", image="") -> dict:
    ev = {
        "id": make_id(institution, title, str(d)),
        "title": title,
        "institution": institution,
        "discipline": detect_discipline(title, desc, institution),
        "date": d.isoformat(),
        "time": time_str,
        "end_time": end_time,
        "location": location,
        "description": desc,
        "url": url,
        "speaker": speaker,
        "source_type": source_type,
    }
    if image:
        ev["image"] = image
    return ev


# ── Indico (IHP) ──────────────────────────────────────────────────────────────

_INDICO_INTERNAL = re.compile(r"\b(r[ée]union|meeting|sign[- ]up|stage coll[èe]ge|weekly)\b", re.I)


def scrape_indico(name, base, categ, location_default, *, skip_meetings=False,
                  keep_loc=None) -> list[dict]:
    """skip_meetings : écarte les réunions internes (type Indico « meeting »).
    keep_loc : regex — pour une instance nationale, ne garder que les
    événements dont le lieu (location / room / address) y correspond."""
    print(f"→ Indico: {name}...")
    events = []
    # Sur un an d'un coup, l'export Indico ne rend qu'un sous-ensemble (IHP :
    # 287 événements au lieu de 548, IJCLab 11 au lieu de 48) : on découpe
    # l'année en tranches de 60 jours et on fusionne par id.
    results, seen_ids, failed = [], set(), 0
    start = TODAY
    while start <= HORIZON:
        stop = min(start + timedelta(days=60), HORIZON)
        url = (f"{base}/export/categ/{categ}.json"
               f"?from={start.isoformat()}&to={stop.isoformat()}&limit=300")
        data = None
        for attempt in range(1, 4):
            try:
                r = requests.get(url, headers=HEADERS, timeout=35)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                print(f"   [WARN] {start}→{stop} attempt {attempt}: {e}")
        if data is None:
            failed += 1
        for item in (data or {}).get("results", []):
            if item.get("id") not in seen_ids:
                seen_ids.add(item.get("id"))
                results.append(item)
        start = stop + timedelta(days=1)
    if not results:
        print("   [ERROR] Indico unreachable after 3 attempts")
        return events
    print(f"   API returned {len(results)} raw results"
          + (f" ({failed} tranche(s) en échec)" if failed else ""))
    for item in results:
        title = clean_text(item.get("title", ""))
        if not title or is_junk_title(title):
            continue
        raw_start = item.get("startDate", {})
        dt = parse_date(f"{raw_start.get('date', '')} {raw_start.get('time', '')}")
        if not dt or not in_window(dt.date()):
            continue
        end_time = ""
        raw_end = item.get("endDate", {})
        dt_end = parse_date(f"{raw_end.get('date', '')} {raw_end.get('time', '')}")
        if dt_end:
            end_time = dt_end.strftime("%H:%M")
        if skip_meetings and (item.get("type") == "meeting" or _INDICO_INTERNAL.search(title)):
            continue
        where = " ".join(clean_text(item.get(k, "")) for k in ("location", "room", "address"))
        if keep_loc and not keep_loc.search(where):
            continue
        location = (clean_text(item.get("location", "")) or clean_text(item.get("room", ""))
                    or location_default)
        # Indico CNRS-math is nationwide — keep only Paris-area events
        if NON_PARIS.search(location):
            continue
        desc = strip_html(item.get("description", ""))[:400]
        speakers = ", ".join(s.get("fullName", "") for s in item.get("speakers", []))[:120]
        events.append(new_event(
            name, title, dt.date(),
            time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
            end_time=end_time, location=location, desc=desc,
            url=item.get("url", base), speaker=clean_text(speakers),
        ))
    print(f"   {len(events)} events")
    return events


# ── Playwright helpers ────────────────────────────────────────────────────────

def accept_cookies(page):
    labels = ["Tout accepter", "Accepter tout", "Accepter tous les cookies",
              "J'accepte", "Accepter", "Accept all", "I accept",
              "Continuer sans accepter", "OK pour moi"]
    for label in labels:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(label), re.I))
            if btn.count() > 0:
                btn.first.click(timeout=1200)
                page.wait_for_timeout(400)
                return
        except Exception:
            pass
    for sel in ["#tarteaucitronAllAllowed", "#axeptio_btn_acceptAll",
                "[id*='accept' i]", "[class*='accept' i]"]:
        try:
            page.locator(sel).first.click(timeout=800)
            page.wait_for_timeout(300)
            return
        except Exception:
            pass


def click_load_more(page, max_clicks=30) -> int:
    """Repeatedly click 'load more' style buttons. Returns number of clicks."""
    labels = ["Voir plus", "Afficher plus", "Charger plus", "Plus d'événements",
              "Plus de résultats", "Voir tous", "Voir tout", "Load more",
              "Show more", "See more", "Suivant", "Plus"]
    clicks = 0
    for _ in range(max_clicks):
        clicked = False
        for label in labels:
            try:
                pat = re.compile(r"^\s*" + re.escape(label) + r"\s*$", re.I)
                btn = page.get_by_role("button", name=pat)
                if btn.count() == 0:
                    btn = page.get_by_role("link", name=pat)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.scroll_into_view_if_needed(timeout=2000)
                    btn.first.click(timeout=3000)
                    page.wait_for_timeout(1800)
                    clicks += 1
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            break
    if clicks:
        print(f"   clicked 'load more' {clicks}x")
    return clicks


def load_page(page, url: str, exhaustive: bool = True) -> tuple[str, str]:
    """Navigate, wait for JS, accept cookies, scroll.
    exhaustive=True  : full infinite-scroll + click every 'load more' (single-page sites).
    exhaustive=False : light scroll only (for explicitly paginated sites)."""
    # "commit" resolves as soon as the first response bytes arrive, so a slow,
    # heavy site (e.g. Collège de France) won't make goto hang on a late
    # domcontentloaded. If goto still times out, we DON'T give up — the DOM is
    # often there anyway; we wait a bit more and read it.
    try:
        page.goto(url, timeout=60000, wait_until="commit")
    except Exception as e:
        print(f"   [warn] goto {url}: {e} — continuing with partial load")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=20000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        page.wait_for_timeout(2500)
    accept_cookies(page)

    def _scroll_bottom():
        try:
            page.evaluate(
                "() => { if (document.body) window.scrollTo(0, document.body.scrollHeight); }")
        except Exception:
            pass

    def _height():
        try:
            return page.evaluate("() => document.body ? document.body.scrollHeight : 0")
        except Exception:
            return 0

    if exhaustive:
        # Infinite scroll until the page stops growing
        last_h = 0
        for _ in range(30):
            _scroll_bottom()
            page.wait_for_timeout(850)
            h = _height()
            if h == 0 or h == last_h:
                break
            last_h = h
        try:
            if click_load_more(page):
                for _ in range(12):
                    _scroll_bottom()
                    page.wait_for_timeout(700)
        except Exception:
            pass
    else:
        for _ in range(5):
            _scroll_bottom()
            page.wait_for_timeout(550)

    try:
        page.evaluate("() => window.scrollTo(0, 0)")
    except Exception:
        pass
    page.wait_for_timeout(300)
    try:
        return page.content(), page.title()
    except Exception:
        return "", ""


def is_error_page(title: str, html: str) -> bool:
    t = title.lower()
    return (len(html) < 1500
            or "404" in t or "403" in t
            or "non trouvée" in t or "not found" in t
            or "forbidden" in t or "erreur" in t)


# ── JSON-LD + universal HTML extractor ────────────────────────────────────────

def extract_jsonld_events(soup) -> list[dict]:
    out = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "{}")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and "@graph" in data:
            items = data["@graph"]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type", "")
            t = t if isinstance(t, str) else " ".join(t)
            if "Event" in t:
                out.append(item)
    return out


def _find_title(container):
    el = container.find(["h1", "h2", "h3", "h4", "h5"])
    if not el:
        el = container.select_one("[class*='title' i], [class*='name' i], strong, b")
    return el


def _find_speaker(container):
    el = container.select_one(
        "[class*='author' i], [class*='speaker' i], [class*='professeur' i], "
        "[class*='professor' i], [class*='intervenant' i]"
    )
    return clean_text(el.get_text()) if el else ""


def _best_link(container, title_el=None) -> str:
    """Find the most likely event-detail link: prefer the link on the title,
    then the link wrapping the card, then the first real link."""
    if title_el is not None:
        a = title_el.find("a", href=True) or title_el.find_parent("a", href=True)
        if a:
            href = (a.get("href") or "").strip()
            if href and href not in ("#", "/"):
                return href
    for a in container.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if (href and href not in ("#", "/")
                and not href.lower().startswith(("javascript:", "mailto:", "tel:"))):
            return href
    return ""


def extract_events_universal(html, institution, location_default, base_url) -> list[dict]:
    """4-strategy extractor: JSON-LD, <time datetime>, data-* attrs, French text."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    events, seen = [], set()

    def add(ev):
        if not ev or not ev["title"] or is_junk_title(ev["title"]):
            return
        key = (ev["title"][:50].lower(), ev["date"])
        if key not in seen:
            seen.add(key)
            events.append(ev)

    # Strategy 1: JSON-LD
    for item in extract_jsonld_events(soup):
        title = clean_text(item.get("name", ""))
        dt = parse_date(item.get("startDate") or item.get("startTime"))
        if not title or not dt or not in_window(dt.date()):
            continue
        loc = item.get("location", {})
        loc_str = (clean_text(loc.get("name", "")) if isinstance(loc, dict) else clean_text(loc)) or location_default
        add(new_event(institution, title, dt.date(),
                      time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                      location=loc_str, desc=strip_html(item.get("description", ""))[:400],
                      url=make_absolute(item.get("url", ""), base_url)))

    # Strategy 2: <time datetime>
    for time_el in soup.select("time[datetime]"):
        dt = parse_date(time_el.get("datetime", ""))
        if not dt or not in_window(dt.date()):
            continue
        container = time_el
        for _ in range(10):
            container = container.parent
            if container is None or container.name in ("body", "html"):
                break
            title_el = _find_title(container)
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 5:
                continue
            href = _best_link(container, title_el)
            desc = strip_html(container.find("p"))[:400] if container.find("p") else ""
            add(new_event(institution, title, dt.date(),
                          time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                          location=location_default, desc=desc,
                          url=make_absolute(href, base_url),
                          speaker=_find_speaker(container)))
            break

    # Strategy 3: data-* date attributes
    for sel in ["[data-date]", "[data-start-date]", "[data-event-date]",
                "[data-start]", "[data-datetime]", "[data-timestamp]"]:
        for el in soup.select(sel):
            raw = (el.get("data-date") or el.get("data-start-date") or el.get("data-event-date")
                   or el.get("data-start") or el.get("data-datetime") or el.get("data-timestamp") or "")
            if raw.isdigit():
                try:
                    dt = datetime.fromtimestamp(int(raw) / (1000 if len(raw) > 10 else 1))
                except Exception:
                    continue
            else:
                dt = parse_date(raw)
            if not dt or not in_window(dt.date()):
                continue
            container, title_el = el, None
            for _ in range(10):
                title_el = _find_title(container)
                if title_el:
                    break
                container = container.parent
                if container is None or container.name in ("body", "html"):
                    break
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 5:
                continue
            href = _best_link(container, title_el)
            add(new_event(institution, title, dt.date(),
                          time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                          location=location_default,
                          url=make_absolute(href, base_url)))

    # Strategy 4: French date text inside event-like containers
    container_sel = ("article, [class*='event' i], [class*='agenda' i], [class*='conference' i],"
                     " [class*='seminaire' i], [class*='card' i], [class*='item' i],"
                     " [class*='lecture' i], [class*='cours' i], li[class*='program' i],"
                     " div[class*='program' i], [class*='teaser' i], [class*='evenement' i],"
                     " [class*='manifestation' i], [class*='actualite' i], li[class*='result' i],"
                     # Dauphine (TYPO3) : chaque événement est une ligne
                     # Bootstrap nue dans .news-list — aucune classe parlante,
                     # seul le lien porte 'card_link', et il n'a pas la date.
                     " .news-list > .row")
    for container in soup.select(container_sel):
        d = parse_french_date_text(container.get_text(" ", strip=True))
        if not d or not in_window(d):
            continue
        if container.find_parent(["nav", "header", "footer"]):
            continue
        title_el = _find_title(container)
        if not title_el:
            continue
        title = clean_text(title_el.get_text())
        if not title or is_junk_title(title):
            continue
        href = _best_link(container, title_el)
        desc = strip_html(container.find("p"))[:400] if container.find("p") else ""
        add(new_event(institution, title, d,
                      location=location_default, desc=desc,
                      url=make_absolute(href, base_url),
                      speaker=_find_speaker(container)))

    if len(events) < 3:
        from collections import Counter
        cls = Counter()
        for el in soup.find_all(class_=True):
            for c in el.get("class", []):
                cls[c] += 1
        top = ", ".join(f"{c}x{n}" for c, n in cls.most_common(22))
        print(f"   [DEBUG] {institution}: jsonld={len(extract_jsonld_events(soup))} "
              f"time[datetime]={len(soup.select('time[datetime]'))} "
              f"articles={len(soup.select('article'))} links={len(soup.select('a[href]'))}")
        print(f"   [CLASSES] {top}")
    return events


# ── Captured JSON parsing ─────────────────────────────────────────────────────

def capture_json(response, store):
    """Playwright response handler — stores (url, json_body) tuples."""
    try:
        ct = response.headers.get("content-type", "").lower()
        if response.status == 200 and "json" in ct:
            store.append((response.url, response.json()))
    except Exception:
        pass


def _deep_find_event_lists(obj, depth=0):
    """Recursively find lists of dicts that look like event lists."""
    found = []
    if depth > 4:
        return found
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            found.append(obj)
        for x in obj[:50]:
            found.extend(_deep_find_event_lists(x, depth + 1))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.extend(_deep_find_event_lists(v, depth + 1))
    return found


def events_from_captured_json(captured, institution, location, base_url) -> list[dict]:
    """Extract events from captured JSON API responses."""
    events, seen = [], set()
    for _url, body in captured:
        for lst in _deep_find_event_lists(body):
            for item in lst:
                if not isinstance(item, dict):
                    continue
                inner = item.get("event") if isinstance(item.get("event"), dict) else item
                title = clean_text(
                    inner.get("title") or inner.get("titre") or inner.get("name")
                    or inner.get("label") or inner.get("intitule") or inner.get("summary") or ""
                )
                if not title or len(title) < 5:
                    continue
                start = (inner.get("startDate") or inner.get("start_date") or inner.get("date_debut")
                         or inner.get("date") or inner.get("dateDebut") or inner.get("start")
                         or inner.get("start_at") or inner.get("starts_at") or "")
                dt = parse_date(str(start)) if start else None
                if not dt or not in_window(dt.date()):
                    continue
                key = (title[:50].lower(), dt.date().isoformat())
                if key in seen:
                    continue
                seen.add(key)
                speaker = inner.get("speaker") or inner.get("intervenant") or inner.get("professeur") or ""
                if isinstance(inner.get("speakers"), list) and inner["speakers"]:
                    sp0 = inner["speakers"][0]
                    speaker = sp0.get("name", "") or sp0.get("fullName", "") if isinstance(sp0, dict) else ""
                url = inner.get("url") or inner.get("link") or inner.get("slug") or ""
                events.append(new_event(
                    institution, title, dt.date(),
                    time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                    location=location, desc=strip_html(inner.get("description") or inner.get("resume") or "")[:400],
                    url=make_absolute(url, base_url), speaker=clean_text(speaker),
                ))
    return events


def _is_luma_france(ev):
    """True if a Luma event dict is located in France."""
    geo = ev.get("geo_address_info") or {}
    if isinstance(geo, dict):
        country = str(geo.get("country") or geo.get("country_code") or "").strip().lower()
        if country:
            return country in ("france", "fr")
        text = " ".join(str(geo.get(k, "")) for k in
                        ("full_address", "address", "city_state", "city", "region"))
    else:
        text = str(geo)
    text = (text + " " + str(ev.get("location") or ev.get("address") or "")).lower()
    if "france" in text or "paris" in text:
        return True
    return bool(re.search(r"\b75\d{3}\b", text))


def extract_events_deep_json(obj, institution_default, source_type="institution",
                             base_url="", require_france=False,
                             _depth=0, _out=None, _seen=None):
    """Recursively walk ANY JSON structure, collecting event-like dicts.
    An 'event' = any dict with a name/title field AND a start-date field.
    require_france=True keeps only events located in France (for Luma)."""
    if _out is None:
        _out, _seen = [], set()
    if _depth > 12:
        return _out
    if isinstance(obj, list):
        for x in obj[:600]:
            extract_events_deep_json(x, institution_default, source_type, base_url,
                                     require_france, _depth + 1, _out, _seen)
    elif isinstance(obj, dict):
        ev = obj.get("event") if isinstance(obj.get("event"), dict) else obj
        name = (ev.get("name") or ev.get("title") or ev.get("titre")
                or ev.get("summary") or ev.get("label"))
        start = (ev.get("start_at") or ev.get("startDate") or ev.get("start_date")
                 or ev.get("starts_at") or ev.get("dateDebut") or ev.get("date_debut")
                 or ev.get("date"))
        if isinstance(name, str) and name.strip() and start:
            dt = parse_date(str(start))
            if dt and in_window(dt.date()):
                title = clean_text(name)
                key = (title[:50].lower(), dt.date().isoformat())
                if (not is_junk_title(title) and key not in _seen
                        and not (require_france and not _is_luma_france(ev))):
                    _seen.add(key)
                    geo = ev.get("geo_address_info") or ev.get("location") or {}
                    if isinstance(geo, dict):
                        loc = clean_text(geo.get("full_address") or geo.get("address")
                                         or geo.get("name") or geo.get("city") or "")
                    else:
                        loc = clean_text(geo)
                    api_id = ev.get("api_id") or ev.get("id") or ""
                    url = (ev.get("url") or ev.get("link") or ev.get("permalink")
                           or ev.get("canonical_url") or ev.get("path")
                           or ev.get("slug") or "")
                    if not url and api_id and source_type == "luma":
                        url = f"https://lu.ma/{api_id}"
                    hosts = obj.get("hosts") or obj.get("host_calendars") or ev.get("hosts") or []
                    inst = institution_default
                    if isinstance(hosts, list) and hosts and isinstance(hosts[0], dict):
                        inst = clean_text(hosts[0].get("name", "")) or institution_default
                    img = ""
                    price = ""
                    if source_type == "luma":
                        img = (ev.get("cover_url") or ev.get("social_image_url")
                               or (obj.get("cover_image") if isinstance(obj.get("cover_image"), str) else "")
                               or "")
                        # Prix : ticket_info contient {price: {cents, currency}, is_free}
                        ti = obj.get("ticket_info") if isinstance(obj.get("ticket_info"), dict) else {}
                        if ti.get("is_free"):
                            price = "Gratuit"
                        elif isinstance(ti.get("price"), dict):
                            cents = ti["price"].get("cents")
                            cur = (ti["price"].get("currency") or "").upper()
                            if isinstance(cents, (int, float)) and cents > 0:
                                sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(cur, cur)
                                amt = int(cents) // 100
                                price = f"{amt} {sym}".strip()
                                mx = ti.get("max_price")
                                if isinstance(mx, dict) and isinstance(mx.get("cents"), (int, float)):
                                    max_amt = int(mx["cents"]) // 100
                                    if max_amt > amt:
                                        price = f"{amt}–{max_amt} {sym}".strip()
                    ne = new_event(
                        inst, title, dt.date(),
                        time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                        location=loc or "Paris",
                        desc=strip_html(ev.get("description") or ev.get("description_short") or "")[:400],
                        url=make_absolute(url, base_url or "https://lu.ma"),
                        source_type=source_type, image=img,
                    )
                    if price:
                        ne["price"] = price
                    _out.append(ne)
        for v in obj.values():
            extract_events_deep_json(v, institution_default, source_type, base_url,
                                     require_france, _depth + 1, _out, _seen)
    return _out


# ── Paginated HTML scraper (CdF, EHESS, ENS, Sciences Po, Sorbonne) ───────────

def scrape_paginated(browser, name, agenda_urls, max_pages=15, source_type="institution"):
    """Scrape paginated agendas, trying BOTH ?page=N and /page/N/ URL styles
    (different CMS use different pagination). agenda_urls = [(url, loc, base), ...]."""
    print(f"→ {name} (paginated)...")
    all_events, seen = [], set()
    captured = []

    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="fr-FR",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
    )
    page = ctx.new_page()
    page.on("response", lambda r: capture_json(r, captured))

    def harvest(url, location, site_base, label):
        """Load a page, extract NEW events, return their count (None on error page)."""
        html, title = load_page(page, url, exhaustive=False)
        if is_error_page(title, html):
            return None
        evs = extract_events_universal(html, name, location, site_base)
        new = 0
        for e in evs:
            k = (e["title"][:50].lower(), e["date"])
            if k not in seen:
                seen.add(k)
                all_events.append(e)
                new += 1
        print(f"   {label}: {new} new / {len(evs)} found (html={len(html)})")
        return new

    for base_url, location, site_base in agenda_urls:
        # Page 1 = bare URL
        if harvest(base_url, location, site_base, "page 1") is None:
            continue
        sep = "&" if "?" in base_url else "?"

        # Style A: ?page=N
        empty = 0
        for n in range(1, max_pages):
            r = harvest(f"{base_url}{sep}page={n}", location, site_base, f"?page={n}")
            if r is None:
                break
            empty = 0 if r else empty + 1
            if empty >= 2:
                break

        # Style B: /page/N/  (WordPress-style)
        empty = 0
        for n in range(2, max_pages):
            r = harvest(f"{base_url.rstrip('/')}/page/{n}/", location, site_base, f"/page/{n}/")
            if r is None:
                break
            empty = 0 if r else empty + 1
            if empty >= 2:
                break

    ctx.close()

    # Add events found in captured API JSON (deep recursive search)
    base0 = agenda_urls[0][2]
    api_count = 0
    for _url, body in captured:
        for e in extract_events_deep_json(body, name, "institution", base0):
            key = (e["title"][:50].lower(), e["date"])
            if key not in seen:
                seen.add(key)
                all_events.append(e)
                api_count += 1
    if api_count:
        print(f"   +{api_count} events from captured JSON API ({len(captured)} responses)")

    print(f"   ✓ Total {name}: {len(all_events)} events")
    return all_events


# Full browser-like headers. The Collège de France site sits behind BunnyCDN,
# which answers minimal-header requests with 403 / hangs, but serves the
# CDN-cached HTML normally when the request looks like a real Chrome navigation.
CDF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def scrape_college_de_france(browser=None):
    """Collège de France — Drupal 11 site behind BunnyCDN.

    Pure `requests` (no Playwright): the agenda is fully server-rendered, so
    headless Chromium added nothing but trouble — it hung on the slow *uncached*
    ?page=N URLs (the 45 s timeouts we kept hitting). The bare /fr/agenda is
    CDN-cached and always fast; paginated pages are best-effort (retried, but we
    tolerate timeouts and keep whatever loaded). Combined with the carry-forward
    in main(), a partial run never wipes the source. `browser` is accepted but
    ignored so the call site in main() stays unchanged.
    """
    print("→ Collège de France (requests)...")
    BASE = "https://www.college-de-france.fr"
    LOC_DEFAULT = "Collège de France, 11 place Marcelin-Berthelot, Paris 5e"
    sess = requests.Session()
    sess.headers.update(CDF_HEADERS)

    deadline = time.monotonic() + 150  # hard wall-clock budget for the whole source
    events, seen = [], set()

    def fetch(url, tries=2, timeout=30):
        for attempt in range(1, tries + 1):
            if time.monotonic() > deadline:
                return None
            try:
                r = sess.get(url, timeout=timeout)
                if r.status_code == 200 and r.text:
                    return r.text
                print(f"   [warn] {url} -> HTTP {r.status_code}")
            except Exception as e:
                print(f"   [warn] {url}: {type(e).__name__} (try {attempt}/{tries})")
        return None

    def parse_cards(html):
        # Python's built-in parser (not lxml): the runner sometimes gets a
        # slow/partial page from BunnyCDN with malformed attributes that crash
        # lxml's strict SAX parser (_getNsTag "not enough values to unpack").
        # html.parser is lenient and never raises on that.
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            print(f"   [warn] parse error: {type(e).__name__}")
            return 0
        added = 0
        for node in soup.select(".node--type-event"):
            link = node.select_one("a.card-event[href]") or node.find("a", href=True)
            href = link.get("href", "") if link else ""
            title_el = node.select_one(".card-event__title")
            title = clean_text(title_el.get_text()) if title_el else ""
            if not title or is_junk_title(title):
                continue
            # Date + time: prefer the ISO <time datetime> (UTC -> Paris via parse_date)
            d, time_str = None, ""
            t_el = node.select_one("time[datetime]")
            if t_el and t_el.get("datetime"):
                dt = parse_date(t_el["datetime"])
                if dt:
                    d = dt.date()
                    if dt.hour or dt.minute:
                        time_str = dt.strftime("%H:%M")
            if d is None:
                date_el = node.select_one(".card-event__date")
                if date_el:
                    d = parse_french_date_text(date_el.get_text(" ", strip=True))
            if d is None or d < CUTOFF or d > HORIZON:
                continue
            key = href or f"{title[:60].lower()}|{d.isoformat()}"
            if key in seen:
                continue
            seen.add(key)
            place_el = node.select_one(".card-event__place")
            speaker_el = node.select_one(".card-event__main-speaker")
            cycle_el = node.select_one(".card-event__cycle")
            type_el = node.select_one(".card-event__type")
            desc = " · ".join(x for x in [
                clean_text(type_el.get_text()) if type_el else "",
                clean_text(cycle_el.get_text()) if cycle_el else "",
            ] if x)
            events.append(new_event(
                "Collège de France", title, d, time_str=time_str,
                location=clean_text(place_el.get_text()) if place_el else LOC_DEFAULT,
                desc=desc,
                speaker=clean_text(speaker_el.get_text()) if speaker_el else "",
                url=make_absolute(href, BASE),
            ))
            added += 1
        return added

    # Only /fr/agenda: it is CDN-cached and carries every upcoming event.
    # (/fr/enseignements/agenda just 403s / times out and adds nothing.)
    for base_url in (f"{BASE}/fr/agenda",):
        html = fetch(base_url, tries=4, timeout=40)   # slow from datacenter IPs but worth waiting
        if not html:
            print(f"   [warn] {base_url} unreachable")
            continue
        n0 = parse_cards(html)
        print(f"   page 0 ({base_url}): +{n0}  ·  total {len(events)}")
        misses = 0
        for p in range(1, 12):
            if time.monotonic() > deadline:
                print("   [info] time budget reached — stopping pagination")
                break
            html = fetch(f"{base_url}?page={p}", tries=2, timeout=30)
            if not html:
                misses += 1
                if misses >= 3:
                    break
                continue
            added = parse_cards(html)
            print(f"   ?page={p}: +{added}  ·  total {len(events)}")
            if added == 0:
                misses += 1
                if misses >= 2:
                    break
            else:
                misses = 0

    print(f"   ✓ Total Collège de France: {len(events)} events")
    return events


def scrape_ehess(browser):
    """Dedicated EHESS parser — events are .jnews-event-card elements
    (.jnews-event-title for the title, .chiffre-cle + .month for the date)."""
    print("→ EHESS (dedicated parser)...")
    events, seen = [], set()
    BASE = "https://www.ehess.fr"
    LOC = "EHESS, 54 boulevard Raspail, Paris 6e"

    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="fr-FR",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    )
    page = ctx.new_page()
    html, _ = load_page(page, "https://www.ehess.fr/jcms/kmo_28682/fr/agenda-de-l-ehess")
    ctx.close()

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(".jnews-event-card")
    print(f"   found {len(cards)} .jnews-event-card")
    if cards:
        print(f"   [SAMPLE CARD] {clean_text(str(cards[0]))[:650]}")

    stats = {"no_title": 0, "no_date": 0, "past": 0, "too_far": 0, "kept": 0}
    for card in cards:
        title_el = card.select_one(".jnews-event-title")
        title = clean_text(title_el.get_text()) if title_el else ""
        if not title or is_junk_title(title):
            stats["no_title"] += 1
            continue
        # Date: structured day + month first, free-text fallback
        d = None
        day_el = card.select_one(".chiffre-cle")
        month_el = card.select_one(".month")
        if day_el and month_el:
            d = _day_month_to_date(day_el.get_text(), month_el.get_text())
        if not d:
            d = parse_french_date_text(card.get_text(" ", strip=True))
        if not d:
            stats["no_date"] += 1
            continue
        if d < CUTOFF:
            stats["past"] += 1
            continue
        if d > HORIZON:
            stats["too_far"] += 1
            continue
        # Time
        time_str = ""
        hour_el = card.select_one(".hour")
        if hour_el:
            m = re.search(r"(\d{1,2})\s*[hH:]\s*(\d{2})?", hour_el.get_text())
            if m:
                time_str = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
        # EHESS cards are JS-clickable: the URL is in data-jalios-url, not <a href>
        href = card.get("data-jalios-url", "")
        if not href:
            link = card.find("a", href=True)
            href = link.get("href", "") if link else ""
        key = (title[:60].lower(), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        stats["kept"] += 1
        events.append(new_event("EHESS", title, d, time_str=time_str,
                                location=LOC, url=make_absolute(href, BASE)))
    print(f"   stats: {stats}")
    print(f"   ✓ Total EHESS: {len(events)} events")
    return events


def scrape_ens(browser):
    return scrape_paginated(browser, "ENS Paris", [
        ("https://www.ens.psl.eu/agenda",
         "ENS, 45 rue d'Ulm, Paris 5e",
         "https://www.ens.psl.eu"),
    ], max_pages=20)


def scrape_sciences_po(browser):
    return scrape_paginated(browser, "Sciences Po", [
        ("https://www.sciencespo.fr/fr/evenements/",
         "Sciences Po, 27 rue Saint-Guillaume, Paris 7e",
         "https://www.sciencespo.fr"),
    ], max_pages=15)


def scrape_sorbonne(browser):
    """Dedicated Sorbonne parser — events are .thumbnail[role=article] cards,
    paginated with ?page=N (Drupal style)."""
    print("→ Sorbonne Université (dedicated parser)...")
    events, seen = [], set()
    BASE = "https://www.sorbonne-universite.fr"
    LOC = "Sorbonne Université, Paris"

    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="fr-FR",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    )
    page = ctx.new_page()
    sample_dumped = False

    for page_num in range(0, 12):
        url = ("https://www.sorbonne-universite.fr/evenements" if page_num == 0
               else f"https://www.sorbonne-universite.fr/evenements?page={page_num}")
        html, title = load_page(page, url, exhaustive=False)
        if is_error_page(title, html):
            break
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div.thumbnail[role='article'], div.thumbnail")

        # Dump one card (without <img>, which would bury the structure)
        if not sample_dumped and cards:
            s = BeautifulSoup(str(cards[0]), "lxml")
            for img in s.find_all("img"):
                img.decompose()
            print(f"   [SAMPLE] {clean_text(str(s))[:900]}")
            sample_dumped = True

        page_new = 0
        for card in cards:
            title_el = card.select_one(".thumbnail__title")
            t = clean_text(title_el.get_text()) if title_el else ""
            if not t or is_junk_title(t):
                continue
            date_el = card.select_one(".thumbnail__date")
            d = parse_french_date_text(date_el.get_text()) if date_el else None
            if not d:
                d = parse_french_date_text(card.get_text(" ", strip=True))
            if not d or not in_window(d):
                continue
            link = card.select_one(".thumbnail__title a") or card.find("a", href=True)
            href = link.get("href", "") if link else ""
            key = (t[:60].lower(), d.isoformat())
            if key in seen:
                continue
            seen.add(key)
            page_new += 1
            events.append(new_event("Sorbonne Université", t, d,
                                    location=LOC, url=make_absolute(href, BASE)))
        print(f"   page {page_num}: {page_new} new ({len(cards)} cards)")
        if page_num > 0 and page_new == 0:
            break

    ctx.close()
    print(f"   ✓ Total Sorbonne: {len(events)} events")
    return events


def scrape_dauphine(browser):
    return scrape_paginated(browser, "Université Paris Dauphine", [
        ("https://dauphine.psl.eu/dauphine/media-et-communication/evenements/evenements-a-venir",
         "Université Paris Dauphine, Place du Maréchal de Lattre de Tassigny, Paris 16e",
         "https://dauphine.psl.eu"),
    ], max_pages=15)


def scrape_pse(browser):
    return scrape_paginated(browser, "Paris School of Economics", [
        ("https://www.parisschoolofeconomics.eu/evenements/",
         "Paris School of Economics, 48 boulevard Jourdan, Paris 14e",
         "https://www.parisschoolofeconomics.eu"),
    ], max_pages=15)


def scrape_psl(browser):
    return scrape_paginated(browser, "Université PSL", [
        ("https://psl.eu/agenda",
         "Université PSL, 60 rue Mazarine, Paris 6e",
         "https://psl.eu"),
    ], max_pages=15)


# ── Sources « cartes » (HTML statique, sans navigateur) ───────────────────────
# Chaque site est décrit par ses sélecteurs CSS et passe par le même parseur
# _scrape_cards. Tous servent leur agenda en HTML côté serveur : requests
# suffit, ce qui garde le job GitHub rapide malgré le nombre de sources.

# Vie de campus, démarches : pas des conférences. (Les soutenances ne sont
# plus jetées : _SOUTENANCE les étiquette, le site les range à part.)
_OFF_TOPIC = re.compile(
    r"don du sang|d[ée]pistage|r[ée]paration de v[ée]los|rollerdisco|"
    r"livres en don|roadshow|welcome party|soir[ée]e internationale|"
    r"forum de rentr[ée]e|cr[ée]maill[èe]re|[ée]lections? des|"
    r"remise des dipl[ôo]mes|c[ée]r[ée]monie des docteur|contrats doctoraux|"
    r"visite street-art|jeu de piste|journ[ée]e d'accueil|webinaire d.accueil|"
    r"ateliers? de pratiques? artistiques?|assurance maladie|^exposition\b",
    re.I)

_TIME_RE = re.compile(r"(?<![\d/.-])([01]?\d|2[0-3])\s*(?:h|H|:)\s*([0-5]\d)?(?!\d)")


# Soutenances de thèse / HDR : gardées, mais kind="soutenance" → catégorie à
# part sur le site (masquées par défaut, un bouton les affiche).
_SOUTENANCE = re.compile(
    r"^(avis de )?soutenance|\bsoutenance (de|d'|publique|hdr)|\bph\.?d\.? defen[cs]e|"
    r"\bthesis defen[cs]e|habilitation [àa] diriger", re.I)


# Réservé aux membres (adhérents, bénéficiaires, élèves d'une école…) : gardé,
# mais marqué members=True → 🔒 et filtre « Accès » sur le site.
_MEMBERS_ONLY = re.compile(
    r"r[ée]serv[ée]e?s? (exclusivement |uniquement )?aux? (membres|adh[ée]rents?|b[ée]n[ée]ficiaires|"
    r"mentor[ée]s|filleul|alumni|[ée]tudiants? d[eu']|[ée]l[èe]ves? d[eu'])|"
    r"membres uniquement|adh[ée]rents uniquement|members[- ]only|sur invitation( uniquement)?\b", re.I)


def _times(text):
    """« 18h-19h30 », « 18:30 – 20:00 », « de 12h30 à 14h30 » → ('18:00', '19:30')."""
    tms = _TIME_RE.findall(re.sub(r"\s*[-–]\s*(?=\d)", " - ", text or ""))
    fmt = lambda x: f"{int(x[0]):02d}:{x[1] or '00'}"
    return (fmt(tms[0]) if tms else "", fmt(tms[1]) if len(tms) > 1 else "")


def _time_of(text) -> str:
    """'19 h', '14h30', '10:00' → 'HH:MM' ; minuit = pas d'heure."""
    m = _TIME_RE.search(text or "")
    if not m:
        return ""
    t = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    return "" if t == "00:00" else t


def _card_date(el):
    """(date, 'HH:MM') d'un élément : <time datetime> ISO d'abord, sinon texte."""
    times = ([el] if el.name == "time" else []) + el.select("time[datetime]")
    for t in times:
        raw = (t.get("datetime") or "").split("/")[0]
        if re.match(r"\d{4}-\d{2}-\d{2}", raw):
            dt = parse_date(raw)
            if dt:
                return dt.date(), (dt.strftime("%H:%M") if (dt.hour or dt.minute) else "")
    txt = el.get_text(" ", strip=True)
    # « 30 - Septembre » (Jeunes IHEDN) → « 30 Septembre »
    txt = re.sub(r"(\d{1,2})\s*-\s*([^\W\d_]{3,})", r"\1 \2", txt)
    tm = _time_of(txt)
    # « Jeudi 24 18:00 Sept. 2026 » (FMSH) : l'heure coupe « 24 … Sept. »
    txt = re.sub(r"\b\d{1,2}[:h]\d{2}\b", " ", txt)
    d = parse_french_date_text(txt)
    # « Du 20 mai au 26 sept » sans année : le début, déjà passé, serait
    # déduit en 2027 (après la fin) → événement en cours, on l'écarte.
    if d and not (_FR_DATE_RE.search(txt) or _ISO_DATE_RE.search(txt) or _FR_SLASH_RE.search(txt)):
        ms = list(_FR_NOYEAR_RE.finditer(txt))
        if len(ms) >= 2:
            d2 = _day_month_to_date(ms[1].group(1), ms[1].group(2))
            if d2 and d > d2:
                return None, ""
    if not d and len(txt) <= 80:
        # Secours seulement (notre parseur, réglé sur les sources historiques,
        # garde la main) : dateparser lit l'anglais (« 1 Feb ») et les formats
        # inattendus. Base 15 jours en arrière = même inférence d'année que
        # _day_month_to_date. Limité aux textes courts, il sur-interprète.
        # Langue auto-détectée : avec languages=["fr", …], « 1 Mar » devient
        # « mardi 1 ». On exige un n° de jour (« Sep 2026 » → faux 8 sept.).
        found = search_dates(txt, settings={
            "PREFER_DATES_FROM": "future", "DATE_ORDER": "DMY",
            "RELATIVE_BASE": datetime.combine(TODAY - timedelta(days=15), datetime.min.time())})
        d = next((dt.date() for s, dt in found or []
                  if re.search(r"(?<!\d)\d{1,2}(?!\d)", s)), None)
    return d, tm


# CIENS et CERES (ENS) envoient une mauvaise chaîne de certificats : l'ancien
# intermédiaire « GEANT OV RSA CA 4 » au lieu de « GEANT TLS RSA/ECC 1 »
# (HARICA). Les navigateurs la complètent seuls, pas Python : on ajoute ces
# deux intermédiaires officiels (crt.harica.gr) au magasin de certifi, pour
# ces hôtes seulement. La vérification TLS reste entière.
_EXTRA_CA = Path(__file__).parent / "certs" / "harica-geant-tls.pem"
_EXTRA_CA_HOSTS = ("ciens.ens.psl.eu", "ceres.ens.psl.eu")
_ca_bundle = None


def _verify_for(url):
    global _ca_bundle
    if not any(h in url for h in _EXTRA_CA_HOSTS):
        return True
    if _ca_bundle is None:
        import certifi
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False, encoding="utf-8") as f:
            f.write(Path(certifi.where()).read_text(encoding="utf-8") + "\n"
                    + _EXTRA_CA.read_text(encoding="utf-8"))
        _ca_bundle = f.name
    return _ca_bundle


def _soup(url):
    """Page → BeautifulSoup. On passe les octets bruts : BeautifulSoup lit le
    charset du <meta> (Sorbonne Nouvelle est en cp1252 sans le dire à HTTP)."""
    r = requests.get(url, headers=CDF_HEADERS, timeout=35, verify=_verify_for(url))
    r.raise_for_status()
    declared = "charset" in r.headers.get("content-type", "").lower()
    soup = BeautifulSoup(r.content, "lxml", from_encoding=r.encoding if declared else None)
    if (soup.original_encoding or "").lower() in ("iso-8859-1", "latin-1", "latin1"):
        # Comme les navigateurs (norme WHATWG) : « latin-1 » annoncé = cp1252,
        # sinon les apostrophes typographiques (’) disparaissent.
        soup = BeautifulSoup(r.content, "lxml", from_encoding="cp1252")
    return soup


def _scrape_cards(name, url, card, *, title, base, location, date=None,
                  link=None, place=None, kind=None, keep_kind=None,
                  drop_kind=None, page_url=None, max_pages=8, page_start=1,
                  one_per_title=False, time=None, drop=None, members=None,
                  speaker=None, keep_loc=None, place_only=False):
    """Parseur générique d'agenda en cartes.
    card/title/date/link/place/kind : sélecteurs CSS (relatifs à la carte).
    keep_kind / drop_kind : filtre sur le texte de `kind` (sous-chaînes).
    page_url : format '{n}' des pages suivantes ; on s'arrête dès qu'une page
    n'apporte rien de nouveau. one_per_title : un colloque sur 3 jours
    apparaît 3 fois → on garde son premier jour.
    time : sélecteur « 18:30 – 20:00 » (début + fin). drop : regex de titres
    écartés. members : regex sur le texte de la carte → accès réservé (🔒).
    speaker : sélecteur de l'orateur. keep_loc : regex que le lieu doit
    contenir (sinon carte écartée). place_only : le lieu de la carte est une
    adresse complète, pas un simple complément de `location`."""
    print(f"→ {name}...")
    events, seen, stats = [], set(), {"cards": 0, "off": 0, "kind": 0, "date": 0}
    urls = [url] + ([page_url.format(n=n) for n in range(page_start, page_start + max_pages - 1)]
                    if page_url else [])
    for u in urls:
        try:
            soup = _soup(u)
        except Exception as e:
            print(f"   [warn] {u}: {e}")
            break
        cards = soup.select(card)
        stats["cards"] += len(cards)
        new = 0
        for c in cards:
            t_el = c.select_one(title)
            t = clean_text(t_el.get_text(" ")) if t_el else ""
            if not t or is_junk_title(t):
                continue
            if _OFF_TOPIC.search(t) or (drop and drop.search(t)):
                stats["off"] += 1
                continue
            k = clean_text(c.select_one(kind).get_text(" ")) if kind and c.select_one(kind) else ""
            kl = k.lower()
            if ((keep_kind and not any(x in kl for x in keep_kind))
                    or (drop_kind and any(x in kl for x in drop_kind))):
                stats["kind"] += 1
                continue
            d_el = c.select_one(date) if date else None
            d, tm = _card_date(d_el or c)
            if not d or not in_window(d):
                stats["date"] += 1
                continue
            key = t.lower()[:60] if one_per_title else (t.lower()[:60], d.isoformat())
            if key in seen:
                continue
            seen.add(key)
            a = (c.select_one(link) if link else None) or (c if c.name == "a" else None) \
                or (t_el.find("a", href=True) if t_el else None) \
                or (t_el.find_parent("a", href=True) if t_el else None) or c.find("a", href=True)
            p = clean_text(c.select_one(place).get_text(" ")) if place and c.select_one(place) else ""
            if p and (NON_PARIS.search(p) or (keep_loc and not keep_loc.search(p))):
                continue
            end = ""
            if time and c.select_one(time):
                t0, end = _times(c.select_one(time).get_text(" "))
                tm = t0 or tm
            sp = clean_text(c.select_one(speaker).get_text(" ")) if speaker and c.select_one(speaker) else ""
            if re.match(r"(journ[ée]e|organis|colloque|s[ée]minaire|conf[ée]rence|table ronde|atelier)", sp, re.I):
                sp = ""                        # « Journée organisée par… » : pas un orateur
            events.append(new_event(
                name, t, d, time_str=tm, end_time=end,
                url=make_absolute(a.get("href", "") if a else "", base),
                location=(_where_or(p, location) if place_only else
                          f"{p} — {location}" if p and p.lower() not in location.lower() else location),
                desc=k, speaker=re.sub(r"^(Par|Avec)\s+", "", sp)[:160]))
            if members and members.search(c.get_text(" ")):
                events[-1]["members"] = True
            new += 1
        if page_url and (not cards or not new):
            break
    print(f"   stats: {stats}")
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


def scrape_paris_cite():
    # All-in-One Event Calendar : ~12 événements par vue, pages via ?ai1ec=…
    return _scrape_cards(
        "Université Paris Cité", "https://u-paris.fr/agenda/", ".ai1ec-univ-event",
        title=".ai1ec-event-title", date=".ai1ec-event-date", place=".ai1ec-event-location",
        base="https://u-paris.fr",
        location="Université Paris Cité, 85 boulevard Saint-Germain, Paris 6e",
        page_url="https://u-paris.fr/agenda/?ai1ec=action~agenda|page_offset~{n}", max_pages=6)


def scrape_cnam():
    return _scrape_cards(
        "Cnam", "https://www.cnam.fr/agenda", "li.page-agenda__resultats",
        title="h3", date="time", base="https://www.cnam.fr",
        location="Cnam, 292 rue Saint-Martin, Paris 3e")


def scrape_mnhn():
    # L'agenda mêle expos, ateliers enfants et visites : on garde la parole.
    return _scrape_cards(
        "Muséum national d'Histoire naturelle", "https://www.mnhn.fr/fr/l-agenda-du-museum",
        ".mt-tuile", title=".mt-tuile__title", date=".field--name-field-dates-text",
        kind=".mt-tuile-category", keep_kind=("conférence", "rencontre", "colloque", "débat", "table ronde"),
        place=".field--name-extra-field-place-name", base="https://www.mnhn.fr",
        location="Muséum national d'Histoire naturelle, 57 rue Cuvier, Paris 5e",
        page_url="https://www.mnhn.fr/fr/l-agenda-du-museum?page={n}", max_pages=8)


def scrape_bnf():
    # Filtre « Conférences » de l'agenda (quoi=2585), 8 par page.
    u = "https://www.bnf.fr/fr/agenda?quoi%5B0%5D=2585"
    return _scrape_cards(
        "BnF", u, "article.blockEvent", title="h3", date="time",
        kind=".cycle-event", place=".etiquette_rectangular.white", base="https://www.bnf.fr",
        location="Bibliothèque nationale de France, Paris",
        page_url=u + "&page={n}", max_pages=10)


def scrape_pasteur():
    return _scrape_cards(
        "Institut Pasteur", "https://research.pasteur.fr/en/events/", ".timeline .item",
        title="h3", date=".atc_date_start", place=".location",
        kind=".label", base="https://research.pasteur.fr",
        location="Institut Pasteur, 25-28 rue du Docteur Roux, Paris 15e")


def scrape_curie():
    # Liste triée par date décroissante : la 1re page contient tout le futur.
    return _scrape_cards(
        "Institut Curie", "https://curie.fr/evenements-scientifiques",
        'li:has(a[href^="/evenements-scientifiques/"])',
        title='a[href^="/evenements-scientifiques/"]', date="div.mt-4", kind="span",
        base="https://curie.fr", location="Institut Curie, 26 rue d'Ulm, Paris 5e")


def scrape_institut_cerveau():
    return _scrape_cards(
        "Institut du Cerveau", "https://institutducerveau.org/agenda", ".card-event",
        title=".card-event-title", date=".card-event-date", kind=".card-event-category",
        base="https://institutducerveau.org",
        location="Institut du Cerveau, 47 boulevard de l'Hôpital, Paris 13e",
        page_url="https://institutducerveau.org/agenda?page={n}", max_pages=8)


def scrape_inalco():
    return _scrape_cards(
        "Inalco", "https://www.inalco.fr/agenda", "article.inalco-card--event",
        title=".inalco-link--card", date="time", place=".inalco-event-location__content",
        base="https://www.inalco.fr",
        location="Inalco, 65 rue des Grands Moulins, Paris 13e",
        page_url="https://www.inalco.fr/agenda?page={n}", max_pages=10)


def scrape_ephe():
    return _scrape_cards(
        "EPHE", "https://www.ephe.psl.eu/agenda", "article.article-event",
        title="h3", date=".teaser-txt__date", kind=".teaser-txt__chapo",
        base="https://www.ephe.psl.eu", location="EPHE, 4-14 rue Ferrus, Paris 14e")


def scrape_bernardins():
    # Webflow : jour + mois abrégé anglais (« 30 Sep »), sans année.
    return _scrape_cards(
        "Collège des Bernardins", "https://www.collegedesbernardins.fr/agenda",
        ".item-agenda", title="h2", date=".tag-date-wrapper", kind=".tag-vignette-agenda-v2",
        base="https://www.collegedesbernardins.fr",
        location="Collège des Bernardins, 20 rue de Poissy, Paris 5e")


def scrape_academie_sciences():
    return _scrape_cards(
        "Académie des sciences", "https://www.academie-sciences.fr/events", ".NodeEventTeaser",
        title=".NodeEventTeaser-title", date="time", kind=".NodeEventTeaser-type",
        place=".NodeEventTeaser-location", base="https://www.academie-sciences.fr",
        location="Académie des sciences, 23 quai de Conti, Paris 6e",
        page_url="https://www.academie-sciences.fr/events?page={n}", max_pages=5)


def scrape_cite_sciences():
    # « Ma première conférence » et « Adolesciences » visent les scolaires.
    return _scrape_cards(
        "Cité des sciences",
        "https://www.cite-sciences.fr/fr/au-programme/activites-spectacles/conferences",
        ".BlocContenuSdL", title=".titre", date=".date", kind=".sousTitre",
        drop_kind=("première conférence", "adolesciences"),
        base="https://www.cite-sciences.fr",
        location="Cité des sciences et de l'industrie, 30 avenue Corentin-Cariou, Paris 19e")


def scrape_sorbonne_nouvelle():
    # Une page par année (« Colloques 2026 ») liée depuis la page d'accueil
    # des colloques ; on suit celles de l'année en cours et de la suivante.
    base = "https://www.sorbonne-nouvelle.fr"
    loc = "Université Sorbonne Nouvelle, 8 avenue de Saint-Mandé, Paris 12e"
    pages = ["https://www.sorbonne-nouvelle.fr/conferences-scientifiques-de-la-sorbonne-nouvelle-60950.kjsp?RH=1236178100008"]
    try:
        soup = _soup(base + "/colloques-journees-d-etudes-de-la-sorbonne-nouvelle-23462.kjsp?RH=1236178100008")
        years = (str(TODAY.year), str(TODAY.year + 1))
        pages += [make_absolute(a["href"], base) for a in soup.find_all("a", href=True)
                  if re.search(r"colloques", a["href"]) and any(y in a.get_text() for y in years)]
    except Exception as e:
        print(f"   [warn] Sorbonne Nouvelle index: {e}")
    out = []
    for u in dict.fromkeys(pages):
        out += _scrape_cards("Université Sorbonne Nouvelle", u, "ul.liste-objets li",
                             title="a", date=".date-liste", base=base, location=loc)
    return out


def scrape_paris8():
    # Pas d'agenda central : la frise de la page d'accueil couvre ~1 mois,
    # le report quotidien (carry-forward) fait le reste.
    return _scrape_cards(
        "Université Paris 8", "https://www.univ-paris8.fr", ".cd-timeline-block",
        title="h3", date=".cd-date", base="https://www.univ-paris8.fr/",
        location="Université Paris 8, 2 rue de la Liberté, Saint-Denis",
        one_per_title=True)


def scrape_nanterre():
    # Export iCal natif de l'agenda (Kosmos) sur un an glissant.
    name = "Université Paris Nanterre"
    print(f"→ {name} (iCal)...")
    fmt = lambda d: d.strftime("%d%%2F%m%%2F%Y")
    u = ("https://www.parisnanterre.fr/servlet/com.kosmos.agenda.export.ExportAgendaServlet"
         f"?DTSTART={fmt(TODAY)}&DTEND={fmt(HORIZON)}&THEMATIQUE=&CATEGORIE=&LIEU="
         "&CODE_RUBRIQUE=1713186750251&CODE_RATTACHEMENT=&EXT=agenda")
    r = requests.get(u, headers=CDF_HEADERS, timeout=35)
    r.raise_for_status()
    events = []
    for v in icalendar.Calendar.from_ical(r.content).walk("VEVENT"):
        t = clean_text(v.get("SUMMARY"))
        start = v.decoded("DTSTART", None)
        if start is None:
            continue
        # DTSTART en UTC (…Z) → heure de Paris ; un jour entier reste une date
        dt = to_paris(start) if isinstance(start, datetime) else datetime.combine(start, datetime.min.time())
        if not t or not in_window(dt.date()) or _OFF_TOPIC.search(t):
            continue
        loc = clean_text(v.get("LOCATION"))
        events.append(new_event(
            name, t, dt.date(), time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
            location=f"{loc} — Université Paris Nanterre, 200 avenue de la République, Nanterre"
            if loc else "Université Paris Nanterre, 200 avenue de la République, Nanterre",
            url=str(v.get("URL") or "https://www.parisnanterre.fr/agenda"),
            desc=clean_text(v.get("DESCRIPTION"))[:400]))
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


# ── Universités & lieux de recherche (ajout 2) ────────────────────────────────

def scrape_paris1():
    # Agenda général + agenda de la recherche : même thème Drupal (article.event)
    name, base = "Université Paris 1 Panthéon-Sorbonne", "https://www.pantheonsorbonne.fr"
    loc = "Université Paris 1 Panthéon-Sorbonne, 12 place du Panthéon, Paris 5e"
    out = []
    for site in (base, "https://recherche.pantheonsorbonne.fr"):
        out += _scrape_cards(name, site + "/evenements", "article.event", title="h2.title",
                             date=".date-style", kind=".categ-style", base=base, location=loc,
                             page_url=site + "/evenements?page={n}", max_pages=6)
    return out


def scrape_assas():
    return _scrape_cards(
        "Université Paris-Panthéon-Assas", "https://www.assas-universite.fr/fr/evenements",
        ".liste__evenements .event", title="h3", kind=".type__evenement", place=".adresse",
        base="https://www.assas-universite.fr",
        location="Université Paris-Panthéon-Assas, 92 rue d'Assas, Paris 6e",
        page_url="https://www.assas-universite.fr/fr/evenements?page={n}", max_pages=6)


def scrape_paris_saclay():
    return _scrape_cards(
        "Université Paris-Saclay", "https://www.universite-paris-saclay.fr/evenements", "article.thumbnail",
        title="h3", date=".thumbnail__info__date", place=".thumbnail__info__place",
        base="https://www.universite-paris-saclay.fr",
        location="Université Paris-Saclay, Gif-sur-Yvette",
        page_url="https://www.universite-paris-saclay.fr/evenements?page={n}", max_pages=6)


def scrape_condorcet():
    p = ("https://www.campus-condorcet.fr/agenda?l=0&beanKey=agendaSearchParam&&site=ACCUEIL"
         "&dateAgenda=true&onlyAgenda=true&s=MAJ_EVENT_ASC&limit=10&page={n}")
    return _scrape_cards(
        "Campus Condorcet", "https://www.campus-condorcet.fr/agenda", "li.avec_vignette",
        title="a.item-title__element_title", date=".date_agenda", kind=".date_agenda_typeEvenement",
        base="https://www.campus-condorcet.fr",
        location="Campus Condorcet, 8 cours des Humanités, Aubervilliers",
        page_url=p, page_start=2, max_pages=8)


def scrape_iea():
    """Institut d'études avancées : chaque ligne est un lien « 24 Sep 2026, Titre »."""
    name = "Institut d'études avancées de Paris"
    print(f"→ {name}...")
    base = "https://www.paris-iea.fr"
    events = []
    for a in _soup(base + "/fr/evenements").select("a:has(> span.dates)"):
        out_of_town = a.select_one(".infos-emplacement-event")
        if out_of_town and "hors les murs" in out_of_town.get_text().lower():
            continue                              # colloques de fellows à l'étranger
        d = parse_french_date_text(a.select_one("span.dates").get_text(" "))
        for x in a.select("span.dates, .infos-emplacement-event"):
            x.extract()
        title = clean_text(a.get_text(" "))
        if not d or not in_window(d) or not title or is_junk_title(title):
            continue
        events.append(new_event(name, title, d, url=make_absolute(a.get("href", ""), base),
                                location="Institut d'études avancées de Paris, 17 quai d'Anjou, Paris 4e"))
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


def scrape_fmsh():
    return _scrape_cards(
        "Fondation Maison des Sciences de l'Homme", "https://www.fmsh.fr/agenda",
        "article.node--event.node--view-mode--search-item", title="h2, h3", date=".dates, .date",
        kind=".field_type", link="a[href*='/agenda/']",
        base="https://www.fmsh.fr", location="FMSH, 54 boulevard Raspail, Paris 6e",
        page_url="https://www.fmsh.fr/agenda?page={n}", max_pages=5)


def scrape_quai_branly():
    base = "https://www.quaibranly.fr"
    out = []
    for path in ("/fr/recherche-scientifique/activites/colloques-et-enseignements/conferences-et-colloques",
                 "/fr/expositions-evenements/au-musee/rendez-vous-du-salon-de-lecture-jacques-kerchache"):
        out += _scrape_cards(
            "Musée du quai Branly", base + path, "article.push, article.push-big", title="h3", date=".date",
            kind=".categories", link="a.related-event", base=base,
            location="Musée du quai Branly – Jacques Chirac, 37 quai Branly, Paris 7e")
    return out


# ── Indico des labos (même code que l'IHP) ────────────────────────────────────

# Lieux d'Île-de-France, pour réduire une instance nationale à la région
_IDF_RE = re.compile(
    r"\b(paris|lpnhe|apc|jussieu|ijclab|orsay|saclay|palaiseau|ihp|henri poincar[ée]|"
    r"meudon|observatoire|condorcet|aubervilliers|gif|bures|villejuif|cr[ée]teil|"
    r"nanterre|saint-denis|versailles|cergy|[ée]vry|marne-la-vall[ée]e|champs-sur-marne)\b"
    # + codes postaux franciliens, à la française (« 75016 », « 94270 Le
    # Kremlin-Bicêtre ») — pas un ZIP américain après l'État (« CA 92697 »).
    r"|(?<!(?-i:[A-Z][A-Z]) )\b(?:75|77|78|91|92|93|94|95)\d{3}\b(?=\s+[^\W\d_]|\s*$)", re.I)


def scrape_ijclab():
    return scrape_indico("IJCLab", "https://indico.ijclab.in2p3.fr", "0",
                         "IJCLab, 15 rue Georges Clemenceau, Orsay", skip_meetings=True)


def scrape_in2p3_paris():
    # Instance nationale : on ne garde que LPNHE, APC & co en Île-de-France.
    return scrape_indico("IN2P3", "https://indico.in2p3.fr", "0",
                         "LPNHE, 4 place Jussieu, Paris 5e", skip_meetings=True, keep_loc=_IDF_RE)


def scrape_observatoire():
    return scrape_indico("Observatoire de Paris", "https://indico.obspm.fr", "0",
                         "Observatoire de Paris, 61 avenue de l'Observatoire, Paris 14e",
                         skip_meetings=True)


# ── Sciencesconf.org (colloques CNRS / universités) ───────────────────────────

def _range_start(text):
    """« 23-25 sept. 2026 », « 28 sept.-1 oct. 2026 » → date de début."""
    end = parse_french_date_text(text)
    m = re.match(r"\s*(\d{1,2})(?:er)?\s*([^\d\s-][^-]*?)?\s*(\d{4})?\s*-", text or "")
    if not end or not m:
        return end
    month = _month_num(m.group(2)) if m.group(2) else end.month
    year = int(m.group(3)) if m.group(3) else end.year - (1 if month and month > end.month else 0)
    try:
        return date(year, month or end.month, int(m.group(1)))
    except ValueError:
        return end


def scrape_sciencesconf():
    """Le portail ne liste que ~200 colloques à venir (≈ 3 semaines) : le
    report quotidien fait le reste. Fiche détaillée lue pour les seuls
    colloques franciliens : adresse, site du colloque, GPS."""
    name = "Sciencesconf.org"
    print(f"→ {name}...")
    base = "https://portal.sciencesconf.org"
    events = []
    for td in _soup(base + "/browse/list").select("td.miniconf_bloc"):
        raw = clean_text(td.select_one(".miniconf_titre").get_text(" ")) if td.select_one(".miniconf_titre") else ""
        ps = [clean_text(p.get_text(" ")) for p in td.select("p.miniconf_dateou")]
        a = td.select_one("p.miniconf_voir a[href]")
        if not raw or len(ps) < 2 or not a or "France" not in ps[0] or not _IDF_RE.search(ps[0]):
            continue
        d = _range_start(ps[1])
        if not d or not in_window(d):
            continue
        title = raw.split(" : ", 1)[-1]           # « ACRONYME : Titre complet »
        fiche = make_absolute(a["href"], base)
        loc, url, desc, lat, lon = ps[0], fiche, "", None, None
        try:
            f = _soup(fiche)
            loc = clean_text(f.select_one(".conference .city").get_text(" ")) or loc
            site = f.select_one(".conference h3 a[href]")
            url = site["href"] if site else fiche
            desc = clean_text(f.select_one(".conference .description").get_text(" "))[:400] \
                if f.select_one(".conference .description") else ""
            html = str(f)
            mlat = re.search(r"\blat\s*=\s*(-?\d+\.\d+)", html)
            mlon = re.search(r"\blon\s*=\s*(-?\d+\.\d+)", html)
            lat, lon = (float(mlat.group(1)), float(mlon.group(1))) if mlat and mlon else (None, None)
        except Exception as e:
            print(f"   [warn] fiche {fiche}: {e}")
        ev = new_event(name, title, d, location=loc, desc=desc, url=url)
        ev["description"] = desc or "Colloque"
        if lat and lon:
            ev["lat"], ev["lng"], ev["geo_exact"] = lat, lon, True
        events.append(ev)
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


# ── Carrières (événements de recrutement étudiants) ───────────────────────────
# Catégorie à part sur le site (kind="carriere", masquée du fil principal,
# bouton « 💼 Carrières »). Deux sources : le portail d'événements Eightfold
# (API publique, autorisée par son robots.txt) pour les recruteurs qui s'en
# servent, et scraper/carrieres.json — liste suivie + événements vérifiés à la
# main, enrichi chaque semaine par une recherche.

CARRIERES_FILE = Path(__file__).parent / "carrieres.json"
_SECTOR_DISCIPLINE = {
    "Banque & finance": "Économie", "Conseil": "Économie", "Audit & conseil": "Économie",
    "Tech": "Sciences", "Industrie & énergie": "Sciences", "Pharma & santé": "Sciences",
    "Chimie & matériaux": "Sciences", "Recherche & ingénierie": "Sciences",
    "Spatial & défense": "Sciences", "Deeptech & IA": "Sciences",
}


def _career_event(company, sector, title, dt, *, time_str="", end_time="", location="",
                  desc="", url="", image="", kind_label="Événement recrutement"):
    ev = new_event(company, title, dt, time_str=time_str, end_time=end_time,
                   location=location, desc=f"{kind_label} · {sector}" + (f" — {desc}" if desc else ""),
                   url=url, source_type="entreprise", image=image)
    ev["kind"] = "carriere"
    ev["discipline"] = _SECTOR_DISCIPLINE.get(sector, "Autre")
    return ev


def _carrieres_config():
    try:
        return json.loads(CARRIERES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"   [warn] carrieres.json: {e}")
        return {}


def scrape_eightfold():
    """Portails Eightfold (bcg.eightfold.ai…) : tous les événements publics de
    chaque recruteur, gardés s'ils ont lieu en Île-de-France (ou en ligne avec
    Paris / France dans le titre)."""
    print("→ Carrières · Eightfold...")
    events = []
    for c in _carrieres_config().get("entreprises", []):
        if not c.get("eightfold"):
            continue
        n = 0
        for page in range(1, 25):
            try:
                r = requests.get(f"https://{c['eightfold']}.eightfold.ai/api/events/open/list",
                                 params={"domain": c["domaine"], "page": page},
                                 headers=HEADERS, timeout=25)
                r.raise_for_status()
                rows = r.json().get("plannedEventList") or []
            except Exception as e:
                print(f"   [warn] {c['nom']} p{page}: {e}")
                break
            for x in rows:
                if x.get("isCancelled") or not x.get("startTimestamp"):
                    continue
                where = clean_text(x.get("completeVenue") or x.get("venue") or x.get("address"))
                online = x.get("eventLocationType") == "virtual"
                name = clean_text(x.get("name"))
                # Lieu souvent vague (« TBC ») : le titre dit alors « BCG Paris - … »
                if not (_IDF_RE.search(f"{where} {name}")
                        or (online and re.search(r"\b(paris|france)\b", name, re.I))):
                    continue
                dt = to_paris(datetime.fromtimestamp(int(x["startTimestamp"]), dateutil_tz.UTC))
                if not in_window(dt.date()):
                    continue
                end = x.get("endTimestamp")
                end_time = to_paris(datetime.fromtimestamp(int(end), dateutil_tz.UTC)).strftime("%H:%M") if end else ""
                events.append(_career_event(
                    c["nom"], c["secteur"], name, dt.date(), time_str=dt.strftime("%H:%M"),
                    end_time=end_time,
                    location=where if _IDF_RE.search(where) else ("En ligne" if online else f"{c['nom']}, Paris"),
                    desc=strip_html(x.get("description"))[:300], url=x.get("eventLandingPage") or "",
                    image=x.get("thumbnailImage") or ""))
                n += 1
            if len(rows) < 10:
                break
        print(f"   {c['nom']}: {n}")
    print(f"   ✓ Total Carrières · Eightfold: {len(events)} events")
    return events


def scrape_carrieres_verifiees():
    """Événements vérifiés à la main dans scraper/carrieres.json."""
    print("→ Carrières · sélection vérifiée...")
    events = []
    for x in _carrieres_config().get("evenements", []):
        try:
            d = date.fromisoformat(x["date"])
        except (KeyError, ValueError):
            continue
        if not in_window(d):
            continue
        events.append(_career_event(
            x.get("entreprise", ""), x.get("secteur", ""), x.get("titre", ""), d,
            time_str=x.get("heure", ""), end_time=x.get("fin", ""), location=x.get("lieu", ""),
            desc=x.get("description", ""), url=x.get("url", ""),
            kind_label=x.get("type") or "Événement recrutement"))
        if x.get("membres"):                  # forum réservé aux élèves d'une école…
            events[-1]["members"] = True
    print(f"   ✓ Total Carrières · sélection: {len(events)} events")
    return events


# ── Associations étudiantes ───────────────────────────────────────────────────
# Même principe que les carrières : scraper/associations.json liste les
# associations suivies et les événements vérifiés à la main (celles qui ne
# publient que sur Instagram / LinkedIn / Eventbrite, illisibles par un robot) ;
# celles qui ont un agenda lisible ont en plus leur propre scraper.

ASSOCIATIONS_FILE = Path(__file__).parent / "associations.json"


def scrape_jeunes_ihedn():
    # Conférences publiques + rencontres de membres (« Popote »…, rangées
    # « Uncategorized ») : ces dernières sont gardées, marquées 🔒.
    evs = _scrape_cards(
        "Jeunes IHEDN", "https://www.jeunes-ihedn.org/evenements-a-venir/", ".wildworld_calendar_item",
        title=".wildworld_calendar_item_title", date=".wildworld_calendar_item_time",
        kind=".wildworld_calendar_item_category",
        base="https://www.jeunes-ihedn.org", location="Paris")
    for e in evs:
        e["source_type"] = "association"
        if not re.search(r"conf[ée]rence|table ronde|colloque|d[ée]bat|atelier", e.get("description", ""), re.I):
            e["members"] = True
    return evs


# Ateliers « franchisés » (fresques, DIY…) : nombreux et peu « conférence »
_MAKESENSE_SKIP = re.compile(r"fresque|\bdiy\b|ap[ée]ro|pique-nique|yoga|m[ée]ditation|c'est moi qui l'ai fait", re.I)


def scrape_makesense():
    """makesense (engagement citoyen) : conférences, débats, ateliers publics.
    La page liste ~1 semaine d'événements en JSON-LD (partout en France) ; on
    garde l'Île-de-France, le report quotidien accumule les semaines."""
    print("→ makesense...")
    base = "https://chiche.makesense.org"
    soup = _soup(base + "/events")
    # Le JSON-LD n'a pas d'URL : on la retrouve par le slug du titre, comparé
    # sans séparateurs (makesense écrit « lespoir » là où slugify met « l-espoir »)
    key = lambda s: re.sub(r"[^a-z0-9]", "", s)[:32]
    links = {}
    for a in soup.select('a[href^="/events/e/"]'):
        slug = a["href"].rstrip("/").split("/")[-1].rsplit("-", 1)[0]
        links.setdefault(key(slug), base + a["href"])
    events = []
    for it in extract_jsonld_events(soup):
        title = clean_text(it.get("name"))
        loc = it.get("location") or {}
        addr = clean_text(loc.get("address") if isinstance(loc, dict) else loc)
        d = parse_date(it.get("startDate"))
        if (not title or not d or not in_window(d.date()) or not _IDF_RE.search(addr)
                or _MAKESENSE_SKIP.search(title) or _OFF_TOPIC.search(title)):
            continue
        org = it.get("organizer")
        org = clean_text(org.get("name") if isinstance(org, dict) else org)
        desc = " — ".join(p for p in (f"Organisé par {org}" if org else "",
                                      strip_html(it.get("description"))[:300]) if p)
        ev = new_event("makesense", title, d.date(), location=addr, desc=desc,
                       url=links.get(key(slugify(title)), base + "/events"),
                       source_type="association", image=it.get("image") or "")
        if it.get("isAccessibleForFree"):
            ev["price"] = "Gratuit"
        events.append(ev)
    print(f"   ✓ Total makesense: {len(events)} events")
    return events


def scrape_associations_verifiees():
    """Événements vérifiés à la main dans scraper/associations.json."""
    print("→ Associations · sélection vérifiée...")
    try:
        cfg = json.loads(ASSOCIATIONS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"   [warn] associations.json: {e}")
        return []
    events = []
    for x in cfg.get("evenements", []):
        try:
            d = date.fromisoformat(x["date"])
        except (KeyError, ValueError):
            continue
        if not in_window(d):
            continue
        events.append(new_event(
            x.get("association", ""), x.get("titre", ""), d, time_str=x.get("heure", ""),
            end_time=x.get("fin", ""), location=x.get("lieu", ""),
            desc=" — ".join(p for p in (x.get("type"), x.get("description")) if p),
            url=x.get("url", ""), speaker=x.get("intervenants", ""),
            # Propositions du formulaire : une conférence de labo / d'université
            # y est rangée avec "source": "institution"
            source_type="institution" if x.get("source") == "institution" else "association"))
        if x.get("membres"):                  # réservé aux adhérents / bénéficiaires
            events[-1]["members"] = True
    print(f"   ✓ Total Associations · sélection: {len(events)} events")
    return events


# ── Que faire à Paris (open data Ville de Paris) ──────────────────────────────

QFAP_API = ("https://parisdata.opendatasoft.com/api/explore/v2.1/catalog/"
            "datasets/que-faire-a-paris-/records")
# Le tag « Conférence » de la Ville est large : visites guidées de musée,
# petits-déjeuners de réseau, soirées bien-être… hors sujet ici.
_QFAP_SKIP = re.compile(
    r"^visites?\b|\bvisites?[- ](guid|conf)|astrolog|petit[- ]d[ée]j|ap[ée]ro\b|"
    r"speed[- ]dating|yoga|m[ée]ditation|sophrolog|tarot|networking", re.I)


def scrape_que_faire_a_paris():
    """Agenda officiel de la Ville de Paris, tag « Conférence » : une API, pas
    de scraping. Lieu, GPS, prix et image arrivent structurés. Catégorie de
    source à part (source_type « ville ») ; l'institution affichée est le lieu
    (médiathèque, mairie…), comme l'hôte d'un événement Luma."""
    print("→ Que faire à Paris (API open data)...")
    events, offset = [], 0
    while True:
        r = requests.get(QFAP_API, timeout=35, params={
            "where": 'search(qfap_tags, "Conférence") and date_end >= now()',
            "order_by": "date_start", "limit": 100, "offset": offset})
        r.raise_for_status()
        rows = r.json().get("results", [])
        for x in rows:
            tags = x.get("qfap_tags") or ""
            title = clean_text(x.get("title"))
            if ("Enfants" in tags or not title or _OFF_TOPIC.search(title)
                    or _QFAP_SKIP.search(title)):
                continue
            # Une conférence en plusieurs séances = plusieurs « occurrences » :
            # on garde la prochaine, le scrape du lendemain passera à la suivante.
            starts = []
            for occ in (x.get("occurrences") or x.get("date_start") or "").split(";"):
                try:
                    starts.append(to_paris(datetime.fromisoformat(occ.split("_")[0])))
                except ValueError:
                    pass
            dt = next((s for s in sorted(starts) if in_window(s.date())), None)
            if not dt:
                continue
            venue = clean_text(x.get("address_name") or x.get("contact_organisation_name")) or "Ville de Paris"
            loc = ", ".join(p for p in (venue, clean_text(x.get("address_street")),
                                         clean_text(f"{x.get('address_zipcode') or ''} {x.get('address_city') or ''}")) if p)
            desc = clean_text(x.get("lead_text")) or strip_html(x.get("description"))[:400]
            ev = new_event(venue, title, dt.date(),
                           time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                           location=loc, desc=desc, url=x.get("url") or "",
                           source_type="ville", image=x.get("cover_url") or "")
            # Les tags (« Histoire », « Littérature »…) aident le classement
            ev["discipline"] = detect_discipline(title, f"{desc} {tags.replace(';', ' ')}", venue)
            if x.get("price_type") == "gratuit":
                ev["price"] = "Gratuit"
            geo = x.get("lat_lon") or {}
            if geo.get("lat") and geo.get("lon"):
                ev["lat"], ev["lng"], ev["geo_exact"] = geo["lat"], geo["lon"], True
            events.append(ev)
        if len(rows) < 100 or offset >= 900:
            break
        offset += 100
    print(f"   ✓ Total Que faire à Paris: {len(events)} events")
    return events


def _drop_city_duplicates(events):
    """Une conférence de Sciences Po ou de la BnF peut aussi être publiée sur
    Que faire à Paris : la source institutionnelle l'emporte."""
    key = lambda e: (slugify(e.get("title", ""))[:50], e.get("date"))
    known = {key(e) for e in events if e.get("source_type") != "ville"}
    out = [e for e in events if e.get("source_type") != "ville" or key(e) not in known]
    if len(out) < len(events):
        print(f"Que faire à Paris : {len(events) - len(out)} doublons d'autres sources écartés")
    return out


# ── Liste de sites proposée par kovarci (sept. 2026) ─────────────────────────

def _where_or(where, default):
    """Lieu précis s'il est situable (ville, rue, campus connu), sinon
    « salle X, <adresse par défaut> »."""
    if not where:
        return default
    if _IDF_RE.search(where) or re.search(r"\d+,?\s+(rue|av|bd|boulevard|place|quai)\b", where, re.I):
        return where
    return f"{where}, {default}"


def scrape_tribe(name, base, location, *, drop=None, source_type="institution",
                 default_kind="Séminaire", discipline=None):
    """Agenda WordPress « The Events Calendar » : son API REST publique
    (/wp-json/tribe/events/v1) rend dates, lieux et descriptions propres."""
    print(f"→ {name}...")
    events = []
    url = (f"{base}/wp-json/tribe/events/v1/events?per_page=50"
           f"&start_date={TODAY.isoformat()}&end_date={HORIZON.isoformat()}")
    for _ in range(10):
        r = requests.get(url, headers=HEADERS, timeout=35)
        r.raise_for_status()
        data = r.json()
        for it in data.get("events", []):
            title = clean_text(html_unescape(it.get("title", "")))
            if not title or is_junk_title(title) or (drop and drop.search(title)):
                continue
            dt = parse_date(it.get("start_date", ""))
            if not dt or not in_window(dt.date()):
                continue
            end = parse_date(it.get("end_date", ""))
            v = it.get("venue") if isinstance(it.get("venue"), dict) else {}
            where = clean_text(html_unescape(", ".join(
                p for p in (v.get("venue"), v.get("address"), v.get("zip"), v.get("city")) if p)))
            if where and (NON_PARIS.search(where) or (v.get("city") and not _IDF_RE.search(where))):
                continue
            cats = [clean_text(html_unescape(c.get("name", ""))) for c in it.get("categories") or []]
            # Catégories-séries seulement (pas « ANNÉE 2026-2027 », « Séances suivantes »)
            cats = [c for c in cats if re.search(
                r"s[ée]minaire|seminar|colloqu|groupe de travail|journ[ée]e|workshop|conf[ée]rence", c, re.I)]
            # Séminaires titrés du seul nom de l'orateur : « Antoine Joux »,
            # « Monica Musso (University of Bath) »
            bare = re.sub(r"\s*\(.*?\)", "", title)
            if len(bare.split()) <= 5 and not re.search(r"[:«»?!–]", title):
                speaker = title
                title = f"{cats[0] if cats else default_kind} : {title}"
            else:
                speaker = ""
            timed = not it.get("all_day") and (dt.hour or dt.minute)
            img = it.get("image") if isinstance(it.get("image"), dict) else {}
            events.append(new_event(
                name, title, dt.date(), time_str=dt.strftime("%H:%M") if timed else "",
                end_time=end.strftime("%H:%M") if timed and end and end.date() == dt.date() else "",
                location=_where_or(where, location),
                desc=strip_html(html_unescape(it.get("description", "")))[:400],
                url=it.get("url") or base, speaker=speaker, source_type=source_type,
                image=img.get("url", "")))
            if discipline:
                events[-1]["discipline"] = discipline
        url = data.get("next_rest_url")
        if not url:
            break
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


def scrape_hi_paris():
    # Centre IA & données d'IP Paris et d'HEC (Hi!ckathon, career fair, reading groups)
    return scrape_tribe("Hi! PARIS", "https://hi-paris.fr",
                        "Institut Polytechnique de Paris, Palaiseau")


def scrape_ens_maths():
    # Département de mathématiques de l'ENS : colloquium, séminaires, « Maths + IA »
    return scrape_tribe("ENS Paris", "https://www.math.ens.psl.eu",
                        "ENS, 45 rue d'Ulm, Paris 5e",
                        default_kind="Séminaire de mathématiques", discipline="Mathématiques")


_PRAIRIE_SKIP = re.compile(r"formation qualifiante", re.I)


def scrape_prairie():
    """PR[AI]RIE-PSAI (institut IA de PSL, Inria, CNRS…). Cartes WordPress :
    dates « Oct | 02 | 2026 | Oct | 04 | 2026 », puis type, titre, lieu."""
    print("→ PR[AI]RIE...")
    base = "https://www.prairie-psai.fr"
    events = []
    for c in _soup(f"{base}/agenda/").select("li.wp-block-post.evenement"):
        box = c.select_one(".wp-pattern-event-card__dates")
        parts = list(box.stripped_strings) if box else []
        dt = parse_date(" ".join(parts[:3])) if len(parts) >= 3 else None
        t_el = c.select_one("h2, h3, .wp-block-post-title")
        title = clean_text(t_el.get_text(" ")) if t_el else ""
        if not dt or not title or not in_window(dt.date()) or _PRAIRIE_SKIP.search(title):
            continue
        a = t_el.find("a", href=True) or t_el.find_parent("a", href=True)
        lines = [clean_text(x) for x in c.stripped_strings]
        place = lines[-1] if lines and lines[-1] != title else ""
        if place and NON_PARIS.search(place):
            continue
        events.append(new_event(
            "PR[AI]RIE", title, dt.date(), url=make_absolute(a["href"], base) if a else f"{base}/agenda/",
            location=_where_or(place, "PR[AI]RIE-PSAI, Paris"),
            desc=" · ".join(x for x in lines[len(parts):] if x not in (title, place, ","))[:200]))
    print(f"   ✓ Total PR[AI]RIE: {len(events)} events")
    return events


def scrape_item_ens():
    """ITEM (ENS/CNRS, manuscrits modernes) : conférences et colloques,
    triés du plus lointain au plus proche ; « Lieu : … (17h-19h00) »."""
    print("→ ITEM (ENS)...")
    base, events = "https://www.item.ens.fr", []
    for n in range(1, 5):
        url = f"{base}/conferences/" + (f"page/{n}/" if n > 1 else "")
        try:
            cards = _soup(url).select("li.loop-post-single")
        except Exception as e:
            print(f"   [warn] {url}: {e}")
            break
        dates = []
        for c in cards:
            a = c.select_one("h2 a[href]")
            t = c.select_one("time")
            d = parse_french_date_text(t.get_text(" ", strip=True)) if t else None
            if d:
                dates.append(d)
            if not a or not d or not in_window(d):
                continue
            txt = c.get_text(" ", strip=True)
            m = re.search(r"Lieu\s*:\s*(.+?)(?=\s{2}|$)", txt)
            lieu = clean_text(m.group(1))[:200] if m else ""
            if lieu and not _IDF_RE.search(lieu):
                continue                       # Dakar, Genève…
            t0, t1 = _times(lieu)              # « … Salle Dussane - (17h-19h00) »
            lieu = re.sub(r"[\s.,–-]*\(?\s*\d{1,2}\s*h.*$", "", lieu).strip(" -–.,")
            events.append(new_event(
                "ENS Paris", clean_text(a.get_text(" ")), d, time_str=t0, end_time=t1,
                location=lieu or "ITEM (ENS-CNRS), 45 rue d'Ulm, Paris 5e",
                url=make_absolute(a["href"], base), desc="ITEM — Institut des textes et manuscrits modernes"))
            if events[-1]["discipline"] == "Autre":
                events[-1]["discipline"] = "Littérature"
        if not cards or (dates and max(dates) < TODAY):
            break
    print(f"   ✓ Total ITEM: {len(events)} events")
    return events


def scrape_ciens():
    """CIENS (ENS, enjeux stratégiques) : « 25/09/2026 | titre | Lieu : … »."""
    print("→ CIENS (ENS)...")
    events = []
    for c in _soup("https://ciens.ens.psl.eu/evenements-fr/").select(".upcoming-events .event"):
        t, d_el, p, a = c.select_one("h3"), c.select_one(".dateevent"), c.select_one("p"), c.select_one("a[href]")
        d = parse_french_date_text(d_el.get_text(" ", strip=True)) if d_el else None
        if not t or not d or not in_window(d):
            continue
        lieu = re.sub(r"^\s*Lieu\s*:\s*", "", p.get_text(" ", strip=True)) if p else ""
        events.append(new_event(
            "ENS Paris", clean_text(t.get_text(" ")), d, url=a["href"] if a else "https://ciens.ens.psl.eu",
            location=_where_or(clean_text(lieu), "ENS, 45 rue d'Ulm, Paris 5e"),
            desc="CIENS — Centre interdisciplinaire sur les enjeux stratégiques"))
    print(f"   ✓ Total CIENS: {len(events)} events")
    return events


_DAY_MONTH_RE = re.compile(r"(\d{1,2})(?:er)?\s+(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|"
                           r"ao[uû]t|septembre|octobre|novembre|d[ée]cembre)", re.I)
# Même chose, mois abrégés (« 3 nov., 1er déc., 5 janv. 2027 ») et année facultative
_DAY_MONTH_ABBR_RE = re.compile(
    r"(\d{1,2})(?:er)?\s+(janv|f[ée]vr?|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[ée]c)"
    r"[a-zéû]*\.?(?:\s+(20\d\d))?", re.I)
_CERES_FIELD = r"(?=\s+(?:Salle|Lieu|Modalit|M odalit|Public|Nombre|Programme|Horaires?|Jour|Niveau|ECTS|Contact|Enseignant)[^:]{0,25}:|$)"


def scrape_ceres():
    """CERES (ENS, environnement) : une page par séminaire / cycle, avec
    « Jour et heure : Jeudi 18h-20h », « Dates : 3 décembre, 21 janvier… »."""
    print("→ CERES (ENS)...")
    base = "https://ceres.ens.psl.eu/"
    events = []
    menu = _soup(base + "-Cours-et-seminaires-")
    pages = {make_absolute(a["href"], base): clean_text(a.get_text(" "))
             for a in menu.select("a[href]")
             if re.match(r"(s[ée]minaire|cycle de conf)", clean_text(a.get_text(" ")), re.I)}
    for url, name in list(pages.items())[:25]:
        try:
            soup = _soup(url)
        except Exception as e:
            print(f"   [warn] {url}: {e}")
            continue
        txt = " ".join(soup.get_text(" ").split())
        # Pages des années passées (« Archives des enseignements / 2024-2025 »)
        # : leurs dates sans année seraient lues comme à venir.
        if re.search(r"Archives des enseignements\s*/\s*20\d\d", txt):
            continue
        m = re.search(r"Dates?\s*:\s*(.+?)" + _CERES_FIELD, txt)
        if not m or re.search(r"\bdu\s+\d", m.group(1)):
            continue                       # « du 17 sept. au 17 déc. » : hebdo, non daté
        h = re.search(r"(?:Jour et heure|Horaires?)\s*:\s*(.+?)" + _CERES_FIELD, txt)
        t0, t1 = _times(h.group(1)) if h else ("", "")
        lieu = re.search(r"(?:Lieu|Salle)\s*:\s*(.+?)" + _CERES_FIELD, txt)
        title = " ".join(re.sub(r"\d{4}\s*[-–/]\s*\d{4}", " ", name).split()).strip(" :")
        toks = list(_DAY_MONTH_ABBR_RE.finditer(m.group(1)))
        # Année universitaire : 1re date explicite, sinon titre « 2026-2027 », sinon l'actuelle
        ay = re.search(r"(20\d\d)\s*[-–/]\s*20\d\d", name)
        first = next((t for t in toks if t.group(3)), None)
        if first:
            ay = int(first.group(3)) - (_month_num(first.group(2)) < 8)
        else:
            ay = int(ay.group(1)) if ay else TODAY.year - (TODAY.month < 8)
        seen = set()
        for t in toks:
            mon = _month_num(t.group(2))
            try:
                d = date(int(t.group(3)) if t.group(3) else ay + (mon < 8), mon, int(t.group(1)))
            except (TypeError, ValueError):
                continue
            if d in seen or not in_window(d):
                continue
            seen.add(d)
            events.append(new_event(
                "ENS Paris", title, d, time_str=t0, end_time=t1,
                location=_where_or(re.split(r"\s+Programme\b", clean_text(lieu.group(1)))[0][:160]
                                   if lieu else "", "ENS, 45 rue d'Ulm, Paris 5e"),
                url=url, desc="CERES — Centre de formation sur l'environnement et la société (ENS)"))
    print(f"   ✓ Total CERES: {len(events)} events")
    return events


def scrape_hec_paris():
    """HEC Paris : séminaires de recherche (Jouy-en-Josas) et conférences à
    Paris. On écarte les webinaires et les réunions d'information Executive."""
    print("→ HEC Paris...")
    base, events = "https://www.hec.edu", []
    for n in range(0, 8):
        try:
            cards = _soup(f"{base}/fr/evenements" + (f"?page={n}" if n else "")).select(".event-item")
        except Exception as e:
            print(f"   [warn] page {n}: {e}")
            break
        new = 0
        for c in cards:
            t = c.select_one("h3")
            dd = c.select_one(".event-item__date")
            cat = clean_text(c.select_one(".event-item__cartridge").get_text(" ")) if c.select_one(".event-item__cartridge") else ""
            title = clean_text(t.get_text(" ")) if t else ""
            d = parse_french_date_text(dd.get_text(" ", strip=True)) if dd else None
            if not title or not d or not in_window(d):
                continue
            icons = {i.find("i")["class"][-1].replace("webfont-", ""): clean_text(i.get_text(" "))
                     for i in c.select(".event-item__icon") if i.find("i") and i.find("i").get("class")}
            place = icons.get("lieu", "")
            desc = clean_text(c.select_one(".event-item__description").get_text(" ")) if c.select_one(".event-item__description") else ""
            if (not place or re.search(r"webinar|webinaire|tout savoir en", f"{title} {desc}", re.I)
                    or cat == "Executive Education"):
                continue
            if re.search(r"jouy", place, re.I):
                loc = "HEC Paris, 1 rue de la Libération, Jouy-en-Josas"
            elif _IDF_RE.search(place):
                loc = place
            else:
                continue
            a = t.find_parent("a", href=True)
            sp = re.search(r"(?:Intervenant|Speaker)\s*:\s*(.+?)(?:\s+(?:Salle|Heure|Conference)\b|$)", desc)
            sp = re.sub(r"\s+Professor\s*-\s*(.+)$", r" (\1)", clean_text(sp.group(1)))[:120] if sp else ""
            if re.fullmatch(r"(tbc|tba|à venir|tbd)\.?", title, re.I) or (sp and sp.startswith(title)):
                title = f"Séminaire de recherche HEC : {sp or title}"
            events.append(new_event(
                "HEC Paris", title, d, time_str=_time_of(icons.get("heure", "")), location=loc,
                url=make_absolute(a["href"], base) if a else f"{base}/fr/evenements",
                desc=" · ".join(x for x in (cat, desc) if x)[:300], speaker=sp))
            if cat == "Faculté et Recherche":
                events[-1]["discipline"] = "Économie"
            new += 1
        if not cards or not new and n > 1:
            break
    print(f"   ✓ Total HEC Paris: {len(events)} events")
    return events


def scrape_hec_ia():
    """Association HEC IA : dîners, paper clubs, hackathons à Paris."""
    evs = _scrape_cards(
        "HEC IA", "https://hec-ia.com/en/events", '[data-slot="card"]',
        title='[data-slot="card-title"]', date='[data-slot="badge"]', base="https://hec-ia.com",
        location="Paris — lieu précisé sur la page de l'événement")
    for e in evs:
        e["source_type"] = "association"
    return evs


def _next_data(soup):
    tag = soup.find("script", id="__NEXT_DATA__")
    return json.loads(tag.string) if tag and tag.string else {}


def scrape_louvre():
    """Musée du Louvre : conférences et colloques de l'auditorium. Page Next.js
    filtrable par mois (?date=<dernier jour du mois>), données dans __NEXT_DATA__."""
    print("→ Musée du Louvre...")
    base = "https://www.louvre.fr"
    events, seen = [], set()
    m = date(TODAY.year, TODAY.month, 1)
    while m <= HORIZON:
        nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        try:
            data = _next_data(_soup(f"{base}/expositions-et-evenements/evenements-activites"
                                    f"?date={(nxt - timedelta(days=1)).isoformat()}"))
        except Exception as e:
            print(f"   [warn] {m:%Y-%m}: {e}")
            data = {}
        stack, found = [data], []
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if x.get("type") == "Event" and x.get("title"):
                    found.append(x)
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
        for x in found:
            tags = {t.get("label", "") for t in x.get("tags") or []}
            raw = clean_text(x.get("date", ""))
            dm = _DAY_MONTH_RE.search(raw)
            # « 30 septembre 2026 – 25 février 2027 » = cycle / période : écarté
            if not tags & {"Conférences", "Colloques"} or not dm or re.search(r"[–-]", raw):
                continue
            mon = _month_num(dm.group(2))
            yr = re.search(r"\b(20\d\d)\b", raw)
            yr = int(yr.group(1)) if yr else (m.year if mon >= m.month else m.year + 1)
            try:
                d = date(yr, mon, int(dm.group(1)))
            except ValueError:
                continue
            title = clean_text(x["title"])
            if (title, d) in seen or not in_window(d):
                continue
            seen.add((title, d))
            desc = strip_html(re.sub(r"<\?xml[^>]*\?>", "", (x.get("description") or {}).get("html", "")))
            sp = re.match(r"Avec\s+(.{3,120}?)(?:\.|$)", desc)
            img = ((x.get("image") or {}).get("hashes") or {}).get("w1200_16_9", "")
            events.append(new_event(
                "Musée du Louvre", title, d, desc=desc[:400],
                location="Musée du Louvre, auditorium Michel Laclotte, Paris 1er",
                url=make_absolute(((x.get("link") or {}).get("url") or ""), base),
                speaker=clean_text(sp.group(1)) if sp else "", image=img))
        m = nxt
    print(f"   ✓ Total Musée du Louvre: {len(events)} events")
    return events


def scrape_pompidou():
    """Centre Pompidou (fermé pour travaux) : rencontres et conférences hors
    les murs — Bpi, Ircam, BULAC, mk2… On garde la parole, à Paris."""
    print("→ Centre Pompidou...")
    base, events, seen = "https://www.centrepompidou.fr", [], set()
    for c in _soup(f"{base}/fr/programme/agenda/").select(".event-card"):
        typ = clean_text(c.select_one(".event-type").get_text(" ")) if c.select_one(".event-type") else ""
        place = clean_text(c.get("data-place", ""))
        t = c.select_one(".event-title")
        raw = clean_text(c.select_one(".dateEvenement").get_text(" ")) if c.select_one(".dateEvenement") else ""
        if (not t or not re.search(r"rencontre|conf[ée]rence|d[ée]bat|colloque|table ronde|s[ée]minaire", typ, re.I)
                or re.search(r"projection|cin[ée]ma|film", typ, re.I)
                or not _IDF_RE.search(place) or re.search(r"jusqu|partir", raw, re.I)):
            continue
        d = _range_start(raw)
        title = clean_text(t.get_text(" "))
        if not d or not in_window(d) or (title, d) in seen:
            continue
        seen.add((title, d))
        a = c.select_one("a[href]")
        sub = c.select_one(".event-subtitle")
        events.append(new_event(
            "Centre Pompidou", title, d, location=place,
            url=make_absolute(a["href"], base) if a else f"{base}/fr/programme/agenda/",
            desc=" · ".join(x for x in (typ, clean_text(sub.get_text(" ")) if sub else "") if x)))
    print(f"   ✓ Total Centre Pompidou: {len(events)} events")
    return events


def scrape_mardis_philo():
    """Les Mardis de la Philo (35 bis rue de Sèvres) : cycles de conférences,
    payants, en accès libre pour les moins de 26 ans."""
    print("→ Les Mardis de la Philo...")
    base, events = "https://www.lesmardisdelaphilo.com", []
    for path, disc in (("programme-philosophie", "Philosophie"), ("programme-litterature", "Littérature")):
        try:
            soup = _soup(f"{base}/{path}")
        except Exception as e:
            print(f"   [warn] {path}: {e}")
            continue
        for row in soup.select(".table_accordion"):
            cells = row.select(".table_accordion-row > .table_column")
            t = row.select_one(".table_numero-cycle-wrapper [fs-cmssort-field]")
            if not t or len(cells) < 4:
                continue
            tms = _TIME_RE.findall(cells[2].get_text(" "))
            fmt = lambda x: f"{int(x[0]):02d}:{x[1] or '00'}"
            content = row.select_one(".table_accordion-content-layout > div:not([class])")
            dates = sorted({d for d in (parse_french_date_text(x) for x in cells[3].get_text(" ").split(",")) if d})
            for i, d in enumerate(dates, 1):
                if not in_window(d):
                    continue
                ev = new_event(
                    "Les Mardis de la Philo",
                    clean_text(t.get_text(" ")) + (f" ({i}/{len(dates)})" if len(dates) > 1 else ""), d,
                    time_str=fmt(tms[0]) if tms else "", end_time=fmt(tms[1]) if len(tms) > 1 else "",
                    location="Les Mardis de la Philo, 35 bis rue de Sèvres, Paris 6e (et en direct sur Zoom)",
                    desc=clean_text(content.get_text(" "))[:400] if content else "",
                    url=f"{base}/{path}", source_type="association")
                ev["discipline"] = disc
                ev["price"] = "Payant · entrée libre pour les moins de 26 ans"
                events.append(ev)
    print(f"   ✓ Total Les Mardis de la Philo: {len(events)} events")
    return events


def scrape_universite_ouverte():
    """Université Ouverte (Université Paris Cité) : conférences gratuites.
    Articles WordPress ; la date est dans le texte (« jeudi 1er octobre à 17h »)."""
    print("→ Université Ouverte (Paris Cité)...")
    events = []
    soup = _soup("https://u-paris.fr/universite-ouverte/category/conferences-gratuites/")
    for art in soup.select("article"):
        a = art.select_one("h2 a[href], h3 a[href]")
        if not a:
            continue
        body = art.get_text(" ", strip=True)
        head = body.split(clean_text(a.get_text(" ")), 1)[-1]
        # 1re date du chapeau, en sautant la date de publication (« 16 septembre 2026 | »)
        head = re.sub(r"^\s*\d{1,2}\s+\S+\s+20\d\d", "", head)
        dm = _DAY_MONTH_RE.search(head)
        d = _day_month_to_date(dm.group(1), dm.group(2)) if dm else None
        if not d or not in_window(d):
            continue
        tm = re.search(r"\b(?:à|de)\s*(\d{1,2})\s*h\s*(\d{2})?", head[dm.start():dm.start() + 80])
        events.append(new_event(
            "Université Paris Cité", clean_text(a.get_text(" ")), d,
            time_str=f"{int(tm.group(1)):02d}:{tm.group(2) or '00'}" if tm else "",
            location="Université Ouverte — Université Paris Cité, Paris",
            url=a["href"], desc=("Université Ouverte · conférence gratuite · " + head.strip(" |"))[:400]))
        events[-1]["price"] = "Gratuit"
    print(f"   ✓ Total Université Ouverte: {len(events)} events")
    return events


# ── Deuxième lot (sept. 2026) : think tanks, finance, écoles, culture ─────────

def scrape_jsonld(name, url, location, *, drop=None, keep=None):
    """Agenda qui publie ses événements en JSON-LD schema.org (Event)."""
    print(f"→ {name}...")
    soup = _soup(url)
    events, seen = [], set()
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(sc.string or "")
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for x in items:
            if not isinstance(x, dict) or x.get("@type") not in ("Event", "EducationEvent", "BusinessEvent"):
                continue
            title = clean_text(html_unescape(x.get("name", "")))
            dt = parse_date(x.get("startDate", ""))
            if (not title or not dt or title.lower() in seen or not in_window(dt.date())
                    or is_junk_title(title) or _OFF_TOPIC.search(title)
                    or (drop and drop.search(title)) or (keep and not keep.search(title))):
                continue
            seen.add(title.lower())                    # 1er jour seulement
            loc = x.get("location") if isinstance(x.get("location"), dict) else {}
            where = clean_text(html_unescape(loc.get("name", "")))
            offers = x.get("offers") if isinstance(x.get("offers"), dict) else {}
            events.append(new_event(
                name, title, dt.date(), time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                location=_where_or(where, location), desc=strip_html(x.get("description", ""))[:400],
                url=offers.get("url") or x.get("url") or url))
            if str(offers.get("price", "")) == "0":
                events[-1]["price"] = "Gratuit"
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


_TALK_KINDS = ("conférence", "conference", "rencontre", "débat", "debat", "dialogue", "colloque",
               "table ronde", "séminaire", "seminaire", "journée d'étude", "journée d’étude",
               "cours public", "leçon", "talk", "forum")


def scrape_inha():
    # Institut national d'histoire de l'art : débats, conférences, colloques
    return _scrape_cards(
        "INHA", "https://www.inha.fr/agenda/", "article.card-agenda",
        title=".text-content p", date="a > span:not(.time)", time="span.time",
        kind=".text-content .cat", drop_kind=("exposition",), place=".venue",
        drop=re.compile(r"report[ée]e|annul[ée]", re.I),
        base="https://www.inha.fr", location="INHA, 2 rue Vivienne, Paris 2e",
        page_url="https://www.inha.fr/agenda/page/{n}/", page_start=2, max_pages=6)


def scrape_ifri():
    # Institut français des relations internationales. « Sur invitation » → 🔒
    return _scrape_cards(
        "Ifri", "https://www.ifri.org/fr/agenda", "div.agenda-container.view-content > div",
        title="h2", date=".event-date .font-title", time=".event-date .font-title-light",
        kind=".u-flex.u-align-items-center.u-mb10", drop_kind=("visioconférence", "webinaire"),
        members=re.compile(r"Sur invitation", re.I), base="https://www.ifri.org",
        location="Ifri, 27 rue de la Procession, Paris 15e",
        page_url="https://www.ifri.org/fr/agenda?page={n}", page_start=1, max_pages=4)


def scrape_iris():
    # Institut de relations internationales et stratégiques
    return _scrape_cards(
        "IRIS", "https://www.iris-france.org/evenements/", "div.row.gy-base.mb-3 > div.col-sm-6",
        title="h3", date="p.card-subheading", drop=re.compile(r"\breplay\b|webinaire", re.I),
        base="https://www.iris-france.org", location="IRIS, 2 bis rue Mercœur, Paris 11e")


def scrape_institut_delors():
    return _scrape_cards(
        "Institut Jacques Delors", "https://institutdelors.eu/evenements/",
        "div.facetwp-template > ul > li", title="h3", date=".bg-primary", time=".text-gray-600",
        kind="span.inline-block", drop_kind=("en ligne",), base="https://institutdelors.eu",
        location="Paris — lieu précisé sur la page de l'événement")


def scrape_jean_jaures():
    # Fondation Jean-Jaurès : débats, rencontres. « Du … au … » (prix, festivals) écartés
    return _scrape_cards(
        "Fondation Jean-Jaurès", "https://www.jean-jaures.org/evenements/",
        "div.line-agenda div.row-flex", title="h3.thumbnail-title",
        date=".card-agenda .card-date", time=".thumbnail-infos", place=".card-location address",
        kind=".thumbnail-tags", keep_loc=_IDF_RE, place_only=True, base="https://www.jean-jaures.org",
        location="Fondation Jean-Jaurès, 12 cité Malesherbes, Paris 9e",
        page_url="https://www.jean-jaures.org/evenements/page/{n}/", page_start=2, max_pages=5)


def scrape_louis_bachelier():
    # Institut Louis Bachelier (recherche en finance) : conférences de Place,
    # séminaires. L'agenda relaie aussi des courses caritatives : écartées.
    return _scrape_cards(
        "Institut Louis Bachelier", "https://www.institutlouisbachelier.org/evenements/",
        "div.collection-item-events", title=".event-title_text", date=".event-date_text",
        kind=".event-type_text", place=".event-venue_text",
        drop=re.compile(r"\brun\b|course|marathon|trail", re.I),
        base="https://www.institutlouisbachelier.org",
        location="Institut Louis Bachelier, 28 place de la Bourse, Paris 2e")


def scrape_citeco():
    # Cité de l'économie : conférences et débats (pas les visites ni ateliers)
    return _scrape_cards(
        "Citéco", "https://www.citeco.fr/agenda", "div.slider-ruban-content > div.content-zone-ruban",
        title=".content-zone-ruban-titre", date=".ruban-info-bulle", time=".ruban-info-bulle",
        drop=re.compile(r"^visite|atelier|escape|jeu\b|enfant|famille|en réalité augmentée|nocturne", re.I),
        base="https://www.citeco.fr", location="Citéco, 1 place du Général Catroux, Paris 17e")


def scrape_ima():
    return _scrape_cards(
        "Institut du monde arabe", "https://www.imarabe.org/fr/agenda/rencontres-et-debats",
        "div.cards-grid > div.card", title="h3", date=".dates",
        drop=re.compile(r"séance d'écoute|concert", re.I), base="https://www.imarabe.org",
        location="Institut du monde arabe, 1 rue des Fossés-Saint-Bernard, Paris 5e")


def scrape_beaux_arts():
    return _scrape_cards(
        "Beaux-Arts de Paris", "https://beauxartsparis.fr/fr/agenda", "div.view-content.row > div",
        title="h4", date="h3", time="time", kind="div.fw-bold.text-uppercase", keep_kind=_TALK_KINDS,
        place="div.fw-light.text-uppercase", base="https://beauxartsparis.fr",
        location="Beaux-Arts de Paris, 14 rue Bonaparte, Paris 6e",
        page_url="https://beauxartsparis.fr/fr/agenda?page={n}", page_start=1, max_pages=5)


def scrape_ens_saclay():
    # Scène de recherche de l'ENS Paris-Saclay (hors spectacles et animations enfants)
    return _scrape_cards(
        "ENS Paris-Saclay", "https://www.ens-paris-saclay.fr/agenda", "div.view-event-item",
        title=".event-title", date=".content-date", time=".content-date", kind=".event-category",
        drop_kind=("théâtre", "spectacle", "concert", "animation", "danse", "cinéma"),
        drop=re.compile(r"réparation|vélo|yoga|sport", re.I),
        base="https://www.ens-paris-saclay.fr",
        location="ENS Paris-Saclay, 4 avenue des Sciences, Gif-sur-Yvette")


def scrape_escp():
    return _scrape_cards(
        "ESCP Business School", "https://escp.eu/fr/events", "a.item-event",
        title="h2.title-item", date="p.date-item", kind="p.subtitle-item",
        drop_kind=("webinar", "online"), place="p.locat-seal", keep_loc=_IDF_RE, place_only=True,
        drop=re.compile(r"webinar|info(rmation)? session|réunion d'information|portes ouvertes|open day|"
                        r"london|londres|berlin|madrid|turin|torino|warsaw|varsovie", re.I),
        base="https://escp.eu", location="ESCP Business School, 79 avenue de la République, Paris 11e")


def scrape_sorbonne_paris_nord():
    # Agenda « Modern Events Calendar » en JSON-LD ; surtout vie de campus,
    # on garde colloques, conférences, journées d'étude.
    return scrape_jsonld(
        "Université Sorbonne Paris Nord", "https://www.univ-spn.fr/agenda/",
        "Université Sorbonne Paris Nord, 99 avenue Jean-Baptiste Clément, Villetaneuse",
        drop=re.compile(r"^\[(exposition|visite|théâtre|concert|atelier)|campus tour|start campus|"
                        r"piles usagées|salon studyrama|portes ouvertes|patrimoine", re.I))


def scrape_chartes():
    return _scrape_cards(
        "École nationale des chartes", "https://www.chartes.psl.eu/gazette-chartiste/agenda",
        "li.c-grid-card__item", title="h3", date=".icon-calendar + .c-tags__tags",
        time=".icon-clock + .c-tags__tags", kind=".c-taxonomy__text", speaker=".c-card__description",
        base="https://www.chartes.psl.eu", location="École nationale des chartes, 65 rue de Richelieu, Paris 2e")


# Noms d'institution des sources ci-dessus (carry-forward, hubs i/*.html).
# Doit rester aligné sur MAIN_INST dans web/src/lib.js.
NEW_INSTITUTIONS = [
    "Université Paris Cité", "Cnam", "Muséum national d'Histoire naturelle", "BnF",
    "Institut Pasteur", "Institut Curie", "Institut du Cerveau", "Inalco", "EPHE",
    "Collège des Bernardins", "Académie des sciences", "Cité des sciences",
    "Université Sorbonne Nouvelle", "Université Paris 8", "Université Paris Nanterre",
    "IJCLab", "IN2P3", "Observatoire de Paris", "Sciencesconf.org",
    "Université Paris 1 Panthéon-Sorbonne", "Université Paris-Panthéon-Assas", "Université Paris-Saclay", "Campus Condorcet", "Institut d'études avancées de Paris", "Fondation Maison des Sciences de l'Homme", "Musée du quai Branly",
    "Hi! PARIS", "PR[AI]RIE", "HEC Paris", "Musée du Louvre", "Centre Pompidou",
    "INHA", "Ifri", "IRIS", "Institut Jacques Delors", "Fondation Jean-Jaurès",
    "Institut Louis Bachelier", "Citéco", "Institut du monde arabe", "Beaux-Arts de Paris", "ENS Paris-Saclay",
    "ESCP Business School", "Université Sorbonne Paris Nord", "École nationale des chartes",
]

# Ordre = ordre d'exécution dans main() ; tous sans navigateur.
STATIC_SOURCES = [
    scrape_paris_cite, scrape_cnam, scrape_mnhn, scrape_bnf, scrape_pasteur,
    scrape_curie, scrape_institut_cerveau, scrape_inalco, scrape_ephe,
    scrape_bernardins, scrape_academie_sciences, scrape_cite_sciences,
    scrape_sorbonne_nouvelle, scrape_paris8, scrape_nanterre,
    scrape_ijclab, scrape_in2p3_paris, scrape_observatoire, scrape_sciencesconf,
    scrape_eightfold, scrape_carrieres_verifiees,
    scrape_jeunes_ihedn, scrape_makesense, scrape_associations_verifiees,
    scrape_paris1, scrape_assas, scrape_paris_saclay, scrape_condorcet, scrape_iea, scrape_fmsh, scrape_quai_branly,
    scrape_hi_paris, scrape_ens_maths, scrape_prairie, scrape_item_ens, scrape_ciens, scrape_ceres,
    scrape_hec_paris, scrape_hec_ia, scrape_louvre, scrape_pompidou, scrape_mardis_philo,
    scrape_universite_ouverte,
    scrape_inha, scrape_ifri, scrape_iris, scrape_institut_delors, scrape_jean_jaures,
    scrape_louis_bachelier, scrape_citeco, scrape_ima, scrape_beaux_arts, scrape_ens_saclay,
    scrape_escp, scrape_sorbonne_paris_nord, scrape_chartes,
]


# ── Luma ──────────────────────────────────────────────────────────────────────

# Luma geolocates by IP. From the US-based CI runner the topic pages
# (tech / ai / arts / ...) only ever return US events, so they are useless
# here — we keep just the Paris discover feed, which is genuinely Paris.
LUMA_PAGES = [
    "https://lu.ma/discover/paris",
]


def _luma_category(url):
    """Topic label derived from a Luma page URL, used to filter Luma by theme.
    .../discover/paris -> 'paris' ; luma.com/tech -> 'tech'."""
    seg = url.rstrip("/").split("/")[-1].split("?")[0].lower()
    return seg or "paris"


def scrape_luma(browser, pages=None) -> list[dict]:
    """Scrape Luma — Paris discover page + topic category pages — keeping ONLY
    events located in France. The browser is geolocated to Paris so the topic
    pages surface French events instead of US ones.

    `pages` overrides LUMA_PAGES — used by the local refresh script, which runs
    from a French IP and can therefore also harvest the topic pages (those
    return US events from the GitHub runner)."""
    print("→ Luma (France only)...")
    events, seen = [], {}
    captured = []

    # Pretend we are browsing from Paris (locale + timezone + geolocation)
    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="fr-FR",
        timezone_id="Europe/Paris",
        geolocation={"latitude": 48.8566, "longitude": 2.3522},
        permissions=["geolocation"],
        viewport={"width": 1366, "height": 900},
    )
    page = ctx.new_page()
    page.on("response", lambda r: capture_json(r, captured))

    for url in (pages or LUMA_PAGES):
        seen_before = len(captured)
        page_blobs = []
        try:
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                page.wait_for_timeout(3000)
            accept_cookies(page)
            for _ in range(8):
                page.evaluate(
                    "() => { if (document.body) window.scrollTo(0, document.body.scrollHeight); }")
                page.wait_for_timeout(1100)
            html = page.content()
            nd = BeautifulSoup(html, "lxml").find("script", {"id": "__NEXT_DATA__"})
            if nd and nd.string:
                try:
                    page_blobs.append(json.loads(nd.string))
                except Exception:
                    pass
        except Exception as e:
            print(f"   [WARN] {url}: {e}")

        # JSON captured while this page was loading
        for _u, body in captured[seen_before:]:
            page_blobs.append(body)

        # how many events on the page total, and how many in France
        total = sum(len(extract_events_deep_json(b, "Luma", "luma", "https://lu.ma"))
                    for b in page_blobs)
        cat = _luma_category(url)
        new = 0
        for blob in page_blobs:
            for ev in extract_events_deep_json(blob, "Luma", source_type="luma",
                                               base_url="https://lu.ma", require_france=True):
                key = (ev["title"][:50].lower(), ev["date"])
                if key not in seen:
                    ev["luma_categories"] = [cat] if cat else []
                    seen[key] = ev
                    events.append(ev)
                    new += 1
                elif cat and cat not in seen[key].get("luma_categories", []):
                    seen[key].setdefault("luma_categories", []).append(cat)
        print(f"   {url}: {total} events on page → +{new} in France")

    ctx.close()
    print(f"   ✓ {len(events)} events (France only)")
    return events


# ── Article 1 (association) ───────────────────────────────────────────────────

ARTICLE1_URL = "https://article1.my.salesforce-sites.com/AG_VFP_Calendar?bv=jeune"


def scrape_article1(browser) -> list[dict]:
    """Article 1 calendar — Vue/Salesforce site. Events arrive via a JS Remoting
    XHR (apexremote → AG_ActiveCampaignControllerV2.getAteliers); we capture
    that response. We keep the entire calendar (jeune + mentors), all cities
    + online; the user filters by city via the location shown on each card."""
    print("→ Article 1 (association)...")
    events, seen = [], set()
    captured = []
    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="fr-FR",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    )
    page = ctx.new_page()
    page.on("response", lambda r: capture_json(r, captured))
    try:
        page.goto(ARTICLE1_URL, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            page.wait_for_timeout(3000)
        page.wait_for_timeout(2500)  # give Vue + apex-remoting time to fire
    except Exception as e:
        print(f"   [WARN] goto Article 1: {e}")
    ctx.close()

    def _campaign_list(res):
        """L'API a déjà changé de forme : getAteliers renvoyait la liste
        directement, getAllCampaign renvoie {"campaigns": [...]}."""
        if isinstance(res, dict):
            for k in ("campaigns", "ateliers", "result"):
                if isinstance(res.get(k), list):
                    return res[k]
            return []
        return res if isinstance(res, list) else []

    raw = []
    for _u, body in captured:
        if not (isinstance(body, list) and body and isinstance(body[0], dict)):
            continue
        lst = _campaign_list(body[0].get("result"))
        # On reconnaît le bon payload à sa FORME (des objets datés), pas au
        # nom de la méthode : Article 1 l'a renommée une fois déjà
        # (getAteliers -> getAllCampaign) et le scraper est tombé à 0 en
        # silence pendant des semaines.
        if lst and isinstance(lst[0], dict) and "StartDate" in lst[0]:
            raw = lst
            break
    print(f"   {len(raw)} raw events")

    def _norm_time(s):
        s = clean_text(s or "")
        m = re.match(r"(\d{1,2})\s*[hH:]\s*(\d{0,2})", s)
        return f"{int(m.group(1)):02d}:{(m.group(2) or '00').rjust(2, '0')[:2]}" if m else ""

    for it in raw:
        ms = it.get("StartDate")
        if not ms:
            continue
        try:
            d = datetime.utcfromtimestamp(int(ms) / 1000).date()
        except Exception:
            continue
        if d < CUTOFF or d > HORIZON:
            continue
        # Name est le libellé technique « Ville - Titre - JJ-MM-AAAA » ;
        # TECH_Nom_Campagne_saisie__c porte le titre propre saisi à la main.
        title = clean_text(it.get("TECH_Nom_Campagne_saisie__c") or "")
        if not title:
            title = re.sub(r"\s*-\s*\d{2}-\d{2}-\d{4}\s*$", "",
                           clean_text(it.get("Name") or ""))
        # Saisies manuelles : titre entièrement encadré de guillemets droits,
        # ou guillemet ouvrant resté orphelin. Les deux passent mal en carte
        # comme en balise SEO.
        if title.count('"') == 1 or (title.startswith('"') and title.endswith('"')):
            title = title.replace('"', "").strip()
        if not title or is_junk_title(title):
            continue
        city = clean_text(it.get("Ville__c") or "")
        region = clean_text(it.get("Region_campagne__c") or "")
        is_digital = bool(it.get("A_distance__c")) or it.get("Physique_ou_Digital__c") == "Digital"
        loc = "En ligne" if is_digital else (city or region or "Paris")
        # Les champs Description_*__c ont disparu de l'API : on reconstruit
        # une phrase courte à partir de ce qui reste exposé.
        desc = strip_html(it.get("Description_Jeunes__c")
                          or it.get("Description_Benevoles__c") or "")[:400]
        if not desc:
            desc = " · ".join(b for b in (
                clean_text(it.get("Type_evenement__c") or ""),
                clean_text(it.get("Public__c") or "")) if b)
        key = (title[:60].lower(), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        events.append(new_event(
            "Article 1", title, d,
            time_str=_norm_time(it.get("Heure_de_debut_text__c")),
            end_time=_norm_time(it.get("Heure_de_fin_texte__c")),
            location=loc, desc=desc,
            # Lien direct vers l'inscription quand il existe : plus utile
            # que la page calendrier générique.
            url=(clean_text(it.get("Lien_inscription__c") or "").startswith("http")
                 and clean_text(it["Lien_inscription__c"]) or ARTICLE1_URL),
            source_type="association", image=it.get("image_EVT__c") or "",
        ))
        # Public_cible__c liste les publics invités (« EL;PP;Mentors…») ; seuls
        # les événements qui citent « Extérieur » sont ouverts hors communauté.
        if "extérieur" not in clean_text(it.get("Public_cible__c") or "").lower():
            events[-1]["members"] = True
    print(f"   ✓ Total Article 1: {len(events)} events")
    return events


# ── Sciences et Cultures (association — Linktree → Framaforms) ───────────────

SCIENCES_CULTURES_LINKTREE = "https://linktr.ee/Sciences_et_Cultures"


def scrape_sciences_cultures(past_days: int = 0) -> list[dict]:
    """Sciences et Cultures (association étudiante).
    Their Linktree page lists each conference with a framaforms.org inscription
    URL. The URL itself carries the date as DDMMYYYY (e.g.
    `inscription-conference-anssi-16062026-sciences-cultures-c`), and the link
    title carries the speaker + topic. So we parse it all straight from the
    Linktree's embedded JSON — no need to fetch each Framaforms page.

    past_days > 0 also keeps events from the last N days (used by the local
    bootstrap to feed Historique with recently-passed conferences). The daily
    runner uses past_days=0; once a future event is seen, it lands in
    events.json and is auto-archived when its date passes."""
    print("→ Sciences et Cultures (Linktree)...")
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
         "Accept-Language": "fr-FR,fr;q=0.9", "Accept": "text/html,*/*"}
    try:
        r = requests.get(SCIENCES_CULTURES_LINKTREE, headers=H, timeout=30)
    except Exception as e:
        print(f"   [WARN] {type(e).__name__}: {e}")
        return []
    if r.status_code != 200:
        print(f"   HTTP {r.status_code}")
        return []
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', r.text, re.S)
    if not m:
        print("   no __NEXT_DATA__")
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("url"), str) and isinstance(o.get("title"), str):
                yield o["title"], o["url"]
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for x in o:
                yield from walk(x)

    SKIP_KW = ("recrutement", "partenariats", "filmer", "nous-rejoindre")
    floor = CUTOFF - timedelta(days=past_days) if past_days > 0 else CUTOFF
    events, seen = [], set()
    raw_count = 0
    for title, url in walk(data):
        if "framaforms.org" not in url:
            continue
        raw_count += 1
        if any(kw in url.lower() for kw in SKIP_KW):
            continue
        # DDMMYYYY between hyphens (e.g. -16062026-)
        dm = re.search(r"-(\d{2})(\d{2})(20\d{2})(?:-|\b)", url)
        if not dm:
            continue
        try:
            d = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
        except Exception:
            continue
        if d < floor or d > HORIZON:
            continue
        title = clean_text(title)
        if not title or is_junk_title(title):
            continue
        key = (title[:60].lower(), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        events.append(new_event(
            "Sciences et Cultures", title, d,
            location="Sorbonne, Paris",
            desc="Inscription requise via le lien.",
            url=url, source_type="association",
        ))
    n_future = sum(1 for e in events if e["date"] >= CUTOFF.isoformat())
    n_past = len(events) - n_future
    print(f"   {raw_count} liens framaforms · {n_future} à venir"
          + (f" · {n_past} récemment passés (pour Historique)" if n_past else ""))
    return events


# ── Main ──────────────────────────────────────────────────────────────────────

def _richness(ev):
    """Pour garder la meilleure fiche d'un doublon inter-sources."""
    return ((ev.get("source_type") == "institution") * 4 + bool(ev.get("time")) * 2
            + bool(ev.get("speaker")) + min(len(ev.get("description") or ""), 300) / 300)


def merge_cross_source(events):
    """Même titre + même date chez deux organisateurs (BnF + EPHE, PSL +
    Dauphine…) : une seule fiche, la plus complète ; les autres organisateurs
    sont notés dans « also ». Titres trop courts / génériques ignorés."""
    groups = {}
    for ev in events:
        t = slugify(ev.get("title", ""))
        if len(t) < 20:
            groups[id(ev)] = [ev]
            continue
        groups.setdefault((t[:45], ev.get("date")), []).append(ev)
    out, merged = [], 0
    for g in groups.values():
        if len({e.get("institution") for e in g}) < 2:
            out.extend(g)
            continue
        best = max(g, key=_richness)
        others = sorted({e.get("institution") for e in g} - {best.get("institution")})
        best["also"] = sorted(set(best.get("also", [])) | set(others))
        out.append(best)
        merged += len(g) - 1
    if merged:
        print(f"Doublons inter-sources fusionnés : {merged}")
    return out


def deduplicate(events):
    seen, out = set(), []
    for ev in events:
        key = (ev["title"].lower()[:60], ev["date"], ev["institution"])
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out


# ── Geocoding + iCal feed (map view & calendar subscription) ──────────────────

GEOCACHE_FILE = OUTPUT_FILE.parent / "geocache.json"
ICS_FILE = OUTPUT_FILE.parent / "calendar.ics"
ARCHIVE_FILE = OUTPUT_FILE.parent / "events-archive.json"
META_FILE = OUTPUT_FILE.parent / "meta.json"


def update_meta(field: str, value=None) -> None:
    """Stamp data/meta.json with the current UTC time for `field`, or with
    `value` when one is given. Used by main() (`last_workflow_run`,
    `fresh_counts`) and refresh_local.py (`last_manual_run`) so the site can
    show 'last update' indicators. Preserves the other fields if present."""
    try:
        m = json.loads(META_FILE.read_text(encoding="utf-8"))
    except Exception:
        m = {}
    from datetime import timezone
    m[field] = (value if value is not None else
                datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"))
    try:
        META_FILE.write_text(json.dumps(m, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] meta write: {e}")
ARCHIVE_MAX_DAYS = 365     # keep at most one year of past events
MAX_NEW_GEOCODE = 220      # courtesy cap on Nominatim lookups per run

# Seeds the cache so big institutions always map even if Nominatim is down.
SEED_GEOCODE = {
    "ihp, 11 rue pierre et marie curie, paris 5e": [48.8438, 2.3437],
    "collège de france, 11 place marcelin-berthelot, paris 5e": [48.8489, 2.3446],
    "ens, 45 rue d'ulm, paris 5e": [48.8417, 2.3446],
    "ehess, 54 boulevard raspail, paris 6e": [48.8488, 2.3270],
    "sciences po, 27 rue saint-guillaume, paris 7e": [48.8543, 2.3280],
    "paris school of economics, 48 boulevard jourdan, paris 14e": [48.8216, 2.3379],
    "université psl, 60 rue mazarine, paris 6e": [48.8555, 2.3382],
    "sorbonne université, paris": [48.8479, 2.3433],
}

# Fallback coordinates per institution — used when an event's exact location
# (a room name, a building code…) can't be geocoded.
INSTITUTION_COORDS = {
    "Institut Henri Poincaré":   [48.8438, 2.3437],
    "Collège de France":         [48.8489, 2.3446],
    "ENS Paris":                 [48.8417, 2.3446],
    "EHESS":                     [48.8488, 2.3270],
    "Sciences Po":               [48.8543, 2.3280],
    "Paris School of Economics": [48.8216, 2.3379],
    "Université PSL":            [48.8555, 2.3382],
    "Sorbonne Université":       [48.8479, 2.3433],
    "Sciences et Cultures":      [48.8479, 2.3433],   # Sorbonne (Paris 5e)
    "Université Paris Dauphine": [48.8702, 2.2745],
    "Université Paris Cité":     [48.8508, 2.3431],
    "Cnam":                      [48.8667, 2.3553],
    "Muséum national d'Histoire naturelle": [48.8440, 2.3590],
    "BnF":                       [48.8336, 2.3758],
    "Institut Pasteur":          [48.8404, 2.3106],
    "Institut Curie":            [48.8440, 2.3440],
    "Institut du Cerveau":       [48.8387, 2.3622],
    "Inalco":                    [48.8276, 2.3810],
    "EPHE":                      [48.8322, 2.3405],
    "Collège des Bernardins":    [48.8490, 2.3528],
    "Académie des sciences":     [48.8574, 2.3372],
    "Cité des sciences":         [48.8958, 2.3878],
    "Université Sorbonne Nouvelle": [48.8465, 2.3960],
    "Université Paris 8":        [48.9454, 2.3634],
    "Université Paris Nanterre": [48.9035, 2.2129],
    "IJCLab":                    [48.6985, 2.1840],
    "IN2P3":                     [48.8467, 2.3560],   # LPNHE, Jussieu
    "Observatoire de Paris":     [48.8364, 2.3364],
    "Université Paris 1 Panthéon-Sorbonne": [48.8467, 2.3441],
    "Université Paris-Panthéon-Assas": [48.8436, 2.3325],
    "Université Paris-Saclay": [48.711, 2.17],
    "Campus Condorcet": [48.9063, 2.3703],
    "Institut d'études avancées de Paris": [48.8518, 2.3584],
    "Fondation Maison des Sciences de l'Homme": [48.8488, 2.327],
    "Musée du quai Branly": [48.8609, 2.2977],
    "Hi! PARIS": [48.7133, 2.2089],
    "PR[AI]RIE": [48.8445, 2.3445],
    "HEC Paris": [48.7596, 2.1682],
    "Musée du Louvre": [48.8606, 2.3376],
    "Centre Pompidou": [48.8607, 2.3522],
    "INHA": [48.868, 2.3395],
    "Ifri": [48.8395, 2.3065],
    "IRIS": [48.8546, 2.3808],
    "Institut Jacques Delors": [48.8773, 2.329],
    "Fondation Jean-Jaurès": [48.881, 2.338],
    "Institut Louis Bachelier": [48.869, 2.341],
    "Citéco": [48.8836, 2.308],
    "Institut du monde arabe": [48.849, 2.3572],
    "Beaux-Arts de Paris": [48.8566, 2.3336],
    "ENS Paris-Saclay": [48.712, 2.168],
    "ESCP Business School": [48.8637, 2.3835],
    "Université Sorbonne Paris Nord": [48.957, 2.3417],
    "École nationale des chartes": [48.8675, 2.3383],
}

# A location worth geocoding looks like a real street address (postal code,
# or "<number> <street type>"). Vague names ("amphi Fermat", "1R2") do not.
_ADDR_RE = re.compile(
    r"\b\d{5}\b|"
    r"\b\d{1,4}\s?(?:bis|ter)?\s+(rue|avenue|av\.|bd|boulevard|place|quai|cours|"
    r"impasse|passage|all[ée]e|chemin|esplanade|square)\b", re.I)


def looks_like_address(loc):
    return bool(_ADDR_RE.search(loc or ""))


# Villes hors Paris déjà vues dans les données (Article 1 couvre toute la
# France) : leur présence empêche d'ancrer la recherche sur Paris.
_FR_CITY_RE = re.compile(
    r"\b(nantes|bordeaux|lyon|marseille|toulouse|lille|strasbourg|montpellier|"
    r"rennes|reims|nancy|metz|grenoble|dijon|angers|nice|clermont[- ]ferrand|"
    r"saint[- ][ée]tienne|tours|orl[ée]ans|caen|rouen|amiens|limoges|"
    r"besan[çc]on|poitiers|brest|le mans|avignon|mulhouse|perpignan|n[îi]mes|"
    r"toulon|villeurbanne|aix[- ]en[- ]provence|roissy|la r[ée]union|"
    r"guadeloupe|martinique|mayotte)\b", re.I)


def _nominatim(sess, address):
    """Look up one address via OpenStreetMap Nominatim. Returns [lat, lng] or None."""
    if re.search(r"\bonline\b|en ligne|visio|webinaire|zoom|distanciel", address, re.I):
        return None
    q = address
    if "france" not in q.lower():
        # N'ancrer sur Paris que si aucune autre ville n'est nommée. Depuis
        # qu'Article 1 remonte aussi ses événements de province, une adresse
        # nantaise deviendrait sinon « …, Nantes, Paris, France ».
        anchored = "paris" in q.lower() or _FR_CITY_RE.search(q)
        q = q + ("" if anchored else ", Paris") + ", France"
    try:
        r = sess.get("https://nominatim.openstreetmap.org/search",
                     params={"q": q, "format": "json", "limit": 1, "countrycodes": "fr"},
                     timeout=15)
        if r.ok and r.json():
            d = r.json()[0]
            return [round(float(d["lat"]), 6), round(float(d["lon"]), 6)]
    except Exception:
        pass
    return None


def geocode_all(events):
    """Add lat/lng to events. Real addresses are geocoded (Nominatim, cached);
    vague locations fall back to the event's institution coordinates."""
    try:
        cache = json.loads(GEOCACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    for k, v in SEED_GEOCODE.items():
        cache.setdefault(k, v)

    sess = requests.Session()
    sess.headers.update({"User-Agent": "ParisAcademique/1.0 (github.com/kovarci/zzzz)"})
    new = 0
    for ev in events:
        if ev.get("geo_exact") and "lat" in ev:
            continue                         # GPS fourni par la source (Ville de Paris, Sciencesconf)
        loc = clean_text(ev.get("location") or "")
        coords = None
        if loc and looks_like_address(loc):
            key = loc.lower()[:140]
            if key not in cache and new < MAX_NEW_GEOCODE:
                cache[key] = _nominatim(sess, loc)
                new += 1
                time.sleep(1.1)   # Nominatim asks for max 1 request/second
            coords = cache.get(key)
        if not coords:                       # fallback → institution coordinates
            coords = INSTITUTION_COORDS.get(ev.get("institution"))
        if coords:
            ev["lat"], ev["lng"] = coords[0], coords[1]

    try:
        GEOCACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    except Exception as e:
        print(f"[WARN] geocache write: {e}")
    located = sum(1 for e in events if "lat" in e)
    print(f"Geocoded: {new} new lookups · {located}/{len(events)} events placed on map")


def write_ics(events):
    """Write the global subscribable .ics feed + one feed per institution
    (data/cal/<slug>.ics), used by the per-institution header on the site."""
    def esc(s):
        return (str(s or "").replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\r", "").replace("\n", "\\n"))
    stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")

    def vcal(evts, calname):
        out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Paris Academique//FR",
               "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
               f"X-WR-CALNAME:{esc(calname)}",
               "X-WR-TIMEZONE:Europe/Paris"]
        for ev in evts:
            d = ev["date"].replace("-", "")
            tm = ev.get("time", "")
            if tm and re.match(r"\d{1,2}:\d{2}", tm):
                h, m = tm.split(":")[:2]
                dtstart = f"DTSTART:{d}T{int(h):02d}{int(m):02d}00"
                et = ev.get("end_time", "")
                if et and re.match(r"\d{1,2}:\d{2}", et):
                    eh, em = et.split(":")[:2]
                    dtend = f"DTEND:{d}T{int(eh):02d}{int(em):02d}00"
                else:
                    dtend = f"DTEND:{d}T{min(int(h)+2,23):02d}{int(m):02d}00"
            else:
                dtstart = f"DTSTART;VALUE=DATE:{d}"
                try:
                    nd = (datetime.strptime(ev["date"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
                except Exception:
                    nd = d
                dtend = f"DTEND;VALUE=DATE:{nd}"
            desc = esc((ev.get("description") or "") + (("\n" + ev["url"]) if ev.get("url") else ""))
            out += ["BEGIN:VEVENT", f"UID:{ev['id']}@paris-academique",
                    f"DTSTAMP:{stamp}", dtstart, dtend,
                    f"SUMMARY:{esc(ev['title'])}", f"DESCRIPTION:{desc}",
                    f"LOCATION:{esc(ev.get('location', ''))}"]
            if ev.get("url"):
                out.append(f"URL:{esc(ev['url'])}")
            out.append("END:VEVENT")
        out.append("END:VCALENDAR")
        return "\r\n".join(out) + "\r\n"

    try:
        ICS_FILE.write_text(vcal(events, "Conférences académiques · Paris"),
                            encoding="utf-8")
        print(f"Calendar feed: {len(events)} events → calendar.ics")
    except Exception as e:
        print(f"[WARN] ics write: {e}")

    # Per-institution feeds (academic + association sources only — not the
    # dozens of one-off Luma hosts / Que faire à Paris venues). Same slug
    # logic as the frontend.
    cal_dir = OUTPUT_FILE.parent / "cal"
    cal_dir.mkdir(exist_ok=True)
    by_inst = {}
    for ev in events:
        if ev.get("source_type") in ("luma", "ville", "entreprise"):
            continue
        by_inst.setdefault(ev.get("institution", ""), []).append(ev)
    written = set()
    for inst, evts in by_inst.items():
        slug = slugify(inst)
        if not slug:
            continue
        written.add(f"{slug}.ics")
        try:
            (cal_dir / f"{slug}.ics").write_text(vcal(evts, f"{inst} · Lotent"),
                                                 encoding="utf-8")
        except Exception as e:
            print(f"[WARN] ics {slug}: {e}")
    for f in cal_dir.glob("*.ics"):       # prune calendars of vanished sources
        if f.name not in written:
            try:
                f.unlink()
            except Exception:
                pass
    print(f"Calendriers par institution : {len(written)}")


SITE_URL = "https://lotent.fr"
EVENT_PAGES_DIR = OUTPUT_FILE.parent.parent / "e"
DIGEST_FILE = OUTPUT_FILE.parent / "digest.json"
RSS_FILE = OUTPUT_FILE.parent / "digest.xml"

_MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre"]


def _esc_attr(s) -> str:
    import html as _html
    return _html.escape(str(s or ""), quote=True)


def _date_fr(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.day} {_MONTHS_FR[d.month - 1]} {d.year}"
    except Exception:
        return iso


ONLINE_RE = re.compile(r"\b(online|en ligne|visio|distanciel|webinaire|webinar|"
                       r"zoom|teams|à distance|hybride|streaming)\b", re.I)

# Site officiel par institution — sert à remplir organizer.url dans le JSON-LD
# (sinon Google se plaint « Champ url manquant dans organizer »).
INSTITUTION_URLS = {
    "Collège de France": "https://www.college-de-france.fr",
    "ENS Paris": "https://www.ens.psl.eu",
    "EHESS": "https://www.ehess.fr",
    "Institut Henri Poincaré": "https://www.ihp.fr",
    "Paris School of Economics": "https://www.parisschoolofeconomics.eu",
    "Sciences Po": "https://www.sciencespo.fr",
    "Sorbonne Université": "https://www.sorbonne-universite.fr",
    "Université PSL": "https://psl.eu",
    "Article 1": "https://article-1.eu",
    "Sciences et Cultures": "https://linktr.ee/Sciences_et_Cultures",
    "Université Paris Dauphine": "https://dauphine.psl.eu",
    "Université Paris Cité": "https://u-paris.fr",
    "Cnam": "https://www.cnam.fr",
    "Muséum national d'Histoire naturelle": "https://www.mnhn.fr",
    "BnF": "https://www.bnf.fr",
    "Institut Pasteur": "https://www.pasteur.fr",
    "Institut Curie": "https://curie.fr",
    "Institut du Cerveau": "https://institutducerveau.org",
    "Inalco": "https://www.inalco.fr",
    "EPHE": "https://www.ephe.psl.eu",
    "Collège des Bernardins": "https://www.collegedesbernardins.fr",
    "Académie des sciences": "https://www.academie-sciences.fr",
    "Cité des sciences": "https://www.cite-sciences.fr",
    "Université Sorbonne Nouvelle": "https://www.sorbonne-nouvelle.fr",
    "Université Paris 8": "https://www.univ-paris8.fr",
    "Université Paris Nanterre": "https://www.parisnanterre.fr",
    "IJCLab": "https://www.ijclab.in2p3.fr",
    "IN2P3": "https://www.in2p3.cnrs.fr",
    "Observatoire de Paris": "https://www.observatoiredeparis.psl.eu",
    "Sciencesconf.org": "https://www.sciencesconf.org",
    "Université Paris 1 Panthéon-Sorbonne": "https://www.pantheonsorbonne.fr",
    "Université Paris-Panthéon-Assas": "https://www.assas-universite.fr",
    "Université Paris-Saclay": "https://www.universite-paris-saclay.fr",
    "Campus Condorcet": "https://www.campus-condorcet.fr",
    "Institut d'études avancées de Paris": "https://www.paris-iea.fr",
    "Fondation Maison des Sciences de l'Homme": "https://www.fmsh.fr",
    "Musée du quai Branly": "https://www.quaibranly.fr",
    "Hi! PARIS": "https://hi-paris.fr",
    "PR[AI]RIE": "https://www.prairie-psai.fr",
    "HEC Paris": "https://www.hec.edu",
    "Musée du Louvre": "https://www.louvre.fr",
    "Centre Pompidou": "https://www.centrepompidou.fr",
    "INHA": "https://www.inha.fr",
    "Ifri": "https://www.ifri.org",
    "IRIS": "https://www.iris-france.org",
    "Institut Jacques Delors": "https://institutdelors.eu",
    "Fondation Jean-Jaurès": "https://www.jean-jaures.org",
    "Institut Louis Bachelier": "https://www.institutlouisbachelier.org",
    "Citéco": "https://www.citeco.fr",
    "Institut du monde arabe": "https://www.imarabe.org",
    "Beaux-Arts de Paris": "https://beauxartsparis.fr",
    "ENS Paris-Saclay": "https://ens-paris-saclay.fr",
    "ESCP Business School": "https://escp.eu",
    "Université Sorbonne Paris Nord": "https://www.univ-spn.fr",
    "École nationale des chartes": "https://www.chartes.psl.eu",
}


def _event_jsonld(ev):
    """schema.org Event JSON-LD — feeds Google's rich results (date & venue
    shown directly in search). Includes every recommended field (image,
    endDate, performer, organizer.url, offers) so Search Console doesn't
    flag missing properties. '</' is split to be safe inside a <script>."""
    eid = ev["id"]
    start = ev["date"] + (f"T{ev['time']}:00" if ev.get("time") else "")
    # endDate : si pas d'heure de fin scrappée, on suppose +2h (cohérent
    # avec le calendrier .ics) plutôt que de laisser le champ absent.
    if ev.get("end_time"):
        end = ev["date"] + f"T{ev['end_time']}:00"
    elif ev.get("time"):
        try:
            h, m = ev["time"].split(":")
            end = ev["date"] + f"T{min(int(h)+2,23):02d}:{int(m):02d}:00"
        except Exception:
            end = start
    else:
        end = start
    inst = ev.get("institution") or ""
    organizer = {"@type": "Organization", "name": inst}
    if INSTITUTION_URLS.get(inst):
        organizer["url"] = INSTITUTION_URLS[inst]
    elif ev.get("url"):
        organizer["url"] = ev["url"]
    # performer : si pas d'intervenant scrappé, on liste l'institution comme
    # PerformingGroup — acceptable et évite le warning « Champ performer
    # manquant ». Sinon, la personne nommée.
    if ev.get("speaker"):
        performer = {"@type": "Person", "name": ev["speaker"]}
    else:
        performer = {"@type": "PerformingGroup", "name": inst or "Conférencier"}
    # image : fallback vers l'og.png par institution (toujours fraîche) ou
    # l'og.png global du site -> tout event a une image.
    img = ev.get("image")
    if not img:
        slug = slugify(inst)
        img = f"{SITE_URL}/data/og/{slug}.png" if slug else f"{SITE_URL}/og.png"
    # offers : Google le demande même pour les confs gratuites. On marque
    # explicitement le prix (Luma a un champ price ; sinon, 0/gratuit).
    price_str = ev.get("price") or ""
    if "gratuit" in price_str.lower():
        price = "0"
    else:
        m = re.search(r"(\d+)", price_str)
        price = m.group(1) if m else "0"
    offers = {
        "@type": "Offer",
        "price": price, "priceCurrency": "EUR",
        "availability": "https://schema.org/InStock",
        "url": ev.get("url") or f"{SITE_URL}/e/{eid}.html",
        "validFrom": ev["date"],
    }
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": ev.get("title") or "",
        "startDate": start,
        "endDate": end,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": ("https://schema.org/OnlineEventAttendanceMode"
                                if ev.get("location") and ONLINE_RE.search(ev["location"])
                                else "https://schema.org/OfflineEventAttendanceMode"),
        "url": f"{SITE_URL}/e/{eid}.html",
        "image": img,
        "organizer": organizer,
        "performer": performer,
        "offers": offers,
    }
    if ev.get("location"):
        data["location"] = {
            "@type": "Place",
            "name": ev["location"],
            "address": {"@type": "PostalAddress",
                        "addressLocality": "Paris", "addressCountry": "FR"},
        }
    if ev.get("description"):
        data["description"] = ev["description"][:500]
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


# Couleurs de discipline — identiques à web/src/app.css
DISC_COLORS = {"Mathématiques": "#3B82F6", "Sciences": "#10B981", "Économie": "#F59E0B", "Histoire": "#A16207",
               "Philosophie": "#8B5CF6", "Littérature": "#EC4899", "Sociologie & Anthropologie": "#EAB308",
               "Droit & Sciences politiques": "#0EA5E9", "Arts & Culture": "#F43F5E", "Autre": "#71717A"}
_KIND_RE = re.compile(r"^(Cours|Séminaire|Colloque|Conférence|Leçon inaugurale|Journée d'étude|Atelier|Workshop|Table ronde|Rencontre|Lecture)\b", re.I)
_WDS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
_MOS = ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]


def _kind_of(ev):
    m = _KIND_RE.match(ev.get("description", "") or "") or _KIND_RE.match(ev.get("title", "") or "")
    if m:
        k = m.group(1)
        return k[0].upper() + k[1:].lower()
    return "Rencontre" if ev.get("source_type") == "luma" else "Conférence"


def _wds(d):
    try: return _WDS[date.fromisoformat(d).weekday()]
    except Exception: return ""


def _dnum(d):
    try: return str(date.fromisoformat(d).day)
    except Exception: return ""


def _mos(d):
    try: return _MOS[date.fromisoformat(d).month - 1]
    except Exception: return ""


def _series_key(ev):
    """(institution, titre sans le « (n) ») : regroupe les séances d'un cycle."""
    base = re.sub(r"\s*\(\d+\)\s*", " ", ev.get("title", "") or "").strip()
    # Collège de France colle le nom de l'intervenant à la fin du titre.
    sp = (ev.get("speaker") or "").strip()
    if sp and base.endswith(sp):
        base = base[:-len(sp)].strip()
    return (ev.get("institution", ""), base)


def write_event_pages(events):
    """One small static page per event (e/<id>.html): Open Graph tags for a
    proper link preview on WhatsApp/Discord/Twitter, plus REAL visible content
    (title, date, place, description, registration link) so Google can index
    each conference individually — an instant redirect would be treated as a
    redirect by crawlers and never indexed. A prominent button sends humans
    to the calendar app with the event modal open."""
    EVENT_PAGES_DIR.mkdir(exist_ok=True)
    today_iso = TODAY.isoformat()
    # Maillage interne : Search Console classait une partie des pages en
    # « Explorée, actuellement non indexée » — pages trop minces (description
    # de 30 caractères) et quasi identiques d'une séance à l'autre d'un même
    # cycle (« Cours X (1) », « (2) »…), sans aucun lien sortant à part la
    # home. On relie chaque page à son hub institution, aux autres séances du
    # cycle et aux prochaines conférences de la même institution : contenu
    # unique par page + Google découvre les pages autrement que via le sitemap.
    hubs = {slugify(i) for i in SHARE_INSTITUTIONS
            if (INST_PAGES_DIR / f"{slugify(i)}.html").exists()}
    upcoming = [e for e in events if e.get("date", "") >= today_iso
                and re.fullmatch(r"[0-9a-f]{12}", e.get("id") or "")]
    upcoming.sort(key=lambda e: (e.get("date", ""), e.get("time", "")))
    by_inst, by_series = {}, {}
    for e in upcoming:
        by_inst.setdefault(e.get("institution", ""), []).append(e)
        by_series.setdefault(_series_key(e), []).append(e)

    def _links(evts, cls):
        items = "".join(
            f'<li><a href="{e["id"]}.html"><span>{_esc_attr(e.get("title", ""))}</span>'
            f'<span class="d">{_esc_attr(_date_fr(e.get("date", "")))}</span></a></li>'
            for e in evts)
        return f'<ul class="{cls}">{items}</ul>' if items else ""

    keep = set()
    for ev in events:
        eid = ev.get("id") or ""
        if not re.fullmatch(r"[0-9a-f]{12}", eid):
            continue
        if f"{eid}.html" in keep:
            continue
        keep.add(f"{eid}.html")
        inst_raw = ev.get("institution", "")
        inst_slug = slugify(inst_raw)
        hub_url = f"{SITE_URL}/i/{inst_slug}.html" if inst_slug in hubs else ""
        # Autres séances du même cycle (même titre sans le numéro), puis
        # d'autres conférences de l'institution — 5 max chacune, hors self.
        series = [e for e in by_series.get(_series_key(ev), []) if e["id"] != eid][:5]
        series_ids = {e["id"] for e in series}
        others = [e for e in by_inst.get(inst_raw, [])
                  if e["id"] != eid and e["id"] not in series_ids][:5]
        n_series = len(by_series.get(_series_key(ev), []))
        m = re.search(r"\((\d+)\)", ev.get("title", "") or "")
        series_note = ""
        if m and n_series > 1:
            series_note = (f"Séance {m.group(1)} du cycle « {_esc_attr(_series_key(ev)[1])} »"
                           f" — {n_series} séances programmées.")
        title = _esc_attr(ev.get("title"))
        date_label = _date_fr(ev.get("date", "")) + (f" à {ev['time']}" if ev.get("time") else "")
        inst = _esc_attr(ev.get("institution", ""))
        loc = _esc_attr(ev.get("location", ""))
        speaker = _esc_attr(ev.get("speaker", ""))
        body_desc = _esc_attr(ev.get("description", ""))
        # Title SEO : on rajoute date + institution -> match plus de requêtes
        # long-tail (« conférence X juin 2026 », « X collège de france »).
        # Cap à ~70 caractères pour ne pas se faire tronquer dans Google.
        seo_title_full = f"{ev.get('title','')[:55]} · {_date_fr(ev.get('date',''))} · {ev.get('institution','')}"
        seo_title = _esc_attr(seo_title_full[:67])
        # Meta description : phrase naturelle + mots-clés (intervenant, lieu,
        # date) — 150 caractères, format optimal pour Google SERP.
        parts = [f"{ev.get('title','')} — conférence {('à ' + ev['location']) if ev.get('location') else 'à Paris'}"]
        parts.append(f"organisée par {ev.get('institution','')} le {_date_fr(ev.get('date',''))}")
        if ev.get("speaker"):
            parts.append(f"avec {ev['speaker'][:50]}")
        if ev.get("time"):
            parts.append(f"à {ev['time']}")
        meta_desc = _esc_attr((". ".join(parts) + ".")[:155])
        img = _esc_attr(ev.get("image") or f"{SITE_URL}/og.png")
        ext = _esc_attr(ev.get("url") or "")
        # « /?event= » et non « ../index.html?event= » : sinon Google découvre
        # des milliers de variantes index.html?… d'une même page.
        target = f"/?event={eid}"
        jsonld = _event_jsonld(ev)
        dcolor = DISC_COLORS.get(ev.get("discipline", ""), DISC_COLORS["Autre"])
        kind = _kind_of(ev)
        real_img = ev.get("image") or ""
        cover_html = (f'<div class="cover"><img src="{_esc_attr(real_img)}" alt="" loading="eager"><span class="kind">{kind}</span></div>' if real_img
                      else f'<div class="cover typo"><span class="kind">{kind}</span><b>{inst}</b></div>')
        crumbs = [("Accueil", f"{SITE_URL}/")]
        if hub_url:
            crumbs.append((inst_raw, hub_url))
        crumbs.append((ev.get("title", ""), f"{SITE_URL}/e/{eid}.html"))
        crumb_ld = json.dumps({
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                for i, (n, u) in enumerate(crumbs)]}, ensure_ascii=False).replace("</", "<\\/")
        crumb_html = " › ".join(
            f'<a href="{u}">{_esc_attr(n)}</a>' if i < len(crumbs) - 1 else _esc_attr(n)
            for i, (n, u) in enumerate(crumbs))
        inst_html = (f'<a href="{hub_url}">{inst}</a>' if hub_url else inst)
        page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{seo_title}</title>
<link rel="canonical" href="{SITE_URL}/e/{eid}.html">
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="conférence Paris, {_esc_attr(ev.get('institution',''))}, {_esc_attr((ev.get('speaker','') or ev.get('discipline','')))}, séminaire académique">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="event">
<meta property="og:url" content="{SITE_URL}/e/{eid}.html">
<meta property="og:image" content="{img}">
<meta property="og:locale" content="fr_FR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{meta_desc}">
<meta name="twitter:image" content="{img}">
<script type="application/ld+json">{jsonld}</script>
<script type="application/ld+json">{crumb_ld}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#fff;--fg:#0a0a0b;--card:#fff;--muted:#f4f4f5;--muted-fg:#71717a;--border:#e4e4e7;--primary:#18181b;--primary-fg:#fafafa}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0a0a0b;--fg:#fafafa;--card:#0e0e10;--muted:#27272a;--muted-fg:#a1a1aa;--border:#27272a;--primary:#fafafa;--primary-fg:#18181b}}}}
*{{box-sizing:border-box}}
body{{font-family:Geist,system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:24px 16px 40px;line-height:1.5;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:560px;margin:0 auto}}
.crumb{{font-size:12px;color:var(--muted-fg);margin:0 0 14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.crumb a{{color:inherit;text-decoration:none}}.crumb a:hover{{color:var(--fg)}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:16px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,.04),0 12px 32px -16px rgba(0,0,0,.25)}}
.cover{{position:relative;aspect-ratio:16/9;background:var(--muted);overflow:hidden}}
.cover img{{width:100%;height:100%;object-fit:cover;display:block}}
.cover.typo{{display:flex;align-items:flex-end;padding:18px;color:#fff;background:linear-gradient(135deg,var(--dc),color-mix(in srgb,var(--dc) 55%,#000))}}
.cover.typo::before{{content:"";position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.35) 1px,transparent 1px);background-size:16px 16px;-webkit-mask-image:radial-gradient(ellipse at top right,#000,transparent 70%);mask-image:radial-gradient(ellipse at top right,#000,transparent 70%)}}
.cover.typo b{{position:relative;font-size:22px;line-height:1.15;letter-spacing:-.01em;text-wrap:balance;text-shadow:0 1px 8px rgba(0,0,0,.35)}}
.kind{{position:absolute;top:12px;left:12px;background:rgba(255,255,255,.92);color:#18181b;font-size:11px;font-weight:600;padding:3px 8px;border-radius:6px}}
.body{{padding:20px 22px 22px}}
.badges{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}}
.badge{{display:inline-flex;align-items:center;border:1px solid var(--border);border-radius:6px;padding:2px 8px;font-size:11px;font-weight:600}}
h1{{font-size:24px;line-height:1.2;letter-spacing:-.02em;margin:0 0 14px;text-wrap:balance}}
.date{{display:flex;align-items:center;gap:12px;border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin-bottom:14px}}
.date .d{{display:flex;flex-direction:column;align-items:center;justify-content:center;background:var(--muted);border-radius:8px;min-width:56px;padding:6px 10px}}
.date .d small{{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted-fg)}}
.date .d b{{font-size:22px;line-height:1;font-variant-numeric:tabular-nums}}
.date .t{{font-size:14px}}.date .t span{{display:block;color:var(--muted-fg)}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:14px;margin:0 0 14px}}
dt{{color:var(--muted-fg)}}dd{{margin:0;overflow-wrap:anywhere}}dd a{{color:inherit;text-decoration:underline;text-underline-offset:2px}}
.desc{{font-size:14px;line-height:1.6;color:var(--muted-fg);margin:0 0 16px}}
.cta{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:4px}}
.cta a{{display:flex;align-items:center;justify-content:center;text-align:center;padding:13px 12px;border-radius:10px;font-weight:600;font-size:14px;text-decoration:none;line-height:1.2}}
.cta .site{{background:var(--primary);color:var(--primary-fg)}}
.cta .ext{{background:var(--dc);color:#fff}}
.cta a:hover{{filter:brightness(1.08)}}
@media (max-width:420px){{.cta{{grid-template-columns:1fr}}}}
.note{{font-size:12px;color:var(--muted-fg);text-align:center;margin:10px 0 0}}
h2{{font-size:13px;color:var(--muted-fg);font-weight:600;margin:22px 0 8px;text-transform:uppercase;letter-spacing:.06em}}
.rel{{list-style:none;padding:0;margin:0;border:1px solid var(--border);border-radius:10px;overflow:hidden}}
.rel li{{font-size:14px;line-height:1.4}}
.rel li+li{{border-top:1px solid var(--border)}}
.rel a{{display:flex;justify-content:space-between;gap:12px;padding:10px 12px;color:inherit;text-decoration:none}}
.rel a:hover{{background:var(--muted)}}
.rel .d{{color:var(--muted-fg);font-size:12px;white-space:nowrap;font-variant-numeric:tabular-nums}}
.more{{display:inline-block;margin-top:10px;font-size:14px;font-weight:600;color:inherit;text-decoration:none}}
.foot{{text-align:center;margin-top:24px;font-size:12px;color:var(--muted-fg)}}
.foot a{{color:inherit}}
</style>
</head>
<body>
<div class="wrap">
<nav class="crumb" aria-label="Fil d'Ariane">{crumb_html}</nav>
<main class="card" style="--dc:{dcolor}">
{cover_html}
<div class="body">
<div class="badges"><span class="badge" style="border-color:{dcolor};color:{dcolor}">{_esc_attr(ev.get('discipline',''))}</span><span class="badge">{kind}</span>{'<span class="badge">Entrée libre</span>' if str(ev.get('price','')) == '0' else ''}</div>
<h1>{title}</h1>
<div class="date"><div class="d"><small>{_wds(ev.get('date',''))}</small><b>{_dnum(ev.get('date',''))}</b><small>{_mos(ev.get('date',''))}</small></div><div class="t">{_esc_attr(date_label)}<span>{loc or 'Paris'}</span></div></div>
<dl><dt>Organisé par</dt><dd>{inst_html}</dd>{f'<dt>Avec</dt><dd>{speaker}</dd>' if speaker else ''}</dl>
{f'<p class="desc">{body_desc}</p>' if body_desc and len(body_desc) > 40 and body_desc != speaker else ''}
{f'<p class="desc">{series_note}</p>' if series_note else ''}
<div class="cta"><a class="site" href="{target}">Voir sur Lotent →</a>{f'<a class="ext" href="{ext}" rel="noopener">Page officielle · inscription ↗</a>' if ext else ''}</div>
<p class="note">Vérifie les horaires sur la page officielle avant de te déplacer.</p>
</div>
</main>
{f'<h2>Autres séances du cycle</h2>{_links(series, "rel")}' if series else ''}
{f'<h2>Prochaines conférences · {inst}</h2>{_links(others, "rel")}' if others else ''}
{f'<a class="more" href="{hub_url}">Toutes les conférences de {inst} →</a>' if hub_url else ''}
<div class="foot"><a href="{SITE_URL}/">Lotent — toutes les conférences de Paris</a> · <a href="https://github.com/kovarci/zzzz/issues" rel="noopener">Questions &amp; recommandations</a></div>
</div>
</body>
</html>
"""
        try:
            (EVENT_PAGES_DIR / f"{eid}.html").write_text(page, encoding="utf-8")
        except Exception as e:
            print(f"[WARN] event page {eid}: {e}")
    removed = 0
    for f in EVENT_PAGES_DIR.glob("*.html"):
        if f.name not in keep:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    print(f"Pages événement : {len(keep)} générées · {removed} obsolètes supprimées")


OG_FILE = OUTPUT_FILE.parent.parent / "og.png"
OG_INST_DIR = OUTPUT_FILE.parent / "og"
INST_PAGES_DIR = OUTPUT_FILE.parent.parent / "i"

# Institutions « phares » pour lesquelles on génère une page partage dédiée
# avec image OG personnalisée. Doit correspondre à INSTITUTION_SITES côté JS.
SHARE_INSTITUTIONS = [
    "Collège de France", "ENS Paris", "EHESS", "Institut Henri Poincaré",
    "Paris School of Economics", "Sciences Po", "Sorbonne Université",
    "Université PSL", "Article 1", "Sciences et Cultures",
    "Université Paris Dauphine", *NEW_INSTITUTIONS,
]


def write_institution_share_pages(events):
    """Pour chaque grande institution : 1 PNG (data/og/<slug>.png) + 1 page
    HTML (i/<slug>.html) avec balises OG dédiées et redirection vers
    l'app filtrée. Partage WhatsApp/Twitter de l'URL = aperçu propre,
    contenu indexable par Google. Régénéré à chaque scrape."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"[WARN] institution OG skipped (no Playwright): {e}")
        return

    OG_INST_DIR.mkdir(exist_ok=True)
    INST_PAGES_DIR.mkdir(exist_ok=True)

    # Stats par institution (uniquement les futures)
    today_iso = TODAY.isoformat()
    by_inst = {}
    for ev in events:
        inst = ev.get("institution", "")
        if inst not in SHARE_INSTITUTIONS:
            continue
        if ev.get("date", "") < today_iso:
            continue
        by_inst.setdefault(inst, []).append(ev)

    written_pngs, written_pages = set(), set()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        for inst in SHARE_INSTITUTIONS:
            slug = slugify(inst)
            if not slug:
                continue
            evts = by_inst.get(inst, [])
            n = len(evts)
            initial = inst[0].upper()
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&family=Space+Grotesk:wght@600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1200px; height:630px; background:#07070d; overflow:hidden; position:relative;
       font-family:'Space Grotesk',sans-serif; color:#ececf2; }}
.blob {{ position:absolute; border-radius:50%; filter:blur(120px); opacity:.55; }}
.b1 {{ width:560px; height:560px; background:#6d28d9; top:-180px; left:-120px; }}
.b2 {{ width:480px; height:480px; background:#1d4ed8; top:120px; right:-140px; }}
.b3 {{ width:430px; height:430px; background:#be185d; bottom:-200px; left:330px; }}
.grain {{ position:absolute; inset:0;
         background-image:radial-gradient(rgba(255,255,255,.03) 1px,transparent 1px);
         background-size:4px 4px; }}
.wrap {{ position:absolute; inset:0; display:flex; flex-direction:column;
        justify-content:center; padding:0 90px; }}
.brand {{ font-size:24px; font-weight:500; color:#8888a0; margin-bottom:22px;
         letter-spacing:.04em; }}
.row {{ display:flex; align-items:center; gap:32px; margin-bottom:34px; }}
.avatar {{ width:130px; height:130px; border-radius:36px; flex:0 0 130px;
          display:flex; align-items:center; justify-content:center;
          font-size:74px; font-weight:700; color:#fff;
          background:linear-gradient(135deg,#a78bfa,#60a5fa,#f472b6);
          box-shadow:0 18px 60px -10px rgba(120,100,255,.6); }}
h1 {{ font-size:56px; font-weight:700; line-height:1.05; letter-spacing:-.5px;
     background:linear-gradient(100deg,#ececf2 30%,#a78bfa 80%);
     -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.count {{ font-size:42px; font-weight:600; color:#c2c2d0;
         font-family:Inter,sans-serif; }}
.count b {{ background:linear-gradient(100deg,#a78bfa,#60a5fa);
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;
            font-weight:700; }}
.foot {{ position:absolute; bottom:48px; left:90px; right:90px;
        display:flex; justify-content:space-between; align-items:center;
        font-family:Inter,sans-serif; font-size:19px; color:#8888a0; }}
.orb {{ width:18px; height:18px; border-radius:50%; display:inline-block;
       background:linear-gradient(135deg,#a78bfa,#60a5fa,#f472b6);
       vertical-align:-3px; margin-right:9px; }}
</style></head><body>
<div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div>
<div class="grain"></div>
<div class="wrap">
  <div class="brand">CONFÉRENCES À PARIS</div>
  <div class="row">
    <div class="avatar">{initial}</div>
    <div>
      <h1>{_esc_attr(inst)}</h1>
    </div>
  </div>
  <div class="count"><b>{n}</b>&nbsp;conférence{'s' if n != 1 else ''} à venir</div>
</div>
<div class="foot">
  <span><span class="orb"></span>lotent.fr</span>
  <span>mis à jour chaque jour</span>
</div>
</body></html>"""
            tmp = OG_INST_DIR / f"_tmp_{slug}.html"
            tmp.write_text(html, encoding="utf-8")
            png_path = OG_INST_DIR / f"{slug}.png"
            try:
                pg = b.new_page(viewport={"width": 1200, "height": 630})
                pg.goto(tmp.resolve().as_uri())
                pg.wait_for_timeout(1500)
                pg.screenshot(path=str(png_path), type="png")
                pg.close()
                written_pngs.add(f"{slug}.png")
            except Exception as e:
                print(f"[WARN] OG {slug}: {e}")
            finally:
                try: tmp.unlink()
                except Exception: pass

            # Page HTML stub avec balises OG + contenu indexable
            from urllib.parse import quote
            inst_quoted = quote(inst)
            target = f"../index.html?institution={inst_quoted}"
            short = f"{n} conférence{'s' if n != 1 else ''} à venir à Paris."
            # Dédupliqué et sans le nom de l'institution : un cycle de cours
            # répète le même intervenant sur 10 séances, et certaines sources
            # remplissent « speaker » avec le nom de l'établissement.
            speakers, _seen_sp = [], set()
            for ev in evts[:40]:
                sp = (ev.get("speaker") or "").strip()[:60]
                key = sp.lower()
                if not sp or key in _seen_sp or key == inst.lower():
                    continue
                _seen_sp.add(key)
                speakers.append(sp)
            speakers_section = ""
            if speakers:
                speakers_section = "<p>Avec : " + ", ".join(_esc_attr(s) for s in speakers[:5]) + (" et d'autres" if len(speakers) > 5 else "") + ".</p>"

            # Liens vers les pages événement. Sans ça les 800+ pages e/*.html
            # ne sont atteignables que par le sitemap : Google les considère
            # comme orphelines et n'en indexe presque aucune. Ces 10 pages
            # institution servent de hubs de crawl vers l'ensemble du site.
            _MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.",
                     "août", "sept.", "oct.", "nov.", "déc."]
            items = []
            for ev in evts[:60]:
                eid = ev.get("id") or ""
                if not re.fullmatch(r"[0-9a-f]{12}", eid):
                    continue
                try:
                    d = date.fromisoformat(ev.get("date", ""))
                    when = f"{d.day} {_MOIS[d.month - 1]}"
                except Exception:
                    when = ""
                items.append(
                    f'<li><a href="../e/{eid}.html">'
                    f'<span class="d">{_esc_attr(when)}</span>'
                    f'{_esc_attr((ev.get("title") or "")[:110])}</a></li>')
            events_section = ""
            if items:
                events_section = ("<h2>Prochaines conférences</h2><ul class=\"evts\">"
                                  + "".join(items) + "</ul>")
            page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc_attr(inst)} — Conférences à Paris</title>
<link rel="canonical" href="{SITE_URL}/i/{slug}.html">
<meta name="description" content="{_esc_attr(short)} Calendrier mis à jour chaque jour sur lotent.fr.">
<meta property="og:title" content="{_esc_attr(inst)} — {n} conférence{'s' if n != 1 else ''} à venir">
<meta property="og:description" content="{_esc_attr(short)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}/i/{slug}.html">
<meta property="og:image" content="{SITE_URL}/data/og/{slug}.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="fr_FR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_esc_attr(inst)} — {n} conférences à venir">
<meta name="twitter:description" content="{_esc_attr(short)}">
<meta name="twitter:image" content="{SITE_URL}/data/og/{slug}.png">
<style>
body{{font-family:Inter,system-ui,sans-serif;background:#07070d;color:#ececf2;margin:0;
display:flex;align-items:flex-start;justify-content:center;min-height:100vh;padding:22px;box-sizing:border-box}}
h2{{font-size:15px;margin:26px 0 10px;color:#8888a0;font-weight:600;
letter-spacing:.04em;text-transform:uppercase}}
ul.evts{{list-style:none;padding:0;margin:0}}
ul.evts li{{border-top:1px solid rgba(255,255,255,.08)}}
ul.evts a{{display:flex;gap:12px;padding:11px 2px;color:#c2c2d0;
text-decoration:none;font-size:14px;line-height:1.45}}
ul.evts a:hover{{color:#fff}}
ul.evts .d{{flex:0 0 62px;color:#8888a0;font-variant-numeric:tabular-nums}}
.card{{max-width:560px;width:100%;background:linear-gradient(160deg,#1c1c2eb8,#11111db8);
border:1px solid rgba(255,255,255,.14);border-radius:18px;padding:28px}}
.k{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8888a0;margin-bottom:10px}}
h1{{font-size:26px;line-height:1.25;margin:0 0 14px}}
p{{color:#c2c2d0;font-size:14.5px;line-height:1.7;margin:8px 0}}
.btn{{display:block;text-align:center;margin-top:22px;padding:13px;border-radius:12px;font-weight:600;
text-decoration:none;color:#fff;background:linear-gradient(120deg,#7c5cff,#3f7dff)}}
.foot{{text-align:center;margin-top:18px;font-size:12px}}
.foot a{{color:#8888a0}}
.crumb{{font-size:12px;color:#8888a0;margin-bottom:14px}}
.crumb a{{color:#8ab4ff;text-decoration:none}}
h2{{font-size:14px;color:#8888a0;margin:22px 0 8px;font-weight:600}}
.rel{{list-style:none;padding:0;margin:0}}
.rel li{{font-size:13.5px;line-height:1.5;margin:4px 0}}
.rel a{{color:#c2c2d0;text-decoration:none}}
.rel a:hover{{color:#fff}}
.rel .d{{color:#8888a0;font-size:12px}}
p a{{color:#8ab4ff;text-decoration:none}}
</style>
</head>
<body>
<main class="card">
<div class="k">Conférences à Paris</div>
<h1>{_esc_attr(inst)}</h1>
<p><strong>{n} conférence{'s' if n != 1 else ''} à venir</strong> dans le calendrier Lotent.</p>
{speakers_section}
{events_section}
<a class="btn" href="{target}">Voir le calendrier →</a>
<div class="foot"><a href="{SITE_URL}">lotent.fr — toutes les conférences académiques de Paris</a></div>
</main>
</body>
</html>
"""
            (INST_PAGES_DIR / f"{slug}.html").write_text(page, encoding="utf-8")
            written_pages.add(f"{slug}.html")
        b.close()

    # Nettoyage : si une institution est retirée de SHARE_INSTITUTIONS,
    # supprimer ses anciens fichiers.
    for f in OG_INST_DIR.glob("*.png"):
        if f.name not in written_pngs:
            try: f.unlink()
            except Exception: pass
    for f in INST_PAGES_DIR.glob("*.html"):
        if f.name not in written_pages:
            try: f.unlink()
            except Exception: pass
    print(f"Pages institution : {len(written_pages)} HTML + {len(written_pngs)} PNG")


def write_og_image(events):
    """Re-render og.png (1200x630) with the current event count baked in,
    so any share of lotent.fr unfurls with today's live numbers instead
    of a stale figure. Uses Playwright (already needed for scraping)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"[WARN] og.png skipped (no Playwright): {e}")
        return
    n = len(events)
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&family=Space+Grotesk:wght@600;700&display=swap');
* { margin:0; padding:0; box-sizing:border-box; }
body { width:1200px; height:630px; background:#07070d; overflow:hidden;
       position:relative; font-family:'Space Grotesk',sans-serif; color:#ececf2; }
.blob { position:absolute; border-radius:50%; filter:blur(120px); opacity:.55; }
.b1 { width:560px; height:560px; background:#6d28d9; top:-180px; left:-120px; }
.b2 { width:480px; height:480px; background:#1d4ed8; top:120px; right:-140px; }
.b3 { width:430px; height:430px; background:#be185d; bottom:-200px; left:330px; }
.grain { position:absolute; inset:0;
         background-image:radial-gradient(rgba(255,255,255,.03) 1px,transparent 1px);
         background-size:4px 4px; }
.wrap { position:absolute; inset:0; display:flex; flex-direction:column;
        justify-content:center; padding:0 90px; }
.orb { width:34px; height:34px; border-radius:50%;
       background:linear-gradient(135deg,#a78bfa,#60a5fa,#f472b6);
       display:inline-block; vertical-align:middle; margin-right:16px; }
.brand { font-size:30px; font-weight:600; color:#c2c2d0;
         display:flex; align-items:center; margin-bottom:34px; }
h1 { font-size:74px; font-weight:700; line-height:1.12; letter-spacing:-1px;
     background:linear-gradient(100deg,#ececf2 20%,#a78bfa 55%,#60a5fa 80%);
     -webkit-background-clip:text; -webkit-text-fill-color:transparent;
     margin-bottom:34px; }
.sub { font-family:Inter,sans-serif; font-size:27px; color:#9a9ab2;
       line-height:1.5; max-width:900px; }
.badges { position:absolute; bottom:54px; left:90px; display:flex; gap:14px;
          font-family:Inter,sans-serif; }
.badge { font-size:20px; padding:10px 22px; border-radius:999px;
         border:1px solid rgba(255,255,255,.16);
         background:rgba(255,255,255,.05); color:#c2c2d0; }
.badge b { color:#fff; }
</style></head><body>
<div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div>
<div class="grain"></div>
<div class="wrap">
  <div class="brand"><span class="orb"></span>lotent.fr</div>
  <h1>Toutes les conférences<br>académiques de Paris.</h1>
  <div class="sub">Collège de France · ENS · EHESS · Sorbonne · Sciences Po · IHP · PSE · PSL — mis à jour chaque jour.</div>
</div>
<div class="badges">
  <span class="badge"><b>__N__</b>&nbsp;événements à venir</span>
  <span class="badge">Gratuit, sans compte</span>
  <span class="badge">Carte · Agenda · iCal</span>
</div>
</body></html>""".replace("__N__", str(n))
    tmp = OG_FILE.parent / "_og_template.html"
    tmp.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            pg = b.new_page(viewport={"width": 1200, "height": 630})
            pg.goto(tmp.resolve().as_uri())
            pg.wait_for_timeout(1800)  # webfont load
            pg.screenshot(path=str(OG_FILE), type="png")
            b.close()
        print(f"og.png régénéré avec {n} événements")
    except Exception as e:
        print(f"[WARN] og.png render: {e}")
    finally:
        try: tmp.unlink()
        except Exception: pass


SITEMAP_FILE = OUTPUT_FILE.parent.parent / "sitemap.xml"

# IndexNow (Bing) — propre clé persistante. Le fichier <key>.txt servi à la
# racine du domaine prouve qu'on contrôle bien le site.
INDEXNOW_KEY = "8c5d9e1f4a2b6e3d7c5f8a1b9d2e4c6f"
INDEXNOW_KEY_FILE = OUTPUT_FILE.parent.parent / f"{INDEXNOW_KEY}.txt"


def notify_indexnow(urls):
    """Ping IndexNow (Bing, Yandex) avec la liste d'URLs qui viennent
    d'apparaître/changer — indexation quasi-immédiate côté Bing."""
    urls = [u for u in urls if u.startswith("http")]
    if not urls:
        return
    # Crée la clé-fichier à la racine si manquante
    if not INDEXNOW_KEY_FILE.exists():
        INDEXNOW_KEY_FILE.write_text(INDEXNOW_KEY, encoding="utf-8")
    payload = {
        "host": "lotent.fr",
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls[:10000],   # IndexNow accepte jusqu'à 10 000 URLs/batch
    }
    try:
        r = requests.post("https://api.indexnow.org/IndexNow",
                          json=payload, timeout=20,
                          headers={"Content-Type": "application/json; charset=utf-8"})
        # 200 OK · 202 Accepted (déjà reçu, en traitement) sont les succès
        print(f"IndexNow : {len(urls)} URLs envoyées (HTTP {r.status_code})")
    except Exception as e:
        print(f"[WARN] IndexNow: {type(e).__name__}: {e}")


def write_sitemap(events):
    """sitemap.xml at the site root: home, about, the institution hubs and
    every UPCOMING event page.

    Past events keep their e/<id>.html page — old shared links must not
    break — but they are deliberately left out of the sitemap. Asking
    Google to index 2000+ expired conferences burns the crawl budget of a
    young site, and none of them can rank anyway. Only pages that are
    still worth ranking get submitted.
    """
    today = TODAY.isoformat()
    urls = [f"<url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>",
            f"<url><loc>{SITE_URL}/apropos.html</loc><changefreq>monthly</changefreq></url>"]
    # Hubs par institution : ce sont eux qui lient vers les pages événement,
    # ils doivent être crawlés souvent.
    for f in sorted(INST_PAGES_DIR.glob("*.html")):
        urls.append(f"<url><loc>{SITE_URL}/i/{f.name}</loc>"
                    f"<lastmod>{today}</lastmod><changefreq>weekly</changefreq></url>")
    seen, n_past = set(), 0
    for ev in events:
        eid = ev.get("id") or ""
        if not re.fullmatch(r"[0-9a-f]{12}", eid) or eid in seen:
            continue
        if ev.get("date", "") < today:
            n_past += 1
            continue
        seen.add(eid)
        # lastmod = date d'ajout réelle. Estampiller « aujourd'hui » des
        # milliers de pages inchangées apprend à Google à ignorer le champ.
        lastmod = ev.get("added_at") or today
        urls.append(f"<url><loc>{SITE_URL}/e/{eid}.html</loc>"
                    f"<lastmod>{lastmod}</lastmod></url>")
    xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
           "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
           + "".join(urls) + "</urlset>")
    try:
        SITEMAP_FILE.write_text(xml, encoding="utf-8")
        print(f"Sitemap : {len(urls)} URLs ({n_past} pages archivées "
              f"laissées en ligne mais non soumises)")
    except Exception as e:
        print(f"[WARN] sitemap: {e}")


# Mots-clés qui signalent un événement marquant (gros invité, leçon rare…)
_DIGEST_KW = re.compile(
    r"nobel|fields|médaille|ancien(?:ne)? (?:premier )?ministre|ambassad|"
    r"président|prix\b|inaugural|leçon (?:inaugurale|de clôture)|"
    r"académie|colloque international", re.I)
_DIGEST_WEIGHT = {
    "Collège de France": 3, "Sciences et Cultures": 2.5, "ENS Paris": 2,
    "EHESS": 1.5, "Sciences Po": 1.5, "Sorbonne Université": 1.5,
    "Institut Henri Poincaré": 1, "Paris School of Economics": 1,
    "Université PSL": 1, "Article 1": 1,
}


def build_digest(events):
    """Pick the ~10 'immanquables' of the next 7 days and write
    data/digest.json (for the site's strip) + data/digest.xml (RSS feed).
    Heuristic: institution weight + headline keywords + has speaker/time,
    capped at 2 events per institution for variety."""
    end = TODAY + timedelta(days=7)
    pool = [e for e in events
            if TODAY.isoformat() <= e.get("date", "") <= end.isoformat()
            and not e.get("kind")                 # soutenances / carrières : catégories à part
            and not is_junk_title(e.get("title", ""))]

    def score(e):
        s = _DIGEST_WEIGHT.get(e.get("institution"), 0.5)
        if _DIGEST_KW.search(f"{e.get('title', '')} {e.get('description', '')} {e.get('speaker', '')}"):
            s += 3
        if e.get("speaker"):
            s += 0.7
        if e.get("time"):
            s += 0.3
        if e.get("source_type") == "luma":
            s -= 1.5
        return s

    pool.sort(key=score, reverse=True)
    picked, per_inst = [], {}
    for e in pool:
        inst = e.get("institution")
        if per_inst.get(inst, 0) >= 2:
            continue
        picked.append(e)
        per_inst[inst] = per_inst.get(inst, 0) + 1
        if len(picked) >= 10:
            break
    picked.sort(key=lambda e: (e["date"], e.get("time", "")))

    period = f"du {_date_fr(TODAY.isoformat())} au {_date_fr(end.isoformat())}"
    try:
        DIGEST_FILE.write_text(json.dumps(
            {"generated": TODAY.isoformat(), "period": period, "events": picked},
            ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] digest write: {e}")

    items = []
    for e in picked:
        link = f"{SITE_URL}/e/{e['id']}.html"
        d = _date_fr(e.get("date", "")) + (f" à {e['time']}" if e.get("time") else "")
        items.append(
            f"<item><title>{_esc_attr(e['title'])}</title>"
            f"<link>{link}</link><guid isPermaLink=\"true\">{link}</guid>"
            f"<description>{_esc_attr(d + ' — ' + e.get('institution', '') + (' · ' + e['location'] if e.get('location') else ''))}</description>"
            f"</item>")
    rss = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
           "<rss version=\"2.0\"><channel>"
           "<title>Lotent — les immanquables de la semaine</title>"
           f"<link>{SITE_URL}</link>"
           "<description>Les conférences à ne pas manquer cette semaine à Paris, sélection automatique.</description>"
           "<language>fr</language>"
           + "".join(items) + "</channel></rss>")
    try:
        RSS_FILE.write_text(rss, encoding="utf-8")
    except Exception as e:
        print(f"[WARN] rss write: {e}")
    print(f"Digest : {len(picked)} immanquables ({period})")


def load_previous_events():
    """Read the events.json from the previous run (or [] if none)."""
    try:
        return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def update_archive(previous_events):
    """Move events that have aged into the past from the previous events.json
    into the persistent archive. Used by the site's 'Historique' tab."""
    try:
        archive = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        archive = []
    today_iso = TODAY.isoformat()
    seen = {e.get("id") for e in archive if e.get("id")}
    added = 0
    for e in previous_events:
        if (e.get("date", "") < today_iso and e.get("id")
                and e["id"] not in seen):
            archive.append(e)
            seen.add(e["id"])
            added += 1
    # Cap: keep only the last ARCHIVE_MAX_DAYS days
    cutoff = (TODAY - timedelta(days=ARCHIVE_MAX_DAYS)).isoformat()
    archive = [e for e in archive if e.get("date", "") >= cutoff]
    # Sort: most recent past first
    archive.sort(key=lambda e: (e.get("date", ""), e.get("time", "")), reverse=True)
    try:
        # Minified: the browser downloads this file, indentation costs ~40%
        ARCHIVE_FILE.write_text(json.dumps(archive, ensure_ascii=False,
                                           separators=(",", ":")),
                                encoding="utf-8")
        print(f"Archive: +{added} new past events, total {len(archive)}")
    except Exception as e:
        print(f"[WARN] archive write: {e}")


def main():
    prev_events = load_previous_events()
    all_events = []

    try:
        all_events.extend(scrape_indico(
            "Institut Henri Poincaré", "https://indico.math.cnrs.fr", "0",
            "IHP, 11 rue Pierre et Marie Curie, Paris 5e"))
    except Exception as e:
        print(f"[ERROR] IHP: {e}")
        traceback.print_exc()

    try:
        all_events.extend(scrape_sciences_cultures())
    except Exception as e:
        print(f"[ERROR] Sciences et Cultures: {e}")
        traceback.print_exc()

    for fn in STATIC_SOURCES + [scrape_que_faire_a_paris]:
        try:
            all_events.extend(fn())
        except Exception as e:
            print(f"[ERROR] {fn.__name__}: {e}")
            traceback.print_exc()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            for fn in [scrape_college_de_france, scrape_ehess, scrape_ens,
                       scrape_sciences_po, scrape_sorbonne, scrape_dauphine,
                       scrape_pse, scrape_psl, scrape_luma, scrape_article1]:
                try:
                    all_events.extend(fn(browser))
                except Exception as e:
                    print(f"[ERROR] {fn.__name__}: {e}")
                    traceback.print_exc()
        finally:
            browser.close()

    # Compteurs du scrape FRAIS, avant carry-forward : c'est le seul instant
    # où l'on voit ce que chaque source a réellement rendu aujourd'hui. Une
    # fois le report appliqué, une source morte garde ses anciens événements
    # et paraît vivante — c'est ainsi qu'Article 1 est resté cassé sans
    # déclencher la moindre alerte. check_health.py lit ces compteurs.
    fresh_counts = {}
    for e in all_events:
        k = e.get("institution") or "?"
        fresh_counts[k] = fresh_counts.get(k, 0) + 1
    update_meta("fresh_counts", fresh_counts)

    # Carry-forward: union this run with the still-upcoming events from the
    # previous run, per known source (and Luma). A flaky scrape (slow site, a
    # page that timed out, partial pagination, a geo-blocked Luma) therefore can
    # never shrink or wipe a source — at worst the site keeps yesterday's events
    # until their date passes. Dedup by id below removes the overlap; past
    # events are filtered out and archived, so the dataset stays bounded.
    KNOWN_SOURCES = {
        "Institut Henri Poincaré", "Collège de France", "Paris School of Economics",
        "Université PSL", "EHESS", "ENS Paris", "Sciences Po", "Sorbonne Université",
        "Université Paris Dauphine", *NEW_INSTITUTIONS,
    }
    present_ids = {e.get("id") for e in all_events}
    today_iso = TODAY.isoformat()
    carried = 0
    for e in prev_events:
        if not (e.get("institution") in KNOWN_SOURCES
                or e.get("source_type") in ("luma", "association", "ville", "entreprise")):
            continue
        if e.get("date", "") < today_iso:
            continue  # past event — the archive handles it, don't resurrect
        if e.get("id") in present_ids:
            continue
        all_events.append(e)
        present_ids.add(e.get("id"))
        carried += 1
    if carried:
        print(f"⚠ Carried forward {carried} upcoming events from the previous run")

    all_events = merge_cross_source(_drop_city_duplicates(deduplicate(all_events)))
    # Titres parasites (menus lus comme événements) — y compris reportés
    all_events = [e for e in all_events if not is_junk_title(e.get("title", ""))]
    for e in all_events:                  # toutes sources, anciennes comprises
        reclassify(e)
        if _SOUTENANCE.search(e.get("title", "")):
            e["kind"] = "soutenance"
        if _MEMBERS_ONLY.search(f"{e.get('title', '')} {e.get('description', '')}"):
            e["members"] = True

    # Date d'ajout : on garde celle de prev_events si l'id existait déjà,
    # sinon TODAY → le frontend tague "nouveau" tout ce qui a < 48 h.
    prev_added = {e.get("id"): e.get("added_at") for e in prev_events if e.get("id")}
    today_iso = TODAY.isoformat()
    for ev in all_events:
        if ev.get("id"):
            ev["added_at"] = prev_added.get(ev["id"]) or today_iso
    all_events = [e for e in all_events if e.get("date", "") >= CUTOFF.isoformat()]
    all_events.sort(key=lambda e: (e["date"], e.get("time", "")))

    try:
        geocode_all(all_events)
    except Exception as e:
        print(f"[ERROR] geocoding: {e}")
        traceback.print_exc()

    try:
        write_ics(all_events)
    except Exception as e:
        print(f"[ERROR] ics: {e}")
        traceback.print_exc()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, separators=(",", ":"))

    try:
        update_archive(prev_events)
    except Exception as e:
        print(f"[ERROR] archive: {e}")
        traceback.print_exc()

    # Per-event share pages (current + archived, so old shared links survive)
    try:
        arch = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        arch = []
    try:
        write_event_pages(all_events + arch)
    except Exception as e:
        print(f"[ERROR] event pages: {e}")
        traceback.print_exc()

    # Avant le sitemap : celui-ci liste les hubs i/*.html réellement présents.
    try:
        write_institution_share_pages(all_events)
    except Exception as e:
        print(f"[ERROR] institution pages: {e}")
        traceback.print_exc()

    try:
        write_sitemap(all_events + arch)
    except Exception as e:
        print(f"[ERROR] sitemap: {e}")
        traceback.print_exc()

    try:
        write_og_image(all_events)
    except Exception as e:
        print(f"[ERROR] og image: {e}")
        traceback.print_exc()

    # Notifie Bing/Yandex des nouveautés du jour pour accélérer l'indexation.
    try:
        fresh_urls = [f"{SITE_URL}/e/{e['id']}.html" for e in all_events
                      if e.get("added_at") == today_iso and re.fullmatch(r"[0-9a-f]{12}", e.get("id") or "")]
        # Ping aussi la home + sitemap + hubs institution : leur liste de
        # prochaines conférences a changé en même temps, et ce sont eux qui
        # mènent Bing vers les nouvelles pages événement.
        if fresh_urls:
            hubs = [f"{SITE_URL}/i/{f.name}"
                    for f in sorted(INST_PAGES_DIR.glob("*.html"))]
            fresh_urls = ([f"{SITE_URL}/", f"{SITE_URL}/sitemap.xml"]
                          + hubs + fresh_urls)
            notify_indexnow(fresh_urls)
    except Exception as e:
        print(f"[WARN] IndexNow ping: {e}")

    try:
        build_digest(all_events)
    except Exception as e:
        print(f"[ERROR] digest: {e}")
        traceback.print_exc()

    update_meta("last_workflow_run")

    by_inst = {}
    for e in all_events:
        by_inst[e["institution"]] = by_inst.get(e["institution"], 0) + 1
    n_luma = sum(1 for e in all_events if e.get("source_type") == "luma")
    print(f"\n{'='*50}")
    print(f"✓ TOTAL: {len(all_events)} events ({len(all_events) - n_luma} institutions · {n_luma} Luma)")
    for inst, n in sorted(by_inst.items(), key=lambda x: -x[1]):
        print(f"   {n:4d}  {inst}")


if __name__ == "__main__":
    main()
