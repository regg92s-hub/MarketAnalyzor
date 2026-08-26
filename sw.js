const CACHE = 'analysor-2026-08-24-analysor-v20';
const CORE = ['./','./index.html','./trend.html','./report.html','./roadmap.html','./portfolio.html','./backtest.html','./screener.html',
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
  const isHtmlNav = e.request.mode === 'navigate' || url.endsWith('.html') || url.endsWith('/');
  if (url.endsWith('.json') || isHtmlNav) {         // data + sider: network-first, ALDRI stale HTML
    e.respondWith(fetch(e.request).then(r => {
      const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); return r;
    }).catch(() => caches.match(e.request)));
  } else {                                           // statiske ressurser (chart-lib, ikoner): cache-first
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
