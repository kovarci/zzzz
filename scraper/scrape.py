#!/usr/bin/env python3
"""
Scraper for Paris academic conferences.
Strategies (per source, in order of reliability):
1. Indico JSON API (IHP)
2. Luma JSON API + HTML
3. Universal extractor based on <time datetime="..."> for JS-rendered sites
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

# ── Discipline detection ──────────────────────────────────────────────────────

DISCIPLINE_KEYWORDS = {
    "Mathématiques": [
        "mathémat", "algèbre", "géométrie", "topologie", "analyse fonction",
        "probabilit", "statistique", "calcul", "arithmétique", "combinatoire",
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


# ── French date text parser ───────────────────────────────────────────────────

FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

_FR_DATE_RE = re.compile(
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)[\s,]*"
    r"(\d{1,2})(?:er|ère|ème|e)?\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)"
    r"\s+(\d{4})",
    re.I,
)
_FR_DATE_SHORT_RE = re.compile(
    r"(\d{1,2})(?:er|ère|ème|e)?\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)"
    r"\s+(\d{4})",
    re.I,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_FR_SLASH_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def parse_french_date_text(text: str):
    """Extract a date from French text like 'Mardi 3 juin 2025' or '3 juin 2025'."""
    for pattern in (_FR_DATE_RE, _FR_DATE_SHORT_RE):
        m = pattern.search(text)
        if m:
            day, month_str, year = m.groups()
            month = FRENCH_MONTHS.get(month_str.lower().replace("é", "e").replace("û", "u").replace("ô", "o"))
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
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def make_id(*parts) -> str:
    raw = "-".join(str(p) for p in parts if p)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def clean_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def strip_html(s) -> str:
    if not s:
        return ""
    if hasattr(s, "get_text"):
        return clean_text(s.get_text(separator=" "))
    try:
        text = BeautifulSoup(str(s), "lxml").get_text(separator=" ")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", str(s))
    return clean_text(text)


def parse_date(s):
    if not s:
        return None
    try:
        return dateparser.parse(str(s), dayfirst=True, languages=["fr", "en"], fuzzy=True)
    except Exception:
        return None


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


# ── Indico (IHP) ──────────────────────────────────────────────────────────────

def scrape_indico(name: str, base: str, categ: str, location_default: str) -> list[dict]:
    print(f"→ Indico: {name}...")
    events = []
    today = date.today()
    end = today + timedelta(days=120)
    url = f"{base}/export/categ/{categ}.json?from={today.isoformat()}&to={end.isoformat()}&limit=200"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"   [WARN] {e}")
        return events

    for item in data.get("results", []):
        title = clean_text(item.get("title", ""))
        if not title:
            continue
        raw_start = item.get("startDate", {})
        try:
            dt = dateparser.parse(f"{raw_start.get('date', '')} {raw_start.get('time', '')}".strip())
            if not dt:
                continue
        except Exception:
            continue

        location = clean_text(item.get("location", "")) or clean_text(item.get("room", "")) or location_default
        end_time = ""
        try:
            raw_end = item.get("endDate", {})
            dt_end = dateparser.parse(f"{raw_end.get('date', '')} {raw_end.get('time', '')}".strip())
            if dt_end:
                end_time = dt_end.strftime("%H:%M")
        except Exception:
            pass

        desc = strip_html(item.get("description", ""))[:400]
        speakers = ", ".join(s.get("fullName", "") for s in item.get("speakers", []))[:120]

        events.append({
            "id": make_id(name, title, str(dt.date())),
            "title": title,
            "institution": name,
            "discipline": detect_discipline(title, desc),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
            "end_time": end_time,
            "location": location,
            "description": desc,
            "url": item.get("url", base),
            "speaker": clean_text(speakers),
            "source_type": "institution",
        })
    print(f"   {len(events)} events")
    return events


# ── Universal HTML extractor (uses <time datetime> as anchor) ─────────────────

def accept_cookies(page):
    """Try common cookie consent buttons (French sites)."""
    labels = [
        "Tout accepter", "Accepter tout", "Accepter tous les cookies",
        "J'accepte", "Accepter", "Accept all", "I accept",
        "Continuer sans accepter", "Refuser",
    ]
    for label in labels:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            if btn.count() > 0:
                btn.first.click(timeout=1500)
                page.wait_for_timeout(500)
                return
        except Exception:
            pass
    for sel in ["#tarteaucitronAllAllowed", "#axeptio_btn_acceptAll", "[id*='accept']", "[class*='accept']"]:
        try:
            page.locator(sel).first.click(timeout=1000)
            page.wait_for_timeout(500)
            return
        except Exception:
            pass


def pw_get_html(browser, url: str, scroll: bool = True, extra_wait: int = 0) -> tuple[str, str]:
    """Load URL with Playwright. Returns (html, page_title)."""
    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="fr-FR",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
    )
    page = ctx.new_page()
    html, title = "", ""
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except PWTimeout:
            page.wait_for_timeout(3000)
        accept_cookies(page)
        if extra_wait:
            page.wait_for_timeout(extra_wait)
        if scroll:
            for i in range(8):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(900)
                if i == 3:
                    page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
        html = page.content()
        title = page.title()
        print(f"   html_len={len(html)} title='{title[:60]}'")
    except Exception as e:
        print(f"   [WARN] {url}: {e}")
    finally:
        ctx.close()
    return html, title


def extract_jsonld_events(soup) -> list[dict]:
    """Extract events from JSON-LD structured data."""
    events = []
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
            if "Event" not in (t if isinstance(t, str) else " ".join(t)):
                continue
            events.append(item)
    return events


def _build_event(institution, title, d, dt, location, desc, url, base_url):
    """Build a normalized event dict."""
    time_str = ""
    if dt and (dt.hour or dt.minute):
        time_str = dt.strftime("%H:%M")
    return {
        "id": make_id(institution, title, str(d)),
        "title": title,
        "institution": institution,
        "discipline": detect_discipline(title, desc),
        "date": d.isoformat(),
        "time": time_str,
        "end_time": "",
        "location": location,
        "description": desc,
        "url": make_absolute(url, base_url),
        "speaker": "",
        "source_type": "institution",
    }


def _find_title_in_container(container):
    """Find a title element within a container node."""
    title_el = container.find(["h1", "h2", "h3", "h4", "h5"])
    if not title_el:
        title_el = container.select_one(
            "[class*='title' i], [class*='Title'], [class*='name' i], strong, b"
        )
    return title_el


def extract_events_universal(html, institution, location_default, base_url):
    """Robust extractor: 4 strategies in order of reliability."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    events = []
    seen = set()
    today = date.today()
    cutoff = today - timedelta(days=1)

    def _add(ev):
        key = (ev["title"][:50].lower(), ev["date"])
        if key not in seen and ev["title"]:
            seen.add(key)
            events.append(ev)

    # Strategy 1: JSON-LD
    for item in extract_jsonld_events(soup):
        title = clean_text(item.get("name", ""))
        start = item.get("startDate") or item.get("startTime")
        if not title or not start:
            continue
        dt = parse_date(start)
        if not dt or dt.date() < cutoff:
            continue
        url = item.get("url") or base_url
        location = item.get("location", {})
        loc_str = (clean_text(location.get("name", "")) if isinstance(location, dict) else str(location)) or location_default
        desc = strip_html(item.get("description", ""))[:400]
        _add(_build_event(institution, title, dt.date(), dt, loc_str, desc, url, base_url))

    # Strategy 2: <time datetime>
    for time_el in soup.select("time[datetime]"):
        raw_dt = time_el.get("datetime", "")
        dt = parse_date(raw_dt)
        if not dt or dt.date() < cutoff:
            continue
        container = time_el
        for _ in range(10):
            container = container.parent
            if container is None or container.name in ("body", "html"):
                break
            title_el = _find_title_in_container(container)
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 5:
                continue
            link_el = container.find("a", href=True)
            href = link_el.get("href", "") if link_el else ""
            desc = strip_html(container.find("p"))[:400] if container.find("p") else ""
            _add(_build_event(institution, title, dt.date(), dt, location_default, desc,
                               make_absolute(href, base_url), base_url))
            break

    # Strategy 3: data-date / data-start attributes
    date_attr_selectors = [
        "[data-date]", "[data-start-date]", "[data-event-date]",
        "[data-start]", "[data-datetime]", "[data-timestamp]",
    ]
    for sel in date_attr_selectors:
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
            if not dt or dt.date() < cutoff:
                continue
            container = el
            title_el = None
            for _ in range(10):
                title_el = _find_title_in_container(container)
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
            link_el = el.find_parent("a") or el.find("a", href=True)
            href = link_el.get("href", "") if link_el else ""
            _add(_build_event(institution, title, dt.date(), dt, location_default, "",
                               make_absolute(href, base_url), base_url))

    # Strategy 4: French text date scan in event-like containers
    EVENT_CONTAINER_SELECTORS = (
        "article, [class*='event' i], [class*='agenda' i], [class*='conference' i],"
        " [class*='seminaire' i], [class*='card' i],"
        " [class*='item' i], [class*='lecture' i], [class*='cours' i],"
        " li[class*='program' i], div[class*='program' i]"
    )
    for container in soup.select(EVENT_CONTAINER_SELECTORS):
        full_text = container.get_text(" ", strip=True)
        d = parse_french_date_text(full_text)
        if not d or d < cutoff:
            continue
        title_el = _find_title_in_container(container)
        if not title_el:
            continue
        title = clean_text(title_el.get_text())
        if not title or len(title) < 8 or title.lower().startswith(("agenda", "programme", "calendrier")):
            continue
        if container.find_parent(["nav", "header", "footer"]):
            continue
        link_el = container.find("a", href=True)
        href = link_el.get("href", "") if link_el else ""
        desc_el = container.find("p")
        desc = strip_html(desc_el)[:400] if desc_el else ""
        _add(_build_event(institution, title, d, None, location_default, desc,
                           make_absolute(href, base_url), base_url))

    if not events:
        print(f"   [DEBUG] soup size={len(str(soup))} | time_datetime={len(soup.select('time[datetime]'))} | articles={len(soup.select('article'))}")

    return events


