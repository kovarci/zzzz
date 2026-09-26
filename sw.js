/* Service worker — installable PWA + offline mode.
   Strategy: network-first (fresh online), cache fallback when offline.
   Bumped CACHE version forces clients to refresh their precache. */

const CACHE = "lotent-v40";

// Precached on install : the shell that lets the app boot fully offline,
// even on first visit-when-offline. Per-event pages (e/<id>.html) are
// cached opportunistically as the user navigates to them.
const SHELL = [
  "./", "./index.html", "./app.js", "./app.css", "./apropos.html",
  "./manifest.json", "./icon.svg", "./og.png",
  "./data/m/index.json", "./data/digest.json", "./data/meta.json",
];
// Les mois de l'agenda (data/m/*.json) et l'historique (2 Mo) ne sont plus
// précachés : chaque installation du worker les retéléchargeait tous. Ils sont
// mis en cache au fil de la navigation (réseau d'abord, cache hors-ligne).

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
    p.endsWith(".webp") || p.endsWith(".ics") || p.endsWith(".xml") ||
    p.endsWith(".js") || p.endsWith(".css")
  );
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Cross-origin (Google Fonts, Leaflet CDN, OSM tiles, Luma covers, etc.) —
  // straight to network so we don't bloat the cache with megabytes of tiles.
  if (url.origin !== location.origin) return;

  // Data files come with a cache-busting ?timestamp or ?v=hash ; store them
  // under the canonical path so the offline lookup always finds them (and a
  // month's old versions don't pile up in the cache).
  const isData = url.pathname.includes("/data/m/")
              || url.pathname.endsWith("/events.json")
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
      .catch(async () => {
        const cached = await caches.match(cacheKey, { ignoreSearch: true });
        if (cached) return cached;
        // La coquille de l'appli seulement pour une page : servie à la place
        // d'un fichier JSON ou d'un script, elle cassait son lecteur. (Avant,
        // `caches.match(...) || new Response(...)` ne tombait jamais sur la
        // Response : une promesse est toujours « vraie ».)
        if (req.mode === "navigate") {
          const shell = await caches.match("./index.html");
          if (shell) return shell;
        }
        return new Response("Hors-ligne — ressource non disponible.",
                            { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
      })
  );
});

// Notification « Tes intervenants reviennent » (envoyée via le worker sur
// Android) : un clic ramène sur le site, dans l'onglet déjà ouvert s'il existe.
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      const open = list.find((c) => "focus" in c);
      return open ? open.focus() : self.clients.openWindow("./");
    })
  );
});
