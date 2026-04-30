// Service Worker Simplificado (Não quebra a API)
self.addEventListener('install', (e) => {
    self.skipWaiting();
    console.log('[Service Worker] Instalado e pronto.');
});

self.addEventListener('activate', (e) => {
    console.log('[Service Worker] Ativado.');
});

self.addEventListener('fetch', (e) => {
    // Apenas deixa a conexão passar direto (bypass)
    e.respondWith(fetch(e.request));
});