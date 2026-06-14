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

import requests
from bs4 import BeautifulSoup
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
        "mathémat", "algèbre", "géométrie", "topologie", "analyse fonction",
        "probabilit", "statistique", "arithmétique", "combinatoire",
        "théorie des nombres", "équation", "logique mathématique", " math ",
        "poincaré", "graphe", "tenseur", "variété",
    ],
    "Philosophie": [
        "philosoph", "éthique", "métaphysique", "épistémologie", "ontologie",
        "phénoménologie", "wittgenstein", "hegel", " kant ", "nietzsche",
        "platon", "aristote", "esthétique philosophique", "morale",
    ],
    "Littérature": [
        "littératur", "roman", "poésie", "poème", "narratologie", "récit",
        "fiction", "écrivain", "stylistique", "rhétorique", "traduction littéraire",
        "linguistique", "philolog",
    ],
    "Histoire": [
        "histoir", "archive", "mémoire collective", "patrimoine", "médiéval",
        "antiquité", "révolution", "colonialism", "esclavage", " guerre ",
        "empire", "historiograph", "chronologie",
    ],
    "Sciences": [
        "physique", "chimie", "biologie", "neuroscienc", "génétique", "écologie",
        "astronomie", "astrophysique", "quantique", "thermodynamique", "évolution",
        "darwin", "climat", "environnement", "science cognitiv", "machine learning",
        "intelligence artificielle", "deep learning", "data science",
    ],
    "Économie": [
        "économi", "macroéco", "microéco", "marché", "finance", "monétaire",
        "fiscal", "inégalité", "croissance", "emploi", "chômage", "salaire",
        "capitalisme", "économétrie",
    ],
    "Sociologie & Anthropologie": [
        "sociologi", "anthropologi", "ethnolog", "terrain", "enquête", "société",
        "classe sociale", "genre ", "racisme", "discrimination", "migration",
        "identité", "rituel", "bourdieu", "durkheim", "famille",
    ],
    "Droit & Sciences politiques": [
        " droit ", "juridique", "constitutionnel", "science politique",
        "démocratie", "gouvernance", "parlement", "élection",
        "souveraineté", "politique publique", "géopolitique",
    ],
    "Arts & Culture": [
        " art ", "musique", "cinéma", " film ", "théâtre", "peinture", "sculpture",
        "architecture", "danse", "muséolog", "exposition", "photographie",
        "design", "musical",
    ],
}


def detect_discipline(title: str, description: str = "") -> str:
    text = " " + (title + " " + description).lower() + " "
    scores = {}
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score:
            scores[discipline] = score
    return max(scores, key=scores.get) if scores else "Autre"


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
    r"filtrer|affiner( par)?|trier( par)?|recherche[rz]?|"
    r"prochains? [eé]v[eé]nements?|[aà] venir|en ce moment|menu|"
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
    r"talence|frumam|upjv|braconnier|ljad|insa toulouse|insa lyon)\b",
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
        "discipline": detect_discipline(title, desc),
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

