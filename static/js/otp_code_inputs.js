(function () {
  function digitsOnly(value) {
    return (value || "").replace(/\D/g, "");
  }

  function initOtpCodeInputs(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("[data-otp-code-inputs]").forEach(function (group) {
      if (group.dataset.otpCodeInputsInit === "1") return;
      group.dataset.otpCodeInputsInit = "1";

      var inputs = Array.prototype.slice.call(group.querySelectorAll(".auth-otp-digit"));
      var hiddenId = group.getAttribute("data-otp-hidden-input");
      var hidden = hiddenId ? document.getElementById(hiddenId) : null;
      if (!inputs.length || !hidden) return;

      function updateHidden() {
        hidden.value = inputs.map(function (input) {
          input.classList.toggle("is-filled", Boolean(input.value));
          return input.value;
        }).join("");
      }

      function fillFrom(value, startIndex) {
        var digits = digitsOnly(value).slice(0, inputs.length - startIndex);
        digits.split("").forEach(function (digit, offset) {
          inputs[startIndex + offset].value = digit;
        });
        updateHidden();
        var next = Math.min(startIndex + digits.length, inputs.length - 1);
        inputs[next].focus();
        inputs[next].select();
      }

      inputs.forEach(function (input, index) {
        input.addEventListener("input", function () {
          var value = digitsOnly(input.value);
          if (value.length > 1) {
            fillFrom(value, index);
            return;
          }
          input.value = value;
          updateHidden();
          if (value && inputs[index + 1]) {
            inputs[index + 1].focus();
            inputs[index + 1].select();
          }
        });

        input.addEventListener("keydown", function (event) {
          if (event.key === "Backspace" && !input.value && inputs[index - 1]) {
            inputs[index - 1].focus();
            inputs[index - 1].value = "";
            updateHidden();
            event.preventDefault();
          }
          if (event.key === "ArrowLeft" && inputs[index - 1]) {
            inputs[index - 1].focus();
            event.preventDefault();
          }
          if (event.key === "ArrowRight" && inputs[index + 1]) {
            inputs[index + 1].focus();
            event.preventDefault();
          }
        });

        input.addEventListener("paste", function (event) {
          var text = event.clipboardData && event.clipboardData.getData("text");
          if (!text) return;
          event.preventDefault();
          fillFrom(text, index);
        });

        input.addEventListener("focus", function () {
          input.select();
        });
      });

      var form = group.closest("form");
      if (form) {
        form.addEventListener("submit", updateHidden);
      }
      updateHidden();
    });
  }

  function boot() {
    initOtpCodeInputs();
    document.body.addEventListener("htmx:load", function (event) {
      initOtpCodeInputs(event.target);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
