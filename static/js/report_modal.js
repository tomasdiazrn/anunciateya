(function () {
  var modal;
  var lastTrigger;

  function getFocusable(root) {
    if (!root) return [];
    return Array.prototype.slice.call(
      root.querySelectorAll(
        "a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex='-1'])"
      )
    ).filter(function (el) {
      return el.offsetParent !== null || el === document.activeElement;
    });
  }

  function openModal(trigger) {
    if (!modal) return;
    lastTrigger = trigger || document.activeElement;
    modal.hidden = false;
    document.documentElement.classList.add("has-report-modal-open");

    var focusable = getFocusable(modal);
    if (focusable.length) focusable[0].focus();
  }

  function closeModal() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.documentElement.classList.remove("has-report-modal-open");
    if (lastTrigger && typeof lastTrigger.focus === "function") {
      lastTrigger.focus();
    }
  }

  function trapFocus(event) {
    if (!modal || modal.hidden || event.key !== "Tab") return;
    var focusable = getFocusable(modal);
    if (!focusable.length) return;

    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function boot() {
    modal = document.querySelector("[data-report-modal]");
    if (!modal) return;

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-report-modal-open]");
      if (trigger) {
        openModal(trigger);
        return;
      }
      if (event.target.closest("[data-report-modal-close]")) {
        closeModal();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeModal();
      trapFocus(event);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