def scrape_indico(name, base, categ, location_default) -> list[dict]:
    print(f"→ Indico: {name}...")
    events = []
    url = (f"{base}/export/categ/{categ}.json"
           f"?from={TODAY.isoformat()}&to={HORIZON.isoformat()}&limit=300")
    data = None
    for attempt in range(1, 4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=35)
            print(f"   attempt {attempt}: HTTP {r.status_code} ({len(r.content)} bytes)")
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            print(f"   [WARN] attempt {attempt}: {e}")
    if not data:
        print("   [ERROR] Indico unreachable after 3 attempts")
        return events

    results = data.get("results", [])
    print(f"   API returned {len(results)} raw results")
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
                     " [class*='manifestation' i], [class*='actualite' i], li[class*='result' i]")
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

    raw = []
    for _u, body in captured:
        if (isinstance(body, list) and body and isinstance(body[0], dict)
                and body[0].get("method") == "getAteliers"):
            raw = body[0].get("result") or []
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
        title = clean_text(it.get("Name") or "")
        if not title or is_junk_title(title):
            continue
        city = clean_text(it.get("Ville__c") or "")
        region = clean_text(it.get("Region_campagne__c") or "")
        is_digital = bool(it.get("A_distance__c")) or it.get("Physique_ou_Digital__c") == "Digital"
        loc = "En ligne" if is_digital else (city or region or "Paris")
        desc = strip_html(it.get("Description_Jeunes__c")
                          or it.get("Description_Benevoles__c") or "")[:400]
        key = (title[:60].lower(), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        events.append(new_event(
            "Article 1", title, d,
            time_str=_norm_time(it.get("Heure_de_debut_text__c")),
            end_time=_norm_time(it.get("Heure_de_fin_texte__c")),
            location=loc, desc=desc, url=ARTICLE1_URL,
            source_type="association", image=it.get("image_EVT__c") or "",
        ))
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


def update_meta(field: str) -> None:
    """Stamp data/meta.json with the current UTC time for `field`.
    Used by main() (`last_workflow_run`) and refresh_local.py
    (`last_manual_run`) so the site can show 'last update' indicators.
    Preserves the other field if present."""
    try:
        m = json.loads(META_FILE.read_text(encoding="utf-8"))
    except Exception:
        m = {}
    from datetime import timezone
    m[field] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
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
}

# A location worth geocoding looks like a real street address (postal code,
# or "<number> <street type>"). Vague names ("amphi Fermat", "1R2") do not.
_ADDR_RE = re.compile(
    r"\b\d{5}\b|"
    r"\b\d{1,4}\s?(?:bis|ter)?\s+(rue|avenue|av\.|bd|boulevard|place|quai|cours|"
    r"impasse|passage|all[ée]e|chemin|esplanade|square)\b", re.I)


def looks_like_address(loc):
    return bool(_ADDR_RE.search(loc or ""))


def _nominatim(sess, address):
    """Look up one address via OpenStreetMap Nominatim. Returns [lat, lng] or None."""
    if re.search(r"\bonline\b|en ligne|visio|webinaire|zoom|distanciel", address, re.I):
        return None
    q = address
    if "france" not in q.lower():
        q = q + ("" if "paris" in q.lower() else ", Paris") + ", France"
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
    # dozens of one-off Luma hosts). Same slug logic as the frontend.
    cal_dir = OUTPUT_FILE.parent / "cal"
    cal_dir.mkdir(exist_ok=True)
    by_inst = {}
    for ev in events:
        if ev.get("source_type") == "luma":
            continue
        by_inst.setdefault(ev.get("institution", ""), []).append(ev)
    written = set()
    for inst, evts in by_inst.items():
        slug = slugify(inst)
        if not slug:
            continue
        written.add(f"{slug}.ics")
        try:
            (cal_dir / f"{slug}.ics").write_text(vcal(evts, f"{inst} · Paris Académique"),
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


def _event_jsonld(ev):
    """schema.org Event JSON-LD — feeds Google's rich results (date & venue
    shown directly in search). Returns a JSON string with no HTML-unsafe
    sequences (the closing '</' is split to be safe inside a <script> tag)."""
    eid = ev["id"]
    start = ev["date"] + (f"T{ev['time']}:00" if ev.get("time") else "")
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": ev.get("title") or "",
        "startDate": start,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": ("https://schema.org/OnlineEventAttendanceMode"
                                if ev.get("location") and ONLINE_RE.search(ev["location"])
                                else "https://schema.org/OfflineEventAttendanceMode"),
        "url": f"{SITE_URL}/e/{eid}.html",
        "organizer": {"@type": "Organization", "name": ev.get("institution") or ""},
    }
    if ev.get("end_time"):
        data["endDate"] = ev["date"] + f"T{ev['end_time']}:00"
    if ev.get("location"):
        data["location"] = {
            "@type": "Place",
            "name": ev["location"],
            "address": {"@type": "PostalAddress",
                        "addressLocality": "Paris", "addressCountry": "FR"},
        }
    if ev.get("description"):
        data["description"] = ev["description"][:500]
    if ev.get("image"):
        data["image"] = ev["image"]
    if ev.get("speaker"):
        data["performer"] = {"@type": "Person", "name": ev["speaker"]}
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


