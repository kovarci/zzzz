import re, requests, icalendar, scrape
def feed(u):
    r = requests.get(u, headers=scrape.CDF_HEADERS, timeout=40)
    cal = icalendar.Calendar.from_ical(r.content)
    ev = list(cal.walk("VEVENT"))
    ds = sorted(str(v.decoded("DTSTART"))[:10] for v in ev)
    print(u, r.status_code, len(r.content), "VEVENT:", len(ev), "dates:", ds[:3], "…", ds[-3:])
    return ev
ev = feed("https://u-paris.fr/?feed=eo-events")
for v in ev[:3]:
    print("  ", v.get("SUMMARY"), "|", v.get("DTSTART").to_ical(), "|", v.get("LOCATION"), "|", v.get("URL"))
for q in ("&posts_per_page=200", "&paged=2", "&eo_interval=future", "&event-category=conference"):
    try: feed("https://u-paris.fr/?feed=eo-events" + q)
    except Exception as e: print(q, "ERR", e)
r = requests.get("https://u-paris.fr/?feed=eo-events", headers=scrape.CDF_HEADERS, timeout=40)
print(r.text[:1500])
