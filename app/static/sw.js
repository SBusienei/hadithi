const CACHE_NAME = "hadithi-legends-v7";
const SHELL = [
  "/",
  "/portal",
  "/portal/la-llorona",
  "/legend/luanda-magere",
  "/legend/la-llorona",
  "/static/styles.css",
  "/static/app.js",
  "/static/la-llorona-environment.js",
  "/static/models/la-llorona-character-study.glb",
  "/static/models/la-llorona-model.json",
  "/static/portal.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request)),
  );
});
