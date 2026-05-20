#!/usr/bin/env python3
"""Source health check — run after the scrape.

Prints a GitHub Actions ::warning:: for any minor source at 0 events, and
::error:: + non-zero exit for any *major* source at 0 (which fails the
workflow run, so GitHub e-mails you that something broke)."""

import json
import sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "events.json"

# Big, reliable sources — if one of these is empty, the scraper is broken.
CRITICAL = ["Institut Henri Poincaré", "Collège de France",
            "Paris School of Economics", "Université PSL"]
# Smaller sources — worth a heads-up if they vanish, but not a hard failure.
WATCH = ["EHESS", "ENS Paris", "Sciences Po", "Sorbonne Université"]


def main():
    try:
        events = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"::error::Impossible de lire events.json : {e}")
        sys.exit(1)

    counts = {}
    for e in events:
        counts[e.get("institution", "?")] = counts.get(e.get("institution", "?"), 0) + 1

    for s in WATCH:
        if counts.get(s, 0) == 0:
            print(f"::warning::Source à vérifier — « {s} » renvoie 0 événement")

    broken = [s for s in CRITICAL if counts.get(s, 0) == 0]
    for s in broken:
        print(f"::error::Source cassée — « {s} » renvoie 0 événement")

    print(f"Total : {len(events)} événements")
    for s in CRITICAL + WATCH:
        print(f"  {counts.get(s, 0):4d}  {s}")

    if broken:
        print(f"\n{len(broken)} source(s) critique(s) cassée(s).")
        sys.exit(1)
    print("\nToutes les sources principales sont opérationnelles.")


if __name__ == "__main__":
    main()
