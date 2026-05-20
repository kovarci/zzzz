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
import traceback
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "events.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
TODAY = date.today()
CUTOFF = TODAY - timedelta(days=1)
HORIZON = TODAY + timedelta(days=200)

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
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_FR_DATE_RE = re.compile(
    r"(\d{1,2})(?:er|ère|ème|e)?\s+"
    r"(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)"
    r"\s+(\d{4})", re.I,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_FR_SLASH_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b")


def parse_french_date_text(text: str):
    """Extract a date object from French text like 'Mardi 3 juin 2026'."""
    m = _FR_DATE_RE.search(text)
    if m:
        day, month_str, year = m.groups()
        key = month_str.lower().replace("é", "e").replace("û", "u")
        month = FRENCH_MONTHS.get(key)
        if month:
            try:
                return date(int(year), month, int(day))
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
    return None


def _day_month_to_date(day_str, month_str):
    """Build a date from a day-number + French month name; infers the year."""
    dm = re.search(r"\d{1,2}", str(day_str or ""))
    if not dm:
        return None
    day = int(dm.group(0))
    key = str(month_str or "").strip().lower().rstrip(".")
    month = FRENCH_MONTHS.get(key) or FRENCH_MONTHS.get(
        key.replace("é", "e").replace("û", "u").replace("ô", "o"))
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


def parse_date(s):
    """Parse a date/datetime string.
    ISO format (YYYY-MM-DD) is parsed year-first; everything else day-first
    (European convention). Falls back to the French text parser."""
    if not s:
        return None
    txt = str(s).strip()
    if not txt:
        return None
    is_iso = bool(re.match(r"\d{4}-\d{2}-\d{2}", txt))
    try:
        return dateparser.parse(txt, dayfirst=not is_iso, yearfirst=is_iso, fuzzy=True)
    except Exception:
        pass
    # Fallback: French text date ("3 juin 2026")
    d = parse_french_date_text(txt)
    if d:
        return datetime(d.year, d.month, d.day)
    return None


_JUNK_TITLE = re.compile(
    r"^\s*(acc[eè]s rapides?|aujourd'?hui|cette semaine|ce mois|cette ann[eé]e|"
    r"agenda|programme|calendrier|r[eé]sultats?|tous les|voir tout|voir plus|"
    r"filtrer|prochains? [eé]v[eé]nements?|[aà] venir|en ce moment|menu|"
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


def in_window(d: date) -> bool:
    return CUTOFF <= d <= HORIZON


def new_event(institution, title, d, time_str="", end_time="", location="",
              desc="", url="", speaker="", source_type="institution") -> dict:
    return {
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


def load_page(page, url: str) -> tuple[str, str]:
    """Navigate, wait for JS, accept cookies, exhaust infinite-scroll + load-more."""
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"   [WARN] goto {url}: {e}")
        return "", ""
    try:
        page.wait_for_load_state("networkidle", timeout=18000)
    except PWTimeout:
        page.wait_for_timeout(3000)
    accept_cookies(page)

    # Infinite scroll until the page stops growing
    last_h = 0
    for _ in range(30):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(850)
        try:
            h = page.evaluate("document.body.scrollHeight")
        except Exception:
            break
        if h == last_h:
            break
        last_h = h

    # Click any "load more" buttons, then scroll again
    if click_load_more(page):
        for _ in range(12):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(700)

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
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


def extract_events_deep_json(obj, institution_default, source_type="institution",
                             base_url="", _depth=0, _out=None, _seen=None):
    """Recursively walk ANY JSON structure, collecting event-like dicts.
    An 'event' = any dict with a name/title field AND a start-date field."""
    if _out is None:
        _out, _seen = [], set()
    if _depth > 12:
        return _out
    if isinstance(obj, list):
        for x in obj[:600]:
            extract_events_deep_json(x, institution_default, source_type, base_url,
                                     _depth + 1, _out, _seen)
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
                if not is_junk_title(title) and key not in _seen:
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
                    _out.append(new_event(
                        inst, title, dt.date(),
                        time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                        location=loc or "Paris",
                        desc=strip_html(ev.get("description") or ev.get("description_short") or "")[:400],
                        url=make_absolute(url, base_url or "https://lu.ma"),
                        source_type=source_type,
                    ))
        for v in obj.values():
            extract_events_deep_json(v, institution_default, source_type, base_url,
                                     _depth + 1, _out, _seen)
    return _out


# ── Paginated HTML scraper (CdF, EHESS, ENS, Sciences Po, Sorbonne) ───────────

def scrape_paginated(browser, name, agenda_urls, max_pages=15, source_type="institution"):
    """Scrape paginated agendas. agenda_urls = [(base_url, location, site_base), ...].
    Loops ?page=N until 2 consecutive pages yield no new events."""
    print(f"→ {name} (paginated, up to {max_pages} pages/url)...")
    all_events, seen = [], set()
    captured = []

    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="fr-FR",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
    )
    page = ctx.new_page()
    page.on("response", lambda r: capture_json(r, captured))

    for base_url, location, site_base in agenda_urls:
        empty_streak = 0
        for page_num in range(0, max_pages):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page_num == 0 else f"{base_url}{sep}page={page_num}"
            html, title = load_page(page, url)
            if is_error_page(title, html):
                print(f"   page {page_num}: ERROR PAGE ('{title[:40]}') — stop this url")
                break

            page_events = extract_events_universal(html, name, location, site_base)
            new = []
            for e in page_events:
                key = (e["title"][:50].lower(), e["date"])
                if key not in seen:
                    seen.add(key)
                    new.append(e)
            print(f"   page {page_num}: {len(new)} new / {len(page_events)} found  (html={len(html)})")

            if not new:
                empty_streak += 1
                if empty_streak >= 2:
                    break
            else:
                empty_streak = 0
                all_events.extend(new)

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


def scrape_college_de_france(browser):
    return scrape_paginated(browser, "Collège de France", [
        ("https://www.college-de-france.fr/fr/enseignements/agenda",
         "Collège de France, 11 place Marcelin-Berthelot, Paris 5e",
         "https://www.college-de-france.fr"),
        ("https://www.college-de-france.fr/fr/agenda",
         "Collège de France, 11 place Marcelin-Berthelot, Paris 5e",
         "https://www.college-de-france.fr"),
    ], max_pages=20)


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
    for card in cards:
        title_el = card.select_one(".jnews-event-title")
        title = clean_text(title_el.get_text()) if title_el else ""
        if not title or is_junk_title(title):
            continue
        # Date: structured day + month first, free-text fallback
        d = None
        day_el = card.select_one(".chiffre-cle")
        month_el = card.select_one(".month")
        if day_el and month_el:
            d = _day_month_to_date(day_el.get_text(), month_el.get_text())
        if not d:
            d = parse_french_date_text(card.get_text(" ", strip=True))
        if not d or not in_window(d):
            continue
        # Time
        time_str = ""
        hour_el = card.select_one(".hour")
        if hour_el:
            m = re.search(r"(\d{1,2})\s*[hH:]\s*(\d{2})?", hour_el.get_text())
            if m:
                time_str = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
        link = card.find("a", href=True)
        href = link.get("href", "") if link else ""
        key = (title[:60].lower(), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        events.append(new_event("EHESS", title, d, time_str=time_str,
                                location=LOC, url=make_absolute(href, BASE)))
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
    """Dedicated Sorbonne parser — events are Bootstrap columns (.col-lg-4 /
    .col-md-6) that contain a thumbnail image and a French date in their text."""
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
    html, _ = load_page(page, "https://www.sorbonne-universite.fr/evenements")
    ctx.close()

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(".col-lg-4, .col-md-6, .col-12, [class*='card' i]")
    print(f"   {len(cards)} candidate columns")
    for card in cards:
        if not card.select_one(".thumbnail, img"):
            continue
        d = parse_french_date_text(card.get_text(" ", strip=True))
        if not d or not in_window(d):
            continue
        title_el = card.find(["h2", "h3", "h4", "h5"])
        title = clean_text(title_el.get_text()) if title_el else ""
        if not title:
            a = card.find("a", href=True)
            title = clean_text(a.get_text()) if a else ""
        if not title or is_junk_title(title):
            continue
        href = _best_link(card, title_el)
        key = (title[:60].lower(), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        events.append(new_event("Sorbonne Université", title, d,
                                location=LOC, url=make_absolute(href, BASE)))

    # Fallback to the universal extractor if the dedicated parser found little
    if len(events) < 3:
        print("   [FALLBACK] universal extractor on Sorbonne HTML")
        for e in extract_events_universal(html, "Sorbonne Université", LOC, BASE):
            key = (e["title"][:60].lower(), e["date"])
            if key not in seen:
                seen.add(key)
                events.append(e)

    print(f"   ✓ Total Sorbonne: {len(events)} events")
    return events


# ── Luma ──────────────────────────────────────────────────────────────────────

def scrape_luma(browser) -> list[dict]:
    print("→ Luma Paris...")
    events, seen = [], set()
    captured = []

    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="fr-FR",
        viewport={"width": 1366, "height": 900},
    )
    page = ctx.new_page()
    page.on("response", lambda r: capture_json(r, captured))

    html = ""
    for luma_url in ["https://lu.ma/discover/paris", "https://lu.ma/paris"]:
        try:
            page.goto(luma_url, timeout=45000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=22000)
            except PWTimeout:
                page.wait_for_timeout(5000)
            accept_cookies(page)
            for _ in range(12):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1300)
            html = page.content()
            print(f"   {luma_url}: html={len(html)}")
            if len(html) > 60000:
                break
        except Exception as e:
            print(f"   [WARN] {luma_url}: {e}")
    ctx.close()

    # Collect all JSON blobs: __NEXT_DATA__ (Luma is Next.js) + captured network JSON
    blobs = []
    if html:
        soup = BeautifulSoup(html, "lxml")
        nd = soup.find("script", {"id": "__NEXT_DATA__"})
        if nd and nd.string:
            try:
                blobs.append(json.loads(nd.string))
                print("   found __NEXT_DATA__")
            except Exception:
                pass
        # Also any inline script assigning a big JSON object
        for sc in soup.find_all("script"):
            txt = sc.string or ""
            if '"start_at"' in txt or '"startDate"' in txt:
                m = re.search(r"(\{.*\}|\[.*\])", txt, re.S)
                if m:
                    try:
                        blobs.append(json.loads(m.group(1)))
                    except Exception:
                        pass

    print(f"   captured {len(captured)} network JSON · {len(blobs)} embedded blobs")
    for _url, body in captured:
        blobs.append(body)

    # Deep-extract events from every blob
    for blob in blobs:
        for ev in extract_events_deep_json(blob, "Luma", source_type="luma",
                                           base_url="https://lu.ma"):
            key = (ev["title"][:50].lower(), ev["date"])
            if key not in seen:
                seen.add(key)
                events.append(ev)

    # Fallback: JSON-LD from rendered HTML
    if html and not events:
        soup = BeautifulSoup(html, "lxml")
        for item in extract_jsonld_events(soup):
            title = clean_text(item.get("name", ""))
            dt = parse_date(item.get("startDate") or item.get("startTime"))
            if not title or not dt or not in_window(dt.date()):
                continue
            key = (title[:50].lower(), dt.date().isoformat())
            if key in seen:
                continue
            seen.add(key)
            events.append(new_event(
                "Luma", title, dt.date(),
                time_str=dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                location="Paris", desc=strip_html(item.get("description", ""))[:400],
                url=make_absolute(item.get("url", ""), "https://lu.ma"), source_type="luma",
            ))

    print(f"   ✓ {len(events)} events")
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


def main():
    all_events = []

    try:
        all_events.extend(scrape_indico(
            "Institut Henri Poincaré", "https://indico.math.cnrs.fr", "0",
            "IHP, 11 rue Pierre et Marie Curie, Paris 5e"))
    except Exception as e:
        print(f"[ERROR] IHP: {e}")
        traceback.print_exc()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            for fn in [scrape_college_de_france, scrape_ehess, scrape_ens,
                       scrape_sciences_po, scrape_sorbonne, scrape_luma]:
                try:
                    all_events.extend(fn(browser))
                except Exception as e:
                    print(f"[ERROR] {fn.__name__}: {e}")
                    traceback.print_exc()
        finally:
            browser.close()

    all_events = deduplicate(all_events)
    all_events = [e for e in all_events if e.get("date", "") >= CUTOFF.isoformat()]
    all_events.sort(key=lambda e: (e["date"], e.get("time", "")))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

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
