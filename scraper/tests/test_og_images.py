"""Images d'événements lues sur la page de l'organisateur (og_images.py) : ce qu'on garde,
ce qu'on écarte (logos, images répétées) et la mémoire entre deux passages."""
import json

import og_images as og

TODAY = "2026-11-03"


def page(img, extra=""):
    return f'<html><head><meta property="og:image" content="{img}">{extra}</head><body></body></html>'


def ev(i, inst="Inalco", url=None, **kw):
    e = dict(id=f"{i:012x}", title=f"Séance {i}", institution=inst, date="2026-11-10", image="",
             url=url or f"https://example.org/{inst}/{i}")
    e.update(kw)
    return e


def test_extract_makes_absolute_https_url():
    assert og.extract_og_image(page("/media/a.jpg"), "https://example.org/x") == "https://example.org/media/a.jpg"
    assert og.extract_og_image(page("http://cdn.example.org/a.jpg?w=1200&amp;q=80"), "https://example.org/").startswith("https://cdn.example.org/a.jpg?w=1200&q=80")


def test_extract_falls_back_to_twitter_image():
    html = '<meta name="twitter:image" content="https://example.org/t.jpg">'
    assert og.extract_og_image(html, "https://example.org/") == "https://example.org/t.jpg"


def test_extract_rejects_logos_icons_and_small_images():
    for bad in ("https://example.org/logo.png", "https://example.org/a.svg", "https://example.org/favicon.ico",
                "https://example.org/img/default-share.jpg"):
        assert og.extract_og_image(page(bad), "https://example.org/") is None
    assert og.extract_og_image(page("https://example.org/ok.jpg", '<meta property="og:image:width" content="120">'), "https://example.org/") is None
    assert og.extract_og_image("<html></html>", "https://example.org/") is None


def test_repeated_image_of_one_organiser_is_dropped():
    same = [(ev(i), "https://example.org/banner.jpg?v=%d" % i) for i in range(3)]
    other = [(ev(10, "IHP"), "https://example.org/banner.jpg"), (ev(11, "IHP"), "https://example.org/p/1.jpg")]
    kept = og.drop_repeated(same + other)
    assert [e["institution"] for e, _ in kept] == ["IHP", "IHP"]       # 3 fois chez Inalco : bandeau, 2 fois ailleurs : on garde


def test_enrich_reads_pages_once_and_remembers(tmp_path):
    cache = tmp_path / "og-cache.json"
    events = [ev(i, "Bernardins") for i in range(4)]
    calls = []

    def fake(url, _s):
        calls.append(url)
        return 200, page(f"https://example.org/img/{url[-1]}.jpg")
    og.enrich_images(events, cache, TODAY, budget=10, host_delay=0, fetch=fake)
    assert len(calls) == 4 and all(e["image"].endswith(".jpg") for e in events)
    # le lendemain : événements re-scrapés sans image, aucune page relue, images remises depuis le cache
    again = [ev(i, "Bernardins") for i in range(4)]
    og.enrich_images(again, cache, TODAY, budget=10, host_delay=0, fetch=fake)
    assert len(calls) == 4 and all(e["image"] for e in again)
    assert json.loads(cache.read_text(encoding="utf-8"))["items"]


def test_budget_limits_pages_read(tmp_path):
    events = [ev(i, f"Org{i}") for i in range(6)]
    calls = []
    og.enrich_images(events, tmp_path / "c.json", TODAY, budget=2, host_delay=0,
                     fetch=lambda u, s: (calls.append(u), (200, page("https://example.org/a%s.jpg" % u[-1])))[1])
    assert len(calls) == 2


def test_organiser_with_same_banner_everywhere_is_skipped_afterwards(tmp_path):
    cache = tmp_path / "c.json"
    events = [ev(i, "Collège") for i in range(20)]
    calls = []

    def fake(u, s):
        calls.append(u)
        return 200, page("https://example.org/bandeau.jpg")
    og.enrich_images(events, cache, TODAY, budget=100, host_delay=0, fetch=fake)
    assert len(calls) <= og.SAMPLE + 1 and not any(e["image"] for e in events)
    n = len(calls)
    og.enrich_images([ev(i, "Collège") for i in range(20, 30)], cache, TODAY, budget=100, host_delay=0, fetch=fake)
    assert len(calls) == n                                              # organisateur marqué générique : plus de requêtes


def test_forbidden_site_is_not_cached_as_empty(tmp_path):
    cache = tmp_path / "c.json"
    og.enrich_images([ev(1)], cache, TODAY, budget=5, host_delay=0, fetch=lambda u, s: (403, None))
    assert json.loads(cache.read_text(encoding="utf-8"))["items"] == {}
