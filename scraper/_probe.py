import re, requests, scrape
from bs4 import BeautifulSoup
def sq(s, n=500): return re.sub(r"\s+", " ", str(s))[:n]
for u in ("https://u-paris.fr/events/event/", "https://u-paris.fr/events/event/page/2/", "https://u-paris.fr/events/",
          "https://u-paris.fr/wp-json/wp/v2/event?per_page=3", "https://u-paris.fr/wp-json/wp/v2/types",
          "https://u-paris.fr/?post_type=event", "https://u-paris.fr/?feed=eo-events&eo_interval=future&posts_per_page=-1",
          "https://u-paris.fr/event/?feed=eo-events"):
    try:
        r = requests.get(u, headers=scrape.CDF_HEADERS, timeout=40)
        ct = r.headers.get("content-type", "")
        print("\n##", u, r.status_code, ct[:30], len(r.content), "→", r.url if r.url != u else "")
        if r.status_code != 200: continue
        if "json" in ct:
            d = r.json()
            if isinstance(d, dict) and "post" in d: print("types:", [(k, v.get("rest_base")) for k, v in d.items()])
            else: print(sq(r.text, 600))
        elif "html" in ct:
            s = BeautifulSoup(r.content, "lxml")
            print("title:", sq(s.title.get_text() if s.title else "", 80), "| article:", len(s.select("article")), "| .eo-event:", len(s.select("[class*=eo-event], [class*=event]")))
            arts = s.select("article")[:3]
            for a in arts: print("  ART:", sq(a, 700))
            print("  links:", sorted({a['href'] for a in s.select("a[href]") if "/évènement/" in a['href'] or "/event" in a['href']})[:12])
            print("  pager:", [(a.get('href'), sq(a.get_text(), 15)) for a in s.select("a.page-numbers, .pagination a, a.next")[:6]])
    except Exception as e:
        print("##", u, "ERR", e)
