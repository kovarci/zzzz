"""Images d'événements récupérées sur la page de l'organisateur (balise og:image).

Plus de la moitié des sources ne donnent aucune image dans leur agenda, alors que la page de
chaque événement en a souvent une. On la lit une fois par page (data/og-cache.json), par petits
lots, en ménageant les sites. On écarte :
  - les logos et icônes (nom de fichier, SVG, trop petites) ;
  - les images répétées : une même image sur au moins 3 événements d'un même organisateur est
    un bandeau ou un logo du site, pas l'image de l'événement ;
  - les organisateurs dont les premières pages montrent déjà ce genre d'image unique (on arrête d'y aller).
"""
import json
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (compatible; LotentBot/1.0; +https://lotent.fr/apropos.html)"
BAD_NAME = re.compile(r"(logo|favicon|sprite|placeholder|default|avatar|blank|spacer|banner-site|icon)", re.I)
META = re.compile(r"<meta\b[^>]*>", re.I | re.S)
ATTR = re.compile(r'([a-zA-Z:_-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')', re.S)
RETRY_EMPTY_DAYS = 14        # une page sans image est revue dans 14 jours (l'organisateur en ajoute parfois)
RETRY_INST_DAYS = 60         # un organisateur « image générique » est revu dans 60 jours
GENERIC_MIN, GENERIC_SHARE, SAMPLE = 3, 0.75, 8


def _attrs(tag):
    return {m.group(1).lower(): (m.group(3) if m.group(3) is not None else m.group(4)) for m in ATTR.finditer(tag)}


def extract_og_image(html, base_url):
    """Première image d'aperçu de la page (og:image, sinon twitter:image), en URL absolue https.
    None si elle ressemble à un logo ou à une icône."""
    found, width = None, None
    for tag in META.findall(html[:300_000]):
        a = _attrs(tag)
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:url", "og:image:secure_url") and a.get("content") and not found:
            found = a["content"].strip()
        elif key == "twitter:image" and a.get("content") and not found:
            found = a["content"].strip()
        elif key == "og:image:width":
            try:
                width = int(a.get("content", ""))
            except ValueError:
                pass
    if not found:
        return None
    url = urljoin(base_url, found.replace("&amp;", "&"))
    if urlparse(url).scheme == "http":
        url = "https" + url[4:]
    path = urlparse(url).path.lower()
    if (not url.startswith("https://") or path.endswith((".svg", ".ico", ".gif")) or BAD_NAME.search(path)
            or (width is not None and width < 300)):
        return None
    return url


def _norm(img):
    """Même image, quels que soient les paramètres (taille, jeton) ajoutés à l'adresse."""
    p = urlparse(img)
    return f"{p.netloc}{p.path}"


def drop_repeated(pairs):
    """pairs : [(événement, image)] → ceux dont l'image n'est pas répétée chez le même organisateur."""
    n = Counter((e.get("institution"), _norm(img)) for e, img in pairs)
    return [(e, img) for e, img in pairs if n[(e.get("institution"), _norm(img))] < GENERIC_MIN]


def fetch_html(url, session):
    """Début de la page (les balises meta sont dans l'en-tête) ; None si erreur ou autre chose que du HTML."""
    r = session.get(url, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "fr"},
                    timeout=(5, 10), stream=True, allow_redirects=True)
    try:
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type", "").lower():
            return r.status_code, None
        data, size = [], 0
        for chunk in r.iter_content(32768):
            data.append(chunk)
            size += len(chunk)
            if size > 300_000 or b"</head>" in chunk.lower():
                break
        return 200, b"".join(data).decode(r.encoding or "utf-8", errors="replace")
    finally:
        r.close()


def load_cache(path):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return {"items": d.get("items", {}), "inst": d.get("inst", {})}
    except Exception:
        return {"items": {}, "inst": {}}


