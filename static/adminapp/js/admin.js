/**
 * Admin shell: mobile drawer.
 * Scoped to [data-admin-shell].
 */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var root = document.querySelector("[data-admin-shell]");
    if (!root) return;

    var toggle = root.querySelector("[data-admin-menu-toggle]");
    var backdrop = root.querySelector("[data-admin-backdrop]");
    var collapseBtn = root.querySelector("[data-admin-sidebar-collapse]");
    var sidebar = root.querySelector(".admin-layout__sidebar");
    var mqMobile = window.matchMedia("(max-width: 767px)");

    function syncSidebarAria() {
      if (!sidebar) return;
      if (mqMobile.matches) {
        var open = root.classList.contains("admin-layout--nav-open");
        sidebar.setAttribute("aria-hidden", open ? "false" : "true");
      } else {
        sidebar.removeAttribute("aria-hidden");
      }
    }

    function setNavOpen(open) {
      root.classList.toggle("admin-layout--nav-open", open);
      if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (backdrop) {
        backdrop.hidden = !open || !mqMobile.matches;
      }
      syncSidebarAria();
    }

    function syncSidebarControl() {
      if (!collapseBtn) return;
      collapseBtn.setAttribute("aria-expanded", mqMobile.matches ? "true" : "false");
      collapseBtn.setAttribute("aria-label", "Cerrar menú lateral");
    }

    function isNavLinkActive(linkHref, currentPath) {
      try {
        var linkPath = new URL(linkHref, window.location.origin).pathname;
        if (linkPath === "/admin/" || linkPath === "/admin") {
          return currentPath === "/admin/" || currentPath === "/admin";
        }
        return currentPath === linkPath || currentPath.indexOf(linkPath) === 0;
      } catch (e) {
        return false;
      }
    }

    function syncNavActive() {
      var path = window.location.pathname;
      root.querySelectorAll("[data-admin-nav-link]").forEach(function (link) {
        link.classList.toggle("is-active", isNavLinkActive(link.getAttribute("href"), path));
      });
    }

    if (toggle && sidebar) {
      toggle.addEventListener("click", function () {
        setNavOpen(!root.classList.contains("admin-layout--nav-open"));
      });
    }

    if (backdrop) {
      backdrop.addEventListener("click", function () {
        setNavOpen(false);
      });
    }

    if (collapseBtn) {
      collapseBtn.addEventListener("click", function () {
        if (mqMobile.matches) setNavOpen(false);
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setNavOpen(false);
    });

    mqMobile.addEventListener("change", function () {
      setNavOpen(false);
      syncSidebarControl();
    });

    syncSidebarAria();
    syncSidebarControl();
    syncNavActive();
    if (backdrop && !mqMobile.matches) {
      backdrop.hidden = true;
    }

    document.body.addEventListener("htmx:afterSettle", function () {
      if (!document.querySelector("[data-admin-shell]")) return;
      setNavOpen(false);
      syncNavActive();
    });

    document.querySelectorAll("[data-close-hosting-popup]").forEach(function (button) {
      button.addEventListener("click", function () {
        var popup = button.closest("[data-hosting-popup]");
        if (popup) popup.hidden = true;
      });
    });
  });
})();
