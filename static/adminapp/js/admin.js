/**
 * Admin shell: mobile drawer, desktop sidebar collapse.
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
    var STORAGE_KEY = "adminapp_sidebar_collapsed";

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

    function readCollapsed() {
      try {
        return localStorage.getItem(STORAGE_KEY) === "1";
      } catch (e) {
        return false;
      }
    }

    function setCollapsed(collapsed) {
      if (mqMobile.matches) return;
      root.classList.toggle("admin-layout--sidebar-collapsed", collapsed);
      if (collapseBtn) {
        collapseBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
        collapseBtn.setAttribute(
          "aria-label",
          collapsed ? "Expandir menú lateral" : "Contraer menú lateral"
        );
      }
      try {
        localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
      } catch (e) {}
    }

    function syncDesktopCollapse() {
      if (mqMobile.matches) {
        root.classList.remove("admin-layout--sidebar-collapsed");
        if (collapseBtn) {
          collapseBtn.setAttribute("aria-expanded", "true");
          collapseBtn.setAttribute("aria-label", "Contraer menú lateral");
        }
      } else {
        setCollapsed(readCollapsed());
      }
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
        if (mqMobile.matches) return;
        setCollapsed(!root.classList.contains("admin-layout--sidebar-collapsed"));
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setNavOpen(false);
    });

    mqMobile.addEventListener("change", function () {
      setNavOpen(false);
      syncDesktopCollapse();
    });

    syncSidebarAria();
    syncDesktopCollapse();
    if (backdrop && !mqMobile.matches) {
      backdrop.hidden = true;
    }
  });
})();
