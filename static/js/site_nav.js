(function () {
  var MOBILE_QUERY = "(max-width: 719px)";

  function initSiteNav() {
    var header = document.querySelector(".site-header");
    var toggle = document.querySelector("[data-nav-menu-toggle]");
    var menu = document.querySelector("[data-nav-menu]");
    if (!header || !toggle || !menu) return;

    var media = window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null;

    function isMobile() {
      return !media || media.matches;
    }

    function setOpen(open) {
      header.classList.toggle("is-nav-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.querySelector(".visually-hidden").textContent = open ? "Cerrar menú" : "Abrir menú";
    }

    toggle.addEventListener("click", function () {
      if (!isMobile()) return;
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    menu.addEventListener("click", function (event) {
      if (!isMobile() || !event.target.closest("a, button")) return;
      setOpen(false);
    });

    document.addEventListener("click", function (event) {
      if (!isMobile() || !header.classList.contains("is-nav-open")) return;
      if (header.contains(event.target)) return;
      setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || !header.classList.contains("is-nav-open")) return;
      setOpen(false);
      toggle.focus();
    });

    if (media && media.addEventListener) {
      media.addEventListener("change", function () {
        setOpen(false);
      });
    } else if (media && media.addListener) {
      media.addListener(function () {
        setOpen(false);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSiteNav);
  } else {
    initSiteNav();
  }
})();