ONLINE_RE = re.compile(r"\b(online|en ligne|visio|distanciel|webinaire|webinar|"
                       r"zoom|teams|à distance|hybride|streaming)\b", re.I)


def write_event_pages(events):
    """One small static page per event (e/<id>.html): Open Graph tags for a
    proper link preview on WhatsApp/Discord/Twitter, plus REAL visible content
    (title, date, place, description, registration link) so Google can index
    each conference individually — an instant redirect would be treated as a
    redirect by crawlers and never indexed. A prominent button sends humans
    to the calendar app with the event modal open."""
    EVENT_PAGES_DIR.mkdir(exist_ok=True)
    keep = set()
    for ev in events:
        eid = ev.get("id") or ""
        if not re.fullmatch(r"[0-9a-f]{12}", eid):
            continue
        if f"{eid}.html" in keep:
            continue
        keep.add(f"{eid}.html")
        title = _esc_attr(ev.get("title"))
        date_label = _date_fr(ev.get("date", "")) + (f" à {ev['time']}" if ev.get("time") else "")
        inst = _esc_attr(ev.get("institution", ""))
        loc = _esc_attr(ev.get("location", ""))
        speaker = _esc_attr(ev.get("speaker", ""))
        body_desc = _esc_attr(ev.get("description", ""))
        meta_desc = _esc_attr(f"{date_label} — {ev.get('institution', '')}"
                              + (f" · {ev['location']}" if ev.get("location") else ""))
        img = _esc_attr(ev.get("image") or f"{SITE_URL}/og.png")
        ext = _esc_attr(ev.get("url") or "")
        target = f"../index.html?event={eid}"
        jsonld = _event_jsonld(ev)
        page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Paris·Académique</title>
