/* Service worker: rende l'applicazione installabile e utilizzabile anche
   quando il server locale non ha ancora finito di avviarsi.

   Regola di fondo: i dati non si mettono mai in cache. Le chiamate a /api
   passano sempre dalla rete, altrimenti l'interfaccia mostrerebbe offerte
   vecchie facendole passare per aggiornate.

   ATTENZIONE: il nome della cache è cambiato da jobseeker-v1 a
   jobseeker-v2. Serve, altrimenti i browser che hanno già visitato la
   versione precedente continuerebbero a servire dalla cache il vecchio
   style.css e il vecchio app.js, e la nuova interfaccia non comparirebbe. */

const CACHE = "jobseeker-v2";
const SHELL = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "/static/icons/icon.svg",
  "/static/icons/icon-192.png",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // I dati vivi non vengono mai serviti dalla cache.
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request).then((hit) => hit || caches.match("/")))
  );
});
