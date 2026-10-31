"""Les sélecteurs CSS doivent rester acceptés par la version de soupsieve que
le robot GitHub installe (soupsieve 3 refuse les sélecteurs complexes dans
:has(), ce qui faisait planter scrape_iris : 0 événement, exception)."""

import ast
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
import soupsieve
from bs4 import BeautifulSoup

import scrape

SRC = Path(scrape.__file__)


def _has_selectors():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and ":has(" in node.value:
            yield node.value


@pytest.mark.parametrize("selector", sorted(set(_has_selectors())))
def test_has_selectors_compile(selector):
    soupsieve.compile(selector)


def _iris_page():
    d = date.today() + timedelta(days=10)
    months = ["JAN", "FÉV", "MAR", "AVR", "MAI", "JUIN", "JUIL", "AOÛ", "SEP", "OCT", "NOV", "DÉC"]
    stamp = f"{d.day:02d} {months[d.month - 1]}"
    return BeautifulSoup(f"""
    <article class="card"><div class="card-content">
      <p class="card-date">{stamp}</p><p class="card-subheading">OUVERT / 18:30–20:00</p>
      <h3 class="card-title"><a href="/event/climat-et-securite/">Climat et sécurité internationale</a></h3>
    </div></article>
    <article class="card"><div class="card-content">
      <h3 class="card-title"><a href="/analyse/autre/">Une analyse, pas un événement</a></h3>
    </div></article>""", "html.parser")


def test_scrape_iris_reads_dated_cards(monkeypatch):
    monkeypatch.setattr(scrape, "_soup", lambda url: _iris_page())
    events = scrape.scrape_iris()
    assert [e["title"] for e in events] == ["Climat et sécurité internationale"]
