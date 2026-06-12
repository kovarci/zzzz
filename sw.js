/* Service worker — installable PWA + offline mode.
   Strategy: network-first (fresh online), cache fallback when offline.
   Bumped CACHE version forces clients to refresh their precache. */

const CACHE = "paris-academique-v3";

// Precached on install : the shell that lets the app boot fully offline,
// even on first visit-when-offline. Per-event pages (e/<id>.html) are
// cached opportunistically as the user navigates to them.
const SHELL = [
  "./", "./index.html", "./apropos.html",
  "./manifest.json", "./icon.svg", "./og.png",
  "./data/events.json", "./data/events-archive.json",
  "./data/digest.json", "./data/meta.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Allow the page to force activation of a new worker via postMessage
self.addEventListener("message", (e) => {
  if (e.data === "skipWaiting") self.skipWaiting();
});

function isCacheable(url) {
  // Same-origin GET, HTML or JSON or static assets we want to survive offline
  if (url.origin !== location.origin) return false;
  const p = url.pathname;
  return (
    p === "/" || p.endsWith("/") ||
    p.endsWith(".html") || p.endsWith(".json") ||
    p.endsWith(".svg") || p.endsWith(".png") ||
    p.endsWith(".webp") || p.endsWith(".ics") || p.endsWith(".xml")
  );
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Cross-origin (Google Fonts, Leaflet CDN, OSM tiles, Luma covers, etc.) —
  // straight to network so we don't bloat the cache with megabytes of tiles.
  if (url.origin !== location.origin) return;

  // events.json comes with a cache-busting ?timestamp ; store it under the
  // canonical path so the offline lookup always finds it.
  const isData = url.pathname.endsWith("/events.json")
              || url.pathname.endsWith("/events-archive.json")
              || url.pathname.endsWith("/digest.json")
              || url.pathname.endsWith("/meta.json");
  const cacheKey = isData ? url.pathname : req;

  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok && isCacheable(url)) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(cacheKey, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(cacheKey, { ignoreSearch: true })
          .then((cached) => cached
            || caches.match("./index.html")
            || new Response("Hors-ligne — ressource non disponible.",
                            { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }))
      )
  );
});
