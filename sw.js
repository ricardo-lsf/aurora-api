const cacheName = 'bar-app-v5'; // <--- MUDANÇA IMPORTANTE: v19
const assets = [
  './',
  './index.html',
  './admin.html', // Agora guardamos o admin também!
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './screenshot.png',
  'https://cdn.jsdelivr.net/npm/chart.js',
  // IMAGENS LOCAIS (Se tiver adicionado novas, liste aqui)
  './imagens/moscow.jpg',
  './imagens/mojito.jpg',
  './imagens/pina.jpg',
  './imagens/negroni.jpg',
  './imagens/caipirinha.jpg',
  './imagens/caipiroska.jpg',
  './imagens/gin.jpg',
  './imagens/sunset.jpg',
  './imagens/blue.jpg',
  './imagens/pinamock.jpg'
];

// 1. Instalação
self.addEventListener('install', evt => {
  self.skipWaiting(); // Força a atualização imediata!
  evt.waitUntil(
    caches.open(cacheName).then(cache => {
      return cache.addAll(assets);
    })
  );
});

// 2. Ativação (Limpa caches antigos - Mata o Zumbi v4)
self.addEventListener('activate', evt => {
  evt.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(keys
        .filter(key => key !== cacheName)
        .map(key => caches.delete(key)) // Apaga tudo que não seja v5
      );
    })
  );
});

// 3. Busca (Network First para Dados, Cache First para Imagens)
self.addEventListener('fetch', evt => {
  evt.respondWith(
    caches.match(evt.request).then(cacheRes => {
      return cacheRes || fetch(evt.request);
    })
  );
});