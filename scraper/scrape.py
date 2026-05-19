#!/usr/bin/env python3
"""
Scraper for Paris academic conferences.
Runs daily via GitHub Actions and outputs data/events.json.
"""

import json
import re
import hashlib
import traceback
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "events.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ParisConferenceBot/1.0; academic calendar aggregator)"
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ── Discipline detection ──────────────────────────────────────────────────────

DISCIPLINE_KEYWORDS = {
    "Mathématiques": [
        "mathémat", "algèbre", "géométrie", "topologie", "analyse", "probabilité",
        "statistique", "calcul", "arithmétique", "combinatoire", "théorie des nombres",
        "équation", "logique mathématique", "math", "poincaré", "ihp",
    ],
    "Philosophie": [
        "philosoph", "éthique", "métaphysique", "épistémologie", "ontologie",
        "phénoménologie", "wittgenstein", "hegel", "kant", "nietzsche", "platon",
        "aristote", "logique philosophique", "esthétique philosophique",
    ],
    "Littérature": [
        "littératur", "roman", "poésie", "poème", "narratologie", "récit",
        "fiction", "auteur", "écrivain", "texte littéraire", "langue", "stylistique",
        "rhétorique", "traduction littéraire",
    ],
    "Histoire": [
        "histoir", "archive", "mémoire collective", "patrimoine", "médiéval",
        "antiquité", "révolution", "colonialism", "esclavage", "guerre", "empire",
        "historiograph", "sources historiques", "chronologie",
    ],
    "Sciences": [
        "physique", "chimie", "biologie", "neuroscienc", "génétique", "écologie",
        "astronomie", "astrophysique", "quantique", "thermodynamique", "évolution",
        "darwin", "climat", "environnement", "science cognitiv",
    ],
    "Économie": [
        "économi", "macro", "micro", "marché", "finance", "monétaire", "fiscal",
        "inégalité", "croissance", "emploi", "chomage", "travail", "salaire",
        "capitalisme", "économétrie", "comportemental",
    ],
    "Sociologie & Anthropologie": [
        "sociologi", "anthropologi", "ethnolog", "terrain", "enquête", "société",
        "classe sociale", "genre", "racisme", "discrimination", "migration",
        "identité", "culture", "rituel", "bourdieu", "durkheim",
    ],
    "Droit & Sciences politiques": [
        "droit", "juridique", "loi", "constitutionnel", "science politique",
        "démocratie", "gouvernance", "institution", "parlement", "élection",
        "souveraineté", "état", "politique publique", "géopolitique",
    ],
    "Arts & Culture": [
        "art", "musique", "cinéma", "film", "théâtre", "peinture", "sculpture",
        "architecture", "danse", "muséolog", "patrimoine culturel", "exposition",
        "esthétique", "photographie", "design",
    ],
}


def detect_discipline(title: str, description: str = "") -> str:
    text = (title + " " + description).lower()
    scores = {}
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score:
            scores[discipline] = score
    return max(scores, key=scores.get) if scores else "Autre"