# ── Per-institution scrapers ──────────────────────────────────────────────────

def scrape_site(browser, name: str, urls: list[tuple[str, str, str]]) -> list[dict]:
    """Generic site scraper trying multiple URLs."""
    print(f"→ {name}...")
    all_events = []
    for url, loc, base in urls:
        html, title = pw_get_html(browser, url)
        print(f"   [{url}] page_title='{title[:50]}' html_len={len(html)}")
        events = extract_events_universal(html, name, loc, base)
        print(f"   → {len(events)} events from this URL")
        all_events.extend(events)
    seen, out = set(), []
    for e in all_events:
        k = (e["title"][:50].lower(), e["date"])
        if k not in seen:
            seen.add(k)
            out.append(e)
    print(f"   Total {name}: {len(out)} events")
    return out


def scrape_college_de_france(browser):
    """Dedicated Collège de France scraper.

    CdF runs a Nuxt.js site. It loads event data via internal API calls.
    Strategy: intercept network responses + fallback to HTML parsing.
    """
    print("→ Collège de France (network intercept + targeted HTML)...")
    events = []
    captured = []

    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="fr-FR",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    )
    page = ctx.new_page()

    def on_response(response):
        url = response.url
        if response.status == 200 and (
            "college-de-france.fr" in url or "api" in url.lower()
        ) and "json" in response.headers.get("content-type", ""):
            try:
                body = response.json()
                captured.append((url, body))
            except Exception:
                pass

    page.on("response", on_response)

    html = ""
    try:
        page.goto("https://www.college-de-france.fr/fr/agenda",
                  timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=25000)
        except PWTimeout:
            page.wait_for_timeout(4000)
        accept_cookies(page)

        for i in range(10):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(1000)
            if i == 4:
                page.wait_for_timeout(2000)

        for label in ["Voir plus", "Plus d'événements", "Charger plus", "Load more", "Suivant"]:
            try:
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count() > 0:
                    btn.first.click(timeout=2000)
                    page.wait_for_timeout(2000)
                    for _ in range(4):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(800)
            except Exception:
                pass

        html = page.content()
        print(f"   html_len={len(html)} | api_calls_captured={len(captured)}")
    except Exception as e:
        print(f"   [WARN] CdF: {e}")
    finally:
        ctx.close()

    BASE = "https://www.college-de-france.fr"
    LOC = "Collège de France, 11 place Marcelin-Berthelot, Paris 5e"

    # Strategy 1: Parse captured API JSON
    for api_url, body in captured:
        items = []
        if isinstance(body, list):
            items = body
        elif isinstance(body, dict):
            for key in ("data", "events", "results", "items", "conferences", "seminaires"):
                if isinstance(body.get(key), list):
                    items = body[key]
                    break

        for item in items:
            if not isinstance(item, dict):
                continue
            title = clean_text(
                item.get("title") or item.get("titre") or item.get("name") or
                item.get("label") or item.get("intitule") or ""
            )
            if not title or len(title) < 5:
                continue
            start_raw = (
                item.get("startDate") or item.get("start_date") or item.get("date_debut") or
                item.get("date") or item.get("dateDebut") or item.get("start") or ""
            )
            dt = parse_date(str(start_raw)) if start_raw else None
            if not dt or dt.date() < date.today() - timedelta(days=1):
                continue
            speaker = clean_text(
                item.get("speaker") or item.get("intervenant") or
                item.get("professor") or item.get("professeur") or
                ((item.get("speakers") or [{}])[0].get("name") if isinstance(item.get("speakers"), list) else "") or ""
            )
            url = make_absolute(item.get("url") or item.get("link") or item.get("slug") or "", BASE)
            desc = strip_html(item.get("description") or item.get("resume") or "")[:400]
            events.append({
                "id": make_id("cdf", title, str(dt.date())),
                "title": title,
                "institution": "Collège de France",
                "discipline": detect_discipline(title, desc),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                "end_time": "",
                "location": LOC,
                "description": desc,
                "url": url or f"{BASE}/fr/agenda",
                "speaker": speaker,
                "source_type": "institution",
            })

    # Strategy 2/3/4: Parse rendered HTML
    if html:
        seen = {(e["title"][:50].lower(), e["date"]) for e in events}
        soup = BeautifulSoup(html, "lxml")

        CDF_CARD_SELECTORS = [
            ".c-card--event", ".EventCard", ".event-card", ".agenda-card",
            ".c-event-teaser", ".EventTeaser", ".lecture-card",
            "article[class*='event' i]", "article[class*='agenda' i]",
            "div[class*='event-item' i]", "div[class*='EventItem']",
            "li[class*='event' i]", ".program-item",
            "[class*='cours' i]", "[class*='seminar' i]",
        ]
        for sel in CDF_CARD_SELECTORS:
            cards = soup.select(sel)
            if not cards:
                continue
            print(f"   [{sel}] → {len(cards)} cards found")
            for card in cards:
                full_text = card.get_text(" ", strip=True)
                d = parse_french_date_text(full_text)
                if not d:
                    time_el = card.find("time", {"datetime": True})
                    if time_el:
                        dt_obj = parse_date(time_el["datetime"])
                        d = dt_obj.date() if dt_obj else None
                if not d or d < date.today() - timedelta(days=1):
                    continue
                title_el = card.find(["h1", "h2", "h3", "h4", "h5"])
                if not title_el:
                    title_el = card.select_one("[class*='title' i], [class*='name' i]")
                if not title_el:
                    continue
                title = clean_text(title_el.get_text())
                if not title or len(title) < 8:
                    continue
                key = (title[:50].lower(), d.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                link_el = card.find("a", href=True)
                href = link_el.get("href", "") if link_el else ""
                speaker_el = card.select_one(
                    "[class*='author' i], [class*='speaker' i], [class*='professeur' i], "
                    "[class*='professor' i], [class*='intervenant' i]"
                )
                speaker = clean_text(speaker_el.get_text()) if speaker_el else ""
                desc_el = card.find("p")
                desc = strip_html(desc_el)[:400] if desc_el else ""
                events.append({
                    "id": make_id("cdf", title, d.isoformat()),
                    "title": title,
                    "institution": "Collège de France",
                    "discipline": detect_discipline(title, desc),
                    "date": d.isoformat(),
                    "time": "",
                    "end_time": "",
                    "location": LOC,
                    "description": desc,
                    "url": make_absolute(href, BASE),
                    "speaker": speaker,
                    "source_type": "institution",
                })

        if len(events) == 0:
            print("   [FALLBACK] Using universal extractor on CdF HTML")
            events = extract_events_universal(html, "Collège de France", LOC, BASE)

    print(f"   Total Collège de France: {len(events)} events")
    return events


def scrape_ehess(browser):
    return scrape_site(browser, "EHESS", [
        ("https://www.ehess.fr/fr/agenda",
         "EHESS, 54 boulevard Raspail, Paris 6e",
         "https://www.ehess.fr"),
    ])


def scrape_ens(browser):
    return scrape_site(browser, "ENS Paris", [
        ("https://www.ens.psl.eu/agenda",
         "ENS, 45 rue d'Ulm, Paris 5e",
         "https://www.ens.psl.eu"),
        ("https://www.ens.psl.eu/evenements",
         "ENS, 45 rue d'Ulm, Paris 5e",
         "https://www.ens.psl.eu"),
    ])


def scrape_sciences_po(browser):
    return scrape_site(browser, "Sciences Po", [
        ("https://www.sciencespo.fr/agenda/fr",
         "Sciences Po, 27 rue Saint-Guillaume, Paris 7e",
         "https://www.sciencespo.fr"),
        ("https://www.sciencespo.fr/events/fr",
         "Sciences Po, 27 rue Saint-Guillaume, Paris 7e",
         "https://www.sciencespo.fr"),
    ])


def scrape_sorbonne(browser):
    return scrape_site(browser, "Sorbonne Université", [
        ("https://www.sorbonne-universite.fr/evenements",
         "Sorbonne, Paris",
         "https://www.sorbonne-universite.fr"),
        ("https://lettres.sorbonne-universite.fr/agenda",
         "Sorbonne Lettres, 1 rue Victor Cousin, Paris 5e",
         "https://lettres.sorbonne-universite.fr"),
    ])


# ── Luma ──────────────────────────────────────────────────────────────────────

def _parse_luma_event(entry: dict):
    """Parse a single event from Luma's API response format."""
    ev = entry.get("event", entry)
    title = clean_text(ev.get("name", "") or ev.get("summary", "") or "")
    if not title:
        return None
    start_raw = ev.get("start_at") or ev.get("startDate") or ev.get("starts_at") or ""
    dt = parse_date(start_raw)
    if not dt or dt.date() < date.today() - timedelta(days=1):
        return None
    location = ev.get("geo_address_info", {}) or {}
    loc_str = clean_text(
        location.get("full_address") or location.get("address") or
        ev.get("location", "") or "Paris"
    )
    host_info = entry.get("host_calendars") or entry.get("hosts") or []
    institution = "Luma"
    if isinstance(host_info, list) and host_info:
        institution = clean_text(host_info[0].get("name", "Luma")) or "Luma"
    url = ev.get("url") or f"https://lu.ma/{ev.get('api_id', '')}"
    return {
        "id": make_id("luma", title, str(dt.date())),
        "title": title,
        "institution": institution,
        "discipline": detect_discipline(title, ev.get("description", "")),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
        "end_time": "",
        "location": loc_str,
        "description": strip_html(ev.get("description", ""))[:400],
        "url": make_absolute(url, "https://lu.ma"),
        "speaker": "",
        "source_type": "luma",
    }


def scrape_luma(browser) -> list[dict]:
    """Scrape Luma Paris events via network interception of api.lu.ma calls."""
    print("→ Luma Paris (network intercept)...")
    events = []
    captured_responses = []

    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="fr-FR",
        viewport={"width": 1366, "height": 900},
    )
    page = ctx.new_page()

    def handle_response(response):
        url = response.url
        if "api.lu.ma" in url and response.status == 200:
            try:
                body = response.json()
                captured_responses.append(body)
            except Exception:
                pass

    page.on("response", handle_response)

    html = ""
    try:
        page.goto("https://lu.ma/paris", timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except PWTimeout:
            page.wait_for_timeout(3000)
        accept_cookies(page)

        for _ in range(6):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(1200)

        html = page.content()
    except Exception as e:
        print(f"   [WARN] Luma: {e}")
        html = ""
    finally:
        ctx.close()

    print(f"   captured {len(captured_responses)} API responses")

    # Parse captured API responses
    for body in captured_responses:
        entries = body.get("entries") or body.get("events") or body.get("items") or []
        for entry in entries:
            ev = _parse_luma_event(entry)
            if ev:
                events.append(ev)

    # Fallback: JSON-LD + <time> from rendered HTML
    if html:
        soup = BeautifulSoup(html, "lxml")
        seen = {(e["title"][:50].lower(), e["date"]) for e in events}

        for item in extract_jsonld_events(soup):
            title = clean_text(item.get("name", ""))
            start = item.get("startDate") or item.get("startTime")
            if not title or not start:
                continue
            dt = parse_date(start)
            if not dt or dt.date() < date.today() - timedelta(days=1):
                continue
            key = (title[:50].lower(), dt.date().isoformat())
            if key in seen:
                continue
            seen.add(key)
            location = item.get("location", {})
            loc_str = (clean_text(location.get("name", "")) if isinstance(location, dict) else "") or "Paris"
            organizer = item.get("organizer") or {}
            host = organizer.get("name", "Luma") if isinstance(organizer, dict) else "Luma"
            events.append({
                "id": make_id("luma", title, str(dt.date())),
                "title": title,
                "institution": clean_text(host) or "Luma",
                "discipline": detect_discipline(title, item.get("description", "")),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                "end_time": "",
                "location": loc_str,
                "description": strip_html(item.get("description", ""))[:400],
                "url": make_absolute(item.get("url", ""), "https://lu.ma"),
                "speaker": "",
                "source_type": "luma",
            })

        for time_el in soup.select("time[datetime]"):
            dt = parse_date(time_el.get("datetime", ""))
            if not dt or dt.date() < date.today() - timedelta(days=1):
                continue
            container = time_el
            for _ in range(8):
                container = container.parent
                if container is None:
                    break
                a_el = container.find("a", href=True)
                if not a_el:
                    continue
                href = a_el.get("href", "")
                if not re.match(r"^/[a-z0-9_-]+$", href):
                    continue
                title_el = container.find(["h1", "h2", "h3", "h4"])
                if not title_el:
                    texts = [t for t in container.stripped_strings if len(t) > 8]
                    title = texts[0] if texts else ""
                else:
                    title = clean_text(title_el.get_text())
                if len(title) < 5:
                    continue
                key = (title[:50].lower(), dt.date().isoformat())
                if key in seen:
                    break
                seen.add(key)
                events.append({
                    "id": make_id("luma", title, str(dt.date())),
                    "title": title,
                    "institution": "Luma",
                    "discipline": detect_discipline(title),
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                    "end_time": "",
                    "location": "Paris",
                    "description": "",
                    "url": "https://lu.ma" + href,
                    "speaker": "",
                    "source_type": "luma",
                })
                break

    print(f"   {len(events)} events")
    return events


# ── Main ──────────────────────────────────────────────────────────────────────

def deduplicate(events: list[dict]) -> list[dict]:
    seen, out = set(), []
    for ev in events:
        key = (ev["title"].lower()[:60], ev["date"], ev["institution"])
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out


def filter_future(events: list[dict]) -> list[dict]:
    cutoff = (date.today() - timedelta(days=1)).isoformat()
    return [ev for ev in events if ev.get("date", "") >= cutoff]


def main():
    all_events = []

    try:
        all_events.extend(scrape_indico(
            "Institut Henri Poincaré",
            "https://indico.math.cnrs.fr", "0",
            "IHP, 11 rue Pierre et Marie Curie, Paris 5e",
        ))
    except Exception as e:
        print(f"[ERROR] IHP: {e}")
        traceback.print_exc()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            for fn in [
                scrape_college_de_france,
                scrape_ehess,
                scrape_ens,
                scrape_sciences_po,
                scrape_sorbonne,
                scrape_luma,
            ]:
                try:
                    all_events.extend(fn(browser))
                except Exception as e:
                    print(f"[ERROR] {fn.__name__}: {e}")
                    traceback.print_exc()
        finally:
            browser.close()

    all_events = deduplicate(all_events)
    all_events = filter_future(all_events)
    all_events.sort(key=lambda e: (e["date"], e.get("time", "")))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    n_inst = sum(1 for e in all_events if e.get("source_type") == "institution")
    n_luma = sum(1 for e in all_events if e.get("source_type") == "luma")
    print(f"\n✓ {len(all_events)} events ({n_inst} institutions · {n_luma} Luma)")


if __name__ == "__main__":
    main()
