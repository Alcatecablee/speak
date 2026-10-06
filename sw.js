// Cache-first app shell so the app opens instantly and works offline
// (dictation itself still needs a connection in most browsers).
const CACHE = 'speak-your-notes-v2';
const SHELL = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './procedures/relevance.js',
  './procedures/demoProcedures.js',
  './procedures/procedureService.js',
  './procedures/reminderTracker.js',
  './procedures/procedureReminder.js',
  './manifest.webmanifest',
  './icons/icon.svg',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  // Stale-while-revalidate: instant load, refreshed in the background.
  e.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
