const CACHE_VERSION = "anunciateya-pwa-v1";
const OFFLINE_URL = "{% url 'offline' %}";
const STATIC_PATH_PREFIX = "/static/";

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_VERSION).then(function (cache) {
      return cache.add(new Request(OFFLINE_URL, { cache: "reload" }));
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys
          .filter(function (key) {
            return key !== CACHE_VERSION;
          })
          .map(function (key) {
            return caches.delete(key);
          })
      );
    })
  );
  self.clients.claim();
});

function isSameOrigin(requestUrl) {
  return requestUrl.origin === self.location.origin;
}

function isCacheableStaticRequest(request, requestUrl) {
  return (
    request.method === "GET" &&
    isSameOrigin(requestUrl) &&
    requestUrl.pathname.startsWith(STATIC_PATH_PREFIX)
  );
}

function staticAssetResponse(request) {
  return caches.match(request).then(function (cached) {
    var networkFetch = fetch(request)
      .then(function (response) {
        if (response && response.ok) {
          var responseClone = response.clone();
          caches.open(CACHE_VERSION).then(function (cache) {
            cache.put(request, responseClone);
          });
        }
        return response;
      })
      .catch(function () {
        return cached;
      });

    return cached || networkFetch;
  });
}

self.addEventListener("fetch", function (event) {
  var request = event.request;
  var requestUrl = new URL(request.url);

  if (request.method !== "GET" || !isSameOrigin(requestUrl)) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match(OFFLINE_URL);
      })
    );
    return;
  }

  if (isCacheableStaticRequest(request, requestUrl)) {
    event.respondWith(staticAssetResponse(request));
  }
});
