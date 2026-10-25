/**
 * ValidAí Service Worker (v3.5)
 * Cache passivo leve de assets estáticos + rede direta para /api/
 */
const CACHE_NAME = 'validai-static-v3.5';
const PRECACHE_ASSETS = [
  '/static/css/style.css',
  '/static/images/favicon-48x48.png',
  '/static/images/favicon-96x96.png',
  '/static/images/favicon-192x192.png',
  '/static/images/logo.png'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch(() => {});
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Passagem direta para a rede em chamadas de API ou origens externas
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return;
  }

  // Cache passivo (Network First com fallback para cache) em assets estáticos
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      fetch(req)
        .then((networkResp) => {
          if (networkResp && networkResp.status === 200) {
            const respClone = networkResp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, respClone)).catch(() => {});
          }
          return networkResp;
        })
        .catch(() => caches.match(req))
    );
  }
});

