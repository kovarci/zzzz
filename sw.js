/* Service worker — makes the site installable (PWA) and usable offline.
   Strategy: network-first (always fresh online), cached copy when offline. */

const CACHE = "paris-academique-v1";
const SHELL = ["./", "./index.html", "./manifest.json", "./icon.svg", "./data/events.json"];

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

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;   // fonts, Leaflet, map tiles → straight to network

  const isData = url.pathname.endsWith("/events.json");

  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          // events.json is fetched with a cache-busting ?timestamp — store it
          // under a fixed key so the offline lookup always finds it.
          caches.open(CACHE).then((c) => c.put(isData ? "./data/events.json" : req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(isData ? "./data/events.json" : req, { ignoreSearch: true })
          .then((cached) => cached || caches.match("./index.html"))
      )
  );
});
