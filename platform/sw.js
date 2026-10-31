// Groowin SW v2: нашар желіге төзімді. Supabase сұраныстарына тиіспейді (оларды беттің өзі кэштейді).
const V = 'groowin-v2';
const CDN = ['cdn.jsdelivr.net', 'cdnjs.cloudflare.com', 'fonts.googleapis.com', 'fonts.gstatic.com'];
const SHELL = ['./', 'index.html', 'play.html', 'config.js', 'manifest.json', 'icon-192.png', 'glass-bg.jpg',
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(V).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {})))));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V && !k.startsWith('gw-')).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// желі 4 секундта жауап бермесе, кэшті береміз (жаңасы фонда сақталады)
const netFirst = (r, ms) => {
  const net = fetch(r).then(res => { if (res.ok) { const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); } return res; });
  const cached = () => caches.match(r, { ignoreSearch: r.mode === 'navigate' }).then(m => m || (r.mode === 'navigate' ? caches.match('index.html') : undefined));
  return Promise.race([net, new Promise(res => setTimeout(() => cached().then(m => m ? res(m) : null), ms))]).then(x => x || net).catch(() => cached().then(m => m || Response.error()));
};
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET') return;
  if (u.origin === location.origin) { e.respondWith(netFirst(r, 4000)); return; }
  if (CDN.includes(u.hostname)) {
    e.respondWith(caches.open(V).then(c => c.match(r).then(hit => {
      const net = fetch(r).then(res => { if (res.ok || res.type === 'opaque') c.put(r, res.clone()); return res; });
      return hit ? (net.catch(() => {}), hit) : net;
    })));
  }
});
