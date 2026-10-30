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

section("PARIS CITE")
r, s = get("https://u-paris.fr/agenda/")
cal = s.select_one(".Calendar_fr")
print("Calendar_fr:", sq(cal, 1500) if cal else None)
print("iframes:", [i.get("src") for i in s.select("iframe")][:5])
print("scripts:", [x.get("src") for x in s.select("script[src]") if re.search(r"agenda|calend|event|ajax", x.get("src", ""), re.I)][:12])
for sc in s.select("script:not([src])"):
    t = sc.string or ""
    if re.search(r"agenda|evenement|events|ajax_url|rest_url|wp-json", t, re.I):
        print("INLINE:", sq(t, 600))
for u in ("https://u-paris.fr/wp-json/", "https://u-paris.fr/agenda/?ai1ec=action~agenda"):
    try:
        rr = requests.get(u, headers=scrape.CDF_HEADERS, timeout=40)
        print(u, rr.status_code, rr.headers.get("content-type"), len(rr.content))
        if "json" in rr.headers.get("content-type", ""):
            print("  namespaces:", rr.json().get("namespaces"))
    except Exception as e:
        print(u, "ERR", e)
txt = s.get_text(" ", strip=True)
for m in list(re.finditer(r"(conf[ée]rence|s[ée]minaire|colloque)", txt, re.I))[:5]:
    print("CTX:", sq(txt[max(0, m.start() - 150): m.start() + 250], 400))
print("hrefs agenda:", sorted({a["href"] for a in s.select("a[href]") if re.search(r"/(agenda|evenement|evenements)/[^/]+", a["href"])})[:20])

section("USPN future")
r, s = get("https://www.univ-spn.fr/agenda/")
seen = set()
for sc in s.find_all("script", type="application/ld+json"):
    try: data = json.loads(sc.string or "")
    except Exception: continue
    for x in (data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []):
        if isinstance(x, dict) and x.get("@type") == "Event" and str(x.get("startDate", "")) >= "2026-10-30":
            k = (x.get("startDate"), x.get("name"))
            if k not in seen:
                seen.add(k); print("  ", x.get("startDate"), "|", sq(x.get("name"), 90))
print("MEC month nav attrs:", [sq(e, 300) for e in s.select(".mec-next-month")][:1])
