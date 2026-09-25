#!/usr/bin/env python3
"""
Rafraîchissement local — à lancer depuis ta connexion française (chez toi).

Pourquoi ce script existe :
Depuis le serveur GitHub (une IP de data-center, aux États-Unis), quelques
sources sont bloquées ou faussées par géolocalisation IP :
  - Collège de France : son CDN (BunnyCDN) bloque les IP de data-center, donc
    le robot GitHub reçoit 0 événement.
  - Muséum national d'Histoire naturelle et Académie des sciences : même
    chose (403 Forbidden depuis GitHub). Jeunes IHEDN : page vide depuis GitHub.
  - Luma : les pages par thème sont géolocalisées par IP et renvoient des
    événements américains depuis les États-Unis.
Depuis ta connexion française, les deux fonctionnent normalement. Ce script va
les récupérer et mettre à jour data/events.json et data/calendar.ics. Les
autres sources (IHP, PSE, ENS, etc.) ne sont pas touchées : le robot GitHub
s'en occupe très bien tout seul chaque jour.

Utilisation (1 fois par semaine environ) :
    git pull
    python scraper/refresh_local.py
    git add data/events.json data/calendar.ics
    git commit -m "maj manuelle (College de France + Luma)"
    git push

Si c'est la toute première fois, installe le navigateur de Luma (une seule
fois) :
    python -m playwright install chromium
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape  # noqa: E402

# Pages Luma à récupérer. La page « Paris » suffit déjà ; depuis la France tu
# peux AUSSI ajouter tes pages par thème (une URL par ligne) — elles renverront
# bien des événements français, contrairement au robot GitHub.
LUMA_PAGES = [
    "https://lu.ma/discover/paris",
    # Pages par thème : depuis la France elles renvoient bien des événements FR
    # (depuis le robot GitHub elles renverraient des événements américains).
    "https://luma.com/tech",
    "https://luma.com/arts",
    "https://luma.com/wellness",
    "https://luma.com/crypto",
    "https://luma.com/climate",
    "https://luma.com/food",
    "https://luma.com/ai",
    "https://luma.com/fitness",
]


# Sources que le robot GitHub ne peut pas lire (IP de data-center bloquée) :
# ce script les remplace par un scrape frais depuis ta connexion.
MNHN = "Muséum national d'Histoire naturelle"
# Ifri (403), IRIS (page vide) et Fondation Jean-Jaurès (réponse invalide)
# ne répondent pas non plus au robot GitHub depuis septembre 2026.
# Académie nationale de médecine : le robot reçoit une page sans agenda
# (0 événement), alors que depuis la France on en lit une quinzaine.
LOCAL_INSTITUTIONS = {"Collège de France", MNHN, "Académie des sciences", "Jeunes IHEDN",
                      "Ifri", "IRIS", "Fondation Jean-Jaurès", "Académie nationale de médecine",
                      # connexion refusée au robot GitHub (délai dépassé), lues sans souci d'ici
                      "Maison de l'Amérique latine", "Maison de la culture du Japon"}


def _luma_count(events):
    return sum(1 for e in events if e.get("source_type") == "luma")


def _inst_count(events, inst):
    return sum(1 for e in events if e.get("institution") == inst)


def main():
    out = scrape.OUTPUT_FILE
    events = json.loads(out.read_text(encoding="utf-8"))
    print(f"Avant : {len(events)} événements "
          f"(Collège de France {_inst_count(events, 'Collège de France')}, "
          f"Luma {_luma_count(events)})\n")

    # 1) Collège de France — requests, fonctionne depuis une IP française
    cdf = scrape.scrape_college_de_france(None)

    # 1 bis) Muséum, Académie des sciences, Jeunes IHEDN, Ifri, IRIS, Fondation
    # Jean-Jaurès : même blocage des IP de data-center (403 ou page vide sur le
    # robot GitHub), requests suffit depuis la France.
    blocked = []
    for fn in (scrape.scrape_mnhn, scrape.scrape_academie_sciences, scrape.scrape_jeunes_ihedn,
               scrape.scrape_ifri, scrape.scrape_iris, scrape.scrape_jean_jaures,
               scrape.scrape_lamsade, scrape.scrape_academie_medecine,
               scrape.scrape_amerique_latine, scrape.scrape_mcjp):
        try:
            blocked += fn()
        except Exception as e:
            print(f"[!] {fn.__name__} ignoré ({type(e).__name__}: {e}).")

    # 2) Luma — Playwright + géolocalisation Paris, fonctionne depuis la France
    luma = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                luma = scrape.scrape_luma(browser, pages=LUMA_PAGES)
            finally:
                browser.close()
    except Exception as e:
        print(f"[!] Luma ignoré ({type(e).__name__}).")
        print("    Première fois ? Lance une seule fois : "
              "python -m playwright install chromium\n")

    if not cdf:
        print("[!] Collège de France a renvoyé 0 cette fois.")
    if not luma:
        print("[!] Luma a renvoyé 0 cette fois.")

    # Recompose : tout le reste (intact) + sources locales + Luma frais.
    others = [e for e in events
              if e.get("institution") not in LOCAL_INSTITUTIONS
              and e.get("source_type") != "luma"]
    fresh = scrape.deduplicate(cdf + blocked + luma)

    # Filet de sécurité (comme le robot) : on réunit le scrape frais avec les
    # événements à venir DÉJÀ connus du Collège de France / Luma que ce passage
    # n'a pas revus (une page n'a pas répondu, etc.). Un rafraîchissement ne
    # peut donc jamais FAIRE BAISSER une source — au pire il la laisse égale
    # (sauf les anciennes versions d'événements renommés, cf. carry_forward).
    carried = scrape.carry_forward(fresh, events, lambda e: (
        e.get("institution") in LOCAL_INSTITUTIONS or e.get("source_type") == "luma"))

    # Mêmes fusions que le robot : un événement Luma tenu à Sciences Po, une
    # conférence du Collège de France aussi publiée par la Ville de Paris…
    merged = scrape.deduplicate(fresh + carried + others)
    merged = scrape.finalize_events(scrape.merge_cross_source(scrape._drop_city_duplicates(merged)))

    merged = [e for e in merged if e.get("date", "") >= scrape.CUTOFF.isoformat()]
    merged.sort(key=lambda e: (e["date"], e.get("time", "")))

    # Date d'ajout : on garde celle des events existants ; les nouveaux ids
    # (jamais vus avant) reçoivent today -> le tag « nouveau » s'affichera.
    prev_added = {e.get("id"): e.get("added_at") for e in events if e.get("id")}
    today_iso = scrape.TODAY.isoformat()
    n_new = 0
    for ev in merged:
        if ev.get("id"):
            existing = prev_added.get(ev["id"])
            ev["added_at"] = existing or today_iso
            if not existing:
                n_new += 1
    print(f"  {n_new} nouveaux ids estampillés added_at={today_iso}")

    scrape.geocode_all(merged)
    scrape.write_ics(merged)
    out.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    scrape.write_month_files(merged)
    scrape.write_stats(merged)
    try:
        try:
            arch = json.loads(scrape.ARCHIVE_FILE.read_text(encoding="utf-8"))
        except Exception:
            arch = []
        scrape.write_event_pages(merged + arch)
        # Avant le sitemap : il liste les hubs i/*.html réellement présents.
        scrape.write_institution_share_pages(merged)
        scrape.write_discipline_pages(merged)
        scrape.write_sitemap(merged + arch)
        scrape.write_og_image(merged)
        scrape.build_digest(merged)
    except Exception as e:
        print(f"[!] pages/digest : {type(e).__name__}: {e}")
    scrape.update_meta("last_manual_run")

    print(f"\nAprès : {len(merged)} événements "
          f"(Collège de France {_inst_count(merged, 'Collège de France')}, "
          f"Muséum {_inst_count(merged, MNHN)}, "
          f"Académie des sciences {_inst_count(merged, 'Académie des sciences')}, "
          f"Luma {_luma_count(merged)})")
    print("\nÉtape suivante :")
    print("  git add data/events.json data/calendar.ics")
    print('  git commit -m "maj manuelle (College de France + Luma)"')
    print("  git push")


if __name__ == "__main__":
    main()
