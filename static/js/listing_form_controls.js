(function () {
  var SELECT_SELECTOR = ".listing-editor select.form-control, .browse-filter-form select.form-control, .browse-sort-select, .listing-report-form select.form-control";
  var DIGITS_SELECTOR = "[data-digits-only='true']";
  var OPEN_CLASS = "is-open";
  var SELECT_INIT = "customSelectInit";
  var SELECT_INIT_VERSION = "2";
  var SEARCH_MAX_LENGTH = 48;
  var SEARCH_MIN_OPTIONS = 5;
  var REQUIRED_ERROR = "Este campo es obligatorio.";
  var FILTERS_MOBILE_MEDIA = "(max-width: 899.98px)";

  function closestField(el) {
    return el && el.closest ? el.closest(".field") : null;
  }

  function textForOption(option) {
    return option ? (option.textContent || "").trim() : "";
  }

  function isPlaceholder(option) {
    return !option || option.value === "";
  }

  function normalizeSearch(value) {
    var text = (value || "").toString();
    if (text.normalize) text = text.normalize("NFD");
    return text
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function digitsOnlyValue(value) {
    var text = String(value || "").trim();
    if (/^\d+[.,]\d{1,2}$/.test(text)) {
      return text.split(/[.,]/)[0];
    }
    if (/^\d{1,3}([.,]\d{3})+$/.test(text)) {
      return text.replace(/\D/g, "");
    }
    return text.replace(/\D/g, "");
  }

  function isDigitsOnlyInput(input) {
    return input && input.matches && input.matches(DIGITS_SELECTOR);
  }

  function sanitizeDigitsOnlyInput(input) {
    if (!isDigitsOnlyInput(input)) return;
    var clean = digitsOnlyValue(input.value);
    if (input.value !== clean) input.value = clean;
  }

  function initDigitsOnlyInputs(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(DIGITS_SELECTOR).forEach(sanitizeDigitsOnlyInput);
  }

  function closeBrowseFiltersOnMobile(root) {
    if (!window.matchMedia || !window.matchMedia(FILTERS_MOBILE_MEDIA).matches) return;
    var scope = root && root.querySelectorAll ? root : document;
    if (scope.matches && scope.matches(".browse-filters-accordion[open]")) {
      scope.removeAttribute("open");
    }
    scope.querySelectorAll(".browse-filters-accordion[open]").forEach(function (details) {
      details.removeAttribute("open");
    });
  }

  function shouldAllowDigitKey(event) {
    if (event.ctrlKey || event.metaKey || event.altKey) return true;
    if (event.key && event.key.length === 1) return /^\d$/.test(event.key);
    return true;
  }

  function visibleOptions(list) {
    if (!list) return [];
    return Array.prototype.slice.call(list.querySelectorAll(".custom-select__option:not([disabled])")).filter(function (option) {
      return !option.hidden;
    });
  }

  function selectedOption(select) {
    if (!select || select.selectedIndex < 0) return null;
    return select.options[select.selectedIndex] || null;
  }

  function getSelectLabel(select) {
    var aria = select ? (select.getAttribute("aria-label") || "").trim() : "";
    if (aria) return aria;
    var label = select.id ? document.querySelector("label[for='" + select.id + "']") : null;
    return label ? (label.textContent || "").trim() : "Seleccionar";
  }

  function searchableOptionCount(select) {
    if (!select) return 0;
    return Array.prototype.slice.call(select.options).filter(function (option) {
      return !isPlaceholder(option) && !option.disabled;
    }).length;
  }

  function shouldShowSearch(select) {
    return searchableOptionCount(select) >= SEARCH_MIN_OPTIONS;
  }

  function destroyCustomSelect(select) {
    if (!select) return;
    if (select._customSelectObserver) {
      select._customSelectObserver.disconnect();
      delete select._customSelectObserver;
    }
    var wrap = select.nextElementSibling;
    if (wrap && wrap.classList && wrap.classList.contains("custom-select")) {
      closeCustomSelect(wrap);
      wrap.remove();
    }
    delete select.dataset[SELECT_INIT];
    select.classList.remove("native-select--customized");
    var field = closestField(select);
    if (field) field.classList.remove("field--custom-select");
  }

  function updateSearchVisibility(select, wrap) {
    var searchWrap = wrap ? wrap.querySelector(".custom-select__search") : null;
    if (!searchWrap) return;
    var show = shouldShowSearch(select);
    searchWrap.hidden = !show;
    searchWrap.setAttribute("aria-hidden", show ? "false" : "true");
  }

  function closeAllCustomSelects(except) {
    document.querySelectorAll(".custom-select." + OPEN_CLASS).forEach(function (wrap) {
      if (except && wrap === except) return;
      closeCustomSelect(wrap);
    });
  }

  function closeCustomSelect(wrap) {
    if (!wrap) return;
    wrap.classList.remove(OPEN_CLASS);
    var trigger = wrap.querySelector(".custom-select__trigger");
    var panel = wrap.querySelector(".custom-select__panel");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    if (panel) panel.hidden = true;
  }

  function resetSearch(wrap) {
    var search = wrap ? wrap.querySelector(".custom-select__search-input") : null;
    if (!search || !search.value) return;
    search.value = "";
    applySearchFilter(wrap);
  }

  function applySearchFilter(wrap) {
    if (!wrap) return;
    var search = wrap.querySelector(".custom-select__search-input");
    var list = wrap.querySelector(".custom-select__list");
    var empty = wrap.querySelector(".custom-select__empty");
    if (!search || !list) return;

    var query = normalizeSearch(search.value).slice(0, SEARCH_MAX_LENGTH);
    var hasVisibleOptions = false;

    Array.prototype.slice.call(list.querySelectorAll(".custom-select__option")).forEach(function (option) {
      var haystack = option.getAttribute("data-search") || "";
      var isMatch = !query || haystack.indexOf(query) !== -1;
      option.hidden = !isMatch;
      if (isMatch && !option.disabled) hasVisibleOptions = true;
    });

    if (empty) empty.hidden = hasVisibleOptions || !query;
  }

  function openCustomSelect(wrap, preferredValue) {
    if (!wrap) return;
    closeAllCustomSelects(wrap);
    wrap.classList.add(OPEN_CLASS);

    var trigger = wrap.querySelector(".custom-select__trigger");
    var panel = wrap.querySelector(".custom-select__panel");
    var list = wrap.querySelector(".custom-select__list");
    if (trigger) trigger.setAttribute("aria-expanded", "true");
    if (panel) panel.hidden = false;

    resetSearch(wrap);

    var options = visibleOptions(list);
    var target = options[0];
    for (var i = 0; i < options.length; i += 1) {
      if (options[i].getAttribute("data-value") === preferredValue) {
        target = options[i];
        break;
      }
    }

    var search = wrap.querySelector(".custom-select__search-input");
    var searchWrap = wrap.querySelector(".custom-select__search");
    if (search && searchWrap && !searchWrap.hidden) {
      search.focus({ preventScroll: true });
      if (target) target.scrollIntoView({ block: "nearest" });
    } else if (target) {
      target.focus({ preventScroll: true });
    }
  }

  function dispatchNativeChange(select) {
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function addDescribedBy(input, id) {
    if (!input || !id) return;
    var tokens = (input.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (tokens.indexOf(id) === -1) tokens.push(id);
    input.setAttribute("aria-describedby", tokens.join(" "));
  }

  function removeDescribedBy(input, id) {
    if (!input || !id) return;
    var tokens = (input.getAttribute("aria-describedby") || "").split(/\s+/).filter(function (token) {
      return token && token !== id;
    });
    if (tokens.length) {
      input.setAttribute("aria-describedby", tokens.join(" "));
    } else {
      input.removeAttribute("aria-describedby");
    }
  }

  function setSelectValue(select, value) {
    if (!select || select.value === value) return;
    select.value = value;
    dispatchNativeChange(select);
  }

  function renderSelectOptions(select, wrap) {
    var list = wrap.querySelector(".custom-select__list");
    if (!list) return;
    list.innerHTML = "";

    Array.prototype.slice.call(select.options).forEach(function (option, index) {
      var item = document.createElement("button");
      item.type = "button";
      item.className = "custom-select__option";
      item.setAttribute("role", "option");
      item.setAttribute("data-value", option.value);
      item.setAttribute("data-search", normalizeSearch(textForOption(option)));
      item.setAttribute("aria-selected", option.selected ? "true" : "false");
      item.disabled = option.disabled;
      item.textContent = textForOption(option);
      if (option.selected) item.classList.add("is-selected");
      if (isPlaceholder(option)) item.classList.add("is-placeholder");

      item.addEventListener("click", function () {
        setSelectValue(select, option.value);
        syncCustomSelect(select);
        closeCustomSelect(wrap);
        var trigger = wrap.querySelector(".custom-select__trigger");
        if (trigger) trigger.focus({ preventScroll: true });
      });

      item.addEventListener("keydown", function (event) {
        var options = visibleOptions(list);
        var current = options.indexOf(item);
        if (event.key === "ArrowDown") {
          event.preventDefault();
          (options[current + 1] || options[0] || item).focus({ preventScroll: true });
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          (options[current - 1] || options[options.length - 1] || item).focus({ preventScroll: true });
        } else if (event.key === "Home") {
          event.preventDefault();
          (options[0] || item).focus({ preventScroll: true });
        } else if (event.key === "End") {
          event.preventDefault();
          (options[options.length - 1] || item).focus({ preventScroll: true });
        } else if (event.key === "Escape") {
          event.preventDefault();
          closeCustomSelect(wrap);
          var trigger = wrap.querySelector(".custom-select__trigger");
          if (trigger) trigger.focus({ preventScroll: true });
        }
      });

      if (index === 0 && !textForOption(option)) item.textContent = "Seleccionar";
      list.appendChild(item);
    });

    applySearchFilter(wrap);
    updateSearchVisibility(select, wrap);
  }

  function syncCustomSelect(select) {
    if (!select) return;
    var wrap = select.nextElementSibling;
    if (!wrap || !wrap.classList || !wrap.classList.contains("custom-select")) return;

    var trigger = wrap.querySelector(".custom-select__trigger");
    var value = wrap.querySelector(".custom-select__value");
    var option = selectedOption(select);
    var label = textForOption(option) || getSelectLabel(select);
    var hasValue = option && !isPlaceholder(option);

    if (value) value.textContent = label;
    if (trigger) {
      trigger.disabled = select.disabled;
      trigger.classList.toggle("is-placeholder", !hasValue);
      trigger.setAttribute("aria-disabled", select.disabled ? "true" : "false");
      if (select.getAttribute("aria-invalid")) {
        trigger.setAttribute("aria-invalid", select.getAttribute("aria-invalid"));
      } else {
        trigger.removeAttribute("aria-invalid");
      }
      if (select.getAttribute("aria-describedby")) {
        trigger.setAttribute("aria-describedby", select.getAttribute("aria-describedby"));
      } else {
        trigger.removeAttribute("aria-describedby");
      }
    }

    renderSelectOptions(select, wrap);
  }

  function initCustomSelect(select) {
    if (!select) return;
    if (select.closest(".custom-select")) return;

    var wrap = select.nextElementSibling;
    var hasCurrentShell =
      wrap &&
      wrap.classList &&
      wrap.classList.contains("custom-select") &&
      wrap.querySelector(".custom-select__panel") &&
      wrap.querySelector(".custom-select__search-input");

    if (select.dataset[SELECT_INIT] === SELECT_INIT_VERSION && hasCurrentShell) {
      syncCustomSelect(select);
      return;
    }

    if (select.dataset[SELECT_INIT] || (wrap && wrap.classList.contains("custom-select"))) {
      destroyCustomSelect(select);
    }

    select.dataset[SELECT_INIT] = SELECT_INIT_VERSION;
    select.classList.add("native-select--customized");

    var field = closestField(select);
    if (field) field.classList.add("field--custom-select");

    var listId = (select.id || "custom_select") + "__listbox";
    var wrap = document.createElement("div");
    wrap.className = "custom-select";

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "custom-select__trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-controls", listId);
    trigger.setAttribute("aria-label", getSelectLabel(select));

    var value = document.createElement("span");
    value.className = "custom-select__value";
    var icon = document.createElement("span");
    icon.className = "custom-select__chevron";
    icon.setAttribute("aria-hidden", "true");

    trigger.appendChild(value);
    trigger.appendChild(icon);

    var panel = document.createElement("div");
    panel.className = "custom-select__panel";
    panel.hidden = true;

    var searchWrap = document.createElement("div");
    searchWrap.className = "custom-select__search";

    var search = document.createElement("input");
    search.type = "search";
    search.className = "custom-select__search-input";
    search.maxLength = SEARCH_MAX_LENGTH;
    search.autocomplete = "off";
    search.spellcheck = false;
    var fieldLabel = getSelectLabel(select);
    search.placeholder = "Buscar " + fieldLabel.toLowerCase() + "...";
    search.setAttribute("aria-label", "Buscar en " + fieldLabel);

    var list = document.createElement("div");
    list.className = "custom-select__list";
    list.id = listId;
    list.setAttribute("role", "listbox");

    var empty = document.createElement("div");
    empty.className = "custom-select__empty";
    empty.textContent = "Sin resultados";
    empty.hidden = true;

    searchWrap.appendChild(search);
    panel.appendChild(searchWrap);
    panel.appendChild(list);
    panel.appendChild(empty);

    search.addEventListener("input", function () {
      if (search.value.length > SEARCH_MAX_LENGTH) {
        search.value = search.value.slice(0, SEARCH_MAX_LENGTH);
      }
      applySearchFilter(wrap);
    });

    search.addEventListener("keydown", function (event) {
      var options = visibleOptions(list);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (options[0]) options[0].focus({ preventScroll: true });
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (options[options.length - 1]) options[options.length - 1].focus({ preventScroll: true });
      } else if (event.key === "Enter" && options.length === 1) {
        event.preventDefault();
        options[0].click();
      } else if (event.key === "Escape") {
        event.preventDefault();
        closeCustomSelect(wrap);
        trigger.focus({ preventScroll: true });
      }
    });

    trigger.addEventListener("click", function () {
      if (select.disabled) return;
      if (wrap.classList.contains(OPEN_CLASS)) {
        closeCustomSelect(wrap);
      } else {
        openCustomSelect(wrap, select.value);
      }
    });

    trigger.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openCustomSelect(wrap, select.value);
      } else if (event.key === "Escape") {
        closeCustomSelect(wrap);
      }
    });

    select.addEventListener("change", function () {
      syncCustomSelect(select);
    });

    select.addEventListener("focus", function () {
      trigger.focus({ preventScroll: true });
    });

    if (window.MutationObserver) {
      var observer = new MutationObserver(function () {
        syncCustomSelect(select);
      });
      observer.observe(select, {
        attributes: true,
        attributeFilter: ["disabled", "class", "aria-invalid", "aria-describedby"],
        childList: true,
        subtree: true,
      });
      select._customSelectObserver = observer;
    }

    wrap.appendChild(trigger);
    wrap.appendChild(panel);
    select.insertAdjacentElement("afterend", wrap);
    syncCustomSelect(select);
  }

  function initListingControls(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(SELECT_SELECTOR).forEach(initCustomSelect);
    initDigitsOnlyInputs(scope);
  }

  function getSwapTarget(event) {
    return event && event.detail && event.detail.target ? event.detail.target : event.target;
  }

  function editorFor(el) {
    return el && el.closest ? el.closest("form.listing-editor") : null;
  }

  function editorKind(form) {
    return form ? form.getAttribute("data-listing-kind") || "" : "";
  }

  function setOnlyPlaceholder(select, message, disabled) {
    if (!select) return;
    select.innerHTML = "";
    var option = document.createElement("option");
    option.value = "";
    option.textContent = message;
    select.appendChild(option);
    select.value = "";
    select.disabled = Boolean(disabled);
    syncCustomSelect(select);
  }

  function syncDependentModelState(form) {
    if (!form) return;
    var brand = form.querySelector("#id_brand_fk");
    var model = form.querySelector("#id_model_fk");
    if (!brand || !model) return;
    if (!brand.value) {
      setOnlyPlaceholder(model, "Primero elige marca", true);
    } else {
      model.disabled = false;
      syncCustomSelect(model);
    }
  }

  function syncLocationFields(form) {
    if (!form) return;
    var toggle = form.querySelector("#id_add_location");
    var fields = form.querySelector("[data-listing-location-fields]");
    if (!toggle || !fields) return;
    var show = toggle.checked;
    fields.hidden = !show;
    fields.setAttribute("aria-hidden", show ? "false" : "true");
  }

  function bindLocationToggle(form) {
    if (!form) return;
    var toggle = form.querySelector("#id_add_location");
    if (!toggle || toggle.dataset.locationToggleInit === "1") return;
    toggle.dataset.locationToggleInit = "1";
    toggle.addEventListener("change", function () {
      syncLocationFields(form);
    });
  }

  function handleBrandChange(target) {
    if (!target || target.id !== "id_brand_fk") return;
    var form = editorFor(target);
    var model = form ? form.querySelector("#id_model_fk") : null;
    if (!model) return;
    if (!target.value) {
      setOnlyPlaceholder(model, "Primero elige marca", true);
      return;
    }
    setOnlyPlaceholder(model, "Selecciona modelo", false);
    if (model.focus) model.focus({ preventScroll: true });
  }

  function handleItemTypeChange(target) {
    if (!target || target.id !== "id_item_type") return;
    var form = editorFor(target);
    var kind = editorKind(form);
    if (kind !== "electronics" && kind !== "homegoods") return;
    var model = form.querySelector("#id_model_fk");
    setOnlyPlaceholder(model, "Primero elige marca", true);
  }

  function refreshModelsForCurrentBrand(form) {
    if (!form) return;
    var kind = editorKind(form);
    if (kind !== "electronics" && kind !== "homegoods") return;
    var brand = form.querySelector("#id_brand_fk");
    if (!brand || !brand.value) {
      syncDependentModelState(form);
      return;
    }
    var model = form.querySelector("#id_model_fk");
    setOnlyPlaceholder(model, "Cargando modelos...", false);
    dispatchNativeChange(brand);
  }

  function getSelectText(select) {
    if (!select || select.selectedIndex < 0) return "";
    var option = select.options[select.selectedIndex];
    if (!option || !String(option.value).length) return "";
    return (option.text || "").trim();
  }

  function syncVehicleTitle(form) {
    if (!form || editorKind(form) !== "vehicle") return;
    var title = form.querySelector("#id_title");
    var brand = form.querySelector("#id_brand_fk");
    var model = form.querySelector("#id_model_fk");
    var year = form.querySelector("#id_year");
    if (!title || !brand || title.dataset.userEdited === "1") return;
    var parts = [
      getSelectText(brand),
      getSelectText(model),
      year && year.value ? String(year.value).trim() : "",
    ].filter(Boolean);
    if (parts.length) title.value = parts.join(" ");
  }

  function syncPropertyTitle(form) {
    if (!form || editorKind(form) !== "property") return;
    var title = form.querySelector("#id_title");
    var type = form.querySelector("#id_property_type");
    var rooms = form.querySelector("#id_rooms");
    var zone = form.querySelector("#id_zone");
    if (!title || !type || title.dataset.userEdited === "1") return;
    var typeLabel = getSelectText(type);
    var roomCount = rooms && rooms.value ? String(rooms.value).trim() : "";
    var shortLocation = zone && zone.value ? getSelectText(zone) : "";
    var parts = [];
    if (typeLabel) parts.push(typeLabel);
    if (roomCount) parts.push(roomCount + " hab");
    var output = parts.join(" ");
    if (shortLocation) output = output ? output + " en " + shortLocation : shortLocation;
    if (output) title.value = output;
  }

  function markExistingTitles(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("form.listing-editor #id_title").forEach(function (title) {
      if (title.value && title.value.trim()) title.dataset.userEdited = "1";
    });
  }

  function showInlineError(input, message) {
    if (!input) return;
    input.classList.add("is-invalid");
    var el = document.getElementById(input.id + "__inline_error");
    if (!el) {
      el = document.createElement("div");
      el.id = input.id + "__inline_error";
      el.className = "form-errors form-errors--client";
      el.setAttribute("role", "alert");
      el.setAttribute("aria-live", "polite");
      input.insertAdjacentElement("afterend", el);
    }
    el.textContent = message;
    input.setAttribute("aria-invalid", "true");
    addDescribedBy(input, el.id);
    if (input.tagName === "SELECT") syncCustomSelect(input);
  }

  function clearInlineError(input) {
    if (!input) return;
    var errorId = input.id + "__inline_error";
    input.classList.remove("is-invalid");
    removeDescribedBy(input, errorId);
    var field = closestField(input);
    var hasServerError = field && field.querySelector(".form-errors:not(.form-errors--client)");
    if (!hasServerError) input.removeAttribute("aria-invalid");
    var el = document.getElementById(errorId);
    if (el) el.remove();
    if (input.tagName === "SELECT") syncCustomSelect(input);
  }

  function isFieldValueMissing(input) {
    if (!input || input.disabled) return false;
    if (input.type === "checkbox" || input.type === "radio") return input.required && !input.checked;
    if (input.tagName === "SELECT") return input.required && !input.value;
    return input.required && !String(input.value || "").trim();
  }

  function validateRequiredField(input, message) {
    if (!input || input.disabled || input.type === "hidden" || input.type === "file") return true;
    if (!isFieldValueMissing(input)) {
      clearInlineError(input);
      return true;
    }
    showInlineError(input, message || REQUIRED_ERROR);
    return false;
  }

  function validateExtraRequiredField(form, selector, message, options) {
    var input = form.querySelector(selector);
    var validateDisabled = options && options.validateDisabled;
    if (!input || (!validateDisabled && input.disabled) || String(input.value || "").trim()) {
      if (input) clearInlineError(input);
      return true;
    }
    showInlineError(input, message);
    return false;
  }

  function validateListingRequiredFields(form) {
    if (!form) return true;
    var ok = true;
    form.querySelectorAll("input[required], textarea[required], select[required]").forEach(function (input) {
      if (!validateRequiredField(input)) ok = false;
    });

    var kind = editorKind(form);
    if (kind === "vehicle" || kind === "motorcycle") {
      if (!validateExtraRequiredField(form, "#id_brand_fk", "Selecciona una marca.")) {
        ok = false;
      } else if (!validateExtraRequiredField(form, "#id_model_fk", "Selecciona un modelo.", { validateDisabled: true })) {
        ok = false;
      }
    }
    if (kind === "electronics") {
      if (!validateExtraRequiredField(form, "#id_brand_fk", "Selecciona una marca.")) {
        ok = false;
      } else if (!validateExtraRequiredField(form, "#id_model_fk", "Selecciona un modelo.", { validateDisabled: true })) {
        ok = false;
      }
    }
    if (kind === "homegoods") {
      var brand = form.querySelector("#id_brand_fk");
      var model = form.querySelector("#id_model_fk");
      if (model && model.value && brand && !brand.value) {
        showInlineError(brand, "Selecciona una marca.");
        ok = false;
      }
    }
    return ok;
  }

  function validatePriceAmountField(form) {
    if (!form) return true;
    var price = form.querySelector("#id_price_amount");
    if (!price || !String(price.value || "").trim()) return true;
    var raw = String(price.value).trim();
    if (!/^\d+$/.test(raw)) {
      showInlineError(price, "Introduce un precio usando solo números.");
      return false;
    }
    var amount = parseInt(raw, 10);
    if (Number.isNaN(amount) || amount <= 0) {
      showInlineError(price, "Ingresa un precio mayor que cero.");
      return false;
    }
    clearInlineError(price);
    return true;
  }

  function validateVehicleNumberFields(form) {
    if (!form || editorKind(form) !== "vehicle") return true;
    var year = form.querySelector("#id_year");
    var mileage = form.querySelector("#id_mileage");
    var ok = true;
    if (year && year.value) {
      var y = parseInt(year.value, 10);
      var max = new Date().getFullYear() + 1;
      if (Number.isNaN(y) || y < 1980 || y > max) {
        showInlineError(year, "Año entre 1980 y " + max + ".");
        ok = false;
      } else {
        clearInlineError(year);
      }
    }
    if (mileage && mileage.value !== "") {
      var km = parseInt(mileage.value, 10);
      if (Number.isNaN(km) || km < 0) {
        showInlineError(mileage, "Km no puede ser negativo.");
        ok = false;
      } else {
        clearInlineError(mileage);
      }
    }
    return ok;
  }

  function initEditorEnhancements(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("form.listing-editor").forEach(function (form) {
      syncDependentModelState(form);
      bindLocationToggle(form);
      syncLocationFields(form);
      if (window.initPropertyMapboxGeocoder) {
        window.initPropertyMapboxGeocoder(form);
      }
      initImagePreview(form);
    });
    markExistingTitles(scope);
  }

  function initImagePreview(form) {
    var images = form.querySelector("#id_images");
    var grid = form.querySelector("#image-preview-grid");
    var count = form.querySelector("#image-dropzone-count");
    var trigger = form.querySelector("[data-image-picker-trigger]");
    var status = form.querySelector("#image-dropzone-status");
    var dropzone = form.querySelector("#image-dropzone");
    if (!images || !grid || !count || images.dataset.previewInit === "1") return;
    images.dataset.previewInit = "1";
    var maxFiles = parseInt(images.dataset.maxFiles || "10", 10);
    var maxBytes = parseInt(images.dataset.maxBytes || "5242880", 10);
    var allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    var removeFields = form.querySelector("#image-remove-fields");
    var imageOrderInput = form.querySelector("#image-order-input");
    var existingJson = form.querySelector("#listing-existing-images-json");
    var objectUrls = [];
    var selectedFiles = Array.prototype.slice.call(images.files || []);
    var existingImages = [];
    var removedExistingIds = {};
    var itemOrder = [];
    var newFileTokens = {};
    var newFileTokenSeq = 0;
    var draggingToken = "";
    var additiveSelectionSupported = typeof DataTransfer !== "undefined";

    if (existingJson) {
      try {
        existingImages = JSON.parse(existingJson.textContent || "[]");
      } catch (error) {
        existingImages = [];
      }
    }
    itemOrder = existingImages.map(function (img) {
      return "existing:" + img.id;
    });

    function setStatus(message, isError) {
      if (!status) return;
      status.textContent = message || "";
      status.hidden = !message;
      status.classList.toggle("is-error", Boolean(isError));
    }

    function clearObjectUrls() {
      objectUrls.forEach(function (url) { URL.revokeObjectURL(url); });
      objectUrls = [];
    }

    function fileKey(file) {
      return [file.name, file.size, file.lastModified].join("::");
    }

    function tokenForFile(file) {
      var key = fileKey(file);
      if (!newFileTokens[key]) {
        newFileTokenSeq += 1;
        newFileTokens[key] = "new:" + newFileTokenSeq;
      }
      return newFileTokens[key];
    }

    function existingToken(id) {
      return "existing:" + id;
    }

    function existingImageForToken(token) {
      if (!token || token.indexOf("existing:") !== 0) return null;
      var id = parseInt(token.replace("existing:", ""), 10);
      if (removedExistingIds[id]) return null;
      for (var i = 0; i < existingImages.length; i += 1) {
        if (parseInt(existingImages[i].id, 10) === id) return existingImages[i];
      }
      return null;
    }

    function selectedFileForToken(token) {
      if (!token || token.indexOf("new:") !== 0) return null;
      for (var i = 0; i < selectedFiles.length; i += 1) {
        if (tokenForFile(selectedFiles[i]) === token) return selectedFiles[i];
      }
      return null;
    }

    function tokenIsActive(token) {
      return Boolean(existingImageForToken(token) || selectedFileForToken(token));
    }

    function ensureOrderIncludesActiveItems() {
      var seen = {};
      itemOrder = itemOrder.filter(function (token) {
        if (seen[token] || !tokenIsActive(token)) return false;
        seen[token] = true;
        return true;
      });
      activeExistingImages().forEach(function (img) {
        var token = existingToken(img.id);
        if (seen[token]) return;
        itemOrder.push(token);
        seen[token] = true;
      });
      selectedFiles.forEach(function (file) {
        var token = tokenForFile(file);
        if (seen[token]) return;
        itemOrder.push(token);
        seen[token] = true;
      });
    }

    function orderSelectedFilesFromItems() {
      var ordered = [];
      var seen = {};
      itemOrder.forEach(function (token) {
        var file = selectedFileForToken(token);
        if (!file) return;
        ordered.push(file);
        seen[token] = true;
      });
      selectedFiles.forEach(function (file) {
        var token = tokenForFile(file);
        if (seen[token]) return;
        ordered.push(file);
      });
      selectedFiles = ordered;
    }

    function updateImageOrderInput() {
      if (!imageOrderInput) return;
      ensureOrderIncludesActiveItems();
      imageOrderInput.value = itemOrder.map(function (token) {
        if (token.indexOf("existing:") === 0) return token.replace("existing:", "");
        return "__new__";
      }).join(",");
    }

    function mergeFiles(newFiles) {
      var seen = {};
      selectedFiles.forEach(function (file) {
        seen[fileKey(file)] = true;
      });
      newFiles.forEach(function (file) {
        var key = fileKey(file);
        if (seen[key]) return;
        selectedFiles.push(file);
        itemOrder.push(tokenForFile(file));
        seen[key] = true;
      });
    }

    function syncSelectedFilesToInput() {
      ensureOrderIncludesActiveItems();
      orderSelectedFilesFromItems();
      if (!additiveSelectionSupported) return false;
      try {
        var dt = new DataTransfer();
        selectedFiles.forEach(function (file) {
          dt.items.add(file);
        });
        images.files = dt.files;
        return true;
      } catch (error) {
        additiveSelectionSupported = false;
        return false;
      }
    }

    function activeExistingImages() {
      return existingImages.filter(function (img) {
        return !removedExistingIds[img.id];
      });
    }

    function activePhotoCount(files) {
      return activeExistingImages().length + files.length;
    }

    function syncRemoveHiddenInputs() {
      if (!removeFields) return;
      removeFields.innerHTML = "";
      Object.keys(removedExistingIds).forEach(function (id) {
        if (!removedExistingIds[id]) return;
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = "remove_images";
        input.value = id;
        removeFields.appendChild(input);
      });
      removeFields.hidden = removeFields.children.length === 0;
    }

    function validateFiles(files) {
      if (activePhotoCount(files) > maxFiles) {
        return "Puedes tener como máximo " + maxFiles + " fotos en el anuncio.";
      }
      for (var i = 0; i < files.length; i += 1) {
        var file = files[i];
        if (file.size > maxBytes) return "Cada imagen debe pesar como máximo 5 MB.";
        var name = (file.name || "").toLowerCase();
        var hasValidExt = /\.(jpe?g|png|webp)$/.test(name);
        if (allowedTypes.indexOf(file.type) === -1 && !hasValidExt) {
          return "Formato no soportado. Sube JPG, PNG o WEBP.";
        }
      }
      return "";
    }

    function appendPreviewTile(parent, options) {
      var wrap = document.createElement("div");
      var img = document.createElement("img");
      var remove = document.createElement("button");
      var controls = document.createElement("div");
      var moveBefore = document.createElement("button");
      var moveAfter = document.createElement("button");
      wrap.className = "image-preview" + (options.isExisting ? " image-preview--existing" : "");
      wrap.draggable = true;
      wrap.dataset.imageToken = options.token;
      img.alt = options.alt;
      img.loading = "lazy";
      img.decoding = "async";
      img.src = options.url;
      remove.type = "button";
      remove.className = "image-preview__remove";
      remove.setAttribute("aria-label", options.removeLabel);
      remove.textContent = "×";
      remove.addEventListener("click", options.onRemove);
      controls.className = "image-preview__order-actions";
      moveBefore.type = "button";
      moveBefore.className = "image-preview__order-btn";
      moveBefore.textContent = "←";
      moveBefore.disabled = !options.canMoveBefore;
      moveBefore.setAttribute("aria-label", options.moveBeforeLabel);
      moveBefore.addEventListener("click", function () {
        moveImageToken(options.token, -1);
      });
      moveAfter.type = "button";
      moveAfter.className = "image-preview__order-btn";
      moveAfter.textContent = "→";
      moveAfter.disabled = !options.canMoveAfter;
      moveAfter.setAttribute("aria-label", options.moveAfterLabel);
      moveAfter.addEventListener("click", function () {
        moveImageToken(options.token, 1);
      });
      controls.appendChild(moveBefore);
      controls.appendChild(moveAfter);
      wrap.addEventListener("dragstart", function (event) {
        draggingToken = options.token;
        wrap.classList.add("is-dragging");
        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", options.token);
        }
      });
      wrap.addEventListener("dragend", function () {
        draggingToken = "";
        wrap.classList.remove("is-dragging");
        syncOrderFromGrid();
        renderPreviews();
      });
      if (options.isCover) {
        var coverBadge = document.createElement("span");
        coverBadge.className = "image-preview__badge image-preview__badge--cover";
        coverBadge.textContent = "Portada";
        wrap.appendChild(coverBadge);
      } else if (options.isExisting) {
        var badge = document.createElement("span");
        badge.className = "image-preview__badge";
        badge.textContent = "Actual";
        wrap.appendChild(badge);
      }
      wrap.appendChild(img);
      wrap.appendChild(controls);
      wrap.appendChild(remove);
      parent.appendChild(wrap);
    }

    function syncOrderFromGrid() {
      if (!grid) return;
      var tokens = Array.prototype.slice.call(grid.querySelectorAll(".image-preview")).map(function (tile) {
        return tile.dataset.imageToken || "";
      }).filter(Boolean);
      itemOrder = tokens;
      ensureOrderIncludesActiveItems();
      orderSelectedFilesFromItems();
      syncSelectedFilesToInput();
      updateImageOrderInput();
    }

    function moveImageToken(token, delta) {
      ensureOrderIncludesActiveItems();
      var index = itemOrder.indexOf(token);
      var target = index + delta;
      if (index < 0 || target < 0 || target >= itemOrder.length) return;
      var swap = itemOrder[target];
      itemOrder[target] = token;
      itemOrder[index] = swap;
      orderSelectedFilesFromItems();
      updateImageOrderInput();
      renderPreviews();
    }

    function renderPreviews() {
      clearObjectUrls();
      ensureOrderIncludesActiveItems();
      orderSelectedFilesFromItems();
      var canSyncInput = syncSelectedFilesToInput();
      if (!canSyncInput) {
        selectedFiles = Array.prototype.slice.call(images.files || []);
      }
      ensureOrderIncludesActiveItems();
      var error = validateFiles(selectedFiles);
      var total = activePhotoCount(selectedFiles);

      syncRemoveHiddenInputs();
      updateImageOrderInput();

      if (!total) {
        count.textContent = "Sin fotos seleccionadas";
        grid.hidden = true;
        grid.innerHTML = "";
        setStatus("", false);
        if (dropzone) dropzone.classList.remove("has-images", "has-error");
        return;
      }

      count.textContent = total === 1 ? "1 foto en el anuncio" : total + " fotos en el anuncio";
      setStatus(
        error || "Arrastra las fotos para ordenar. La primera será la portada del anuncio.",
        Boolean(error)
      );
      if (dropzone) {
        dropzone.classList.add("has-images");
        dropzone.classList.toggle("has-error", Boolean(error));
      }
      grid.hidden = false;
      grid.innerHTML = "";

      itemOrder.forEach(function (token, index) {
        var existing = existingImageForToken(token);
        var file = selectedFileForToken(token);
        if (existing) {
          appendPreviewTile(grid, {
            token: token,
            isExisting: true,
            isCover: index === 0,
            canMoveBefore: index > 0,
            canMoveAfter: index < itemOrder.length - 1,
            url: existing.url,
            alt: "Foto actual " + (index + 1),
            removeLabel: "Quitar foto actual " + (index + 1),
            moveBeforeLabel: "Mover foto actual " + (index + 1) + " hacia la izquierda",
            moveAfterLabel: "Mover foto actual " + (index + 1) + " hacia la derecha",
            onRemove: function () {
              removedExistingIds[existing.id] = true;
              itemOrder = itemOrder.filter(function (candidate) {
                return candidate !== token;
              });
              renderPreviews();
            },
          });
          return;
        }
        if (!file) return;
        var url = URL.createObjectURL(file);
        objectUrls.push(url);
        appendPreviewTile(grid, {
          token: token,
          isExisting: false,
          isCover: index === 0,
          canMoveBefore: index > 0,
          canMoveAfter: index < itemOrder.length - 1,
          url: url,
          alt: "Nueva foto " + (index + 1),
          removeLabel: "Quitar nueva foto " + (index + 1),
          moveBeforeLabel: "Mover nueva foto " + (index + 1) + " hacia la izquierda",
          moveAfterLabel: "Mover nueva foto " + (index + 1) + " hacia la derecha",
          onRemove: function () {
            selectedFiles = selectedFiles.filter(function (candidate) {
              return tokenForFile(candidate) !== token;
            });
            itemOrder = itemOrder.filter(function (candidate) {
              return candidate !== token;
            });
            renderPreviews();
          },
        });
      });
    }

    grid.addEventListener("dragover", function (event) {
      if (!draggingToken) return;
      var target = event.target.closest ? event.target.closest(".image-preview") : null;
      if (!target || target.parentNode !== grid || target.dataset.imageToken === draggingToken) return;
      event.preventDefault();
      var dragged = null;
      Array.prototype.slice.call(grid.querySelectorAll(".image-preview")).some(function (tile) {
        if (tile.dataset.imageToken !== draggingToken) return false;
        dragged = tile;
        return true;
      });
      if (!dragged) return;
      var rect = target.getBoundingClientRect();
      var after = event.clientX > rect.left + rect.width / 2;
      grid.insertBefore(dragged, after ? target.nextSibling : target);
    });

    grid.addEventListener("drop", function (event) {
      if (!draggingToken) return;
      event.preventDefault();
      syncOrderFromGrid();
      renderPreviews();
    });

    if (trigger) {
      trigger.addEventListener("click", function () {
        images.click();
      });
    }
    images.addEventListener("change", function () {
      var incomingFiles = Array.prototype.slice.call(images.files || []);
      if (additiveSelectionSupported) {
        mergeFiles(incomingFiles);
      } else {
        selectedFiles = incomingFiles;
        itemOrder = activeExistingImages().map(function (img) {
          return existingToken(img.id);
        }).concat(selectedFiles.map(tokenForFile));
      }
      renderPreviews();
    });
    form.addEventListener("submit", function (event) {
      syncOrderFromGrid();
      syncSelectedFilesToInput();
      syncRemoveHiddenInputs();
      updateImageOrderInput();
      var error = validateFiles(selectedFiles);
      if (!error) return;
      event.preventDefault();
      setStatus(error, true);
      if (dropzone) {
        dropzone.classList.add("has-error");
        dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, true);
    window.addEventListener("pagehide", clearObjectUrls, { once: true });
    renderPreviews();
  }

  function boot() {
    initListingControls(document);
    initEditorEnhancements(document);
    closeBrowseFiltersOnMobile(document);

    document.addEventListener("click", function (event) {
      if (!event.target.closest(".custom-select")) {
        closeAllCustomSelects();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeAllCustomSelects();
      if (isDigitsOnlyInput(event.target) && !shouldAllowDigitKey(event)) {
        event.preventDefault();
      }
    });

    document.addEventListener("beforeinput", function (event) {
      if (!isDigitsOnlyInput(event.target)) return;
      if (!event.data || /^\d+$/.test(event.data)) return;
      event.preventDefault();
    }, true);

    document.addEventListener("paste", function (event) {
      var target = event.target;
      if (!isDigitsOnlyInput(target)) return;
      var clipboard = event.clipboardData || window.clipboardData;
      var text = clipboard ? clipboard.getData("text") : "";
      if (/^\d+$/.test(text)) return;
      event.preventDefault();
      var digits = digitsOnlyValue(text);
      if (!digits) return;
      var start = typeof target.selectionStart === "number" ? target.selectionStart : target.value.length;
      var end = typeof target.selectionEnd === "number" ? target.selectionEnd : start;
      target.value = target.value.slice(0, start) + digits + target.value.slice(end);
      target.dispatchEvent(new Event("input", { bubbles: true }));
    });

    document.addEventListener("input", function (event) {
      sanitizeDigitsOnlyInput(event.target);
      if (event.target && event.target.id === "id_title") {
        event.target.dataset.userEdited = "1";
      }
      var form = editorFor(event.target);
      if (form && event.target.matches && event.target.matches("input, textarea, select") && !isFieldValueMissing(event.target)) {
        clearInlineError(event.target);
      }
      if (event.target && event.target.id === "id_zone") syncPropertyTitle(form);
    }, true);

    document.addEventListener("change", function (event) {
      var target = event.target;
      var form = editorFor(target);
      if (form && target.matches && target.matches("input, textarea, select") && !isFieldValueMissing(target)) {
        clearInlineError(target);
      }
      handleItemTypeChange(target);
      handleBrandChange(target);
      if (target && target.id === "id_add_location") {
        syncLocationFields(form);
      }
      if (target && (target.id === "id_brand_fk" || target.id === "id_model_fk" || target.id === "id_year")) {
        syncVehicleTitle(form);
      }
      if (target && (target.id === "id_property_type" || target.id === "id_rooms" || target.id === "id_zone")) {
        syncPropertyTitle(form);
      }
    }, true);

    document.addEventListener("blur", function (event) {
      var target = event.target;
      if (!target) return;
      var form = editorFor(target);
      if (target.id === "id_price_amount") {
        validatePriceAmountField(form);
        return;
      }
      if (target.id !== "id_year" && target.id !== "id_mileage") return;
      validateVehicleNumberFields(form);
    }, true);

    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (!form || !form.matches) return;
      if (form.matches(".browse-filter-form")) {
        form.querySelectorAll(DIGITS_SELECTOR).forEach(sanitizeDigitsOnlyInput);
        return;
      }
      if (!form.matches("form.listing-editor")) return;
      form.querySelectorAll(DIGITS_SELECTOR).forEach(sanitizeDigitsOnlyInput);
      var model = form.querySelector("#id_model_fk");
      var requiredOk = validateListingRequiredFields(form);
      var priceOk = validatePriceAmountField(form);
      var numbersOk = validateVehicleNumberFields(form);
      if (requiredOk && priceOk && numbersOk) {
        if (model) model.disabled = false;
        return;
      }
      event.preventDefault();
      var first = form.querySelector(".is-invalid");
      if (first && first.focus) first.focus({ preventScroll: false });
    }, true);

    document.body.addEventListener("htmx:load", function (event) {
      initListingControls(event.target || document);
      initEditorEnhancements(event.target || document);
      closeBrowseFiltersOnMobile(event.target || document);
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
      var target = getSwapTarget(event);
      if (target && target.matches && target.matches("select.form-control")) {
        syncCustomSelect(target);
      }
      if (target && target.id === "id_model_fk") {
        var form = editorFor(target);
        syncDependentModelState(form);
        syncVehicleTitle(form);
      }
      if (target && target.id === "id_brand_fk") {
        syncCustomSelect(target);
        var brandForm = editorFor(target);
        syncDependentModelState(brandForm);
        refreshModelsForCurrentBrand(brandForm);
      }
      initListingControls(target || document);
      initEditorEnhancements(target || document);
      closeBrowseFiltersOnMobile(target || document);
    });

    document.body.addEventListener("htmx:afterSettle", function (event) {
      var target = event.detail && event.detail.elt ? event.detail.elt : event.target;
      initListingControls(target || document);
      initEditorEnhancements(target || document);
      closeBrowseFiltersOnMobile(target || document);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
