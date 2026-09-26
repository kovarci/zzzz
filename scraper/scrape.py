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
import os
import re
import time
import traceback
from datetime import datetime, date, timedelta, timezone
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
        "medieval", "archaeolog", "paléolithi", "palaeolithi", "paleolithi", "prehistor",
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
        # Collège de France, sept. 2026 : séminaires d'informatique et de
        # paléoanthropologie restés en « Autre »
        "programmation", "programming", "cryptograph", "hominin", " evolution",
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
    "Institut des actuaires": "Économie", "École polytechnique": "Sciences",
    "IHES": "Mathématiques", "Labos de maths d'Île-de-France": "Mathématiques", "IPGP": "Sciences",
    "Maison de l'Amérique latine": "Littérature", "Institut culturel italien": "Arts & Culture",
    "Maison de la culture du Japon": "Arts & Culture",
    "Académie nationale de médecine": "Sciences",
    "Académie des inscriptions et belles-lettres": "Histoire",
    "Mines Paris - PSL": "Sciences",
    "Musée de l'Homme": "Sociologie & Anthropologie",
    "Ined": "Sociologie & Anthropologie",
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


# Mots-clés qui se déclenchaient au milieu d'autres mots : « théâtre » dans
# « amphithéâtre » (lieu de presque tous les séminaires), « tribu » dans
# « contribution », « évolution » dans « révolution », « astronom » dans
# « gastronomie », « ricci » (flot de Ricci) dans « Matteo Ricci »… Préfixes
# (ou mots entiers, pour « ricci ») qui annulent la correspondance.
_KW_NOT_AFTER = {
    "théâtre": ("amphi",), "tribu": ("con", "dis", "at", "rétri"), "évolution": ("r",),
    "moire": ("mé",), "pensée": ("dis", "récom"), "élection": ("s",), "tax": ("syn",),
    "rituel": ("spi",), "étale": ("soci", "vég"), "opera": ("co",), "astronom": ("g",),
    "terrain": ("sou",), "dance ": ("correspon", "dépen", "abun", "atten", "gui", "indépen"),
}
_KW_NOT_BEFORE = {"ricci": re.compile(r"(matteo|institut) ricci")}


def _kw_hit(kw, text):
    if kw not in text:
        return False
    pre = _KW_NOT_AFTER.get(kw)
    if pre:
        return any(not text[:m.start()].endswith(pre) for m in re.finditer(re.escape(kw), text))
    if kw in _KW_NOT_BEFORE:
        return not _KW_NOT_BEFORE[kw].search(text)
    return True


def detect_discipline(title: str, description: str = "",
                      institution: str = "",
                      luma_categories=None) -> str:
    text = " " + (title + " " + description).lower() + " "
    scores = {}
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        score = sum(1 for kw in keywords if _kw_hit(kw, text))
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
    r"la r[ée]union|guadeloupe|martinique|guyane|mayotte|nouvelle-cal[ée]donie|polyn[ée]sie|"
    # Sites du Muséum et partenaires Inalco hors Île-de-France
    r"menton|concarneau|dinard|eyzies|s[ée]rignan|pessac)\b",
    re.I,
)

# « 2 rue de Lille, Paris 7e » (Maison de la Recherche de l'Inalco), « rue de
# Rennes », « boulevard de Strasbourg », « gare de Lyon » : des adresses
# parisiennes, pas Lille ni Rennes. Tous les tests « hors Paris » passent par ici.
_STREET_BEFORE = re.compile(
    r"\b(rue|avenue|av\.?|boulevard|bd|place|pl\.|quai|cours|passage|impasse|square|all[ée]e|"
    r"gare|porte|faubourg|fbg|villa|cit[ée]|chauss[ée]e|route|chemin|pont|h[ôo]tel)\s+"
    r"(de\s+la\s+|de\s+|du\s+|des\s+|d['’]\s*)?$", re.I)


def _names_city(rx, text):
    """Première ville de `rx` nommée dans `text` (match truthy), en ignorant
    les rues parisiennes qui portent un nom de ville."""
    text = text or ""
    for m in rx.finditer(text):
        if not _STREET_BEFORE.search(text[max(0, m.start() - 30):m.start()]):
            return m
    return None


def _non_paris(text):
    return _names_city(NON_PARIS, text)


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
# Catégories de gestion et d'appels à projets (IHP « Gestion - CEB », « Call
# for proposals / appel à projets ») : fiches internes, pas des événements.
_INDICO_ADMIN = re.compile(r"\bgestion\b|call for proposals|appels? [àa] projets|\badmin\b", re.I)


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
        if dt_end and dt_end.date() == dt.date():   # pas l'heure du dernier jour d'un colloque
            end_time = dt_end.strftime("%H:%M")
        if skip_meetings and (item.get("type") == "meeting" or _INDICO_INTERNAL.search(title)):
            continue
        if _INDICO_ADMIN.search(clean_text(item.get("category", ""))) or re.search(r"\s[-–]\s*admin$", title, re.I):
            continue
        where = " ".join(clean_text(item.get(k, "")) for k in ("location", "room", "address"))
        if keep_loc and not keep_loc.search(where):
            continue
        location = (clean_text(item.get("location", "")) or clean_text(item.get("room", ""))
                    or location_default)
        # Indico CNRS-math is nationwide — keep only Paris-area events
        if _non_paris(location):
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


MATHS_IDF = "Labos de maths d'Île-de-France"


def scrape_indico_maths():
    """indico.math.cnrs.fr est national. On lisait toute l'instance (catégorie
    0) : un séminaire de Lyon ou de Bordeaux sans lieu recevait l'adresse de
    l'IHP. On ne lit plus que la catégorie « Région parisienne » (6) — IHP
    (107), IHES (57), Jussieu, CEREMADE, LAGA, CERMICS… — et, parmi les
    conférences (55) et GDR (24) nationaux, ceux qui ont lieu en Île-de-France."""
    base = "https://indico.math.cnrs.fr"
    ihp = scrape_indico("Institut Henri Poincaré", base, "107",
                        "IHP, 11 rue Pierre et Marie Curie, Paris 5e")
    ihes = scrape_indico("IHES", base, "57", "IHES, 35 route de Chartres, Bures-sur-Yvette")
    seen = {e["url"] for e in ihp + ihes}
    rest = [e for e in scrape_indico(MATHS_IDF, base, "6",
                                     "Île-de-France — lieu précisé sur la page de l'événement")
            if e["url"] not in seen]
    for categ in ("55", "24"):
        rest += [e for e in scrape_indico(MATHS_IDF, base, categ, "", keep_loc=_IDF_RE)
                 if e["url"] not in seen]
    out, urls = ihp + ihes, set(seen)
    for e in rest:
        if e["url"] in urls:
            continue
        urls.add(e["url"])
        if re.search(r"\bIHP\b|Henri Poincar", e["location"]):
            e["institution"] = "Institut Henri Poincaré"
        elif re.search(r"\bIHES\b|Bois-Marie", e["location"]):
            e["institution"] = "IHES"
        e["id"] = make_id(e["institution"], e["title"], e["date"])
        out.append(e)
    for e in out:
        if e["discipline"] not in ("Mathématiques", "Sciences"):
            e["discipline"] = "Mathématiques"
    print(f"   ✓ Total Indico maths Île-de-France: {len(out)} events")
    return out


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

def scrape_paginated(browser, name, agenda_urls, max_pages=15, source_type="institution",
                     page_fmt=None, page_start=2):
    """Scrape paginated agendas, trying BOTH ?page=N and /page/N/ URL styles
    (different CMS use different pagination). agenda_urls = [(url, loc, base), ...].
    page_fmt : motif propre au site (« {url}/{n}/ » chez Sciences Po, dont la
    2e page est /1/ : page_start=1), essayé seul à la place des deux styles
    génériques."""
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

        if page_fmt:
            for n in range(page_start, max_pages):
                if not harvest(page_fmt.format(url=base_url.rstrip("/"), n=n),
                               location, site_base, f"page {n}"):
                    break
            continue

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


_NAME_PARTICLE = re.compile(r"^(de|du|des|d['’]\S*|van|von|der|den|la|le|di|da|dit|ben|bin|al|el|y|e|of)$", re.I)


def _person_names(s):
    """Noms de personnes d'une ligne d'intervenants (même règle que
    splitSpeakers() dans web/src/lib.js) : « Aurèle Méthivier & Sandra
    Boehringer » → 2 noms, « Agir pour l'éducation » → aucun."""
    x = s or ""
    while True:
        y = re.sub(r"\([^()]*\)", " ", x)
        if y == x:
            break
        x = y
    out = []
    for t in re.split(r"\s*(?:[,;&/]|\s(?:et|and)\s)\s*", x):
        w = t.split()
        if 2 <= len(w) <= 5 and all(v[:1].isupper() or _NAME_PARTICLE.match(v) for v in w) and w[0][:1].isupper():
            out.append(" ".join(w))
    return out


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

    # Budget large : le Collège de France n'est plus lu que par maj.bat (le robot
    # GitHub est bloqué) et son agenda dépasse 17 pages de 30.
    deadline = time.monotonic() + 420  # hard wall-clock budget for the whole source
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
            speaker = clean_text(speaker_el.get_text()) if speaker_el else ""
            # Certains « grands événements » rangent ici leur sous-titre
            # (« Forum Éducation 2026 » / « Agir pour l'éducation ») : pas un
            # intervenant — la fiche proposait de le « suivre ».
            if speaker and not _person_names(speaker):
                desc, speaker = " · ".join(x for x in (desc, speaker) if x), ""
            events.append(new_event(
                "Collège de France", title, d, time_str=time_str,
                location=clean_text(place_el.get_text()) if place_el else LOC_DEFAULT,
                desc=desc,
                speaker=speaker,
                url=make_absolute(href, BASE),
            ))
            # Le nom de l'intervenant est rangé DANS le titre de la carte
            # (« Pauvreté, migration et protection sociale Esther Duflo ») et
            # s'affichait deux fois. Titre affiché = le seul intitulé ; l'id
            # reste calculé sur l'ancien texte : favoris, liens e/<id> et
            # UID des agendas abonnés ne changent pas.
            dec = title_el.select_one(".card-event__title-decorator")
            shown = clean_text(dec.get_text()) if dec else ""
            if len(shown) >= 4:
                events[-1]["title"] = shown
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
        # Jusqu'à la fin de l'agenda (2 pages vides d'affilée) : bornée à 11
        # pages, la boucle s'arrêtait à ~350 cours sur ~500.
        for p in range(1, 60):
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


