// service-worker.js
// Cache dasar supaya app bisa dibuka offline + handler untuk push notification
// dari Firebase Cloud Messaging (lihat backend/notify.py di sisi server).

const CACHE_NAME = "sinyal-saham-v1";
const ASSETS = ["./index.html", "./manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

// Menampilkan notifikasi push yang dikirim dari backend (via FCM)
self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || "Rekomendasi Saham Hari Ini";
  const options = {
    body: data.body || "Buka app untuk lihat detail 3 profil trading.",
    icon: "icon-192.png",
    badge: "icon-192.png",
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("./index.html"));
});
