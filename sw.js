const CACHE = 'analysor-v5';
const CORE = ['./','./index.html','./report.html','./portfolio.html','./backtest.html',
  './lightweight-charts.standalone.production.js','./manifest.webmanifest'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(
    ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = e.request.url;
  if (url.endsWith('.json')) {                       // data: network-first
    e.respondWith(fetch(e.request).then(r => {
      const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); return r;
    }).catch(() => caches.match(e.request)));
  } else {                                           // shell: cache-first
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
