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
    # Try generic cookie banner close
    for sel in ["#tarteaucitronAllAllowed", "#axeptio_btn_acceptAll", "[id*='accept']", "[class*='accept']"]:
        try:
            page.locator(sel).first.click(timeout=1000)
            page.wait_for_timeout(500)
            return
        except Exception:
            pass


def pw_get_html(browser, url: str, scroll: bool = True) -> tuple[str, str]:
    """Load URL with Playwright. Returns (html, page_title)."""
    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="fr-FR",
        viewport={"width": 1366, "height": 900},
    )
    page = ctx.new_page()
    html, title = "", ""
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeout:
            pass
        accept_cookies(page)
        if scroll:
            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(700)
        html = page.content()
        title = page.title()
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


def extract_events_universal(
    html: str,
    institution: str,
    location_default: str,
    base_url: str,
) -> list[dict]:
    """Robust extractor: JSON-LD first, then <time datetime> scan."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    events = []
    seen = set()

    # Strategy 1: JSON-LD
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
        url = item.get("url") or base_url
        location = item.get("location", {})
        if isinstance(location, dict):
            loc_str = clean_text(location.get("name", "")) or location_default
        else:
            loc_str = str(location) or location_default
        desc = strip_html(item.get("description", ""))[:400]
        events.append({
            "id": make_id(institution, title, str(dt.date())),
            "title": title,
            "institution": institution,
            "discipline": detect_discipline(title, desc),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
            "end_time": "",
            "location": loc_str,
            "description": desc,
            "url": make_absolute(url, base_url),
            "speaker": "",
            "source_type": "institution",
        })

    # Strategy 2: <time datetime> elements
    for time_el in soup.select("time[datetime]"):
        raw_dt = time_el.get("datetime", "")
        dt = parse_date(raw_dt)
        if not dt or dt.date() < date.today() - timedelta(days=1):
            continue

        # Walk up parents to find title + link
        container = time_el
        found = False
        for _ in range(8):
            container = container.parent
            if container is None or container.name in ("body", "html"):
                break
            title_el = container.find(["h1", "h2", "h3", "h4", "h5"])
            if not title_el:
                title_el = container.select_one(
                    "[class*='title' i], [class*='Title'], strong, b"
                )
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 5:
                continue
            key = (title[:50].lower(), dt.date().isoformat())
            if key in seen:
                found = True
                break
            seen.add(key)

            link_el = container.find("a", href=True)
            href = link_el.get("href", "") if link_el else ""
            full_url = make_absolute(href, base_url)

            desc_el = container.find("p")
            desc = strip_html(desc_el)[:400] if desc_el else ""

            events.append({
                "id": make_id(institution, title, str(dt.date())),
                "title": title,
                "institution": institution,
                "discipline": detect_discipline(title, desc),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                "end_time": "",
                "location": location_default,
                "description": desc,
                "url": full_url,
                "speaker": "",
                "source_type": "institution",
            })
            found = True
            break

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
    # Dedup within institution
    seen, out = set(), []
    for e in all_events:
        k = (e["title"][:50].lower(), e["date"])
        if k not in seen:
            seen.add(k)
            out.append(e)
    print(f"   Total {name}: {len(out)} events")
    return out


def scrape_college_de_france(browser):
    return scrape_site(browser, "Collège de France", [
        ("https://www.college-de-france.fr/fr/agenda",
         "Collège de France, 11 place Marcelin-Berthelot, Paris 5e",
         "https://www.college-de-france.fr"),
    ])


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

def scrape_luma(browser) -> list[dict]:
    print("→ Luma Paris...")
    events = []
    html, _ = pw_get_html(browser, "https://lu.ma/paris", scroll=True)
    if html:
        soup = BeautifulSoup(html, "lxml")

        # Try JSON-LD
        for item in extract_jsonld_events(soup):
            title = clean_text(item.get("name", ""))
            start = item.get("startDate") or item.get("startTime")
            if not title or not start:
                continue
            dt = parse_date(start)
            if not dt or dt.date() < date.today() - timedelta(days=1):
                continue
            url = item.get("url", "https://lu.ma/paris")
            location = item.get("location", {})
            loc_str = ""
            if isinstance(location, dict):
                loc_str = clean_text(location.get("name", "")) or clean_text(location.get("address", ""))
            host = (item.get("organizer") or {}).get("name", "Luma") if isinstance(item.get("organizer"), dict) else "Luma"
            events.append({
                "id": make_id("luma", title, str(dt.date())),
                "title": title,
                "institution": clean_text(host) or "Luma",
                "discipline": detect_discipline(title, item.get("description", "")),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                "end_time": "",
                "location": loc_str or "Paris",
                "description": strip_html(item.get("description", ""))[:400],
                "url": make_absolute(url, "https://lu.ma"),
                "speaker": "",
                "source_type": "luma",
            })

        # Fallback: <time datetime> on the page
        seen = {(e["title"][:50].lower(), e["date"]) for e in events}
        for time_el in soup.select("time[datetime]"):
            dt = parse_date(time_el.get("datetime", ""))
            if not dt or dt.date() < date.today() - timedelta(days=1):
                continue
            container = time_el
            for _ in range(6):
                container = container.parent
                if container is None:
                    break
                a_el = container.find("a", href=True) if container.name != "a" else container
                if not a_el:
                    continue
                href = a_el.get("href", "")
                if not re.match(r"^/[a-z0-9-]+$", href):
                    continue
                # title heuristic
                title_el = container.find(["h1", "h2", "h3", "h4"])
                if not title_el:
                    texts = [t for t in container.stripped_strings if len(t) > 8]
                    if not texts:
                        continue
                    title = texts[0]
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

    # Indico APIs
    try:
        all_events.extend(scrape_indico(
            "Institut Henri Poincaré",
            "https://indico.math.cnrs.fr", "0",
            "IHP, 11 rue Pierre et Marie Curie, Paris 5e",
        ))
    except Exception as e:
        print(f"[ERROR] IHP: {e}")
        traceback.print_exc()

    # Browser-based
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
