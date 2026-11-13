// Minimal service worker: makes the app installable. Always loads fresh data from the network.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request).catch(
      () => new Response("You are offline. Please check your internet connection.",
                         { status: 503, headers: { "Content-Type": "text/plain" } })
    )
  );
});