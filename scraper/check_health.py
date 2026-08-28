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
WATCH = ["EHESS", "ENS Paris", "Sciences Po", "Sorbonne Université",
         "Article 1", "Sciences et Cultures", "Université Paris Dauphine"]


def main():
    try:
        events = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"::error::Impossible de lire events.json : {e}")
        sys.exit(1)

    counts = {}
    for e in events:
        counts[e.get("institution", "?")] = counts.get(e.get("institution", "?"), 0) + 1

    # events.json est écrit APRÈS le carry-forward : une source morte y garde
    # ses anciens événements et paraît vivante. Article 1 est ainsi resté
    # cassé sans jamais déclencher d'alerte. fresh_counts, écrit par le
    # scraper avant le report, dit ce que chaque source a rendu aujourd'hui.
    try:
        meta = json.loads((DATA.parent / "meta.json").read_text(encoding="utf-8"))
        fresh = meta.get("fresh_counts") or {}
    except Exception:
        fresh = {}

    def live(source):
        """Nombre ramené aujourd'hui ; retombe sur events.json si le scraper
        n'a pas encore écrit fresh_counts (première exécution)."""
        return fresh.get(source, counts.get(source, 0)) if fresh else counts.get(source, 0)

    for s in WATCH:
        if live(s) == 0:
            kept = counts.get(s, 0)
            extra = f" (events.json en garde {kept} d'un run précédent)" if kept else ""
            print(f"::warning::Source à vérifier — « {s} » n'a rien ramené{extra}")

    broken = [s for s in CRITICAL if live(s) == 0]
    for s in broken:
        print(f"::error::Source cassée — « {s} » n'a rien ramené ce run")

    print(f"Total : {len(events)} événements")
    hdr = "ramenés" if fresh else "en base"
    print(f"  {hdr:>8}  {'en base':>8}  source")
    for s in CRITICAL + WATCH:
        print(f"  {live(s):8d}  {counts.get(s, 0):8d}  {s}")

    if broken:
        print(f"\n{len(broken)} source(s) critique(s) cassée(s).")
        sys.exit(1)
    print("\nToutes les sources principales sont opérationnelles.")


if __name__ == "__main__":
    main()
