"""Flux iCal d'agenda : Université Paris Cité (Event Organiser, depuis que
l'ancien agenda ai1ec affiche un shortcode vide) et Nanterre (Kosmos)."""

from datetime import date, timedelta

import pytest

import scrape


class _Resp:
    def __init__(self, content):
        self.content = content.encode("utf-8")
        self.status_code = 200

    def raise_for_status(self):
        pass


def _vcal(*events):
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n" + "".join(events) + "END:VCALENDAR\r\n"


def _vevent(uid, summary, dtstart, location="", url="", desc=""):
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"SUMMARY:{summary}", dtstart]
    if location:
        lines.append(f"LOCATION:{location}")
    if url:
        lines.append(f"URL:{url}")
    if desc:
        lines.append(f"DESCRIPTION:{desc}")
    return "\r\n".join(lines) + "\r\nEND:VEVENT\r\n"


def _feed():
    soon = date.today() + timedelta(days=6)
    past = date.today() - timedelta(days=40)
    return _vcal(
        _vevent("1", "Colloque Histoire des sciences", f"DTSTART;TZID=Europe/Paris:{soon:%Y%m%d}T183000",
                "Amphi Buffon, 15 rue Hélène Brion", "https://u-paris.fr/events/event/colloque-histoire/", "Un colloque."),
        _vevent("2", "Soutenance passée", f"DTSTART;TZID=Europe/Paris:{past:%Y%m%d}T100000"),
        _vevent("3", "Journée d'étude sans horaire", f"DTSTART;VALUE=DATE:{soon + timedelta(days=1):%Y%m%d}"),
    )


@pytest.fixture
def feed(monkeypatch):
    monkeypatch.setattr(scrape.requests, "get", lambda url, **kw: _Resp(_feed()))


def test_paris_cite_reads_ical_feed(feed):
    events = scrape.scrape_paris_cite()
    assert [e["title"] for e in events] == ["Colloque Histoire des sciences", "Journée d'étude sans horaire"]
    first, second = events
    assert first["institution"] == "Université Paris Cité"
    assert first["time"] == "18:30"
    assert first["url"] == "https://u-paris.fr/events/event/colloque-histoire/"
    assert "Amphi Buffon" in first["location"] and "Paris" in first["location"]
    assert second["time"] == ""


def test_nanterre_still_reads_ical_feed(feed):
    events = scrape.scrape_nanterre()
    assert len(events) == 2
    assert all(e["institution"] == "Université Paris Nanterre" for e in events)
    assert events[0]["time"] == "18:30"
