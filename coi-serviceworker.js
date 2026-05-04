self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', e => {
  if (e.request.cache === 'only-if-cached' && e.request.mode !== 'same-origin') return;
  e.respondWith(
    fetch(e.request).then(r => {
      const h = new Headers(r.headers);
      h.set('Cross-Origin-Opener-Policy', 'same-origin');
      h.set('Cross-Origin-Embedder-Policy', 'credentialless');
      return new Response(r.body, { status: r.status, statusText: r.statusText, headers: h });
    }).catch(() => fetch(e.request))
  );
});
