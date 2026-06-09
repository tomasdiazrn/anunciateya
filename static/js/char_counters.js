/**
 * Contador "len / max" bajo .field-header (solo si hay maxlength en el input).
 * Idempotente: marca inputs con data-char-counter-init.
 * No bloquea entrada; el backend sigue validando.
 */
(function () {
  function initCharCounters(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("[maxlength]").forEach(function (input) {
      if (input.getAttribute("data-char-counter-init") === "1") return;
      var raw = input.getAttribute("maxlength");
      var max = parseInt(raw, 10);
      if (!max || max < 1) return;
      var fieldRoot = input.closest(".field");
      if (!fieldRoot) return;
      var counter = fieldRoot.querySelector(".char-counter");
      if (!counter) return;
      input.setAttribute("data-char-counter-init", "1");

      function update() {
        var len = input.value.length;
        counter.textContent = len + " / " + max;
        counter.classList.remove("is-warning", "is-danger");
        if (len >= max) {
          counter.classList.add("is-danger");
        } else if (len > max * 0.8) {
          counter.classList.add("is-warning");
        }
      }

      input.addEventListener("input", update);
      input.addEventListener("change", update);
      update();
    });
  }

  function boot() {
    initCharCounters(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  document.body.addEventListener("htmx:load", function (e) {
    var root = e.detail && e.detail.elt ? e.detail.elt : e.target;
    initCharCounters(root || document);
  });
  document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.detail && e.detail.target) {
      initCharCounters(e.detail.target);
    }
  });
})();
