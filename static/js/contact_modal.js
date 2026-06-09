(function () {
  var modal;
  var body;
  var whatsappLink;
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

  function setWhatsapp(url) {
    if (!whatsappLink) return;
    if (url) {
      whatsappLink.href = url;
      whatsappLink.hidden = false;
      return;
    }
    whatsappLink.hidden = true;
    whatsappLink.removeAttribute("href");
  }

  function openModal(trigger) {
    if (!modal) return;
    lastTrigger = trigger || document.activeElement;

    if (body) {
      body.innerHTML = '<p class="small muted">Preparando formulario seguro…</p>';
    }
    setWhatsapp(trigger ? trigger.getAttribute("data-contact-whatsapp-url") : "");

    modal.hidden = false;
    document.documentElement.classList.add("has-contact-modal-open");

    var focusable = getFocusable(modal);
    if (focusable.length) focusable[0].focus();
  }

  function closeModal() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.documentElement.classList.remove("has-contact-modal-open");
    if (body) {
      body.innerHTML = '<p class="small muted">El formulario se cargará aquí.</p>';
    }
    setWhatsapp("");
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
    modal = document.querySelector("[data-contact-modal]");
    if (!modal) return;
    body = document.getElementById("listing-contact-modal-body");
    whatsappLink = modal.querySelector("[data-contact-modal-whatsapp]");

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-contact-modal-open]");
      if (trigger) {
        openModal(trigger);
        return;
      }
      if (event.target.closest("[data-contact-modal-close]")) {
        closeModal();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeModal();
      trapFocus(event);
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
      if (!body || event.target !== body) return;
      var focusable = getFocusable(body);
      if (focusable.length) focusable[0].focus();
    });

    document.body.addEventListener("htmx:responseError", function (event) {
      if (!body || event.detail.target !== body) return;
      body.innerHTML = '<p class="form-errors" role="alert">No pudimos cargar el contacto. Intenta otra vez o abre el anuncio.</p>';
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
