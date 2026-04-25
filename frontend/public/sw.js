/* Service Worker — Web Push + offline stub for ScamLens PWA.

   Registered by the frontend app; receives push events from the VAPID
   pipeline and shows native notifications.
*/

self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "ScamLens", body: event.data.text() };
  }
  const title = payload.title || "ScamLens";
  const options = {
    body: payload.body || "",
    icon: "/setup/scamlens-logo.png",
    badge: "/setup/scamlens-logo.png",
    tag: payload.tag || "scamlens",
    data: { url: payload.url || "/account" },
    vibrate: [200, 100, 200],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/account";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((list) => {
      for (const client of list) {
        if (client.url.includes(url) && "focus" in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});

// Minimal offline: serve cached shell when offline.
self.addEventListener("fetch", (event) => {
  // Only handle navigation requests — let everything else pass through.
  if (event.request.mode !== "navigate") return;
  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match("/offline.html").then(
        (r) => r || new Response("Offline — please reconnect.", { status: 503 }),
      ),
    ),
  );
});
