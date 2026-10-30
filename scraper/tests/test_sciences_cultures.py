"""Linktree répond parfois 406/429 à un robot : une seconde tentative évite de
perdre la source pour la journée (406 observé dans le run du 28/10/2026)."""

import json
from datetime import date, timedelta

import scrape


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


def _page():
    d = date.today() + timedelta(days=5)
    url = f"https://framaforms.org/inscription-conference-ia-{d:%d%m%Y}-sciences-cultures"
    data = {"props": {"links": [{"title": "Conférence sur l'IA avec Jeanne Martin", "url": url}]}}
    return ('<html><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(data) + "</script></html>")


def test_retries_once_after_a_refusal(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return _Resp(406) if len(calls) == 1 else _Resp(200, _page())

    monkeypatch.setattr(scrape.requests, "get", fake_get)
    monkeypatch.setattr(scrape.time, "sleep", lambda s: None)
    events = scrape.scrape_sciences_cultures()
    assert len(calls) == 2
    assert [e["title"] for e in events] == ["Conférence sur l'IA avec Jeanne Martin"]


def test_gives_up_after_second_refusal(monkeypatch):
    monkeypatch.setattr(scrape.requests, "get", lambda url, **kw: _Resp(406))
    monkeypatch.setattr(scrape.time, "sleep", lambda s: None)
    assert scrape.scrape_sciences_cultures() == []
