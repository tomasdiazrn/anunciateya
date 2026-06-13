(function () {
  function metaContent(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el ? (el.getAttribute("content") || "").trim() : "";
  }

  function initPropertyMaps() {
    var token = metaContent("mapbox-token");
    var style = metaContent("mapbox-style") || "mapbox://styles/mapbox/streets-v12";
    if (!token || typeof mapboxgl === "undefined") return;

    document.querySelectorAll("[data-property-listing-map]").forEach(function (el) {
      if (el.dataset.mapInit === "1") return;
      var lat = parseFloat(el.getAttribute("data-map-lat") || "");
      var lng = parseFloat(el.getAttribute("data-map-lng") || "");
      if (Number.isNaN(lat) || Number.isNaN(lng)) return;

      el.dataset.mapInit = "1";
      el.innerHTML = "";
      mapboxgl.accessToken = token;

      var map = new mapboxgl.Map({
        container: el,
        style: style,
        center: [lng, lat],
        zoom: 15,
        interactive: true,
        attributionControl: true,
      });

      map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
      new mapboxgl.Marker({ color: "#3CBB6B" }).setLngLat([lng, lat]).addTo(map);
      map.scrollZoom.disable();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPropertyMaps);
  } else {
    initPropertyMaps();
  }
})();
