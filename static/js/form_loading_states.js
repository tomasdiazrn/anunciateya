(function () {
  var FORM_SELECTOR = "form[data-loading-submit]";
  var BUTTON_SELECTOR = "button[type='submit'], input[type='submit']";

  function setButtonText(button, text) {
    if (!button || !text) return;
    if (button.tagName === "INPUT") {
      if (!button.dataset.originalValue) button.dataset.originalValue = button.value;
      button.value = text;
      return;
    }
    if (!button.dataset.originalText) button.dataset.originalText = button.textContent.trim();
    button.textContent = text;
  }

  function restoreButtonText(button) {
    if (!button) return;
    if (button.tagName === "INPUT" && button.dataset.originalValue) {
      button.value = button.dataset.originalValue;
      return;
    }
    if (button.dataset.originalText) button.textContent = button.dataset.originalText;
  }

  function setLoading(form, submitter) {
    if (!form || form.dataset.loadingActive === "1") return;
    form.dataset.loadingActive = "1";
    form.setAttribute("aria-busy", "true");

    var buttons = Array.prototype.slice.call(form.querySelectorAll(BUTTON_SELECTOR));
    var activeButton = submitter && form.contains(submitter) ? submitter : buttons[0];
    var loadingText = activeButton && activeButton.getAttribute("data-loading-text");

    buttons.forEach(function (button) {
      if (!button.dataset.loadingWasDisabled) {
        button.dataset.loadingWasDisabled = button.disabled ? "1" : "0";
      }
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      if (button === activeButton) {
        button.classList.add("is-loading");
        setButtonText(button, loadingText);
      }
    });
  }

  function clearLoading(form) {
    if (!form || form.dataset.loadingActive !== "1") return;
    form.dataset.loadingActive = "0";
    form.removeAttribute("aria-busy");

    form.querySelectorAll(BUTTON_SELECTOR).forEach(function (button) {
      if (button.dataset.loadingWasDisabled !== "1") {
        button.disabled = false;
        button.removeAttribute("aria-disabled");
      }
      delete button.dataset.loadingWasDisabled;
      button.classList.remove("is-loading");
      restoreButtonText(button);
    });
  }

  function initFormLoading(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(FORM_SELECTOR).forEach(function (form) {
      if (form.dataset.loadingSubmitInit === "1") return;
      form.dataset.loadingSubmitInit = "1";

      form.addEventListener("submit", function (event) {
        if (event.defaultPrevented) return;
        if (form.dataset.loadingActive === "1") {
          event.preventDefault();
          return;
        }
        var submitter = event.submitter;
        var defer = window.requestAnimationFrame || function (callback) {
          return window.setTimeout(callback, 0);
        };
        defer(function () {
          if (event.defaultPrevented) return;
          setLoading(form, submitter);
        });
      });
    });
  }

  function boot() {
    initFormLoading();

    document.body.addEventListener("htmx:load", function (event) {
      initFormLoading(event.target);
    });

    document.body.addEventListener("htmx:afterRequest", function (event) {
      clearLoading(event.target && event.target.closest
        ? event.target.closest(FORM_SELECTOR)
        : null);
    });

    window.addEventListener("pageshow", function () {
      document.querySelectorAll(FORM_SELECTOR).forEach(clearLoading);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
