// service-worker.js
// Cache dasar supaya app bisa dibuka offline + handler untuk push notification
// dari Firebase Cloud Messaging (lihat backend/notify.py di sisi server).

const CACHE_NAME = "sinyal-saham-v3";
const ASSETS = [
  "./index.html", "./manifest.json",
  "kobul/kobul-01.jpg", "kobul/kobul-02.jpg", "kobul/kobul-03.jpg", "kobul/kobul-04.jpg",
  "kobul/kobul-05.jpg", "kobul/kobul-06.jpg", "kobul/kobul-07.jpg", "kobul/kobul-08.jpg",
  "kobul/kobul-09.jpg", "kobul/kobul-10.jpg", "kobul/kobul-11.jpg", "kobul/kobul-12.jpg",
  "kobul/kobul-13.jpg",
];

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