def make_id(*parts: str) -> str:
    raw = "-".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def safe_get(url: str, **kwargs) -> requests.Response | None:
    try:
        r = SESSION.get(url, timeout=15, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [WARN] GET {url} failed: {e}")
        return None


# ── Scrapers ──────────────────────────────────────────────────────────────────

def scrape_college_de_france() -> list[dict]:
    """Collège de France – agenda JSON API."""
    events = []
    print("Scraping Collège de France...")
    # CdF exposes a JSON feed for their agenda
    url = "https://www.college-de-france.fr/api/agenda?format=json&nb=100"
    r = safe_get(url)
    if r:
        try:
            data = r.json()
            items = data if isinstance(data, list) else data.get("events", data.get("items", []))
            for item in items:
                title = item.get("title", item.get("name", "")).strip()
                raw_date = item.get("date", item.get("startDate", item.get("start", "")))
                if not title or not raw_date:
                    continue
                try:
                    dt = dateparser.parse(str(raw_date))
                except Exception:
                    continue
                desc = item.get("description", item.get("summary", ""))
                events.append({
                    "id": make_id("cdf", title, str(dt.date())),
                    "title": title,
                    "institution": "Collège de France",
                    "discipline": detect_discipline(title, desc),
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M") if dt.hour else "",
                    "end_time": "",
                    "location": item.get("location", item.get("place", "Collège de France, 11 place Marcelin-Berthelot")),
                    "description": desc[:400],
                    "url": item.get("url", item.get("link", "https://www.college-de-france.fr/fr/agenda")),
                    "speaker": item.get("speaker", item.get("author", "")),
                    "language": "fr",
                })
        except Exception:
            pass

    # Fallback: scrape HTML agenda
    if not events:
        r2 = safe_get("https://www.college-de-france.fr/fr/agenda")
        if r2:
            soup = BeautifulSoup(r2.text, "lxml")
            for card in soup.select("article.event, .event-card, .agenda-item, [class*='event']")[:50]:
                title_el = card.select_one("h2, h3, .title, [class*='title']")
                date_el = card.select_one("time, .date, [class*='date']")
                if not title_el or not date_el:
                    continue
                title = title_el.get_text(strip=True)
                raw_date = date_el.get("datetime", date_el.get_text(strip=True))
                try:
                    dt = dateparser.parse(raw_date, dayfirst=True, languages=["fr"])
                    if not dt:
                        continue
                except Exception:
                    continue
                link_el = card.select_one("a[href]")
                url_path = link_el["href"] if link_el else ""
                full_url = url_path if url_path.startswith("http") else f"https://www.college-de-france.fr{url_path}"
                events.append({
                    "id": make_id("cdf", title, str(dt.date())),
                    "title": title,
                    "institution": "Collège de France",
                    "discipline": detect_discipline(title),
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M") if dt.hour else "",
                    "end_time": "",
                    "location": "Collège de France, 11 place Marcelin-Berthelot, Paris 5e",
                    "description": "",
                    "url": full_url,
                    "speaker": "",
                    "language": "fr",
                })

    print(f"  → {len(events)} events from Collège de France")
    return events


def scrape_ehess() -> list[dict]:
    """EHESS – agenda HTML."""
    events = []
    print("Scraping EHESS...")
    r = safe_get("https://www.ehess.fr/fr/agenda")
    if not r:
        return events
    soup = BeautifulSoup(r.text, "lxml")
    for card in soup.select(".views-row, article, .event-item")[:60]:
        title_el = card.select_one("h2, h3, h4, .views-field-title, .field--name-title")
        date_el = card.select_one("time, .date-display-single, .field--name-field-date, .views-field-field-date")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        raw_date = ""
        if date_el:
            raw_date = date_el.get("datetime", date_el.get_text(strip=True))
        try:
            dt = dateparser.parse(raw_date, dayfirst=True, languages=["fr"])
            if not dt:
                continue
        except Exception:
            continue
        link_el = card.select_one("a[href]")
        url_path = link_el["href"] if link_el else ""
        full_url = url_path if url_path.startswith("http") else f"https://www.ehess.fr{url_path}"
        desc_el = card.select_one(".field--name-body, .views-field-body, p")
        desc = desc_el.get_text(strip=True)[:400] if desc_el else ""
        events.append({
            "id": make_id("ehess", title, str(dt.date())),
            "title": title,
            "institution": "EHESS",
            "discipline": detect_discipline(title, desc),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M") if dt.hour else "",
            "end_time": "",
            "location": "EHESS, 54 boulevard Raspail, Paris 6e",
            "description": desc,
            "url": full_url,
            "speaker": "",
            "language": "fr",
        })
    print(f"  → {len(events)} events from EHESS")
    return events


def scrape_ens() -> list[dict]:
    """ENS PSL – agenda HTML."""
    events = []
    print("Scraping ENS Paris...")
    r = safe_get("https://www.ens.psl.eu/agenda")
    if not r:
        return events
    soup = BeautifulSoup(r.text, "lxml")
    for card in soup.select(".view-row, article, .event, [class*='event-item']")[:60]:
        title_el = card.select_one("h2, h3, .field--name-title, [class*='title']")
        date_el = card.select_one("time, [class*='date'], .field-date")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        raw_date = ""
        if date_el:
            raw_date = date_el.get("datetime", date_el.get_text(strip=True))
        try:
            dt = dateparser.parse(raw_date, dayfirst=True, languages=["fr"])
            if not dt:
                continue
        except Exception:
            continue
        link_el = card.select_one("a[href]")
        url_path = link_el["href"] if link_el else ""
        full_url = url_path if url_path.startswith("http") else f"https://www.ens.psl.eu{url_path}"
        events.append({
            "id": make_id("ens", title, str(dt.date())),
            "title": title,
            "institution": "ENS Paris",
            "discipline": detect_discipline(title),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M") if dt.hour else "",
            "end_time": "",
            "location": "ENS Paris, 45 rue d'Ulm, Paris 5e",
            "description": "",
            "url": full_url,
            "speaker": "",
            "language": "fr",
        })
    print(f"  → {len(events)} events from ENS Paris")
    return events


def scrape_ihp() -> list[dict]:
    """Institut Henri Poincaré – Indico API (CNRS)."""
    events = []
    print("Scraping IHP / Indico...")
    today = date.today()
    end = today + timedelta(days=90)
    url = (
        f"https://indico.math.cnrs.fr/export/categ/0.json"
        f"?from={today.isoformat()}&to={end.isoformat()}&limit=100"
    )
    r = safe_get(url)
    if r:
        try:
            data = r.json()
            for item in data.get("results", []):
                title = item.get("title", "").strip()
                raw_start = item.get("startDate", {})
                if not title or not raw_start:
                    continue
                try:
                    dt_str = f"{raw_start.get('date', '')} {raw_start.get('time', '')}"
                    dt = dateparser.parse(dt_str.strip())
                    if not dt:
                        continue
                except Exception:
                    continue
                raw_end = item.get("endDate", {})
                end_time = ""
                if raw_end:
                    try:
                        dt_end = dateparser.parse(f"{raw_end.get('date', '')} {raw_end.get('time', '')}")
                        end_time = dt_end.strftime("%H:%M") if dt_end else ""
                    except Exception:
                        pass
                desc = item.get("description", "")[:400]
                location = item.get("location", item.get("room", "IHP, 11 rue Pierre et Marie Curie, Paris 5e"))
                events.append({
                    "id": make_id("ihp", title, str(dt.date())),
                    "title": title,
                    "institution": "Institut Henri Poincaré",
                    "discipline": detect_discipline(title, desc),
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M") if dt.hour else "",
                    "end_time": end_time,
                    "location": location,
                    "description": desc,
                    "url": item.get("url", "https://www.ihp.fr/fr/agenda"),
                    "speaker": ", ".join(
                        s.get("fullName", "") for s in item.get("speakers", [])
                    )[:100],
                    "language": "fr",
                })
        except Exception:
            traceback.print_exc()

    # Fallback: IHP own website
    if not events:
        r2 = safe_get("https://www.ihp.fr/fr/agenda")
        if r2:
            soup = BeautifulSoup(r2.text, "lxml")
            for card in soup.select("article, .event-item, .views-row")[:40]:
                title_el = card.select_one("h2, h3, .title")
                date_el = card.select_one("time, .date")
                if not title_el or not date_el:
                    continue
                title = title_el.get_text(strip=True)
                raw_date = date_el.get("datetime", date_el.get_text(strip=True))
                try:
                    dt = dateparser.parse(raw_date, dayfirst=True, languages=["fr"])
                    if not dt:
                        continue
                except Exception:
                    continue
                events.append({
                    "id": make_id("ihp", title, str(dt.date())),
                    "title": title,
                    "institution": "Institut Henri Poincaré",
                    "discipline": detect_discipline(title),
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M") if dt.hour else "",
                    "end_time": "",
                    "location": "IHP, 11 rue Pierre et Marie Curie, Paris 5e",
                    "description": "",
                    "url": "https://www.ihp.fr/fr/agenda",
                    "speaker": "",
                    "language": "fr",
                })

    print(f"  → {len(events)} events from IHP")
    return events


def scrape_sciences_po() -> list[dict]:
    """Sciences Po Paris – agenda HTML."""
    events = []
    print("Scraping Sciences Po...")
    r = safe_get("https://www.sciencespo.fr/agenda/fr")
    if not r:
        return events
    soup = BeautifulSoup(r.text, "lxml")
    for card in soup.select(".view-content .views-row, article.event, .event-card")[:50]:
        title_el = card.select_one("h2, h3, .field--name-title")
        date_el = card.select_one("time, .date-display, .field-date")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        raw_date = ""
        if date_el:
            raw_date = date_el.get("datetime", date_el.get_text(strip=True))
        try:
            dt = dateparser.parse(raw_date, dayfirst=True, languages=["fr"])
            if not dt:
                continue
        except Exception:
            continue
        link_el = card.select_one("a[href]")
        url_path = link_el["href"] if link_el else ""
        full_url = url_path if url_path.startswith("http") else f"https://www.sciencespo.fr{url_path}"
        events.append({
            "id": make_id("scpo", title, str(dt.date())),
            "title": title,
            "institution": "Sciences Po",
            "discipline": detect_discipline(title),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M") if dt.hour else "",
            "end_time": "",
            "location": "Sciences Po, 27 rue Saint-Guillaume, Paris 7e",
            "description": "",
            "url": full_url,
            "speaker": "",
            "language": "fr",
        })
    print(f"  → {len(events)} events from Sciences Po")
    return events


def scrape_sorbonne() -> list[dict]:
    """Sorbonne Université – agenda HTML."""
    events = []
    print("Scraping Sorbonne...")
    r = safe_get("https://lettres.sorbonne-universite.fr/agenda")
    if not r:
        return events
    soup = BeautifulSoup(r.text, "lxml")
    for card in soup.select("article, .event, .agenda-event, .views-row")[:50]:
        title_el = card.select_one("h2, h3, .title")
        date_el = card.select_one("time, .date")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        raw_date = ""
        if date_el:
            raw_date = date_el.get("datetime", date_el.get_text(strip=True))
        try:
            dt = dateparser.parse(raw_date, dayfirst=True, languages=["fr"])
            if not dt:
                continue
        except Exception:
            continue
        link_el = card.select_one("a[href]")
        url_path = link_el["href"] if link_el else ""
        full_url = url_path if url_path.startswith("http") else f"https://lettres.sorbonne-universite.fr{url_path}"
        events.append({
            "id": make_id("sorb", title, str(dt.date())),
            "title": title,
            "institution": "Sorbonne",
            "discipline": detect_discipline(title),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M") if dt.hour else "",
            "end_time": "",
            "location": "Sorbonne, Paris 5e",
            "description": "",
            "url": full_url,
            "speaker": "",
            "language": "fr",
        })
    print(f"  → {len(events)} events from Sorbonne")
    return events


# ── Main ──────────────────────────────────────────────────────────────────────

SCRAPERS = [
    scrape_college_de_france,
    scrape_ehess,
    scrape_ens,
    scrape_ihp,
    scrape_sciences_po,
    scrape_sorbonne,
]


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
    for scraper in SCRAPERS:
        try:
            all_events.extend(scraper())
        except Exception as e:
            print(f"  [ERROR] {scraper.__name__}: {e}")
            traceback.print_exc()

    all_events = deduplicate(all_events)
    all_events = filter_future(all_events)
    all_events.sort(key=lambda e: (e["date"], e.get("time", "")))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(all_events)} events written to {OUTPUT_FILE}")
    print(f"Last updated: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