def save_cache(path, cache, live_urls, today):
    """On ne garde que les pages encore dans l'agenda (ou vues depuis moins de 120 jours)."""
    keep = {u: v for u, v in cache["items"].items()
            if u in live_urls or (v.get("d", "") >= _days_ago(today, 120))}
    path.write_text(json.dumps({"v": 1, "items": keep, "inst": cache["inst"]}, ensure_ascii=False,
                               separators=(",", ":"), sort_keys=True), encoding="utf-8")


def _days_ago(today, n):
    from datetime import date, timedelta
    return (date.fromisoformat(today) - timedelta(days=n)).isoformat()


def enrich_images(events, cache_path, today, budget=150, max_seconds=900, host_delay=0.6, fetch=None, log=print):
    """Ajoute e["image"] aux événements à venir qui n'en ont pas, depuis le cache puis, dans la limite
    de `budget` pages lues, depuis la page de l'organisateur. Renvoie des chiffres pour le journal."""
    import requests
    cache = load_cache(cache_path)
    items, insts = cache["items"], cache["inst"]
    fetch = fetch or (lambda u, s: fetch_html(u, s))
    started = time.time()
    todo = [e for e in events if not e.get("image") and e.get("url") and e.get("date", "") >= today
            and str(e["url"]).startswith("http")]

    def stale(entry):
        return not entry or (not entry.get("i") and entry.get("d", "") < _days_ago(today, RETRY_EMPTY_DAYS))

    def inst_blocked(name):
        v = insts.get(name)
        return bool(v and v.get("generic") and v.get("d", "") >= _days_ago(today, RETRY_INST_DAYS))

    pending = defaultdict(list)
    for e in todo:
        if stale(items.get(e["url"])) and not inst_blocked(e.get("institution")):
            if e["url"] not in {x["url"] for x in pending[e.get("institution")]}:
                pending[e.get("institution")].append(e)
    left = [budget]
    lock = threading.Lock()
    bad_hosts = Counter()
    stats = Counter()

    def work(inst, evts):
        s = requests.Session()
        got = []
        for e in evts:
            with lock:
                if left[0] <= 0 or time.time() - started > max_seconds:
                    return
                left[0] -= 1
            host = urlparse(e["url"]).netloc
            if bad_hosts[host] >= 3:
                continue
            try:
                status, html = fetch(e["url"], s)
            except Exception:
                status, html = 0, None
            stats["pages"] += 1
            if html is None:
                if status in (403, 429, 0) or status >= 500:
                    bad_hosts[host] += 1
                    continue          # on réessaiera plus tard : rien n'est noté dans le cache
                items[e["url"]] = {"i": "", "d": today}
            else:
                img = extract_og_image(html, e["url"])
                items[e["url"]] = {"i": img or "", "d": today}
                if img:
                    got.append(img)
            # Organisateur dont les premières pages montrent la même image : bandeau du site, on s'arrête
            if len(got) >= SAMPLE:
                top, n = Counter(_norm(i) for i in got).most_common(1)[0]
                if n >= GENERIC_MIN and n / len(got) >= GENERIC_SHARE:
                    insts[inst] = {"generic": True, "d": today}
                    stats["organisateurs_génériques"] += 1
                    return
            time.sleep(host_delay)

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda kv: work(*kv), sorted(pending.items(), key=lambda kv: -len(kv[1]))))

    # Application : cache → événements, sans les images répétées chez un même organisateur
    pairs = [(e, items[e["url"]]["i"]) for e in todo if items.get(e["url"], {}).get("i")]
    kept = drop_repeated(pairs)
    for e, img in kept:
        e["image"] = img
    stats["images_appliquées"] = len(kept)
    stats["écartées_répétées"] = len(pairs) - len(kept)
    save_cache(cache_path, cache, {e.get("url") for e in events if e.get("url")}, today)
    log(f"Images (og:image) : {dict(stats)} · {len(todo)} événements sans image, {sum(len(v) for v in pending.values())} pages à lire")
    return stats
