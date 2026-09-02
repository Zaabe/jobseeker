/* Service worker: rende l'applicazione installabile e utilizzabile anche
   quando il server locale non ha ancora finito di avviarsi.

   Regola di fondo: i dati non si mettono mai in cache. Le chiamate a /api
   passano sempre dalla rete, altrimenti l'interfaccia mostrerebbe offerte
   vecchie facendole passare per aggiornate.

   ATTENZIONE: il nome della cache va cambiato a ogni versione. Serve,
   altrimenti i browser che hanno già visitato la versione precedente
   continuerebbero a servire dalla cache il vecchio style.css e il vecchio
   app.js, e la nuova interfaccia non comparirebbe. */

const CACHE = "jobseeker-v5";
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
  // L'accesso non passa mai di qui. Servirlo dalla cache mostrerebbe un modulo
  // vecchio, e intercettarlo toglierebbe al browser la possibilità di seguire
  // il reindirizzamento come farebbe normalmente.
  if (url.pathname === "/login" || url.pathname === "/logout") return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        // `redirected` esclude il caso che conta: sessione scaduta, il server
        // rimanda alla pagina di accesso, e senza questo controllo quella
        // pagina finirebbe in cache sotto la chiave "/" — da lì in poi
        // l'applicazione si aprirebbe sul modulo di login anche da connessa.
        if (response.ok && !response.redirected) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request).then((hit) => hit || caches.match("/")))
  );
});
