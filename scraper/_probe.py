"""Sonde temporaire (supprimée avant fusion)."""
import json, re, sys
import requests
from bs4 import BeautifulSoup
import scrape

def get(u):
    r = requests.get(u, headers=scrape.CDF_HEADERS, timeout=40)
    return r, BeautifulSoup(r.content, "lxml")

def sq(s, n=400):
    return re.sub(r"\s+", " ", str(s))[:n]

def section(t):
    print(f"\n######## {t}", flush=True)

section("PARIS CITE")
r, s = get("https://u-paris.fr/agenda/")
print(r.status_code, len(r.content), r.url)
print("ai1ec-event:", len(s.select(".ai1ec-event")), "ai1ec-date:", len(s.select(".ai1ec-date")))
cls = {}
for el in s.find_all(True, class_=True):
    for c in el["class"]:
        if re.search(r"event|agenda|card|date|calend", c, re.I):
            cls[c] = cls.get(c, 0) + 1
print(sorted(cls.items(), key=lambda x: -x[1])[:40])
m = re.search(r"(Oct|Nov|Déc|Dec)[a-z]*\.? \d{1,2}|\d{1,2} (octobre|novembre|décembre)", s.get_text(" "), re.I)
print("date-like:", m.group(0) if m else None)
main = s.find("main") or s.body
print("MAIN TEXT:", sq(main.get_text(" ", strip=True), 700))
for a in s.select("a[href*='/agenda/'], a[href*='evenement']")[:12]:
    print("  A", a.get("href"), "|", sq(a.get_text(" "), 80))

section("USPN")
r, s = get("https://www.univ-spn.fr/agenda/")
print(r.status_code, r.url, len(r.content))
n = 0
for sc in s.find_all("script", type="application/ld+json"):
    try: data = json.loads(sc.string or "")
    except Exception as e: print("bad json", e); continue
    items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
    for x in items:
        if isinstance(x, dict) and x.get("@type") in ("Event", "EducationEvent", "BusinessEvent"):
            n += 1
            if n <= 6 or str(x.get("startDate", "")) >= "2026-10-30" and n < 40:
                print("  EV", x.get("@type"), x.get("startDate"), "|", sq(x.get("name"), 70))
print("events ld:", n)
dates = sorted({d for sc in s.find_all("script", type="application/ld+json") for d in re.findall(r'"startDate"\s*:\s*"([^"]+)"', sc.string or "")})
print("startDate range:", dates[:2], dates[-3:], len(dates))
print("month nav:", [sq(a, 60) for a in s.select(".mec-calendar-header a, .mec-next-month, .mec-previous-month, [class*=month] a")[:8]])

section("CMAP")
r, s = get("https://cmap.ip-paris.fr/evenements")
print(r.status_code, len(r.content))
print("dates:", [sq(d.get_text(" "), 20) for d in s.select(".element .date")])
print("pager:", [(a.get("href"), sq(a.get_text(" "), 20)) for a in s.select("a[href*='page=']")][:12])
print("form:", sq(s.select_one("form") or "", 900))
for u in ("https://cmap.ip-paris.fr/evenements?page=1", "https://cmap.ip-paris.fr/evenements?page=2"):
    rr, ss = get(u)
    print(u, rr.status_code, [sq(d.get_text(" "), 20) for d in ss.select(".element .date")])

section("LAMSADE")
r, s = get("https://www.lamsade.dauphine.fr/fr/seminaires.html")
print(r.status_code, r.headers.get("content-type"), len(r.content))
print(sq(r.text, 2600))

section("ITEM")
for u in ("https://www.item.ens.fr/", "https://www.item.ens.fr/conferences/", "https://www.item.ens.fr/evenements/", "https://www.item.ens.fr/agenda/"):
    try:
        rr, ss = get(u)
        print(u, rr.status_code, rr.url, len(rr.content), sq(ss.title.get_text() if ss.title else "", 80))
        if rr.status_code == 200:
            links = {(a.get("href"), sq(a.get_text(" "), 50)) for a in ss.select("a[href]") if re.search(r"conf|agenda|event|v[ée]nement|colloque|s[ée]minaire", (a.get("href") or "") + a.get_text(), re.I)}
            print("  links:", sorted(links)[:25])
    except Exception as e:
        print(u, "ERR", e)

section("HEC IA")
r, s = get("https://hec-ia.com/en/events")
print(r.status_code, r.url, len(r.content))
print(sq(r.text, 3200))
for u in ("https://hec-ia.com/", "https://hec-ia.com/fr/events"):
    try:
        rr, ss = get(u)
        print(u, rr.status_code, rr.url, len(rr.content), len(ss.select('[data-slot="card"]')))
    except Exception as e:
        print(u, "ERR", e)
