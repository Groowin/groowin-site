// Groowin SW v2: нашар желіге төзімді. Supabase сұраныстарына тиіспейді (оларды беттің өзі кэштейді).
const V = 'groowin-v7';
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
  if (r.method === 'POST' && u.pathname.endsWith('/share-target')) {
    e.respondWith((async () => {
      try {
        const fd = await r.formData(), fs = fd.getAll('files').filter(f => f && f.name), c = await caches.open('gw-share');
        for (const k of await c.keys()) await c.delete(k);
        let i = 0; for (const f of fs) await c.put('share/' + (i++) + '?n=' + encodeURIComponent(f.name), new Response(f, { headers: { 'content-type': f.type || 'application/octet-stream' } }));
      } catch (_) {}
      return Response.redirect(new URL('./?share=1', self.registration.scope).href, 303);
    })());
    return;
  }
  if (r.method !== 'GET') return;
  if (u.origin === location.origin) { e.respondWith(netFirst(r, 4000)); return; }
  if (CDN.includes(u.hostname)) {
    e.respondWith(caches.open(V).then(c => c.match(r).then(hit => {
      const net = fetch(r).then(res => { if (res.ok || res.type === 'opaque') c.put(r, res.clone()); return res; });
      return hit ? (net.catch(() => {}), hit) : net;
    })));
  }
});

// Push: еске салғыш хабарламалары
self.addEventListener('push', e => {
  let d = {}; try { d = e.data.json(); } catch { d = { title: 'Groowin', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(Promise.all([
    self.registration.showNotification(d.title || 'Groowin', { body: d.body || '', icon: 'icon-192.png', badge: 'icon-192.png', tag: d.tag || 'gw', renotify: true, silent: false, vibrate: [250, 120, 250, 120, 400], data: { url: d.url || './' } }),
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(l => l.forEach(c => { if (c.visibilityState === 'visible') c.postMessage({ type: 'chime' }); }))
  ]));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(l => { for (const c of l) if ('focus' in c) return c.focus(); return clients.openWindow((e.notification.data && e.notification.data.url) || './'); }));
});