def scrape_ehess(browser=None):
    """Dedicated EHESS parser — events are .jnews-event-card elements
    (.jnews-event-title for the title, .chiffre-cle + .month for the date)."""
    print("→ EHESS (dedicated parser)...")
    events, seen = [], set()
    BASE = "https://www.ehess.fr"
    LOC = "EHESS, 54 boulevard Raspail, Paris 6e"
    LOC_CONDORCET = "EHESS, Campus Condorcet, 2 cours des Humanités, Aubervilliers"

    url = "https://www.ehess.fr/jcms/kmo_28682/fr/agenda-de-l-ehess"
    # Page brute d'abord : une fois le JavaScript exécuté (Playwright), les
    # cartes perdent leur attribut data-jalios-url et tous les liens
    # retombaient sur la page d'accueil. Navigateur en secours seulement.
    html = ""
    try:
        r = requests.get(url, headers=CDF_HEADERS, timeout=40)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"   [warn] EHESS sans navigateur : {e}")
    if "jnews-event-card" not in html and browser is not None:
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"], locale="fr-FR",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
        )
        page = ctx.new_page()
        html, _ = load_page(page, url)
        ctx.close()

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(".jnews-event-card")
    print(f"   found {len(cards)} .jnews-event-card")
    if cards:
        print(f"   [SAMPLE CARD] {clean_text(str(cards[0]))[:650]}")

    stats = {"no_title": 0, "no_date": 0, "past": 0, "too_far": 0, "kept": 0, "off": 0}
    for card in cards:
        title_el = card.select_one(".jnews-event-title")
        title = clean_text(title_el.get_text()) if title_el else ""
        if not title or is_junk_title(title):
            stats["no_title"] += 1
            continue
        # Type (« Colloque », « Journé(e) d'études », « Soutenance HDR »…) et
        # ville (« Paris », « Aubervilliers », « Brasilia - Brésil »)
        cat = " · ".join(t for t in (clean_text(x.get_text()) for x in card.select(".meta-cat"))
                         if t and t.upper() != "EHESS")
        cat = re.sub(r"(?i)journ[ée]\(e\)", "Journée", cat)
        if re.search(r"vie (étudiante|de l'école)|réunion|inscription", cat, re.I):
            stats["off"] += 1
            continue
        pin = card.select_one(".caption p.subtitle")
        where = clean_text(pin.get_text()) if pin else ""
        if where and not re.search(r"\bparis\b", where, re.I):
            if not _IDF_RE.search(where):
                stats["off"] += 1          # colloque à Brasilia, Marseille…
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
        # …ou la carte est elle-même le lien : <a class="jnews-event-card" href="jcms/…">
        href = card.get("data-jalios-url", "") or card.get("href", "")
        if not href:
            link = card.find("a", href=True)
            href = link.get("href", "") if link else ""
        key = (title[:60].lower(), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        stats["kept"] += 1
        # Une partie de l'EHESS est au Campus Condorcet : ces événements
        # étaient placés boulevard Raspail (carte, « Près de moi »).
        loc = (LOC_CONDORCET if re.search(r"aubervilliers|condorcet", where, re.I)
               else LOC if not where or re.search(r"\bparis\b", where, re.I) else f"{where}, EHESS")
        events.append(new_event("EHESS", title, d, time_str=time_str, desc=cat,
                                location=loc, url=make_absolute(href, BASE)))
        if re.search(r"soutenance", cat, re.I):
            events[-1]["kind"] = "soutenance"
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
    # Pages suivantes : /fr/evenements/1/, /2/… (numérotées à partir de 0) ;
    # ?page=N et /page/N/ renvoyaient la 1re page : 20 événements sur ~30.
    return scrape_paginated(browser, "Sciences Po", [
        ("https://www.sciencespo.fr/fr/evenements/",
         "Sciences Po, 27 rue Saint-Guillaume, Paris 7e",
         "https://www.sciencespo.fr"),
    ], max_pages=15, page_fmt="{url}/{n}/", page_start=1)


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


def scrape_dauphine(browser=None):
    """Cartes TYPO3 : « Du lundi 5 octobre 2026 à 17h30 au … » dans le
    surtitre, pages suivantes en /page-2, /page-3… (l'extracteur générique ne
    lisait ni les heures ni les pages au-delà de la 1re). Depuis GitHub la
    requête simple ne ramène rien : les pages passent alors par le
    navigateur, le parseur reste le même (comme PSE)."""
    url = "https://dauphine.psl.eu/dauphine/media-et-communication/evenements/evenements-a-venir"
    kw = dict(
        title="h3", date=".card_news_surtitle", time=".card_news_surtitle",
        kind=".card_categories", drop_kind=("vie sportive",), summary="h3 ~ p",
        base="https://dauphine.psl.eu",
        location="Université Paris Dauphine, Place du Maréchal de Lattre de Tassigny, Paris 16e",
        page_url=url + "/page-{n}", page_start=2, max_pages=15)
    evs = _scrape_cards("Université Paris Dauphine", url, "div.news-list > div.row", **kw)
    if not evs and browser is not None:
        ctx = browser.new_context(user_agent=HEADERS["User-Agent"], locale="fr-FR",
                                  extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"})
        page = ctx.new_page()
        try:
            evs = _scrape_cards("Université Paris Dauphine", url, "div.news-list > div.row",
                                fetch=lambda u: BeautifulSoup(load_page(page, u, exhaustive=False)[0], "lxml"), **kw)
        finally:
            ctx.close()
    return evs


def scrape_pse(browser=None):
    """Cartes WordPress avec <time datetime="2026-09-24 12:30:00">, titre,
    orateur et salle. L'extracteur générique (Playwright) prenait l'étiquette
    « Séminaire » pour un titre et décalait des dates : parseur dédié.
    Depuis GitHub, une requête simple reçoit « 418 » (anti-robot) : les pages
    passent alors par le navigateur, le parseur reste le même."""
    kw = dict(
        title="h3.event-item__title", date="time.date__time", kind=".event-item-type",
        speaker=".event-item__speaker", place=".item__salle span:last-child",
        base="https://www.parisschoolofeconomics.eu",
        location="Paris School of Economics, 48 boulevard Jourdan, Paris 14e",
        page_url="https://www.parisschoolofeconomics.eu/evenements/page/{n}/", page_start=2, max_pages=15)
    url = "https://www.parisschoolofeconomics.eu/evenements/"
    evs = _scrape_cards("Paris School of Economics", url, "article", **kw)
    if not evs and browser is not None:
        ctx = browser.new_context(user_agent=HEADERS["User-Agent"], locale="fr-FR",
                                  extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"})
        page = ctx.new_page()
        try:
            evs = _scrape_cards("Paris School of Economics", url, "article",
                                fetch=lambda u: BeautifulSoup(load_page(page, u, exhaustive=False)[0], "lxml"), **kw)
        finally:
            ctx.close()
    for e in evs:
        if e["discipline"] == "Autre":
            e["discipline"] = "Économie"
    return evs


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

    def parse(enc):
        # lxml plante sur certaines pages (« not enough values to unpack » avec
        # bs4 4.12 + lxml 6 : Académie de médecine sur le robot GitHub) :
        # l'analyseur de Python prend alors le relais au lieu de perdre la source.
        try:
            return BeautifulSoup(r.content, "lxml", from_encoding=enc)
        except Exception as e:
            print(f"   [warn] lxml a échoué sur {url} ({type(e).__name__}), repli html.parser")
            return BeautifulSoup(r.content, "html.parser", from_encoding=enc)
    soup = parse(r.encoding if declared else None)
    if (soup.original_encoding or "").lower() in ("iso-8859-1", "latin-1", "latin1"):
        # Comme les navigateurs (norme WHATWG) : « latin-1 » annoncé = cp1252,
        # sinon les apostrophes typographiques (’) disparaissent.
        soup = parse("cp1252")
    return soup


def _scrape_cards(name, url, card, *, title, base, location, date=None,
                  link=None, place=None, kind=None, keep_kind=None,
                  drop_kind=None, page_url=None, max_pages=8, page_start=1,
                  one_per_title=False, time=None, drop=None, members=None,
                  speaker=None, keep_loc=None, place_only=False, fetch=None, summary=None):
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
    adresse complète, pas un simple complément de `location`. fetch : url →
    BeautifulSoup à la place de _soup (pages servies via Playwright).
    summary : sélecteur du chapeau (description) ; à défaut, le texte de `kind`."""
    print(f"→ {name}...")
    events, seen, stats = [], set(), {"cards": 0, "off": 0, "kind": 0, "date": 0}
    raw_seen = set()          # cartes déjà vues, gardées ou non (arrêt de la pagination)
    urls = [url] + ([page_url.format(n=n) for n in range(page_start, page_start + max_pages - 1)]
                    if page_url else [])
    for u in urls:
        try:
            soup = (fetch or _soup)(u)
        except Exception as e:
            print(f"   [warn] {u}: {e}")
            break
        cards = soup.select(card)
        stats["cards"] += len(cards)
        new = 0
        # Nouvelles cartes de la page, retenues ou pas : s'arrêter dès qu'une
        # page ne gardait rien coupait le Muséum après sa 1re page (ateliers et
        # expos), alors que ses conférences étaient plus loin.
        sigs = {c.get_text(" ", strip=True)[:160] for c in cards}
        fresh = len(sigs - raw_seen)
        raw_seen |= sigs
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
            if p and (_non_paris(p) or (keep_loc and not keep_loc.search(p))):
                continue
            end = ""
            if time and c.select_one(time):
                t0, end = _times(c.select_one(time).get_text(" "))
                tm = t0 or tm
            sp = clean_text(c.select_one(speaker).get_text(" ")) if speaker and c.select_one(speaker) else ""
            if re.match(r"(journ[ée]e|organis|colloque|s[ée]minaire|conf[ée]rence|table ronde|atelier)", sp, re.I):
                sp = ""                        # « Journée organisée par… » : pas un orateur
            s_el = c.select_one(summary) if summary else None
            events.append(new_event(
                name, t, d, time_str=tm, end_time=end,
                url=make_absolute(a.get("href", "") if a else "", base),
                location=(_where_or(p, location) if place_only else
                          f"{p} — {location}" if p and p.lower() not in location.lower() else location),
                desc=clean_text(s_el.get_text(" ")) if s_el else k,
                speaker=re.sub(r"^(Par|Avec)\s+", "", sp)[:160]))
            if members and members.search(c.get_text(" ")):
                events[-1]["members"] = True
            new += 1
        if page_url and (not cards or not fresh):
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


_MNHN_SITES = {   # lieux du Muséum hors Jardin des Plantes : leur vraie adresse
    "parc zoologique": "Parc zoologique de Paris, avenue Daumesnil, Paris 12e",
}


def scrape_mnhn():
    # L'agenda mêle expos, ateliers enfants et visites : on garde la parole.
    evs = _scrape_cards(
        "Muséum national d'Histoire naturelle", "https://www.mnhn.fr/fr/l-agenda-du-museum",
        ".mt-tuile", title=".mt-tuile__title", date=".field--name-field-dates-text",
        kind=".mt-tuile-category", keep_kind=("conférence", "rencontre", "colloque", "débat", "table ronde"),
        place=".field--name-extra-field-place-name", base="https://www.mnhn.fr",
        location="Muséum national d'Histoire naturelle, 57 rue Cuvier, Paris 5e",
        page_url="https://www.mnhn.fr/fr/l-agenda-du-museum?page={n}", max_pages=12)
    out = []
    for e in evs:
        place = e["location"].split(" — ")[0].lower()
        if place.startswith("musée de l'homme"):
            continue            # source dédiée (scrape_musee_homme), avec la bonne adresse
        for k, addr in _MNHN_SITES.items():
            if place.startswith(k):
                e["location"] = addr
        out.append(e)
    if len(out) < len(evs):
        print(f"   ({len(evs) - len(out)} du Musée de l'Homme laissés à sa source dédiée)")
    return out


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
        drop_kind=("concert", "famille", "adolescent", "enfant"),
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
                             drop_kind=("exposition", "spectacle", "cérémonie"),
                             page_url=site + "/evenements?page={n}", max_pages=6)
    return out


def scrape_assas():
    return _scrape_cards(
        "Université Paris-Panthéon-Assas", "https://www.assas-universite.fr/fr/evenements",
        ".liste__evenements .event", title="h3", kind=".type__evenement", place=".adresse",
        # vie étudiante : petits-déjeuners offerts, matchs, salons, remises de prix
        drop_kind=("petit-déjeuner", "sportive", "salon", "cérémonie"),
        base="https://www.assas-universite.fr",
        location="Université Paris-Panthéon-Assas, 92 rue d'Assas, Paris 6e",
        page_url="https://www.assas-universite.fr/fr/evenements?page={n}", max_pages=6)


def scrape_paris_saclay():
    return _scrape_cards(
        "Université Paris-Saclay", "https://www.universite-paris-saclay.fr/evenements", "article.thumbnail",
        title="h3", date=".thumbnail__info__date", place=".thumbnail__info__place",
        drop=re.compile(r"^concert", re.I),
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


SCIENCESCONF_CACHE = OUTPUT_FILE.parent / "sciencesconf-sites.json"


def _sc_key(url):
    return re.sub(r"^https?://", "", url or "").rstrip("/").lower()


def _sciencesconf_sitemap(known, *, window=1500, max_fetch=150):
    """Le portail ne montre que ~4 semaines. Le sitemap officiel liste tous les
    sites de colloques, les plus récents à la fin ; l'en-tête de chaque site
    donne « Paris (France) / 2-4 Nov 2026 ». On lit les `window` derniers, en
    cache (data/sciencesconf-sites.json) : seuls les nouveaux sites, et les
    colloques à venir vus il y a plus de 30 jours, sont relus (≤ max_fetch)."""
    try:
        cache = json.loads(SCIENCESCONF_CACHE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    try:
        r = requests.get("https://portal.sciencesconf.org/data/sitemap/sitemap.xml",
                         headers=HEADERS, timeout=60)
        r.raise_for_status()
        sites = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)[-window:]
    except Exception as e:
        print(f"   [warn] sitemap Sciencesconf : {e}")
        return []
    stale = (TODAY - timedelta(days=30)).isoformat()
    todo = [u for u in reversed(sites) if u not in cache] + [
        u for u in sites if u in cache and (cache[u].get("seen", "") < stale or not cache[u].get("t"))
        and (not cache[u].get("s") or cache[u]["s"] >= TODAY.isoformat())
        and (cache[u].get("s") or cache[u].get("seen", "") < stale)]
    fetched = 0
    for u in todo[:max_fetch]:
        try:
            b = BeautifulSoup(requests.get(u, headers=HEADERS, timeout=20).content, "lxml")
        except Exception:
            continue                                   # retentée au prochain passage
        entry = {"seen": TODAY.isoformat()}
        loc, ttl = b.select_one("div.location p"), b.select_one("section p.title")
        if loc:
            parts = [clean_text(x) for x in loc.stripped_strings]
            st = _range_start(parts[1]) if len(parts) > 1 else None
            t = clean_text(ttl.get_text(" ")) if ttl else ""
            if not t and b.title:
                t = re.sub(r"\s*-\s*Sciencesconf\.org\s*$", "", clean_text(b.title.get_text(" ")))
            entry.update(t=t, loc=parts[0] if parts else "",
                         s=st.isoformat() if st and st.year > 2000 else "")
        cache[u] = entry
        fetched += 1
        time.sleep(0.2)
    cache = {u: cache[u] for u in sites if u in cache}
    try:
        SCIENCESCONF_CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")),
                                      encoding="utf-8")
    except Exception as e:
        print(f"   [warn] cache Sciencesconf : {e}")
    events = []
    for u in sites:
        c = cache.get(u) or {}
        if (not c.get("s") or _sc_key(u) in known or "(France)" not in c.get("loc", "")
                or not _IDF_RE.search(c.get("loc", "")) or _non_paris(c.get("loc", ""))):
            continue
        d = date.fromisoformat(c["s"])
        if not in_window(d):
            continue
        # « SGAP: a Scientist's Guide to AI - Paris - 2026 » → sans ville ni année
        title = re.sub(r"\s+-\s+[^-]{2,40}\s+-\s+20\d\d\s*$", "", c.get("t", "")).strip()
        # « gep2026 : Geometry… » : identifiant technique en tête
        title = re.sub(r"^[a-z0-9-]{3,}\s+:\s+", "", title)
        if not title:
            continue
        events.append(new_event("Sciencesconf.org", title, d, location=c["loc"],
                                url=u.rstrip("/") + "/", desc="Colloque"))
    print(f"   sitemap : {len(sites)} sites, {fetched} lus, {len(events)} colloques franciliens en plus")
    return events


def scrape_sciencesconf():
    """Le portail ne liste que ~200 colloques à venir (≈ 4 semaines) ; le
    sitemap (_sciencesconf_sitemap) couvre les mois suivants. Fiche détaillée
    lue pour les seuls colloques franciliens : adresse, site du colloque, GPS."""
    name = "Sciencesconf.org"
    print(f"→ {name}...")
    base = "https://portal.sciencesconf.org"
    events = []
    # Portail injoignable (délai dépassé depuis GitHub, 26/09/2026) : on lit
    # quand même le sitemap au lieu de perdre toute la source.
    try:
        cells = _soup(base + "/browse/list").select("td.miniconf_bloc")
    except Exception as e:
        print(f"   [warn] portail Sciencesconf : {e}")
        cells = []
    for td in cells:
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
    known = {_sc_key(e["url"]) for e in events}
    events += _sciencesconf_sitemap(known)
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
            # Les heures de l'API sont l'heure affichée à Paris, avec un décalage
            # faux : toujours « +02:00 » dans les occurrences (même en hiver),
            # « +00:00 » dans date_start. On lit donc l'heure telle qu'écrite,
            # sans conversion — sinon tout est décalé d'1 h après le passage à
            # l'heure d'hiver, et un festival « toute la journée » affiche 02:00.
            slots = []
            for occ in (x.get("occurrences") or x.get("date_start") or "").split(";"):
                a, _, b = occ.partition("_")
                try:
                    s = datetime.fromisoformat(a[:19])
                    e = datetime.fromisoformat(b[:19]) if b else None
                except ValueError:
                    continue
                slots.append((s, e))
            dt, end = next(((s, e) for s, e in sorted(slots, key=lambda p: p[0]) if in_window(s.date())), (None, None))
            if not dt:
                continue
            # 00:00 → 23:59 : « toute la journée » (expositions, festivals…)
            timed = bool(dt.hour or dt.minute)
            end_s = end.strftime("%H:%M") if timed and end and end.date() == dt.date() and end > dt else ""
            venue = clean_text(x.get("address_name") or x.get("contact_organisation_name")) or "Ville de Paris"
            loc = ", ".join(p for p in (venue, clean_text(x.get("address_street")),
                                         clean_text(f"{x.get('address_zipcode') or ''} {x.get('address_city') or ''}")) if p)
            desc = clean_text(x.get("lead_text")) or strip_html(x.get("description"))[:400]
            ev = new_event(venue, title, dt.date(),
                           time_str=dt.strftime("%H:%M") if timed else "", end_time=end_s,
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


# « Conférence « X » », « Conférence-débat : X », « Table ronde – X »,
# « [SECRE 2027] X » : l'habillage que chaque site met autour du même titre.
_TITLE_WRAP = re.compile(
    r"^\s*(?:\[[^\]]{2,30}\]\s*|(?:conf[ée]rence(?:[- ](?:d[ée]bat|concert))?|table[- ]ronde|rencontre|"
    r"projection(?:[- ]d[ée]bat)?|d[ée]bat|atelier|lecture|colloque(?: international)?|"
    r"pr[ée]sentation (?:du livre|de l['’]ouvrage|d['’]ouvrage))"
    r"\s*(?=[:–—«\"“-])[:–—-]?\s*)", re.I)
# « DÉCRIPT in dialogue | Whose Peace? … » (Inalco) = « Whose Peace? … » (FMSH)
_SERIES_LABEL = re.compile(r"^[^|]{3,40}\|\s*(?=.{15})")


def core_title(title):
    """Titre nu, pour comparer deux versions d'un même événement."""
    t = _TITLE_WRAP.sub("", title or "", count=1)
    t = _SERIES_LABEL.sub("", t, count=1)
    return slugify(t.strip(" «»\"“”'’"))


def _similar(a, b, cut=0.85):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= cut


def _drop_city_duplicates(events):
    """Une conférence de Sciences Po ou de la BnF peut aussi être publiée sur
    Que faire à Paris : la source institutionnelle l'emporte. On compare le
    titre nu : la Ville écrit « Conférence « Hommage à Bernard Frank » » là où
    la Maison de la culture du Japon écrit « Hommage à Bernard Frank »."""
    key = lambda e: (core_title(e.get("title", ""))[:50], e.get("date"))
    known = {key(e): e for e in events if e.get("source_type") != "ville"}
    out = []
    for e in events:
        if e.get("source_type") == "ville" and key(e) in known:
            _absorb(known[key(e)], e)
        else:
            out.append(e)
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
            if where and (_non_paris(where) or (v.get("city") and not _IDF_RE.search(where))):
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
        if place and _non_paris(place):
            continue
        events.append(new_event(
            "PR[AI]RIE", title, dt.date(), url=make_absolute(a["href"], base) if a else f"{base}/agenda/",
            location=_where_or(place, "PR[AI]RIE-PSAI, Paris"),
            desc=" · ".join(x for x in lines[len(parts):] if x not in (title, place, ","))[:200]))
    print(f"   ✓ Total PR[AI]RIE: {len(events)} events")
    return events


_ITEM_TITLE = re.compile(r"^(?P<s>[^«»:]{3,220}\([^()]+\)[^«»:]*?)[\s,]*«\s*(?P<t>[^«»]{6,}?)\s*»\s*\.?$")


def _split_item_title(title):
    """« AURÈLE CRASSON (ITEM-ENS), DELPHINE DESVEAUX (BHVP), « Hors-tout… » »
    → titre « Hors-tout… », intervenants « Aurèle Crasson (ITEM-ENS), Delphine
    Desveaux (BHVP) » (noms en capitales remis en casse normale, sigles entre
    parenthèses intacts). Un titre sans affiliation entre parenthèses est
    laissé tel quel."""
    m = _ITEM_TITLE.match(title)
    if not m:
        return title, ""
    spk = re.sub(r"\([^)]*\)|[^()]+",
                 lambda p: p[0] if p[0].startswith("(") or not p[0].isupper() else p[0].title(),
                 m["s"].strip(" ,–-"))
    return m["t"].strip(), spk


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
            # Le site perd ses tirets : « 59?61, rue Pouchet », « (16:00?18:00) »
            txt = re.sub(r"(?<=\d)\?(?=\d)", "–", c.get_text(" ", strip=True))
            m = re.search(r"Lieu\s*:\s*(.+?)(?=\s{2}|$)", txt)
            lieu = clean_text(m.group(1))[:200] if m else ""
            if lieu and not _IDF_RE.search(lieu):
                continue                       # Dakar, Genève…
            t0, t1 = _times(lieu)              # « … Salle Dussane - (17h-19h00) »
            # horaire (« (17h-19h00) », « (16:00–18:00) ») et tout ce qui suit
            lieu = re.sub(r"[\s.,–-]*\(?\s*\d{1,2}\s*(?:h|:\d\d).*$", "", lieu).strip(" -–.,")
            title, speaker = _split_item_title(clean_text(a.get_text(" ")))
            events.append(new_event(
                "ENS Paris", title, d, time_str=t0, end_time=t1,
                location=lieu or "ITEM (ENS-CNRS), 45 rue d'Ulm, Paris 5e", speaker=speaker,
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
            dsc = x.get("description") or {}
            links = dsc.get("links") if isinstance(dsc.get("links"), dict) else {}
            # « … les commissaires de l'exposition "{{ link_0 }} » : gabarit
            # du site, le lien est dans description.links
            html = re.sub(r"\{\{\s*(\w+)\s*\}\}",
                          lambda m: (links.get(m.group(1)) or {}).get("title", "") or "", dsc.get("html", ""))
            desc = strip_html(re.sub(r"<\?xml[^>]*\?>", "", html))
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
                    location="Les Mardis de la Philo, 35 bis rue de Sèvres, Paris 6e",
                    desc=("Aussi en direct sur Zoom. " + clean_text(content.get_text(" ")))[:400]
                    if content else "Aussi en direct sur Zoom.",
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
            d0, tm0 = _ld_when(x.get("startDate", ""))
            dt = datetime.combine(d0, datetime.strptime(tm0 or "00:00", "%H:%M").time()) if d0 else None
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
    # Institut de relations internationales et stratégiques. Les prochains
    # événements : l'article « à la une » + les cartes datées (« 05 OCT »,
    # « … / OUVERT / 18:30–20:00 ») ; la grille « col-sm-6 » lue avant ne
    # contenait que les événements PASSÉS (0 conférence depuis des semaines).
    return _scrape_cards(
        "IRIS", "https://www.iris-france.org/evenements/",
        "article.event-featured, article.card:has(> .card-content > p.card-date)",
        title="h2.event-title, h3.card-title", date="p.card-date", time="p.card-subheading",
        link='a[href*="/event/"]', drop=re.compile(r"\breplay\b|webinaire", re.I),
        members=re.compile(r"sur invitation|réservé", re.I),
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
        location="Institut du monde arabe, 1 rue des Fossés-Saint-Bernard, Paris 5e",
        # 20 cartes par page ; la suite en ?page=1 (numérotée depuis 0)
        page_url="https://www.imarabe.org/fr/agenda/rencontres-et-debats?page={n}", page_start=1, max_pages=4)


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


# ── Troisième lot : labos de maths appliquées, actuariat, engagement ──────────

def scrape_lamsade():
    """LAMSADE (Dauphine) : séminaires des trois pôles (aide à la décision,
    optimisation combinatoire, sciences des données) + « Jeux et choix social »."""
    base = "https://www.lamsade.dauphine.fr/"
    events = []
    for path in ("fr/seminaires.html",
                 "fr/seminaires/seminaires-du-pole-1-aide-a-la-decision.html",
                 "fr/seminaires/seminaires-du-pole-2-optimisation-combinatoire-algorithmique.html",
                 "fr/seminaires/seminaires-du-pole-3-sciences-des-donnees.html"):
        try:
            evs = _scrape_cards(
                "Université Paris Dauphine", base + path, "div.actus-list > div.actus-item",
                title="h3", date=".actus-date", kind=".actus-category", link="a.actus-more", base=base,
                location="Université Paris Dauphine-PSL, place du Maréchal de Lattre de Tassigny, Paris 16e")
        except Exception as e:
            print(f"   [warn] LAMSADE {path}: {e}")
            continue
        for e in evs:
            # « Romain Plassard - Hayekian Cyborg… » → orateur + titre
            m = re.match(r"(.{3,60}?)\s+[-–]\s+(.+)", e["title"])
            if m:
                e["speaker"], e["title"] = m.group(1), m.group(2)
            e["title"] = f"Séminaire LAMSADE ({e['description'] or 'recherche'}) : {e['title']}"
            e["id"] = make_id(e["institution"], e["title"], e["date"])
            e["discipline"] = "Économie" if "choix social" in e["description"].lower() else "Sciences"
        events.extend(evs)
    return events


def scrape_cmap():
    """CMAP (maths appliquées, École polytechnique) : colloquium et séminaires.
    La carte titre « Colloquium à 10h » ; le vrai titre est dans le chapô."""
    print("→ CMAP (École polytechnique)...")
    base, events = "https://cmap.ip-paris.fr", []
    for c in _soup(f"{base}/evenements").select("div.conteneur-liste > div.conteneur-element"):
        d = parse_french_date_text(c.select_one(".date").get_text(" ", strip=True)) if c.select_one(".date") else None
        h = c.select_one("h2")
        if not d or not h or not in_window(d):
            continue
        head = clean_text(h.get_text(" "))
        chapo = clean_text(c.select_one(".chapo-element").get_text(" ")) if c.select_one(".chapo-element") else ""
        t = re.search(r"Titre\s*:\s*(.+?)(?:\s+R[ée]sum[ée]\s*:|$)", chapo)
        sp = re.search(r"Orat(?:eur|rice)s?\s*:\s*(.+?)(?:\s+Titre\s*:|$)", chapo)
        kind = re.split(r"\s+à\s+\d", head)[0]
        a = h.find("a", href=True)
        events.append(new_event(
            "École polytechnique", f"{kind} du CMAP : {t.group(1)}" if t else f"{head} (CMAP)", d,
            time_str=_time_of(head), speaker=clean_text(sp.group(1))[:120] if sp else "",
            location="CMAP, École polytechnique, route de Saclay, Palaiseau",
            url=make_absolute(a["href"], base) if a else f"{base}/evenements", desc=chapo[:400]))
        if events[-1]["discipline"] == "Autre":
            events[-1]["discipline"] = "Mathématiques"
    print(f"   ✓ Total CMAP: {len(events)} events")
    return events


def scrape_actuaires():
    """Institut des actuaires : conférences, journées (payantes pour la
    plupart ; le prix est dans la classe de la carte)."""
    evs = _scrape_cards(
        "Institut des actuaires", "https://www.institutdesactuaires.com/agenda", "li.event-list-item",
        title="h5", date="header h6", time=".eventHour", kind=".event_list-theme", place=".place",
        keep_loc=_IDF_RE, members=re.compile(r"nouveaux associés|réservé aux (membres|adhérents)", re.I),
        base="https://www.institutdesactuaires.com", location="Paris — lieu précisé sur la page de l'événement",
        page_url="https://www.institutdesactuaires.com/agenda?page={n}", page_start=2, max_pages=4)
    try:
        soup = _soup("https://www.institutdesactuaires.com/agenda")
        paid = {clean_text(li.select_one("h5").get_text(" ")): " ".join(li.get("class", []))
                for li in soup.select("li.event-list-item") if li.select_one("h5")}
        for e in evs:
            cls = paid.get(e["title"], "")
            if "gratuit" in cls:
                e["price"] = "Gratuit"
            elif "payant" in cls:
                e["price"] = "Payant"
    except Exception as e:
        print(f"   [warn] actuaires prix: {e}")
    return evs


def scrape_institut_engagement():
    # Institut de l'Engagement : rencontres des lauréats, ateliers (API The Events Calendar)
    return scrape_tribe("Institut de l'Engagement", "https://www.engagement.fr",
                        "Institut de l'Engagement, Paris", source_type="association")


# ── Quatrième lot : géosciences, instituts culturels ───────────────────────────

def scrape_ipgp():
    # Institut de physique du globe de Paris : séminaires des équipes
    evs = _scrape_cards(
        "IPGP", "https://www.ipgp.fr/agenda/", "div.item.item-event", title="p.titre-item",
        date="p.date", time="p.date", kind="p.categorie", speaker="p.orateur",
        base="https://www.ipgp.fr", location="IPGP, 1 rue Jussieu, Paris 5e")
    for e in evs:
        e["speaker"] = re.sub(r"^Orat(eur|rice)s?\s*:\s*", "", e.get("speaker", ""))
        if e["discipline"] == "Autre":
            e["discipline"] = "Sciences"
    return evs


def scrape_amerique_latine():
    # Maison de l'Amérique latine : rencontres littéraires, débats (pas les projections ni concerts)
    evs = _scrape_cards(
        "Maison de l'Amérique latine", "https://www.mal217.org/fr/agenda", "div.preview-agenda",
        title="p.title", date="time.date", time="time.date", kind="p.flag",
        drop_kind=("projection", "concert", "musique", "cinéma", "exposition", "spectacle", "danse"),
        speaker="p.subtitle", base="https://www.mal217.org",
        location="Maison de l'Amérique latine, 217 boulevard Saint-Germain, Paris 7e")
    # Le sous-titre est tantôt l'invité (« Carol Prunhuber »), tantôt la suite
    # du titre (« Tribune de l'économie » + « latino-américaine et caribéenne »)
    for e in evs:
        sub = e.get("speaker", "")
        if sub and not re.fullmatch(r"(?:[A-ZÀ-Ý][\w'.-]+(?:\s+(?:de|del|da|la|y|et))?\s*){1,4}", sub):
            e["title"], e["speaker"] = f"{e['title']} — {sub}", ""
            e["id"] = make_id(e["institution"], e["title"], e["date"])
    return evs


def scrape_institut_italien():
    # Institut culturel italien : titres « Conférence / … », « Rencontre / … »
    return _scrape_cards(
        "Institut culturel italien", "https://iicparigi.esteri.it/fr/gli_eventi/calendario/",
        "div.row > div.col-12.mt-3", title="h5", date=".category-top span:last-child",
        drop=re.compile(r"^(?!(conf[ée]rence|rencontre|colloque|d[ée]bat|litt[ée]rature|"
                        r"pr[ée]sentation|table ronde|s[ée]minaire|journ[ée]e|lecture)\b)", re.I),
        base="https://iicparigi.esteri.it", location="Institut culturel italien, 50 rue de Varenne, Paris 7e")


def scrape_mcjp():
    # Maison de la culture du Japon : conférences, rencontres (pas les cours ni le cinéma)
    return _scrape_cards(
        "Maison de la culture du Japon", "https://www.mcjp.fr/fr/agenda?subsections=conferences",
        "a.preview", title="div.title", date="div.date", kind="div.genre",
        drop_kind=("cours", "cinéma", "exposition", "spectacle", "atelier"),
        base="https://www.mcjp.fr", location="Maison de la culture du Japon, 101 bis quai Jacques Chirac, Paris 15e")


def _ld_when(s):
    """startDate / endDate schema.org → (date, "HH:MM" ou "").
    L'heure est lue telle qu'écrite (heure de Paris), convertie seulement si
    la source dit UTC (« Z », « +00:00 »). Des sites écrivent « +2:00 » toute
    l'année (Académie de médecine) : convertir décalait d'1 h en hiver. Et
    leurs dates non complétées (« 2027-1-5 ») étaient lues par dateutil
    comme le 1er mai."""
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{1,2}):(\d{2}))?(.*)$", s or "")
    if not m:
        dt = parse_date(s or "")
        return (dt.date(), dt.strftime("%H:%M") if (dt.hour or dt.minute) else "") if dt else (None, "")
    y, mo, d, h, mi, rest = m.groups()
    try:
        dt = datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0))
    except ValueError:
        return None, ""
    if h is not None and re.match(r"\s*(?::\d{2}(?:\.\d+)?)?\s*(?:Z|[+-]00:?00)\s*$", rest or ""):
        dt = to_paris(dt.replace(tzinfo=dateutil_tz.UTC))
    return dt.date(), (dt.strftime("%H:%M") if h is not None and (dt.hour or dt.minute) else "")


_ANM_SKIP = re.compile(r"^\s*(pas de s[ée]ance|[ée]lections?)\b", re.I)


def scrape_academie_medecine():
    """Académie nationale de médecine : séances publiques du mardi (JSON-LD
    schema.org). « Séance à 14h » → titre explicite ; « Pas de séance » et
    « Élections » écartés."""
    name = "Académie nationale de médecine"
    loc = "Académie nationale de médecine, 16 rue Bonaparte, Paris 6e"
    print(f"→ {name}...")
    soup = _soup("https://www.academie-medecine.fr/agenda/")
    events, seen = [], set()
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(sc.string or "")
        except ValueError:
            continue
        for x in (data if isinstance(data, list) else [data]):
            if not isinstance(x, dict) or x.get("@type") != "Event":
                continue
            title = clean_text(html_unescape(x.get("name", "")))
            d, tm = _ld_when(x.get("startDate"))
            _, end = _ld_when(x.get("endDate"))
            if not title or not d or not in_window(d) or _ANM_SKIP.search(title):
                continue
            title = re.sub(r"\s+à\s+\d{1,2}\s*h(?:\s*\d{2})?\s*$", "", title)      # « … à 14h »
            if re.fullmatch(r"s[ée]ance", title, re.I):
                title = "Séance de l'Académie nationale de médecine"
            if (title.lower(), d) in seen:
                continue
            seen.add((title.lower(), d))
            ev = new_event(name, title, d, time_str=tm, end_time=end if end > tm else "", location=loc,
                           desc=strip_html(x.get("description", ""))[:400] or "Séance publique de l'Académie nationale de médecine",
                           url=x.get("url") or "https://www.academie-medecine.fr/agenda/")
            if ev["discipline"] == "Autre":
                ev["discipline"] = "Sciences"
            events.append(ev)
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


def _title_case_caps(s):
    """« Dominique MICHELET » → « Dominique Michelet » (mots tout en capitales)."""
    return re.sub(r"\b[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ'’-]{2,}\b", lambda m: m.group(0).title(), s)


def scrape_aibl():
    """Académie des inscriptions et belles-lettres : séances publiques du
    vendredi, « à 15h30 précises », Grande salle des séances de l'Institut de
    France (horaires et lieu indiqués sur aibl.fr). Une séance réunit souvent
    plusieurs communications : une fiche chacune, même créneau. La page ne
    publie que le trimestre en cours."""
    name = "Académie des inscriptions et belles-lettres"
    loc = "Institut de France, 23 quai de Conti, Paris 6e"
    print(f"→ {name}...")
    soup = _soup("https://aibl.fr/seances-presentation/seances-du-vendredi/")
    events = []
    for it in soup.select("div.seance_vendredi_item"):
        a = it.select_one("a.filterseancesvendredi_items_title")
        d = parse_french_date_text(a.get_text(" ", strip=True)) if a else None
        if not d or not in_window(d):
            continue
        desc_el = it.select_one(".filterseancesvendredi_items_description")
        desc = clean_text(desc_el.get_text(" ")) if desc_el else ""
        # La liste tronque le texte (« … »), la page de la séance le donne en entier
        try:
            main = _soup(make_absolute(a.get("href", ""), "https://aibl.fr")).select_one("main")
            full = re.sub(r"\bM\s+mes?\b", lambda m: m.group(0).replace(" ", ""), clean_text(main.get_text(" "))) if main else ""
            i = full.find("– ")
            if i >= 0 and "«" in full[i:]:
                desc = full[i:]
        except Exception as e:
            print(f"   [warn] AIBL {a.get('href')}: {e}")
        parts = [p.strip(" –-") for p in re.split(r"\s*–\s*(?=(?:Communication|Note|Pr[ée]sentation|Hommage|Allocution|Lecture|Conf[ée]rence)\b)", desc) if p.strip(" –-")]
        for p in parts or [desc]:
            m = re.search(r"«\s*(.+?)\s*(?:»|$)", p)
            title = (m.group(1) if m else p).strip().rstrip(" .")
            if not title or is_junk_title(title):
                continue
            sp = re.search(r"\bde (?:M\.|Mme|MM\.|Mmes)\s+([^,:«]+)", p)
            events.append(new_event(
                name, title[:200], d, time_str="15:30", end_time="17:30", location=loc,
                desc=p[:400], speaker=_title_case_caps(sp.group(1).strip()) if sp else "",
                url=make_absolute(a.get("href", ""), "https://aibl.fr")))
            if events[-1]["discipline"] == "Autre":
                events[-1]["discipline"] = "Histoire"
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


def scrape_mines():
    """Mines Paris – PSL : congrès, conférences, journées (pas les
    expositions du musée de Minéralogie, ni les campus hors Île-de-France)."""
    name, base = "Mines Paris - PSL", "https://www.minesparis.psl.eu"
    loc = "Mines Paris – PSL, 60 boulevard Saint-Michel, Paris 6e"
    print(f"→ {name}...")
    events = []
    for c in _soup(f"{base}/evenements/").select("article.item"):
        a = c.select_one(".title a")
        title = clean_text(a.get_text(" ")) if a else ""
        desc_el = c.select_one(".description")
        desc = clean_text(desc_el.get_text(" ")) if desc_el else ""
        if (not title or is_junk_title(title) or _OFF_TOPIC.search(title)
                or re.search(r"\bexposition\b|webinaire d.information|portes? ouvertes?|\badmissions?\b", title, re.I)
                or _non_paris(desc)
                or re.search(r"Sophia|Antipolis|Fontainebleau|\bPau\b|\bÉvry\b", desc)):
            continue
        d, tm = _card_date(c.select_one(".date") or c)
        if not d or not in_window(d):
            continue
        t0, t1 = _times(desc)
        events.append(new_event(name, title, d, time_str=t0 or tm, end_time=t1, location=loc,
                                desc=desc[:400], url=make_absolute(a.get("href", ""), base)))
        if events[-1]["discipline"] == "Autre":
            events[-1]["discipline"] = "Sciences"
    print(f"   ✓ Total {name}: {len(events)} events")
    return events


def scrape_musee_homme():
    # Musée de l'Homme : conférences et rencontres (pas les expositions ni les ateliers)
    evs = _scrape_cards(
        "Musée de l'Homme", "https://www.museedelhomme.fr/fr/agenda", "div.node--type-evenement",
        title="h3.mt-tuile__title", kind="p.mt-tuile-category", date=".field--name-field-dates-text",
        keep_kind=("conférence", "rencontre", "colloque", "débat", "table ronde", "dialogue"),
        base="https://www.museedelhomme.fr", location="Musée de l'Homme, 17 place du Trocadéro, Paris 16e",
        page_url="https://www.museedelhomme.fr/fr/agenda?page={n}", max_pages=6)
    for e in evs:
        if e["discipline"] == "Autre":
            e["discipline"] = "Sociologie & Anthropologie"
    return evs


def _soup_no_noon_utc(url):
    """Page dont les <time datetime="…T12:00:00Z"> ne sont que des dates
    (convention Drupal pour « sans horaire ») : l'attribut est retiré, sinon
    il se lisait 13:00 / 14:00 heure de Paris."""
    soup = _soup(url)
    for t in soup.select("time[datetime]"):
        if t["datetime"].endswith("T12:00:00Z"):
            del t["datetime"]
    return soup


def scrape_ined():
    # Ined (démographie) : séminaires, colloques, Lundis de l'Ined — cartes DSFR paginées
    evs = _scrape_cards(
        "Ined", "https://www.ined.fr/fr/agenda", ".fr-card--event",
        title=".fr-card__title", date=".fr-card__date", place=".fr-card__location", place_only=True,
        kind=".fr-tag", base="https://www.ined.fr", one_per_title=True, fetch=_soup_no_noon_utc,
        location="Ined, Campus Condorcet, 9 cours des Humanités, Aubervilliers",
        page_url="https://www.ined.fr/fr/agenda?page={n}", max_pages=6)
    for e in evs:
        if e["discipline"] == "Autre":
            e["discipline"] = "Sociologie & Anthropologie"
        if re.match(r"visio", e["location"], re.I):
            e["location"] = "En ligne (visio)"
    return evs


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
    "Institut des actuaires", "École polytechnique",
    "IHES", "Labos de maths d'Île-de-France", "IPGP", "Maison de l'Amérique latine", "Institut culturel italien", "Maison de la culture du Japon",
    "Académie nationale de médecine", "Académie des inscriptions et belles-lettres", "Mines Paris - PSL", "Musée de l'Homme", "Ined",
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
    scrape_lamsade, scrape_cmap, scrape_actuaires, scrape_institut_engagement,
    scrape_ipgp, scrape_amerique_latine, scrape_institut_italien, scrape_mcjp,
    scrape_academie_medecine, scrape_aibl, scrape_mines, scrape_musee_homme, scrape_ined,
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


_IDF_DEPTS = ("75", "77", "78", "91", "92", "93", "94", "95")


def _outside_idf(loc):
    """Lieu manifestement hors Île-de-France, quelle que soit la source : code
    postal d'un autre département sans rien de francilien à côté (soirées
    Luma à Chantilly ou Lamorlaye, dans l'Oise), écoles d'été de l'IJCLab à
    Cargèse ou au GANIL (Caen). « 76006 Paris » (coquille du Lucernaire)
    reste gardé : le mot Paris suffit."""
    if re.search(r"\b(carg[eè]se|ganil)\b", loc or "", re.I):
        return True
    cps = re.findall(r"\b(\d{5})\s+(?=[A-ZÀ-Ý])", loc or "")
    return bool(cps) and not any(cp[:2] in _IDF_DEPTS for cp in cps) and not _IDF_RE.search(loc)


def _article1_local(loc):
    """Lieu Article 1 (ville, sinon région) à garder : Île-de-France ou en ligne."""
    return (not loc or loc == "En ligne" or bool(_IDF_RE.search(loc))
            or bool(re.search(r"[iî]le[- ]de[- ]france|^national$", loc, re.I)))


def scrape_article1(browser) -> list[dict]:
    """Article 1 calendar — Vue/Salesforce site. Events arrive via a JS Remoting
    XHR (apexremote → AG_ActiveCampaignControllerV2.getAteliers); we capture
    that response. We keep the entire calendar (jeune + mentors), Paris /
    Île-de-France + online only : l'agenda est national (Lyon, Toulouse,
    Rennes…) et ces soirées passaient pour des événements parisiens."""
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
            d = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date()
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
        if not _article1_local(loc):
            continue
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


_ACRONYM_STOP = {
    "CNRS", "EHESS", "INHA", "IFRI", "IRIS", "ESCP", "CMAP", "LAMSADE", "ITEM", "CERES",
    "CIENS", "INSERM", "INRIA", "CNAM", "MNHN", "FMSH", "ESSEC", "IHEDN", "UNESCO", "OCDE",
    "OECD", "INSEE", "CNES", "ONERA", "INRAE", "EPHE", "INALCO", "BULAC", "IRCAM", "ENSAE",
    "ESPCI", "IPGG", "ICP", "UPEC", "LPNHE", "IJCLAB", "PSL", "HEC", "ENS", "IHP", "BNF",
}


_CANCELLED = re.compile(
    r"[\[(]\s*(?:annul|report|cancel|postpon)\w*[^\])]{0,20}[\])]"
    r"|^\s*(?:annul[ée]e?s?|report[ée]e?s?|cancell?ed|postponed)\s*[:–-]"
    r"|(?-i:\b(?:ANNUL[ÉE]E?S?|REPORT[ÉE]E?S?|CANCELL?ED|POSTPONED)\b)", re.I)


def merge_cross_source(events):
    """Même titre + même date chez deux organisateurs (BnF + EPHE, PSL +
    Dauphine…) : une seule fiche, la plus complète ; les autres organisateurs
    sont notés dans « also ». Titres trop courts / génériques ignorés."""
    groups = {}
    for ev in events:
        title = ev.get("title", "")
        # Titre nu : l'EHESS écrit « Présentation du livre "Les Balkans…" »,
        # le Campus Condorcet « Les Balkans… » pour la même soirée.
        t = core_title(title)
        # Titre ouvert par un sigle de colloque (« SGAP 2026 Paris – … »,
        # « SGAP: a Scientist's Guide… ») : même sigle + même date = même
        # événement. Pas les titres tout en capitales ni les sigles d'institution.
        acr = re.match(r"([A-Z][A-Z0-9]{3,})\b", title)
        acr = acr.group(1) if acr else None
        # « [SECRE 2027] Colloque… » = « SECRE2027 : Colloque… »
        br = re.match(r"\[\s*([A-Z][A-Z0-9]{2,}(?:\s+\d{2,4})?)\s*\]", title)
        if br:
            acr = br.group(1).replace(" ", "")
        if (acr and re.search(r"[a-zé]", title) and acr not in _ACRONYM_STOP):
            groups.setdefault(("acr", acr, ev.get("date")), []).append(ev)
            continue
        if len(t) < 20:
            # Titre court (« Africa Day 2026 ») : seulement au même endroit
            loc = slugify(ev.get("location", ""))[:20]
            if len(t) >= 8 and len(loc) >= 12:
                groups.setdefault(("court", t, ev.get("date"), loc), []).append(ev)
            else:
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
        for e in g:
            if e is not best:
                _absorb(best, e)
        out.append(best)
        merged += len(g) - 1
    if merged:
        print(f"Doublons inter-sources fusionnés : {merged}")
    return _merge_prefix_titles(out)


# Sites qui republient les événements des autres (colloques, Ville de Paris)
_AGGREGATORS = {"Sciencesconf.org"}


def _absorb(keep, lose):
    """Fiche `lose` fusionnée dans `keep` : son id est gardé (« aliases ») pour
    rediriger sa page e/<id>.html et ses liens ?event= vers `keep`, au lieu
    d'une page supprimée (404) pour qui l'avait partagée."""
    ids = {lose.get("id")} | set(lose.get("aliases") or []) | set(keep.get("aliases") or [])
    ids = sorted(i for i in ids if i and i != keep.get("id"))
    if ids:
        keep["aliases"] = ids


def _merge_prefix_titles(events):
    """Un titre qui en prolonge un autre d'un sous-titre, le même jour, à la
    même heure (ou sans heure) : « Les humanités en formes » (FMSH) et « … :
    sciences humaines et sociales » (Que faire à Paris), « Tsunami Trees » et
    « Conférence « Tsunami Trees : Naoya Hatakeyama… » » (Maison de la culture
    du Japon), « Design in Nature » (Sciencesconf) et « Design in Nature: The
    Evolution of Designs… » (PSL). Seulement chez le même organisateur, ou
    quand l'un des deux est un agrégateur : « Erasmus Days 2026 » a lieu à la
    fois à Paris Cité et à Saclay. Pas Luma : un hôte y publie souvent un même
    événement par niveau ou par tarif."""
    by_date = {}
    for i, e in enumerate(events):
        if e.get("source_type") != "luma":
            by_date.setdefault(e.get("date"), []).append(i)
    drop, n = set(), 0
    for idx in by_date.values():
        if len(idx) < 2:
            continue
        cores = {i: core_title(events[i].get("title", "")) for i in idx}
        for i in idx:
            a = cores[i]
            if len(a) < 10 or i in drop:
                continue
            for j in idx:
                if j == i or j in drop or not cores[j].startswith(a + "-"):
                    continue
                ea, eb = events[i], events[j]
                ta, tb = ea.get("time") or "", eb.get("time") or ""
                if ta and tb and ta != tb:
                    continue
                agg = any(x.get("source_type") == "ville" or x.get("institution") in _AGGREGATORS
                          for x in (ea, eb))
                if not (ea.get("institution") == eb.get("institution") or (agg and len(a) >= 12)):
                    continue
                # La source de l'organisateur l'emporte sur la Ville, puis la fiche la plus riche
                keep = max((ea, eb), key=lambda x: (x.get("source_type") != "ville", _richness(x)))
                lose = eb if keep is ea else ea
                if lose.get("source_type") != "ville":
                    also = ({lose.get("institution")} | set(lose.get("also") or [])) - {keep.get("institution")}
                    if also:
                        keep["also"] = sorted(set(keep.get("also") or []) | also)
                _absorb(keep, lose)
                drop.add(j if keep is ea else i)
                n += 1
                if i in drop:
                    break
    if n:
        print(f"Titres prolongés d'un sous-titre fusionnés : {n}")
    return [e for k, e in enumerate(events) if k not in drop]


def deduplicate(events):
    """Le premier exemplaire l'emporte (le scrape frais passe avant les
    événements reportés). Sur Luma, un lien = un événement : le même, vu
    depuis deux pages avec un hôte différent (« KubeAuto Day » et
    « Kubernetes Automation Day »), ne compte qu'une fois."""
    seen, out, slots = set(), [], {}
    for ev in events:
        # Même titre, même jour, même organisateur : doublon… sauf deux séances
        # distinctes, à des heures ET sur des pages différentes (Collège de
        # France : le cours de 15 h et le séminaire de 16 h 15 portent le même
        # titre « Sortir de cette chambre à moi… (1) »).
        base = (ev["title"].lower()[:60], ev["date"], ev["institution"])
        t, u = ev.get("time") or "", ev.get("url") or ""
        if base in slots and not all(t and kt and t != kt and u != ku for kt, ku in slots[base]):
            continue
        keys = []
        if ev.get("source_type") == "luma" and ev.get("url"):
            keys.append(("luma", ev["url"].rstrip("/").rsplit("/", 1)[-1]))
        # Même organisateur, même lien, même créneau, titre qui commence pareil :
        # deux versions d'un événement retouché (« Traduire les intraduisibles »
        # / « … ? », intervenant corrigé). Le report les gardait toutes deux
        # quand la page n'était plus dans l'agenda. Premier = le plus récent
        # (carry_forward trie par date d'ajout). Deux exposés d'une même séance
        # de l'AIBL ont des titres différents : ils restent séparés.
        if ev.get("url") and ev.get("time"):
            keys.append(("slot", ev["institution"], ev["url"], ev["date"], ev["time"],
                         slugify(ev["title"])[:25]))
        if not any(k in seen for k in keys):
            seen.update(keys)
            slots.setdefault(base, []).append((t, u))
            out.append(ev)
    # Ces séances distinctes partagent leur id (organisateur + titre + date) :
    # la plus tardive reçoit un id dérivé, stable d'un passage à l'autre — une
    # même fiche e/<id>.html, un même favori, un même UID d'agenda pour deux
    # événements, sinon.
    by_id = {}
    for ev in out:
        by_id.setdefault(ev.get("id"), []).append(ev)
    for eid, group in by_id.items():
        if eid and len(group) > 1:
            group.sort(key=lambda e: (e.get("time") or "", e.get("url") or ""))
            for ev in group[1:]:
                ev["id"] = make_id(eid, ev.get("time"), ev.get("url"))
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
    "Institut des actuaires": [48.8718, 2.3236],
    "École polytechnique": [48.7134, 2.2105],
    "IHES": [48.701, 2.1734],
    "IPGP": [48.8464, 2.3561],
    "Maison de l'Amérique latine": [48.8573, 2.3237],
    "Institut culturel italien": [48.8551, 2.3203],
    "Maison de la culture du Japon": [48.8554, 2.2896],
    "Académie nationale de médecine": [48.8556, 2.3345],
    "Académie des inscriptions et belles-lettres": [48.8574, 2.3372],
    "Mines Paris - PSL": [48.8455, 2.3398],
    "Musée de l'Homme": [48.8625, 2.2877],
    "Ined": [48.9068, 2.3719],
}

