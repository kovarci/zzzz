#!/usr/bin/env python3
"""
Scraper for Paris academic conferences.
Combines:
- Indico API (IHP and other CNRS instances)
- Playwright for JavaScript-rendered sites (Collège de France, EHESS, ENS, Sciences Po, Sorbonne)
- Luma API for informal academic events in Paris
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
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
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
        "souveraineté", "politique publique", "géopolitique", "international",
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


def strip_html(s: str) -> str:
    """Strip HTML tags from a string and return clean text."""
    if not s:
        return ""
    try:
        text = BeautifulSoup(s, "lxml").get_text(separator=" ")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", s)
    return clean_text(text)


def parse_date(s: str):
    if not s:
        return None
    try:
        return dateparser.parse(s, dayfirst=True, languages=["fr", "en"], fuzzy=True)
    except Exception:
        return None


# ── Indico-based sources (proper JSON API) ────────────────────────────────────

INDICO_SOURCES = [
    {
        "name": "Institut Henri Poincaré",
        "base": "https://indico.math.cnrs.fr",
        "categ": "0",
        "location_default": "IHP, 11 rue Pierre et Marie Curie, Paris 5e",
        "filter_paris": True,
    },
]


def scrape_indico(source: dict) -> list[dict]:
    print(f"→ Indico: {source['name']}...")
    events = []
    today = date.today()
    end = today + timedelta(days=120)
    url = (
        f"{source['base']}/export/categ/{source['categ']}.json"
        f"?from={today.isoformat()}&to={end.isoformat()}&limit=200"
    )
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

        location = clean_text(item.get("location", "")) or clean_text(item.get("room", ""))
        if source.get("filter_paris"):
            if location and not re.search(
                r"paris|ihp|jussieu|sorbonne|ens |college de france|"
                r"sciences po|cdf|ehess|henri poincar", location, re.I
            ):
                continue
        if not location:
            location = source["location_default"]

        raw_end = item.get("endDate", {})
        end_time = ""
        try:
            dt_end = dateparser.parse(f"{raw_end.get('date', '')} {raw_end.get('time', '')}".strip())
            if dt_end:
                end_time = dt_end.strftime("%H:%M")
        except Exception:
            pass

        desc = strip_html(item.get("description", ""))[:500]
        speakers = ", ".join(s.get("fullName", "") for s in item.get("speakers", []))[:120]

        events.append({
            "id": make_id(source["name"], title, str(dt.date())),
            "title": title,
            "institution": source["name"],
            "discipline": detect_discipline(title, desc),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
            "end_time": end_time,
            "location": location,
            "description": desc,
            "url": item.get("url", source["base"]),
            "speaker": clean_text(speakers),
            "source_type": "institution",
        })
    print(f"   {len(events)} events")
    return events


# ── Playwright-based scrapers (JS-rendered sites) ─────────────────────────────

def pw_get_html(browser, url: str, wait_selector: str | None = None, scroll: bool = False) -> str:
    """Load a URL with Playwright and return the rendered HTML."""
    ctx = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="fr-FR",
        viewport={"width": 1280, "height": 900},
    )
    page = ctx.new_page()
    html = ""
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeout:
            pass
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=8000)
            except PWTimeout:
                pass
        if scroll:
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(800)
        html = page.content()
    except Exception as e:
        print(f"   [WARN] Playwright failed for {url}: {e}")
    finally:
        ctx.close()
    return html


def extract_events_from_html(
    html: str,
    institution: str,
    location_default: str,
    base_url: str,
    selectors: list[str],
) -> list[dict]:
    """Try multiple selector patterns to find event cards in rendered HTML."""
    soup = BeautifulSoup(html, "lxml")
    events = []

    for sel in selectors:
        cards = soup.select(sel)
        if len(cards) < 2:
            continue
        for card in cards[:60]:
            title_el = card.select_one(
                "h1, h2, h3, h4, .title, .field--name-title, [class*='title'], [class*='Title']"
            )
            date_el = card.select_one(
                "time, .date, .field--name-field-date, .views-field-field-date, "
                "[class*='date'], [datetime]"
            )
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 5:
                continue

            raw_date = ""
            if date_el:
                raw_date = date_el.get("datetime") or clean_text(date_el.get_text())
            dt = parse_date(raw_date)
            if not dt:
                continue

            link_el = card.select_one("a[href]")
            url_path = link_el.get("href", "") if link_el else ""
            if url_path.startswith("/"):
                full_url = base_url.rstrip("/") + url_path
            elif url_path.startswith("http"):
                full_url = url_path
            else:
                full_url = base_url

            desc_el = card.select_one(
                ".field--name-body, .views-field-body, .description, .summary, p"
            )
            desc = strip_html(str(desc_el))[:500] if desc_el else ""

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
        if events:
            break
    return events


def scrape_college_de_france(browser) -> list[dict]:
    print("→ Collège de France...")
    html = pw_get_html(
        browser,
        "https://www.college-de-france.fr/fr/agenda",
        wait_selector="article, .card, [class*='event'], [class*='Event']",
        scroll=True,
    )
    events = extract_events_from_html(
        html,
        institution="Collège de France",
        location_default="Collège de France, 11 place Marcelin-Berthelot, Paris 5e",
        base_url="https://www.college-de-france.fr",
        selectors=[
            "article.event-card",
            ".cdf-card-agenda",
            "article[class*='agenda']",
            "[class*='EventCard']",
            ".card-event",
            "article",
        ],
    )
    print(f"   {len(events)} events")
    return events


def scrape_ehess(browser) -> list[dict]:
    print("→ EHESS...")
    html = pw_get_html(
        browser,
        "https://www.ehess.fr/fr/agenda",
        wait_selector=".views-row, article, [class*='event']",
        scroll=True,
    )
    events = extract_events_from_html(
        html,
        institution="EHESS",
        location_default="EHESS, 54 boulevard Raspail, Paris 6e",
        base_url="https://www.ehess.fr",
        selectors=[
            ".views-row",
            "article.event",
            ".node--type-event",
            "article",
            "li.event-item",
        ],
    )
    print(f"   {len(events)} events")
    return events


def scrape_ens(browser) -> list[dict]:
    print("→ ENS Paris...")
    html = pw_get_html(
        browser,
        "https://www.ens.psl.eu/agenda",
        wait_selector=".views-row, article, [class*='event']",
        scroll=True,
    )
    events = extract_events_from_html(
        html,
        institution="ENS Paris",
        location_default="ENS, 45 rue d'Ulm, Paris 5e",
        base_url="https://www.ens.psl.eu",
        selectors=[
            ".view-content .views-row",
            "article.node--type-event",
            ".event-item",
            "article",
        ],
    )
    print(f"   {len(events)} events")
    return events


def scrape_sciences_po(browser) -> list[dict]:
    print("→ Sciences Po...")
    html = pw_get_html(
        browser,
        "https://www.sciencespo.fr/agenda/fr",
        wait_selector=".views-row, article, [class*='event']",
        scroll=True,
    )
    events = extract_events_from_html(
        html,
        institution="Sciences Po",
        location_default="Sciences Po, 27 rue Saint-Guillaume, Paris 7e",
        base_url="https://www.sciencespo.fr",
        selectors=[
            ".view-content .views-row",
            ".node--type-event",
            "article.event",
            "article",
        ],
    )
    print(f"   {len(events)} events")
    return events


def scrape_sorbonne(browser) -> list[dict]:
    print("→ Sorbonne Université...")
    events = []
    urls = [
        ("https://www.sorbonne-universite.fr/evenements",
         "Sorbonne, 21 rue de l'École de Médecine, Paris 6e",
         "https://www.sorbonne-universite.fr"),
        ("https://lettres.sorbonne-universite.fr/agenda",
         "Sorbonne Lettres, 1 rue Victor Cousin, Paris 5e",
         "https://lettres.sorbonne-universite.fr"),
    ]
    for url, loc, base in urls:
        html = pw_get_html(
            browser, url,
            wait_selector="article, .views-row, [class*='event']",
            scroll=True,
        )
        sub_events = extract_events_from_html(
            html,
            institution="Sorbonne Université",
            location_default=loc,
            base_url=base,
            selectors=[
                ".view-content .views-row",
                "article.event",
                ".node--type-event",
                "article",
            ],
        )
        events.extend(sub_events)
    print(f"   {len(events)} events")
    return events


# ── Luma (informal academic events) ───────────────────────────────────────────

def scrape_luma(browser) -> list[dict]:
    """Scrape Luma Paris events page."""
    print("→ Luma Paris...")
    events = []
    html = pw_get_html(
        browser,
        "https://lu.ma/paris",
        wait_selector="a[href*='lu.ma'], .event-card, [class*='event']",
        scroll=True,
    )
    if not html:
        return events

    soup = BeautifulSoup(html, "lxml")
    # Luma renders events as anchor cards. Look for anchors with hrefs and inner content
    seen = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        # Luma event URLs are typically /{slug}
        if not re.match(r"^/[a-z0-9-]+$", href):
            continue
        if href in seen:
            continue
        seen.add(href)

        text_blocks = [clean_text(s) for s in a.stripped_strings]
        if len(text_blocks) < 2:
            continue

        # The structure: usually [date_line, time_line, title, host, location, ...]
        # Heuristic: pick the longest text block as title, look for time pattern, etc.
        title = ""
        time_str = ""
        date_str = ""
        host = ""

        for blk in text_blocks:
            if re.match(r"^\d{1,2}:\d{2}", blk):
                time_str = blk[:5]
            elif re.search(r"(lun|mar|mer|jeu|ven|sam|dim|mon|tue|wed|thu|fri|sat|sun)", blk, re.I) \
                    and not date_str:
                date_str = blk
            elif len(blk) > 10 and not title and not blk.startswith("@"):
                title = blk
            elif not host and 2 < len(blk) < 80 and blk != title:
                host = blk

        if not title:
            continue

        dt = parse_date(date_str)
        # If no parseable date, skip
        if not dt:
            continue

        full_url = "https://lu.ma" + href
        # Filter to upcoming
        if dt.date() < date.today() - timedelta(days=1):
            continue

        events.append({
            "id": make_id("luma", title, str(dt.date())),
            "title": title,
            "institution": host or "Luma",
            "discipline": detect_discipline(title),
            "date": dt.strftime("%Y-%m-%d"),
            "time": time_str,
            "end_time": "",
            "location": "Paris",
            "description": "",
            "url": full_url,
            "speaker": "",
            "source_type": "luma",
        })

    # Also try the JSON discover endpoint
    try:
        r = requests.get(
            "https://api.lu.ma/discover/get-paginated-events",
            params={"period": "future", "pagination_limit": 50, "discover_place_api_id": ""},
            headers=HEADERS,
            timeout=15,
        )
        if r.ok:
            for item in r.json().get("entries", []):
                ev = item.get("event", {})
                title = clean_text(ev.get("name", ""))
                start = ev.get("start_at", "")
                geo = (ev.get("geo_address_info") or {}).get("city_state", "")
                if not title or not start or "paris" not in geo.lower():
                    continue
                dt = parse_date(start)
                if not dt:
                    continue
                events.append({
                    "id": make_id("luma", title, str(dt.date())),
                    "title": title,
                    "institution": clean_text((ev.get("hosts") or [{}])[0].get("name", "Luma")),
                    "discipline": detect_discipline(title, ev.get("description_short", "")),
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M") if (dt.hour or dt.minute) else "",
                    "end_time": "",
                    "location": clean_text(ev.get("geo_address_info", {}).get("address", "Paris")),
                    "description": clean_text(ev.get("description_short", ""))[:500],
                    "url": f"https://lu.ma/{ev.get('url', '')}",
                    "speaker": "",
                    "source_type": "luma",
                })
    except Exception as e:
        print(f"   [WARN] Luma API: {e}")

    print(f"   {len(events)} events")
    return events


# ── Main ──────────────────────────────────────────────────────────────────────

def deduplicate(events: list[dict]) -> list[dict]:
    seen = set()
    out = []
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

    # 1) API-based sources (no browser needed)
    for src in INDICO_SOURCES:
        try:
            all_events.extend(scrape_indico(src))
        except Exception as e:
            print(f"[ERROR] Indico {src['name']}: {e}")
            traceback.print_exc()

    # 2) Browser-based sources
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            for scraper in [
                scrape_college_de_france,
                scrape_ehess,
                scrape_ens,
                scrape_sciences_po,
                scrape_sorbonne,
                scrape_luma,
            ]:
                try:
                    all_events.extend(scraper(browser))
                except Exception as e:
                    print(f"[ERROR] {scraper.__name__}: {e}")
                    traceback.print_exc()
        finally:
            browser.close()

    # 3) Clean up
    all_events = deduplicate(all_events)
    all_events = filter_future(all_events)
    all_events.sort(key=lambda e: (e["date"], e.get("time", "")))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    n_inst = sum(1 for e in all_events if e.get("source_type") == "institution")
    n_luma = sum(1 for e in all_events if e.get("source_type") == "luma")
    print(f"\n✓ {len(all_events)} events ({n_inst} institutions · {n_luma} Luma)")
    print(f"  Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
