#!/usr/bin/env python3
"""Audit en lecture seule des sources : exécute chaque scraper statique et, pour
celles qui rendent 0 événement ou plantent, affiche ce que les pages
contenaient (statut HTTP, titre, structure HTML répétée) afin de réécrire les
sélecteurs. N'écrit aucune donnée, ne committe rien, n'appelle pas IndexNow.

    python scraper/audit_sources.py [fragment-de-nom …]
"""

import collections
import re
import sys
import time
import traceback

import requests
import requests.sessions
from bs4 import BeautifulSoup

import scrape

_DATEISH = re.compile(r"\d{1,2}\s*(?:janv|févr|fevr|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|déc|dec)|"
                      r"\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\d{4}-\d{2}-\d{2}|\b\d{1,2}[h:]\d{2}", re.I)

_fetched = []
_real_request = requests.sessions.Session.request


def _logged_request(self, method, url, *a, **kw):
    try:
        r = _real_request(self, method, url, *a, **kw)
    except Exception as e:
        _fetched.append((url, None, None, f"{type(e).__name__}: {e}"))
        raise
    _fetched.append((url, r.status_code, r, ""))
    return r


requests.sessions.Session.request = _logged_request


def _squash(s, n):
    return re.sub(r"\s+", " ", s)[:n]


def describe(url, status, resp, err):
    print(f"      · {url}")
    if resp is None:
        print(f"        ERREUR {err[:200]}")
        return
    ctype = resp.headers.get("content-type", "")
    print(f"        HTTP {status} · {len(resp.content)} o · {ctype[:40]} · → {resp.url[:100]}")
    if "html" not in ctype and "json" not in ctype and "xml" not in ctype:
        return
    if "json" in ctype:
        print(f"        JSON : {_squash(resp.text, 300)}")
        return
    try:
        soup = BeautifulSoup(resp.content, "lxml")
    except Exception:
        soup = BeautifulSoup(resp.content, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    ld = [s.get_text()[:0] for s in soup.select('script[type="application/ld+json"]')]
    print(f"        titre={title[:90]!r} · article={len(soup.select('article'))} "
          f"time={len(soup.select('time'))} li={len(soup.select('li'))} ld+json={len(ld)}")
    if status >= 400 or len(resp.content) < 3000:
        print(f"        corps : {_squash(soup.get_text(' ', strip=True), 300)}")
    counts = collections.Counter()
    first = {}
    for el in soup.find_all(True, class_=True):
        key = (el.name, tuple(el.get("class")))
        counts[key] += 1
        first.setdefault(key, el)
    ranked = []
    for key, n in counts.items():
        if not 3 <= n <= 120:
            continue
        el = first[key]
        txt = el.get_text(" ", strip=True)
        if len(txt) < 25 or not el.find("a", href=True) and el.name != "a":
            continue
        ranked.append((bool(_DATEISH.search(txt)), n, key, el))
    ranked.sort(key=lambda t: (-t[0], -t[1]))
    for dated, n, key, el in ranked[:4]:
        print(f"        ×{n} {key[0]}.{'.'.join(key[1])[:60]} {'[date]' if dated else ''}")
        print(f"          {_squash(str(el), 420)}")


def run(fn):
    start = len(_fetched)
    t0 = time.time()
    try:
        events = fn()
        err = ""
    except Exception as e:
        events, err = [], f"{type(e).__name__}: {e}"
        traceback.print_exc()
    dt = time.time() - t0
    n = len(events)
    flag = "OK " if n else ("ERR" if err else "ZÉRO")
    print(f"[{flag}] {fn.__name__:<34} {n:4d} événements · {dt:5.1f}s {err[:120]}")
    if not n:
        for rec in _fetched[start:][:6]:
            describe(*rec)
    return n


def main():
    wanted = [a.lower() for a in sys.argv[1:]]
    fns = [scrape.scrape_sciences_cultures, scrape.scrape_indico_maths] + list(scrape.STATIC_SOURCES)
    fns += [scrape.scrape_que_faire_a_paris]
    if wanted:
        fns = [f for f in fns if any(w in f.__name__ for w in wanted)]
    total = 0
    summary = []
    for fn in fns:
        n = run(fn)
        summary.append((fn.__name__, n))
        total += n
    print("\n=== Résumé ===")
    for name, n in summary:
        print(f"{n:5d}  {name}")
    print(f"total : {total}")


if __name__ == "__main__":
    main()
