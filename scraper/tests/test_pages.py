"""Gabarits des pages statiques (e/, i/, d/, s/, p/) : structure de base et
redirection d'un événement renommé (le lien officiel « btn ext » de la page
doit rester retrouvable, c'est lui qui relie l'ancien id au nouveau)."""
import re
from datetime import date, timedelta

import scrape


def ev(**kw):
    day = (date.today() + timedelta(days=3)).isoformat()
    base = dict(id="0123456789ab", title="Séminaire de topologie", date=day, time="18:00", end_time="19:30",
                institution="Collège de France", discipline="Mathématiques",
                location="11 place Marcelin Berthelot, Paris", price="0", description="", speaker="",
                image="", source_type="institution", url="https://example.org/seminaire")
    base.update(kw)
    return base


def hub(evts, **kw):
    args = dict(kicker="Sélection", name="Conférences gratuites à Paris", path="s/gratuites.html", n=len(evts),
                color="#6366F1", evts=evts, target="/?prix=gratuit")
    args.update(kw)
    return scrape._hub_page(**args)


def test_hub_page_structure():
    html = hub([ev()])
    assert html.count("<h1") == 1 and '<main id="main"' in html and 'class="skip"' in html
    assert "/e/0123456789ab.html" in html and "/pages.css?v=" in html
    assert "<b>18:00</b>" in html            # l'heure ouvre la ligne de détail
    assert "Geist" not in html               # plus l'ancienne charte


def test_hub_page_empty_does_not_fail():
    html = hub([], n=0)
    assert "Aucun événement annoncé" in html and "noindex" in html


def test_free_tag_hidden_on_free_page():
    assert ">Gratuit<" in hub([ev()])
    assert ">Gratuit<" not in hub([ev()], hide_free=True)


def test_many_days_get_navigation_and_discipline_filter():
    evts = [ev(id=f"{i:012x}", date=(date.today() + timedelta(days=1 + i % 5)).isoformat(),
               discipline=("Mathématiques", "Philosophie")[i % 2]) for i in range(14)]
    html = hub(evts)
    assert 'class="scroller daynav"' in html and "data-disc" in html and html.count('class="day"') == 5


def test_renamed_event_page_redirects_to_new_id(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "EVENT_PAGES_DIR", tmp_path)
    old = ev(id="aaaaaaaaaaaa")
    scrape.write_event_pages([old])
    page = (tmp_path / "aaaaaaaaaaaa.html").read_text(encoding="utf-8")
    assert re.search(r'<a class="btn ext" href="https://example.org/seminaire"', page)
    new = ev(id="bbbbbbbbbbbb", title="Séminaire de topologie (reporté)")
    scrape.write_event_pages([new])
    redirect = (tmp_path / "aaaaaaaaaaaa.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh" content="0; url=bbbbbbbbbbbb.html"' in redirect


def test_removed_event_becomes_past_page_not_404(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "EVENT_PAGES_DIR", tmp_path)
    scrape.write_event_pages([ev(id="aaaaaaaaaaaa")])
    # l'organisateur retire l'événement (plus de lien commun avec un autre) : on garde une page
    other = ev(id="cccccccccccc", url="https://example.org/autre", title="Autre séminaire")
    scrape.write_event_pages([other])
    stub = (tmp_path / "aaaaaaaaaaaa.html").read_text(encoding="utf-8")
    assert 'name="lotent-past"' in stub and "noindex" in stub
    assert "Séminaire de topologie" in stub and "Événement retiré" in stub   # date à venir : « retiré »
    assert "http-equiv" not in stub                                          # pas de redirection automatique
    scrape.write_event_pages([other])                                        # le lendemain : toujours là
    assert 'name="lotent-past"' in (tmp_path / "aaaaaaaaaaaa.html").read_text(encoding="utf-8")


def test_past_stub_says_event_is_over():
    html = scrape._past_stub("aaaaaaaaaaaa", "Cours d&#x27;histoire", "2020-01-02", "Collège de France", "college-de-france")
    assert "Événement passé" in html and "a eu lieu le 2 janvier 2020" in html and "/?q=" in html


def test_past_event_page_offers_upcoming_events(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "EVENT_PAGES_DIR", tmp_path)
    scrape.write_event_pages([ev(id="dddddddddddd", date="2020-01-02")])
    page = (tmp_path / "dddddddddddd.html").read_text(encoding="utf-8")
    assert "Événement passé" in page and "Voir dans l’historique" in page
