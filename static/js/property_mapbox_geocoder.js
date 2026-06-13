(function () {
  var DEBOUNCE_MS = 320;
  var MIN_QUERY = 3;

  function metaContent(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el ? (el.getAttribute("content") || "").trim() : "";
  }

  function editorKind(form) {
    return form ? form.getAttribute("data-listing-kind") || "" : "";
  }

  function hideSuggestions(list) {
    if (!list) return;
    list.hidden = true;
    list.innerHTML = "";
  }

  function setHiddenValue(form, id, value) {
    var input = form.querySelector(id);
    if (!input) return;
    input.value = value || "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function clearGeocoding(form) {
    setHiddenValue(form, "#id_latitude", "");
    setHiddenValue(form, "#id_longitude", "");
    setHiddenValue(form, "#id_geocoding_provider", "");
    setHiddenValue(form, "#id_geocoding_place_id", "");
  }

  function applyFeature(form, feature) {
    if (!feature || !form) return;
    var center = feature.center || [];
    var lng = center[0];
    var lat = center[1];
    var addressInput = form.querySelector("#id_address_line");
    var placeInput = form.querySelector("#id_address_place_label");
    var label = (feature.text || "").trim();
    var full = (feature.place_name || label || "").trim();

    if (addressInput && full) addressInput.value = full;
    if (placeInput && label && label !== full) placeInput.value = label;

    setHiddenValue(form, "#id_latitude", lat != null ? String(lat) : "");
    setHiddenValue(form, "#id_longitude", lng != null ? String(lng) : "");
    setHiddenValue(form, "#id_geocoding_provider", "mapbox");
    setHiddenValue(form, "#id_geocoding_place_id", feature.id || "");
  }

  function initPropertyGeocoder(form) {
    if (!form || editorKind(form) !== "property") return;
    var wrap = form.querySelector("[data-property-address-geocoder]");
    var addressInput = form.querySelector("#id_address_line");
    var list = form.querySelector("[data-property-address-suggestions]");
    var token = metaContent("mapbox-token");
    var bbox = metaContent("mapbox-bbox");
    if (!wrap || !addressInput || !list || !token) return;
    if (wrap.dataset.geocoderInit === "1") return;
    wrap.dataset.geocoderInit = "1";

    var timer = null;
    var controller = null;
    var lastSelected = addressInput.value || "";

    function fetchSuggestions(query) {
      if (controller) controller.abort();
      controller = new AbortController();
      var url =
        "https://api.mapbox.com/geocoding/v5/mapbox.places/" +
        encodeURIComponent(query) +
        ".json?access_token=" +
        encodeURIComponent(token) +
        "&country=ec&language=es&limit=5&types=address,poi";
      if (bbox) url += "&bbox=" + encodeURIComponent(bbox);

      return fetch(url, { signal: controller.signal })
        .then(function (res) {
          if (!res.ok) throw new Error("geocoder");
          return res.json();
        })
        .then(function (data) {
          return Array.isArray(data.features) ? data.features : [];
        })
        .catch(function () {
          return [];
        });
    }

    function renderSuggestions(features) {
      list.innerHTML = "";
      if (!features.length) {
        hideSuggestions(list);
        return;
      }
      features.forEach(function (feature) {
        var item = document.createElement("li");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "property-address-geocoder__option";
        btn.setAttribute("role", "option");
        btn.textContent = feature.place_name || feature.text || "Dirección";
        btn.addEventListener("click", function () {
          applyFeature(form, feature);
          lastSelected = addressInput.value || "";
          hideSuggestions(list);
        });
        item.appendChild(btn);
        list.appendChild(item);
      });
      list.hidden = false;
    }

    addressInput.addEventListener("input", function () {
      var query = (addressInput.value || "").trim();
      if (query === lastSelected) return;
      clearGeocoding(form);
      if (timer) window.clearTimeout(timer);
      if (query.length < MIN_QUERY) {
        hideSuggestions(list);
        return;
      }
      timer = window.setTimeout(function () {
        fetchSuggestions(query).then(renderSuggestions);
      }, DEBOUNCE_MS);
    });

    addressInput.addEventListener("blur", function () {
      window.setTimeout(function () {
        hideSuggestions(list);
      }, 150);
    });

    addressInput.addEventListener("keydown", function (event) {
      if (event.key === "Escape") hideSuggestions(list);
    });

    form.addEventListener("change", function (event) {
      if (event.target && event.target.id === "id_add_location" && !event.target.checked) {
        hideSuggestions(list);
        clearGeocoding(form);
      }
    });
  }

  function initAll(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var forms = [];
    if (scope.matches && scope.matches("form.listing-editor")) {
      forms = [scope];
    } else {
      forms = Array.prototype.slice.call(scope.querySelectorAll("form.listing-editor"));
    }
    forms.forEach(initPropertyGeocoder);
  }

  window.initPropertyMapboxGeocoder = initAll;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initAll(document);
    });
  } else {
    initAll(document);
  }

  document.body.addEventListener("htmx:load", function (event) {
    initAll(event.target || document);
  });

  document.body.addEventListener("htmx:afterSwap", function (event) {
    initAll(event.detail && event.detail.target ? event.detail.target : document);
  });

  document.body.addEventListener("htmx:afterSettle", function (event) {
    var target = event.detail && event.detail.elt ? event.detail.elt : event.target;
    initAll(target || document);
  });
})();
