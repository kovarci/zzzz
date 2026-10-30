"""Sonde temporaire (supprimée avant fusion)."""
import json, re
import requests
from bs4 import BeautifulSoup
import scrape

def get(u, **kw):
    r = requests.get(u, headers=scrape.CDF_HEADERS, timeout=40, **kw)
    return r, BeautifulSoup(r.content, "lxml")

def sq(s, n=400):
    return re.sub(r"\s+", " ", str(s))[:n]

def section(t):
    print(f"\n######## {t}", flush=True)

section("HEC IA")
r, s = get("https://hec-ia.com/en/events")
cards = s.select('[data-slot="card"]')
print(len(cards))
for c in cards[:6]:
    print("CARD:", sq(c.get_text(" | ", strip=True), 300))
    print("  badges:", [sq(b.get_text(" "), 40) for b in c.select('[data-slot="badge"]')], "| time:", [t.get("datetime") for t in c.select("time")])
print("HTML card0:", sq(cards[0], 1800) if cards else None)

section("PARIS CITE candidates")
for u in ("https://u-paris.fr/evenements/", "https://u-paris.fr/evenements-passes/", "https://u-paris.fr/en/events/",
          "https://u-paris.fr/wp-json/wp/v2/types", "https://u-paris.fr/wp-json/eventorg/v1",
          "https://u-paris.fr/wp-json/wp/v2/event?per_page=3", "https://u-paris.fr/feed/?post_type=event",
          "https://u-paris.fr/event/?feed=ical", "https://u-paris.fr/?feed=eo-events"):
    try:
        rr = requests.get(u, headers=scrape.CDF_HEADERS, timeout=40)
        ct = rr.headers.get("content-type", "")
        print(u, rr.status_code, ct[:30], len(rr.content), "→", rr.url if rr.url != u else "")
        if "json" in ct and rr.status_code == 200:
            print("   JSON:", sq(rr.text, 700))
        elif "html" in ct and rr.status_code == 200:
            ss = BeautifulSoup(rr.content, "lxml")
            print("   title:", sq(ss.title.get_text() if ss.title else "", 80), "| #Event_list:", len(ss.select("#Event_list")), "| article:", len(ss.select("article")))
            main = ss.select_one("#Event_list") or ss.select_one("main") or ss.body
            print("   text:", sq(main.get_text(" ", strip=True), 500))
        elif rr.status_code == 200:
            print("   body:", sq(rr.text, 300))
    except Exception as e:
        print(u, "ERR", e)