# A location worth geocoding looks like a real street address (postal code,
# or "<number> <street type>"). Vague names ("amphi Fermat", "1R2") do not.
_ADDR_RE = re.compile(
    r"\b\d{5}\b|"
    r"\b\d{1,4}\s?(?:bis|ter)?\s+(rue|avenue|av\.|bd|boulevard|place|quai|cours|"
    r"impasse|passage|all[ée]e|chemin|esplanade|square|parvis|villa|cit[ée]|route)\b", re.I)


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


class GeoUnavailable(Exception):
    """Nominatim n'a pas répondu (limite de débit, délai, erreur serveur)."""


def _nominatim(sess, address):
    """Look up one address via OpenStreetMap Nominatim. Returns [lat, lng], or
    None when Nominatim answered but found nothing. Raises GeoUnavailable when
    it did not answer : ce n'est pas une réponse, rien ne doit être mis en
    cache (des adresses exactes restaient sinon « introuvables » pour toujours)."""
    if re.search(r"\bonline\b|en ligne|visio|webinaire|zoom|distanciel", address, re.I):
        return None
    q = address
    if "france" not in q.lower():
        # N'ancrer sur Paris que si aucune autre ville n'est nommée. Depuis
        # qu'Article 1 remonte aussi ses événements de province, une adresse
        # nantaise deviendrait sinon « …, Nantes, Paris, France ».
        ql = q.lower()
        # Commune francilienne nommée (Saint-Denis, Orsay, Jouy-en-Josas…) :
        # « …, Saint-Denis, Paris, France » ne donnait rien.
        anchored = ("paris" in ql or _names_city(_FR_CITY_RE, q) or _IDF_RE.search(q)
                    or any(re.search(rf"\b{re.escape(c)}\b", ql) for c in _CITY_COORDS))
        q = q + ("" if anchored else ", Paris") + ", France"
    try:
        r = sess.get("https://nominatim.openstreetmap.org/search",
                     params={"q": q, "format": "json", "limit": 1, "countrycodes": "fr"},
                     timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise GeoUnavailable(f"{type(e).__name__}: {e}") from e
    if data:
        return [round(float(data[0]["lat"]), 6), round(float(data[0]["lon"]), 6)]
    return None


def _geo_variants(loc):
    """« Builders Factory, 18 Rue la Condamine, 75017 Paris, France » :
    Nominatim ne trouve pas avec le nom du lieu devant → on retire les
    segments de tête un à un, puis on tente « 75017 Paris »."""
    parts = [x.strip() for x in loc.split(",") if x.strip()]
    out = [", ".join(parts[i:]) for i in range(1, len(parts)) if re.search(r"\d", ", ".join(parts[i:]))]
    m = re.search(r"\b(?:75|77|78|91|92|93|94|95)\d{3}\s+"
                  r"(?!(?:salle|amphi|b[aâ]t|hall|niveau|[ée]tage)\b)[^\d,()]{2,40}", loc, re.I)
    if m:
        city = re.split(r"\s+(?:-|–|salle|amphi\w*|b[aâ]t\w*|hall|niveau|[ée]tage)\b",
                        m.group(0).strip(), maxsplit=1, flags=re.I)[0]
        out.append(city.strip() + ", France")
    return list(dict.fromkeys(out))[:3]


# Lieu réduit à une ville (« Orsay (France) », Sciencesconf) : centre de la
# commune. « Paris » seul reste hors carte : un point au centre tromperait.
_CITY_COORDS = {
    "orsay": [48.6986, 2.1875], "gif-sur-yvette": [48.7018, 2.1336], "gif sur yvette": [48.7018, 2.1336],
    "palaiseau": [48.7146, 2.2459], "saclay": [48.7310, 2.1680], "bures-sur-yvette": [48.6966, 2.1638],
    "nanterre": [48.8924, 2.2069], "aubervilliers": [48.9146, 2.3821], "saint-denis": [48.9362, 2.3574],
    "villetaneuse": [48.9570, 2.3417], "créteil": [48.7904, 2.4556], "creteil": [48.7904, 2.4556],
    "champs-sur-marne": [48.8416, 2.5870], "marne-la-vallée": [48.8416, 2.5870], "meudon": [48.8130, 2.2380],
    "cergy": [49.0364, 2.0761], "versailles": [48.8049, 2.1204], "évry": [48.6290, 2.4410],
    "evry": [48.6290, 2.4410], "jouy-en-josas": [48.7648, 2.1680], "villejuif": [48.7919, 2.3634],
    "ivry-sur-seine": [48.8157, 2.3849], "boulogne-billancourt": [48.8397, 2.2399],
    "montrouge": [48.8163, 2.3163], "issy-les-moulineaux": [48.8245, 2.2700],
    "saint-ouen": [48.9118, 2.3345], "la plaine saint-denis": [48.9170, 2.3610],
    "cergy-pontoise": [49.0364, 2.0761], "levallois-perret": [48.8950, 2.2870],
    "puteaux": [48.8840, 2.2390], "vincennes": [48.8474, 2.4390],
    "la défense": [48.8920, 2.2380], "le bourget": [48.9350, 2.4250],
}


# Lieux nommés sans adresse (« Richelieu — Bibliothèque nationale de
# France », « CEA Paris-Saclay », « Maison des Métallos, rue J.-P. Timbaud ») :
# comparés au PREMIER segment du lieu. Sans eux, l'événement prenait le point
# de son organisateur (BnF Richelieu = BnF François-Mitterrand, Saclay =
# Jussieu). Coordonnées OpenStreetMap vérifiées le 26/09/2026.
_PLACE_COORDS = {
    "françois-mitterrand": [48.8338, 2.3756], "françois mitterrand": [48.8338, 2.3756],
    "richelieu": [48.8673, 2.3382], "arsenal": [48.8503, 2.3635],
    "bulac": [48.8271, 2.3756], "institut du monde arabe": [48.8489, 2.3571],
    "maison des métallos": [48.8674, 2.3780], "observatoire de paris": [48.8370, 2.3367],
    "ipht-saclay": [48.7118, 2.1497], "ipht": [48.7118, 2.1497],
    "cea paris-saclay": [48.7290, 2.1457], "cea saclay": [48.7290, 2.1457],
    "lpnhe": [48.8461, 2.3560], "ijclab": [48.6985, 2.1840], "institut pascal": [48.7066, 2.1771],
    "université paris-panthéon-assas": [48.8469, 2.3450],
    "tgcc": [48.5966, 2.1993], "maison de la simulation": [48.7275, 2.1566],
    "lmo": [48.7004, 2.1777], "institut de mathématique d'orsay": [48.7004, 2.1777],
    "inria paris": [48.8414, 2.3848], "maison des sciences économiques": [48.8357, 2.3583],
    "ircam": [48.8598, 2.3514],
    "institut d'astrophysique de paris": [48.8350, 2.3353], "institut astrophysique de paris": [48.8350, 2.3353],
    "iap": [48.8350, 2.3353],
}


def _place_coords(loc):
    first = re.split(r"\s*(?:,|—|–|\s-\s)\s*", re.sub(r"\([^)]*\)", "", loc or "").strip(), maxsplit=1)[0]
    k = first.strip().lower()
    # … ou le nom d'une institution connue (séance IN2P3 « Institut Henri Poincaré »)
    return _PLACE_COORDS.get(k) or next(
        (c for name, c in INSTITUTION_COORDS.items() if name.lower() == k), None)


def _city_coords(loc):
    k = re.sub(r"\s*\([^)]*\)\s*$", "", loc).strip().lower()
    # Sciencesconf : « Université Paris Est Créteil - Créteil (France) » → la
    # commune est le dernier segment
    # (ou le dernier après une virgule : « Humathèque, Campus Condorcet, Aubervilliers »)
    return (_CITY_COORDS.get(k) or _CITY_COORDS.get(re.split(r"\s+-\s+", k)[-1].strip())
            or _CITY_COORDS.get(k.rsplit(",", 1)[-1].strip()))


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
    down = False                             # Nominatim ne répond plus : on arrête pour ce passage
    for ev in events:
        if ev.get("geo_exact") and "lat" in ev:
            continue                         # GPS fourni par la source (Ville de Paris, Sciencesconf)
        loc = clean_text(ev.get("location") or "")
        coords = None
        if loc and looks_like_address(loc):
            key = loc.lower()[:140]
            try:
                if key not in cache and new < MAX_NEW_GEOCODE and not down:
                    new += 1
                    time.sleep(1.1)   # Nominatim asks for max 1 request/second
                    cache[key] = _nominatim(sess, loc)
                # Échec (None) : on retente sans le nom du lieu ; [] = tout essayé
                if cache.get(key, 0) is None and new < MAX_NEW_GEOCODE and not down:
                    found = []
                    for q in _geo_variants(loc):
                        new += 1
                        time.sleep(1.1)
                        hit = _nominatim(sess, q)
                        if hit:
                            found = hit
                            break
                    cache[key] = found
            except GeoUnavailable as e:
                down = True
                print(f"[WARN] Nominatim indisponible ({e}) : géocodage reporté au prochain passage")
            coords = cache.get(key) or None
        if not coords:                       # ville seule (« Orsay (France) »)
            coords = _city_coords(loc)
        if not coords:                       # lieu nommé connu (« Richelieu — BnF »)
            coords = _place_coords(loc)
        if not coords:                       # fallback → institution coordinates
            coords = INSTITUTION_COORDS.get(ev.get("institution"))
        if coords:
            ev["lat"], ev["lng"] = coords[0], coords[1]
        else:
            # Point hérité d'un passage précédent (report) qui n'a plus lieu
            # d'être : mieux vaut hors carte que mal placé.
            ev.pop("lat", None)
            ev.pop("lng", None)

    try:
        GEOCACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    except Exception as e:
        print(f"[WARN] geocache write: {e}")
    located = sum(1 for e in events if "lat" in e)
    print(f"Geocoded: {new} new lookups · {located}/{len(events)} events placed on map")


# Fuseau de Paris décrit dans chaque calendrier (RFC 5545 §3.6.5) : sans lui,
# une heure « flottante » s'affiche à l'heure locale de l'appareil — un
# séminaire à 18 h devenait 18 h à Londres ou à Montréal.
ICS_VTIMEZONE = ["BEGIN:VTIMEZONE", "TZID:Europe/Paris", "X-LIC-LOCATION:Europe/Paris",
                 "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200", "TZNAME:CEST",
                 "DTSTART:19700329T020000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
                 "BEGIN:STANDARD", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100", "TZNAME:CET",
                 "DTSTART:19701025T030000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
                 "END:VTIMEZONE"]


def write_ics(events):
    """Write the global subscribable .ics feed + one feed per institution
    (data/cal/<slug>.ics), used by the per-institution header on the site."""
    def esc(s):
        return (str(s or "").replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\r", "").replace("\n", "\\n"))
    from datetime import timezone
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")    # « Z » = vraiment UTC

    def fold(line):
        """RFC 5545 §3.1 : 75 octets par ligne au plus, la suite sur une ligne
        commençant par une espace — sans couper un caractère UTF-8. Des
        agendas stricts (Outlook…) refusaient les longues descriptions."""
        if len(line.encode("utf-8")) <= 75:
            return line
        parts, cur, size = [], "", 0
        for ch in line:
            n = len(ch.encode("utf-8"))
            if size + n > (75 if not parts else 74):
                parts.append(cur)
                cur, size = "", 0
            cur += ch
            size += n
        parts.append(cur)
        return "\r\n ".join(parts)

    def vcal(evts, calname):
        # UID en « @paris-academique » gardé tel quel : le changer dédoublerait
        # les événements chez les abonnés.
        out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Lotent//FR",
               "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
               f"X-WR-CALNAME:{esc(calname)}",
               "X-WR-TIMEZONE:Europe/Paris", *ICS_VTIMEZONE]
        for ev in evts:
            d = ev["date"].replace("-", "")
            tm = ev.get("time", "")
            if tm and re.match(r"\d{1,2}:\d{2}", tm):
                h, m = tm.split(":")[:2]
                dtstart = f"DTSTART;TZID=Europe/Paris:{d}T{int(h):02d}{int(m):02d}00"
                et = ev.get("end_time", "")
                if et and re.match(r"\d{1,2}:\d{2}", et):
                    eh, em = et.split(":")[:2]
                    dtend = f"DTEND;TZID=Europe/Paris:{d}T{int(eh):02d}{int(em):02d}00"
                else:
                    dtend = f"DTEND;TZID=Europe/Paris:{d}T{min(int(h)+2,23):02d}{int(m):02d}00"
            else:
                dtstart = f"DTSTART;VALUE=DATE:{d}"
                try:
                    nd = (datetime.strptime(ev["date"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
                except Exception:
                    nd = d
                dtend = f"DTEND;VALUE=DATE:{nd}"
            # pas de saut de ligne en tête quand la description est vide
            desc = esc("\n".join(x for x in (ev.get("description") or "", ev.get("url") or "") if x))
            out += ["BEGIN:VEVENT", f"UID:{ev['id']}@paris-academique",
                    f"DTSTAMP:{stamp}", dtstart, dtend,
                    f"SUMMARY:{esc(ev['title'])}", f"DESCRIPTION:{desc}",
                    f"LOCATION:{esc(ev.get('location', ''))}"]
            if ev.get("url"):
                # Valeur de type URI : pas d'échappement des virgules (le lien cassait)
                out.append("URL:" + re.sub(r"[\r\n]", "", ev["url"]))
            out.append("END:VEVENT")
        out.append("END:VCALENDAR")
        return "\r\n".join(fold(l) for l in out) + "\r\n"

    def save(path, text):
        # newline="" : sous Windows (maj.bat), write_text transformait chaque
        # « \r\n » en « \r\r\n » — calendriers illisibles jusqu'au robot suivant.
        path.write_text(text, encoding="utf-8", newline="")

    try:
        save(ICS_FILE, vcal(events, "Toutes les conférences · Lotent"))
        print(f"Calendar feed: {len(events)} events → calendar.ics")
    except Exception as e:
        print(f"[WARN] ics write: {e}")

    # Per-institution feeds (academic + association sources only — not the
    # dozens of one-off Luma hosts / Que faire à Paris venues). Same slug
    # logic as the frontend.
    cal_dir = OUTPUT_FILE.parent / "cal"
    cal_dir.mkdir(exist_ok=True)
    by_inst = {i: [] for i in SHARE_INSTITUTIONS}
    for ev in events:
        # Les établissements « phares » ont toujours leur agenda, même vide ou
        # alimenté par une association : leur page i/ et le bandeau du site y
        # renvoient (4 de ces liens menaient à une page introuvable).
        if ev.get("source_type") in ("luma", "ville", "entreprise") and ev.get("institution") not in by_inst:
            continue
        by_inst.setdefault(ev.get("institution", ""), []).append(ev)
    written = set()
    for inst, evts in by_inst.items():
        slug = slugify(inst)
        if not slug:
            continue
        written.add(f"{slug}.ics")
        try:
            save(cal_dir / f"{slug}.ics", vcal(evts, f"{inst} · Lotent"))
        except Exception as e:
            print(f"[WARN] ics {slug}: {e}")
    # Un agenda par discipline (d-<slug>.ics), relié depuis d/<slug>.html et
    # le bandeau du site quand une seule discipline est filtrée
    for disc in DISC_COLORS:
        if disc == "Autre":
            continue
        name = f"d-{slugify(disc)}.ics"
        written.add(name)
        try:
            save(cal_dir / name, vcal([e for e in events if e.get("discipline") == disc and not e.get("kind")],
                                      f"{disc} · Lotent"))
        except Exception as e:
            print(f"[WARN] ics {name}: {e}")
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


def _jour_fr(n: int) -> str:
    """« 1er octobre », pas « 1 octobre »."""
    return "1er" if n == 1 else str(n)


def _date_fr(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{_jour_fr(d.day)} {_MONTHS_FR[d.month - 1]} {d.year}"
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
    "Institut des actuaires": "https://www.institutdesactuaires.com",
    "École polytechnique": "https://www.polytechnique.edu",
    "IHES": "https://www.ihes.fr",
    "Labos de maths d'Île-de-France": "https://indico.math.cnrs.fr/category/6/",
    "IPGP": "https://www.ipgp.fr",
    "Maison de l'Amérique latine": "https://www.mal217.org",
    "Institut culturel italien": "https://iicparigi.esteri.it",
    "Maison de la culture du Japon": "https://www.mcjp.fr",
    "Académie nationale de médecine": "https://www.academie-medecine.fr",
    "Académie des inscriptions et belles-lettres": "https://aibl.fr",
    "Mines Paris - PSL": "https://www.minesparis.psl.eu",
    "Musée de l'Homme": "https://www.museedelhomme.fr",
    "Ined": "https://www.ined.fr",
}


# Communes d'Île-de-France où se tiennent des événements (sinon : Paris)
_IDF_CITY = re.compile(
    r"\b(Aubervilliers|Orsay|Palaiseau|Gif-sur-Yvette|Saclay|Bures-sur-Yvette|Nanterre|Saint-Denis|"
    r"Villetaneuse|Cr[ée]teil|Versailles|Champs-sur-Marne|Marne-la-Vall[ée]e|Meudon|[ÉE]vry|Cergy|"
    r"Boulogne-Billancourt|Issy-les-Moulineaux|Montrouge|Ivry-sur-Seine|Vincennes|Courbevoie|"
    r"Neuilly-sur-Seine|Clichy|Pantin|Montreuil|Saint-Ouen|Jouy-en-Josas|Fontainebleau|Cachan|Sceaux)\b")


def _event_jsonld(ev):
    """schema.org Event JSON-LD — feeds Google's rich results (date & venue
    shown directly in search). Includes every recommended field (image,
    endDate, performer, organizer.url, offers) so Search Console doesn't
    flag missing properties. '</' is split to be safe inside a <script>."""
    eid = ev["id"]

    def at(hhmm):
        # Heure de Paris avec son décalage (+02:00 l'été, +01:00 l'hiver) :
        # sans lui, Google doit deviner le fuseau.
        try:
            h, m = (int(x) for x in hhmm.split(":")[:2])
            return datetime.combine(date.fromisoformat(ev["date"]), datetime.min.time()).replace(
                hour=h, minute=m, tzinfo=PARIS_TZ).isoformat()
        except Exception:
            return ev["date"]
    start = at(ev["time"]) if ev.get("time") else ev["date"]
    # endDate : si pas d'heure de fin scrappée, on suppose +2h (cohérent
    # avec le calendrier .ics) plutôt que de laisser le champ absent.
    if ev.get("time") and ev.get("end_time") and ev["end_time"] > ev["time"]:   # archive : fins < débuts
        end = at(ev["end_time"])
    elif ev.get("time"):
        try:
            h, m = ev["time"].split(":")
            end = at(f"{min(int(h) + 2, 23):02d}:{int(m):02d}")
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
        # data/og/<slug>.png n'existe que pour les établissements phares : pour
        # un hôte Luma ou un lieu de la Ville, c'était une image introuvable.
        img = (f"{SITE_URL}/data/og/{slug}.png" if slug and (OG_INST_DIR / f"{slug}.png").exists()
               else f"{SITE_URL}/og.png")
    # offers : Google le demande même pour les confs gratuites. On marque
    # explicitement le prix (Luma a un champ price ; sinon, 0/gratuit).
    price_str = str(ev.get("price") or "")
    offers = {
        "@type": "Offer",
        "availability": "https://schema.org/InStock",
        "url": ev.get("url") or f"{SITE_URL}/e/{eid}.html",
        "validFrom": ev["date"],
    }
    # Prix déclaré seulement s'il est connu : avant, un tarif inconnu devenait
    # « 0 € » et « payant, gratuit pour les moins de 26 ans » devenait 26 €.
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|eur\b|euros?\b)", price_str, re.I)
    if price_str == "0" or re.match(r"\s*(gratuit|free|entr[ée]e libre)", price_str, re.I):
        offers.update(price="0", priceCurrency="EUR")
    elif m:
        offers.update(price=m.group(1).replace(",", "."), priceCurrency="EUR")
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
        city = _IDF_CITY.search(ev["location"])
        data["location"] = {
            "@type": "Place",
            "name": ev["location"],
            "address": {"@type": "PostalAddress", "streetAddress": ev["location"][:200],
                        "addressLocality": city.group(1) if city else "Paris", "addressCountry": "FR"},
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


def _is_free(ev):
    """Même règle que isFree() dans web/src/lib.js (« 0 », « Gratuit »…) : le
    badge « Entrée libre » des pages e/ ne tenait compte que de « 0 »."""
    p = str(ev.get("price", "") or "")
    return p == "0" or bool(re.search(r"gratuit|free", p, re.I))


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
        def cut(text, n):
            """Coupe au mot (« … »), jamais au milieu d'un mot ou d'une date."""
            text = text.strip()
            if len(text) <= n:
                return text
            return text[:n - 1].rsplit(" ", 1)[0].rstrip(" ·,;:—-") + "…"
        t_, d_ = ev.get("title", ""), _date_fr(ev.get("date", ""))
        seo_title_full = f"{cut(t_, 55)} · {d_} · {ev.get('institution','')}"
        if len(seo_title_full) > 67:          # l'organisateur ne rentre pas : on le laisse
            seo_title_full = f"{cut(t_, 67 - len(d_) - 3)} · {d_}"
        seo_title = _esc_attr(seo_title_full)
        # Meta description : une phrase naturelle + mots-clés (intervenant,
        # lieu, date) — ~155 caractères, format optimal pour Google SERP.
        # Date, heure et organisateur d'abord : avec un long titre et une
        # adresse complète, ils tombaient au-delà des 155 caractères.
        when = d_ + (f" à {ev['time']}" if ev.get("time") else "")
        # Lieu court, sans répéter l'organisateur (« … par Institut Henri
        # Poincaré · Institut Henri Poincaré, 11 rue… »)
        inst_s = slugify(ev.get("institution", ""))
        bits = [x.strip() for x in re.split(r",| — ", re.sub(r"\([^)]*\)", "", ev.get("location") or ""))
                if x.strip()]
        bits = [x for x in bits if not (inst_s and (slugify(x) in inst_s or inst_s in slugify(x)))]
        where = ", ".join(bits[:2])
        rest = (f" — conférence le {when}, organisée par {ev.get('institution','')}"
                + (f", avec {cut(ev['speaker'], 50)}" if ev.get("speaker") else ""))
        # le titre prend ce qui reste : date et organisateur ne sont jamais coupés
        sent = (cut(t_, max(45, 152 - len(rest))) + rest
                + (f" · {where}" if where and where.lower() != "paris" else " · Paris") + ".")
        meta_desc = _esc_attr(cut(sent, 155))
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
:root{{--bg:#fff;--fg:#0a0a0b;--card:#fff;--muted:#f4f4f5;--muted-fg:#5f5f68;--border:#e4e4e7;--primary:#18181b;--primary-fg:#fafafa}}
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
.dbadge{{border-color:var(--dc);color:color-mix(in srgb,var(--dc) 62%,#000)}}
@media (prefers-color-scheme:dark){{.dbadge{{color:var(--dc)}}}}
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
.cta .ext{{background:color-mix(in srgb,var(--dc) 62%,#000);color:#fff}}
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
<div class="badges"><span class="badge dbadge">{_esc_attr(ev.get('discipline',''))}</span><span class="badge">{kind}</span>{'<span class="badge">Entrée libre</span>' if _is_free(ev) else ''}</div>
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
    # Événement renommé ou déplacé à la source : nouvel id, mais même lien
    # officiel. L'ancienne fiche devient une redirection (liens partagés,
    # favoris ouverts depuis un message…) au lieu d'une 404. Seulement pour un
    # lien propre à UN événement actuel (pas une page d'agenda commune).
    by_url, past_url = {}, {}
    for e in upcoming:
        if e.get("url"):
            by_url.setdefault(html_unescape(e["url"]), []).append(e["id"])
    # Événement passé : l'Historique garde une seule version d'un événement
    # renommé (update_archive) ; la page de l'autre version renvoie vers elle.
    for e in events:
        if (e.get("url") and e.get("date", "") < today_iso
                and re.fullmatch(r"[0-9a-f]{12}", e.get("id") or "")):
            past_url.setdefault(html_unescape(e["url"]), []).append(e["id"])
    # Doublon fusionné dans une autre fiche (même conférence publiée par deux
    # sources) : sa page renvoie vers la fiche gardée, archivée comprise.
    alias_of = {a: e["id"] for e in events if re.fullmatch(r"[0-9a-f]{12}", e.get("id") or "")
                for a in (e.get("aliases") or [])}
    removed = redirected = 0
    for f in EVENT_PAGES_DIR.glob("*.html"):
        if f.name in keep:
            continue
        try:
            old = f.read_text(encoding="utf-8", errors="replace")
            m = (re.search(r'<a class="ext" href="([^"]+)"', old)
                 or re.search(r'<meta name="lotent-src" content="([^"]+)"', old))
            ids = (by_url.get(html_unescape(m.group(1))) or past_url.get(html_unescape(m.group(1)), [])) if m else []
            if f.stem in alias_of:
                ids = [alias_of[f.stem]]
            # Redirection déjà en place vers une fiche toujours publiée : on la
            # garde (la maj locale ne connaît pas tous les alias du robot).
            prev = re.search(r'http-equiv="refresh" content="0; url=([0-9a-f]{12})\.html"', old)
            if not ids and prev and f"{prev.group(1)}.html" in keep:
                continue
            if len(ids) == 1 and f"{ids[0]}.html" != f.name:
                new = ids[0]
                f.write_text(
                    '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
                    f'<title>Événement mis à jour · Lotent</title><meta name="robots" content="noindex">'
                    f'<link rel="canonical" href="{SITE_URL}/e/{new}.html">'
                    f'<meta http-equiv="refresh" content="0; url={new}.html">'
                    + (f'<meta name="lotent-src" content="{_esc_attr(html_unescape(m.group(1)))}">' if m else '')
                    + '</head>'
                    f'<body><p>Cet événement a été mis à jour par son organisateur : '
                    f'<a href="{new}.html">voir la fiche</a>.</p></body></html>', encoding="utf-8")
                redirected += 1
                continue
            f.unlink()
            removed += 1
        except Exception:
            pass
    print(f"Pages événement : {len(keep)} générées · {redirected} redirigées vers leur nouvelle "
          f"fiche · {removed} obsolètes supprimées")


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


_HUB_MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _hub_page(*, kicker, name, path, n, color, evts, target, ics=None, og_image=None,
              intro="", chips_title="", chips=()):
    """Page « hub » (i/<slug>.html par institution, d/<slug>.html par
    discipline) : même charte que les pages événement e/*.html — Geist, clair
    / sombre, carte — avec la liste des prochaines conférences (liens vers
    e/*.html : c'est par ces hubs que Google découvre les pages événement),
    l'agenda .ics à s'abonner et des liens vers les hubs voisins."""
    url = f"{SITE_URL}/{path}"
    plural = "s" if n > 1 else ""          # « 0 conférence », comme « 1 conférence »
    short = f"{n} conférence{plural} à venir à Paris."
    items = []
    for ev in evts[:60]:
        eid = ev.get("id") or ""
        if not re.fullmatch(r"[0-9a-f]{12}", eid):
            continue
        try:
            d = date.fromisoformat(ev.get("date", ""))
            when = f"{_jour_fr(d.day)} {_HUB_MOIS[d.month - 1]}"
        except Exception:
            when = ""
        sub = ev.get("institution", "") if kicker == "Discipline" else ""
        items.append(f'<li><a href="{SITE_URL}/e/{eid}.html"><span class="t">{_esc_attr((ev.get("title") or "")[:110])}'
                     f'{f"<small>{_esc_attr(sub)}</small>" if sub else ""}</span>'
                     f'<span class="d">{_esc_attr(when)}{(" · " + _esc_attr(ev["time"])) if ev.get("time") else ""}</span></a></li>')
    events_html = (f'<h2>Prochaines conférences</h2><ul class="rel">{"".join(items)}</ul>' if items else
                   '<p class="empty">Aucune conférence annoncée pour le moment. En vous abonnant à '
                   'l\'agenda, les prochaines s\'y ajouteront d\'elles-mêmes.</p>')
    # Hub vide : hors index Google (page mince) et hors sitemap (write_sitemap)
    robots = '<meta name="robots" content="noindex, follow">\n' if not n else ""
    chips_html = ""
    if chips:
        chips_html = (f'<h2>{_esc_attr(chips_title)}</h2><div class="chips">'
                      + "".join(f'<a href="{u}">{_esc_attr(label)}</a>' for label, u in chips) + "</div>")
    crumb_ld = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE_URL}/"},
                            {"@type": "ListItem", "position": 2, "name": name, "item": url}]},
        ensure_ascii=False).replace("</", "<\\/")
    img = og_image or f"{SITE_URL}/og.png"
    ics_btn, ics_more = "", ""
    if ics:
        from urllib.parse import quote
        webcal = re.sub(r"^https?:", "webcal:", ics)
        ics_btn = f'<a class="ext" href="{webcal}">S\'abonner à l\'agenda</a>'
        ics_more = (f'<p class="subs">Abonnement : <a href="{webcal}">Apple, Outlook</a> · '
                    f'<a href="https://calendar.google.com/calendar/render?cid={quote(webcal, safe="")}" rel="noopener">Google Agenda</a> · '
                    f'lien à coller dans une autre application : <a href="{ics}">{_esc_attr(ics)}</a>. '
                    f'Il se met à jour tout seul chaque jour.</p>')
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc_attr(name)} — conférences à Paris · Lotent</title>
{robots}<link rel="canonical" href="{url}">
<meta name="description" content="{_esc_attr(short)} {_esc_attr(intro)} Calendrier mis à jour chaque jour sur lotent.fr.">
<meta property="og:title" content="{_esc_attr(name)} — {n} conférence{plural} à venir">
<meta property="og:description" content="{_esc_attr(short)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:locale" content="fr_FR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{img}">
<link rel="icon" href="{SITE_URL}/icon.svg" type="image/svg+xml">
<script type="application/ld+json">{crumb_ld}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#fff;--fg:#0a0a0b;--card:#fff;--muted:#f4f4f5;--muted-fg:#5f5f68;--border:#e4e4e7;--primary:#18181b;--primary-fg:#fafafa}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0a0a0b;--fg:#fafafa;--card:#0e0e10;--muted:#27272a;--muted-fg:#a1a1aa;--border:#27272a;--primary:#fafafa;--primary-fg:#18181b}}}}
*{{box-sizing:border-box}}
body{{font-family:Geist,system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:24px 16px 40px;line-height:1.5;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:620px;margin:0 auto}}
.crumb{{font-size:12px;color:var(--muted-fg);margin:0 0 14px}}
.crumb a{{color:inherit;text-decoration:none}}.crumb a:hover{{color:var(--fg)}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:16px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,.04),0 12px 32px -16px rgba(0,0,0,.25)}}
.head{{position:relative;display:flex;align-items:flex-end;min-height:150px;padding:20px 22px;color:#fff;background:linear-gradient(135deg,color-mix(in srgb,var(--dc) 78%,#000),color-mix(in srgb,var(--dc) 50%,#000))}}
.head::before{{content:"";position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.35) 1px,transparent 1px);background-size:16px 16px;-webkit-mask-image:radial-gradient(ellipse at top right,#000,transparent 70%);mask-image:radial-gradient(ellipse at top right,#000,transparent 70%)}}
.head .k{{position:absolute;top:14px;left:16px;background:rgba(255,255,255,.92);color:#18181b;font-size:11px;font-weight:600;padding:3px 8px;border-radius:6px}}
.head h1{{position:relative;margin:0;font-size:28px;line-height:1.15;letter-spacing:-.02em;text-wrap:balance;text-shadow:0 1px 8px rgba(0,0,0,.3)}}
.body{{padding:20px 22px 22px}}
.count{{font-size:15px;margin:0 0 6px}}.count b{{font-variant-numeric:tabular-nums}}
.intro{{font-size:14px;color:var(--muted-fg);margin:0 0 16px}}
.cta{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.cta a{{display:flex;align-items:center;justify-content:center;text-align:center;padding:13px 12px;border-radius:10px;font-weight:600;font-size:14px;text-decoration:none;line-height:1.2}}
.cta .site{{background:var(--primary);color:var(--primary-fg)}}
.cta .ext{{border:1px solid var(--border);color:inherit}}
.cta a:hover{{filter:brightness(1.08)}}
.cta a:only-child{{grid-column:1/-1}}
.subs{{font-size:12px;color:var(--muted-fg);margin:10px 0 0;overflow-wrap:anywhere}}.subs a{{color:inherit}}
@media (max-width:420px){{.cta{{grid-template-columns:1fr}}}}
h2{{font-size:13px;color:var(--muted-fg);font-weight:600;margin:24px 0 8px;text-transform:uppercase;letter-spacing:.06em}}
.rel{{list-style:none;padding:0;margin:0;border:1px solid var(--border);border-radius:10px;overflow:hidden;background:var(--card)}}
.empty{{color:var(--muted-fg);border:1px dashed var(--border);border-radius:10px;padding:14px 16px;margin:18px 0 0;font-size:14px}}
.rel li{{font-size:14px;line-height:1.4}}
.rel li+li{{border-top:1px solid var(--border)}}
.rel a{{display:flex;justify-content:space-between;gap:12px;padding:10px 12px;color:inherit;text-decoration:none}}
.rel a:hover{{background:var(--muted)}}
.rel .t small{{display:block;color:var(--muted-fg);font-size:12px;margin-top:2px}}
.rel .d{{color:var(--muted-fg);font-size:12px;white-space:nowrap;font-variant-numeric:tabular-nums}}
.chips{{display:flex;flex-wrap:wrap;gap:6px}}
.chips a{{border:1px solid var(--border);border-radius:999px;padding:5px 11px;font-size:13px;color:inherit;text-decoration:none;background:var(--card)}}
.chips a:hover{{background:var(--muted)}}
.foot{{text-align:center;margin-top:24px;font-size:12px;color:var(--muted-fg)}}
.foot a{{color:inherit}}
</style>
</head>
<body>
<div class="wrap">
<nav class="crumb" aria-label="Fil d'Ariane"><a href="{SITE_URL}/">Accueil</a> › {_esc_attr(name)}</nav>
<main class="card" style="--dc:{color}">
<div class="head"><span class="k">{_esc_attr(kicker)}</span><h1>{_esc_attr(name)}</h1></div>
<div class="body">
<p class="count"><b>{n}</b> conférence{plural} à venir dans l'agenda Lotent.</p>
{f'<p class="intro">{_esc_attr(intro)}</p>' if intro else ''}
<div class="cta"><a class="site" href="{target}">Voir dans l'agenda →</a>{ics_btn}</div>
{ics_more}
</div>
</main>
{events_html}
{chips_html}
<div class="foot"><a href="{SITE_URL}/">Lotent — toutes les conférences de Paris</a> · <a href="https://github.com/kovarci/zzzz/issues" rel="noopener">Questions &amp; recommandations</a></div>
</div>
</body>
</html>
"""


def _hub_speakers(evts, exclude=""):
    """Intervenants distincts (un cycle répète le même nom sur 10 séances ;
    certaines sources mettent le nom de l'établissement dans « speaker »)."""
    out, seen = [], set()
    for ev in evts[:40]:
        sp = (ev.get("speaker") or "").strip()[:60]
        key = sp.lower()
        if not sp or key in seen or key == exclude.lower():
            continue
        seen.add(key)
        out.append(sp)
    return out


DISC_PAGES_DIR = OUTPUT_FILE.parent.parent / "d"


def _disc_slug(disc):
    return slugify(disc)


def write_discipline_pages(events):
    """d/<slug>.html : une page par discipline (hors « Autre »), avec les
    prochaines conférences, les principaux organisateurs et l'agenda .ics de
    la discipline (data/cal/d-<slug>.ics, écrit par write_ics)."""
    from urllib.parse import quote
    DISC_PAGES_DIR.mkdir(exist_ok=True)
    today_iso = TODAY.isoformat()
    upcoming = sorted((e for e in events if e.get("date", "") >= today_iso and not e.get("kind")),
                      key=lambda e: (e.get("date", ""), e.get("time", "")))
    hubs = {f.stem for f in INST_PAGES_DIR.glob("*.html")}
    written = set()
    discs = [d for d in DISC_COLORS if d != "Autre"]
    for disc in discs:
        evts = [e for e in upcoming if e.get("discipline") == disc]
        slug = _disc_slug(disc)
        counts = {}
        for e in evts:
            counts[e.get("institution", "")] = counts.get(e.get("institution", ""), 0) + 1
        top = sorted(counts.items(), key=lambda x: -x[1])[:6]
        org = [f"{i} ({c})" for i, c in top[:4]]
        speakers = _hub_speakers(evts)
        intro = ("Principaux organisateurs : " + ", ".join(org) + "." if org else "")
        if speakers:
            intro += " Avec notamment " + ", ".join(speakers[:4]) + "."
        # Hubs voisins : les institutions phares de la discipline, puis les autres disciplines
        chips = [(i, f"{SITE_URL}/i/{slugify(i)}.html") for i, _ in top if slugify(i) in hubs]
        chips += [(d, f"{SITE_URL}/d/{_disc_slug(d)}.html") for d in discs if d != disc]
        page = _hub_page(kicker="Discipline", name=disc, path=f"d/{slug}.html", n=len(evts),
                         color=DISC_COLORS[disc], evts=evts, target=f"/?discipline={quote(disc)}",
                         ics=f"{SITE_URL}/data/cal/d-{slug}.ics", intro=intro.strip(),
                         chips_title="Voir aussi", chips=chips)
        (DISC_PAGES_DIR / f"{slug}.html").write_text(page, encoding="utf-8")
        written.add(f"{slug}.html")
    for f in DISC_PAGES_DIR.glob("*.html"):
        if f.name not in written:
            try: f.unlink()
            except Exception: pass
    print(f"Pages discipline : {len(written)}")


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

            # Page hub (même charte que les pages événement) : balises OG, liste
            # des prochaines conférences — sans ces liens les pages e/*.html ne
            # sont atteignables que par le sitemap et Google les juge orphelines.
            from urllib.parse import quote
            speakers = _hub_speakers(evts, exclude=inst)
            intro = ("Avec : " + ", ".join(speakers[:5]) + (" et d'autres" if len(speakers) > 5 else "") + ".") if speakers else ""
            dcount = {}
            for ev in evts:
                if ev.get("discipline") and ev.get("discipline") != "Autre":
                    dcount[ev["discipline"]] = dcount.get(ev["discipline"], 0) + 1
            discs = sorted(dcount, key=lambda d: -dcount[d])
            page = _hub_page(kicker="Institution", name=inst, path=f"i/{slug}.html", n=n,
                             color=DISC_COLORS.get(discs[0] if discs else "Autre", "#71717A"), evts=evts,
                             target=f"/?institution={quote(inst)}", ics=f"{SITE_URL}/data/cal/{slug}.ics",
                             og_image=f"{SITE_URL}/data/og/{slug}.png", intro=intro,
                             chips_title="Disciplines", chips=[(d, f"{SITE_URL}/d/{_disc_slug(d)}.html") for d in discs[:6]])
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
    # (sauf les hubs vides, marqués noindex par _hub_page)
    for sub, folder in (("i", INST_PAGES_DIR), ("d", DISC_PAGES_DIR)):
        for f in sorted(folder.glob("*.html")):
            if 'content="noindex' in f.read_text(encoding="utf-8", errors="replace")[:3000]:
                continue
            urls.append(f"<url><loc>{SITE_URL}/{sub}/{f.name}</loc>"
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


def _place_sans_inst(e):
    """Lieu sans l'organisateur en tête (« Sciences Po, 27 rue Saint-Guillaume »
    → « 27 rue Saint-Guillaume, Paris 7e ») ; le lieu complet s'il ne le répète pas."""
    inst = slugify(e.get("institution", ""))
    bits = [b.strip() for b in (e.get("location") or "").split(",") if b.strip()]
    while bits and inst and (slugify(bits[0]) in inst or inst in slugify(bits[0])):
        bits.pop(0)
    return ", ".join(bits)


def build_digest(events):
    """Pick the ~10 'immanquables' of the next 7 days and write
    data/digest.json (for the site's strip) + data/digest.xml (RSS feed).
    Heuristic: institution weight + headline keywords + has speaker/time,
    capped at 2 events per institution for variety."""
    end = TODAY + timedelta(days=7)
    pool = [e for e in events
            if TODAY.isoformat() <= e.get("date", "") <= end.isoformat()
            and not e.get("kind")                 # soutenances / carrières : catégories à part
            and not e.get("members")              # « immanquables » : ouverts à tous
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

    from email.utils import format_datetime
    from datetime import timezone

    def rfc822(iso_day):
        # pubDate = jour où l'événement est apparu sur Lotent : sans elle, les
        # lecteurs RSS ne savaient ni dater ni trier les articles.
        try:
            return format_datetime(datetime.combine(date.fromisoformat(iso_day), datetime.min.time())
                                   .replace(hour=8, tzinfo=PARIS_TZ))
        except Exception:
            return format_datetime(datetime.now(timezone.utc))
    items = []
    for e in picked:
        link = f"{SITE_URL}/e/{e['id']}.html"
        d = _date_fr(e.get("date", "")) + (f" à {e['time']}" if e.get("time") else "")
        items.append(
            f"<item><title>{_esc_attr(e['title'])}</title>"
            f"<link>{link}</link><guid isPermaLink=\"true\">{link}</guid>"
            f"<pubDate>{rfc822(e.get('added_at') or TODAY.isoformat())}</pubDate>"
            f"<description>{_esc_attr(d + ' — ' + e.get('institution', '') + (' · ' + _place_sans_inst(e) if _place_sans_inst(e) else ''))}</description>"
            f"</item>")
    rss = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
           "<rss version=\"2.0\"><channel>"
           "<title>Lotent — les immanquables de la semaine</title>"
           f"<link>{SITE_URL}</link>"
           "<description>Les conférences à ne pas manquer cette semaine à Paris, sélection automatique.</description>"
           "<language>fr</language>"
           f"<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>"
           + "".join(items) + "</channel></rss>")
    try:
        RSS_FILE.write_text(rss, encoding="utf-8")
    except Exception as e:
        print(f"[WARN] rss write: {e}")
    print(f"Digest : {len(picked)} immanquables ({period})")


# Types écartés à la source (concerts, expositions, vie étudiante) : la carte
# ne donne que ce type comme description. Même règle ici pour les versions
# déjà enregistrées, que le report (carry_forward) garderait jusqu'à leur date.
_OFF_KIND = re.compile(
    r"^(concerts?|expositions?|spectacles?|c[ée]r[ée]monie|petit-d[ée]jeuner\b.*|"
    r"rencontre sportive|salon|famille|adolescents?|enfants?)$", re.I)
_OFF_TITLE = re.compile(r"^concert[- ]sandwich", re.I)


def finalize_events(events):
    """Règles communes au robot (main) et à la maj locale (refresh_local.py),
    appliquées à toutes les sources, événements reportés compris."""
    # Titres parasites (menus lus comme événements)
    events = [e for e in events if not is_junk_title(e.get("title", ""))]
    n = len(events)
    events = [e for e in events if (e.get("source_type") or "institution") != "institution"
              or not (_OFF_KIND.match((e.get("description") or "").strip())
                      or _OFF_TITLE.match(e.get("title", "")))]
    if len(events) < n:
        print(f"Concerts, expositions, vie étudiante retirés : {n - len(events)}")
    # « [Reporté] Atelier… », « Meetup 5 (POSTPONED) », « [SÉANCE REPORTÉE] »
    n = len(events)
    events = [e for e in events if not _CANCELLED.search(e.get("title", ""))]
    if len(events) < n:
        print(f"Événements annulés / reportés retirés : {n - len(events)}")
    # Soirées Article 1 hors Île-de-France déjà enregistrées : le report
    # (carry_forward) les aurait gardées jusqu'à leur date.
    events = [e for e in events if e.get("institution") != "Article 1"
              or _article1_local(e.get("location", ""))]
    n = len(events)
    events = [e for e in events if not _outside_idf(e.get("location", ""))]
    if len(events) < n:
        print(f"Événements hors Île-de-France retirés : {n - len(events)}")
    for e in events:
        # Colloque sur plusieurs jours : l'heure de fin est celle du dernier jour
        if e.get("end_time") and e.get("time") and e["end_time"] <= e["time"]:
            e["end_time"] = ""
        # Collège de France : versions enregistrées avant que le scraper ne
        # sépare l'intervenant du titre (« … sociale Esther Duflo »)
        sp = (e.get("speaker") or "").strip()
        if (e.get("institution") == "Collège de France" and sp
                and e.get("title", "").endswith(" " + sp) and len(e["title"]) > len(sp) + 4):
            e["title"] = e["title"][:-len(sp)].strip()
        if (e.get("description") or "").strip().lower() == e.get("title", "").strip().lower():
            e["description"] = ""
        reclassify(e)
        if _SOUTENANCE.search(e.get("title", "")):
            e["kind"] = "soutenance"
        if _MEMBERS_ONLY.search(f"{e.get('title', '')} {e.get('description', '')}"):
            e["members"] = True
    return events


def load_previous_events():
    """Read the events.json from the previous run (or [] if none)."""
    try:
        return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def latest_published_events(meta_keys=()):
    """events.json tel qu'il est publié sur GitHub À CET INSTANT (None si
    illisible). Le robot et maj.bat publient tous deux les données ; un scrape
    dure plusieurs minutes et chacun, au moment de pousser, fait gagner sa
    version (-X theirs). Sans cette relecture, le robot effaçait la mise à
    jour locale poussée pendant qu'il tournait (Collège de France, Luma…
    remis à leur état précédent) — et inversement. `meta_keys` : champs de
    data/meta.json écrits par l'autre pipeline, recopiés ici pour ne pas les
    remettre à leur ancienne valeur."""
    import subprocess
    root = OUTPUT_FILE.parent.parent
    show = lambda path: subprocess.run(
        ["git", "show", f"FETCH_HEAD:{path}"], cwd=root, check=True,
        capture_output=True, timeout=60).stdout.decode("utf-8")
    try:
        subprocess.run(["git", "fetch", "--quiet", "origin", "main"], cwd=root,
                       check=True, timeout=120)
        events = json.loads(show("data/events.json"))
    except Exception as e:
        print(f"[WARN] version publiée illisible ({type(e).__name__}) : on garde la copie locale")
        return None
    try:
        meta = json.loads(show("data/meta.json"))
        for k in meta_keys:
            if meta.get(k):
                update_meta(k, meta[k])
    except Exception:
        pass
    return events


def carry_forward(fresh, prev, keep):
    """Événements à venir du passage précédent que ce scrape n'a pas revus
    (page lente, pagination partielle…), pour les sources où `keep(e)` est
    vrai : on les reporte, sauf ceux qui ont été renommés ou déplacés à la
    source. L'id dépend du titre et de la date : un événement renommé change
    d'id, et son ancien titre restait affiché en double jusqu'à sa date
    (« Tim Kretz, TBA » le 26/09 à côté du vrai séminaire du 26/11). On le
    reconnaît à son lien : une page propre à l'événement — un seul événement
    frais la porte, et au plus trois la portaient déjà (une page d'agenda
    commune à toute une source n'est jamais concernée)."""
    today_iso = TODAY.isoformat()
    ids = {e.get("id") for e in fresh}
    fam = lambda e: (e.get("source_type") or "institution", e.get("url"))
    n_fresh, n_prev = {}, {}
    for e in fresh:
        if e.get("url"):
            n_fresh[fam(e)] = n_fresh.get(fam(e), 0) + 1
    for e in prev:
        if e.get("url"):
            n_prev[fam(e)] = n_prev.get(fam(e), 0) + 1
    # Même organisateur, même jour, même heure (ou toutes deux absentes) et
    # titre voisin : l'ancienne version d'un événement dont le titre ET le
    # lien ont changé (« agroécologique » → « agro-écologique », « … (6) »
    # → « … », séance numérotée qui reçoit son vrai titre).
    slot = {}
    for f in fresh:
        slot.setdefault((f.get("institution"), f.get("date"), f.get("time") or ""), []).append(
            core_title(f.get("title", "")))
    out, renamed = [], 0
    # Les plus récemment ajoutés d'abord : entre deux versions reportées d'un
    # même événement Luma, deduplicate() garde ainsi la dernière.
    for e in sorted(prev, key=lambda e: e.get("added_at") or "", reverse=True):
        if not keep(e) or e.get("date", "") < today_iso or e.get("id") in ids:
            continue
        if e.get("url") and n_fresh.get(fam(e)) == 1 and n_prev.get(fam(e), 0) <= 3:
            renamed += 1
            continue
        ct = core_title(e.get("title", ""))
        if len(ct) >= 12 and any(_similar(ct, x) for x in slot.get(
                (e.get("institution"), e.get("date"), e.get("time") or ""), ())):
            renamed += 1
            continue
        out.append(e)
        ids.add(e.get("id"))
    if renamed:
        print(f"Anciennes versions d'événements renommés ou déplacés écartées : {renamed}")
    return out


MONTHS_DIR = OUTPUT_FILE.parent / "m"


def write_month_files(events):
    """Le site charge l'agenda mois par mois (data/m/AAAA-MM.json) : le mois
    en cours et le suivant d'abord, les autres ensuite. index.json liste les
    mois, leur nombre d'événements et un hash du contenu (?v=) : l'URL d'un
    mois ne change que si ses événements changent. events.json reste la
    référence des scripts (report, santé, mise à jour locale)."""
    MONTHS_DIR.mkdir(parents=True, exist_ok=True)
    by_month = {}
    for e in events:
        by_month.setdefault(e.get("date", "")[:7], []).append(
            {k: v for k, v in e.items() if k != "geo_exact"})
    index = []
    for m in sorted(k for k in by_month if re.fullmatch(r"\d{4}-\d{2}", k)):
        payload = json.dumps(by_month[m], ensure_ascii=False, separators=(",", ":"))
        (MONTHS_DIR / f"{m}.json").write_text(payload, encoding="utf-8")
        index.append({"m": m, "n": len(by_month[m]),
                      "v": hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]})
    for f in MONTHS_DIR.glob("*.json"):
        if f.stem != "index" and f.stem not in by_month:
            f.unlink()
    (MONTHS_DIR / "index.json").write_text(
        json.dumps({"total": len(events), "months": index}, separators=(",", ":")), encoding="utf-8")
    print(f"Fichiers mensuels : {len(index)} mois dans data/m/")


def write_stats(events):
    """Chiffres de la page À propos, calculés ici : elle téléchargeait
    events.json + l'archive (3,5 Mo) pour afficher quatre nombres."""
    try:
        archive = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        archive = []
    both = events + archive
    dates = sorted(e["date"] for e in both if e.get("date"))
    update_meta("stats", {
        "total": len(both),
        "upcoming": sum(1 for e in events if e.get("date", "") >= TODAY.isoformat()),
        "institutions": len({e.get("institution") for e in both}),
        "since": dates[0] if dates else "",
    })


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
    # Deux versions d'un même événement (renommé, déplacé : « Founding » →
    # « Founder Members », même lien Luma) étaient toutes deux à l'agenda
    # avant d'être archivées : l'Historique les montrait en double. On garde
    # la plus récemment ajoutée.
    n = len(archive)
    archive = deduplicate(sorted(archive, key=lambda e: e.get("added_at") or "", reverse=True))
    if len(archive) < n:
        print(f"Archive : {n - len(archive)} anciennes versions en double retirées")
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
        all_events.extend(scrape_indico_maths())
    except Exception as e:
        print(f"[ERROR] Indico maths: {e}")
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

    # maj.bat a pu publier pendant ces ~13 min de scrape : on repart de la
    # version publiée la plus récente (événements du Collège de France, de
    # Luma… qu'elle vient de rafraîchir), pas de celle du début du run.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        latest = latest_published_events(meta_keys=("last_manual_run",))
        if latest is not None:
            prev_events = latest

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
    carried = carry_forward(all_events, prev_events, lambda e: (
        e.get("institution") in KNOWN_SOURCES
        or e.get("source_type") in ("luma", "association", "ville", "entreprise")))
    all_events.extend(carried)
    if carried:
        print(f"⚠ Carried forward {len(carried)} upcoming events from the previous run")

    # Titres nettoyés (finalize_events) AVANT les dédoublonnages : une version
    # reportée « Forum Éducation 2026 Agir pour l'éducation » ne se rapprochait
    # pas du « Forum Éducation 2026 » de PSL.
    all_events = merge_cross_source(_drop_city_duplicates(deduplicate(finalize_events(all_events))))

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
        write_month_files(all_events)
    except Exception as e:
        print(f"[ERROR] fichiers mensuels: {e}")
        traceback.print_exc()

    try:
        update_archive(prev_events)
    except Exception as e:
        print(f"[ERROR] archive: {e}")
        traceback.print_exc()
    try:
        write_stats(all_events)
    except Exception as e:
        print(f"[ERROR] stats: {e}")

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
        write_discipline_pages(all_events)
    except Exception as e:
        print(f"[ERROR] discipline pages: {e}")
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
            hubs = ([f"{SITE_URL}/i/{f.name}" for f in sorted(INST_PAGES_DIR.glob("*.html"))]
                    + [f"{SITE_URL}/d/{f.name}" for f in sorted(DISC_PAGES_DIR.glob("*.html"))])
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