<link rel="canonical" href="{SITE_URL}/e/{eid}.html">
<meta name="description" content="{meta_desc}">
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
<style>
body{{font-family:Inter,system-ui,sans-serif;background:#07070d;color:#ececf2;margin:0;
display:flex;align-items:center;justify-content:center;min-height:100vh;padding:22px;box-sizing:border-box}}
.card{{max-width:540px;width:100%;background:linear-gradient(160deg,#1c1c2eb8,#11111db8);
border:1px solid rgba(255,255,255,.14);border-radius:18px;padding:26px}}
.k{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8888a0;margin-bottom:10px}}
h1{{font-size:23px;line-height:1.3;margin:0 0 16px}}
p{{color:#c2c2d0;font-size:14.5px;line-height:1.65;margin:6px 0}}
.lbl{{color:#8888a0}}
.btn{{display:block;text-align:center;margin-top:22px;padding:13px;border-radius:12px;font-weight:600;
text-decoration:none;color:#fff;background:linear-gradient(120deg,#7c5cff,#3f7dff)}}
.ext{{display:block;text-align:center;margin-top:10px;font-size:13.5px;color:#8ab4ff}}
.foot{{text-align:center;margin-top:18px;font-size:12px}}
.foot a{{color:#8888a0}}
</style>
</head>
<body>
<main class="card">
<div class="k">Conférence · Paris</div>
<h1>{title}</h1>
<p><span class="lbl">Quand :</span> {_esc_attr(date_label)}</p>
<p><span class="lbl">Où :</span> {loc or 'Paris'}</p>
<p><span class="lbl">Organisé par :</span> {inst}</p>
{f'<p><span class="lbl">Intervenant :</span> {speaker}</p>' if speaker else ''}
{f'<p>{body_desc}</p>' if body_desc else ''}
<a class="btn" href="{target}">Voir dans le calendrier →</a>
{f'<a class="ext" href="{ext}" rel="noopener">Page officielle / inscription ↗</a>' if ext else ''}
<div class="foot"><a href="{SITE_URL}">Paris·Académique — toutes les conférences de Paris</a></div>
</main>
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
            speakers = []
            for ev in evts[:8]:
                if ev.get("speaker"):
                    speakers.append(ev["speaker"][:60])
            speakers_section = ""
            if speakers:
                speakers_section = "<p>Avec : " + ", ".join(_esc_attr(s) for s in speakers[:5]) + (" et d'autres" if len(speakers) > 5 else "") + ".</p>"
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
display:flex;align-items:center;justify-content:center;min-height:100vh;padding:22px;box-sizing:border-box}}
.card{{max-width:560px;width:100%;background:linear-gradient(160deg,#1c1c2eb8,#11111db8);
border:1px solid rgba(255,255,255,.14);border-radius:18px;padding:28px}}
.k{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8888a0;margin-bottom:10px}}
h1{{font-size:26px;line-height:1.25;margin:0 0 14px}}
p{{color:#c2c2d0;font-size:14.5px;line-height:1.7;margin:8px 0}}
.btn{{display:block;text-align:center;margin-top:22px;padding:13px;border-radius:12px;font-weight:600;
text-decoration:none;color:#fff;background:linear-gradient(120deg,#7c5cff,#3f7dff)}}
.foot{{text-align:center;margin-top:18px;font-size:12px}}
.foot a{{color:#8888a0}}
</style>
</head>
<body>
<main class="card">
<div class="k">Conférences à Paris</div>
<h1>{_esc_attr(inst)}</h1>
<p><strong>{n} conférence{'s' if n != 1 else ''} à venir</strong> dans le calendrier Paris·Académique.</p>
{speakers_section}
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
    """sitemap.xml at the site root: home, about, and every event page.
    Helps Google discover and index each conference individually."""
    today = TODAY.isoformat()
    urls = [f"<url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>",
            f"<url><loc>{SITE_URL}/apropos.html</loc><changefreq>monthly</changefreq></url>"]
    seen = set()
    for ev in events:
        eid = ev.get("id") or ""
        if not re.fullmatch(r"[0-9a-f]{12}", eid) or eid in seen:
            continue
        seen.add(eid)
        urls.append(f"<url><loc>{SITE_URL}/e/{eid}.html</loc>"
                    f"<lastmod>{today}</lastmod></url>")
    xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
           "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
           + "".join(urls) + "</urlset>")
    try:
        SITEMAP_FILE.write_text(xml, encoding="utf-8")
        print(f"Sitemap : {len(urls)} URLs")
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
           "<title>Paris Académique — les immanquables de la semaine</title>"
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

    # Carry-forward: union this run with the still-upcoming events from the
    # previous run, per known source (and Luma). A flaky scrape (slow site, a
    # page that timed out, partial pagination, a geo-blocked Luma) therefore can
    # never shrink or wipe a source — at worst the site keeps yesterday's events
    # until their date passes. Dedup by id below removes the overlap; past
    # events are filtered out and archived, so the dataset stays bounded.
    KNOWN_SOURCES = {
        "Institut Henri Poincaré", "Collège de France", "Paris School of Economics",
        "Université PSL", "EHESS", "ENS Paris", "Sciences Po", "Sorbonne Université",
    }
    present_ids = {e.get("id") for e in all_events}
    today_iso = TODAY.isoformat()
    carried = 0
    for e in prev_events:
        if not (e.get("institution") in KNOWN_SOURCES
                or e.get("source_type") in ("luma", "association")):
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

    all_events = deduplicate(all_events)

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

    try:
        write_institution_share_pages(all_events)
    except Exception as e:
        print(f"[ERROR] institution pages: {e}")
        traceback.print_exc()

    # Notifie Bing/Yandex des nouveautés du jour pour accélérer l'indexation.
    try:
        fresh_urls = [f"{SITE_URL}/e/{e['id']}.html" for e in all_events
                      if e.get("added_at") == today_iso and re.fullmatch(r"[0-9a-f]{12}", e.get("id") or "")]
        # Ping aussi la home + sitemap + pages institution si on a des nouveautés
        if fresh_urls:
            fresh_urls = [f"{SITE_URL}/", f"{SITE_URL}/sitemap.xml"] + fresh_urls
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
