(function () {
  var SELECT_SELECTOR = ".listing-editor select.form-control, .browse-filter-form select.form-control";
  var DIGITS_SELECTOR = "[data-digits-only='true']";
  var OPEN_CLASS = "is-open";
  var SELECT_INIT = "customSelectInit";
  var SELECT_INIT_VERSION = "2";
  var SEARCH_MAX_LENGTH = 48;
  var SEARCH_MIN_OPTIONS = 5;

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
    var location = form.querySelector("#id_location");
    if (!title || !type || title.dataset.userEdited === "1") return;
    var typeLabel = getSelectText(type);
    var roomCount = rooms && rooms.value ? String(rooms.value).trim() : "";
    var rawLocation = location && location.value ? String(location.value).trim() : "";
    var shortLocation = rawLocation ? (rawLocation.split(",")[0] || rawLocation).trim() : "";
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
      el.className = "form-errors";
      el.setAttribute("role", "alert");
      el.setAttribute("aria-live", "polite");
      input.insertAdjacentElement("afterend", el);
    }
    el.textContent = message;
  }

  function clearInlineError(input) {
    if (!input) return;
    input.classList.remove("is-invalid");
    var el = document.getElementById(input.id + "__inline_error");
    if (el) el.remove();
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
    var existingCount = parseInt(images.dataset.existingCount || "0", 10);
    var allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    var objectUrls = [];
    var selectedFiles = Array.prototype.slice.call(images.files || []);
    var additiveSelectionSupported = typeof DataTransfer !== "undefined";

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

    function mergeFiles(newFiles) {
      var seen = {};
      selectedFiles.forEach(function (file) {
        seen[fileKey(file)] = true;
      });
      newFiles.forEach(function (file) {
        var key = fileKey(file);
        if (seen[key]) return;
        selectedFiles.push(file);
        seen[key] = true;
      });
    }

    function syncSelectedFilesToInput() {
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

    function validateFiles(files) {
      if (existingCount + files.length > maxFiles) {
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

    function renderPreviews() {
      clearObjectUrls();
      var canSyncInput = syncSelectedFilesToInput();
      if (!canSyncInput) {
        selectedFiles = Array.prototype.slice.call(images.files || []);
      }
      var error = validateFiles(selectedFiles);
      if (!selectedFiles.length) {
        count.textContent = "Sin fotos seleccionadas";
        grid.hidden = true;
        grid.innerHTML = "";
        setStatus("", false);
        if (dropzone) dropzone.classList.remove("has-images", "has-error");
        return;
      }
      count.textContent = selectedFiles.length === 1 ? "1 foto seleccionada" : selectedFiles.length + " fotos seleccionadas";
      setStatus(error || "Fotos listas. Puedes seguir agregando de a una o guardar el anuncio.", Boolean(error));
      if (dropzone) {
        dropzone.classList.add("has-images");
        dropzone.classList.toggle("has-error", Boolean(error));
      }
      grid.hidden = false;
      grid.innerHTML = "";
      selectedFiles.slice(0, maxFiles).forEach(function (file, index) {
        var url = URL.createObjectURL(file);
        objectUrls.push(url);
        var wrap = document.createElement("div");
        var img = document.createElement("img");
        var remove = document.createElement("button");
        wrap.className = "image-preview";
        img.alt = "Vista previa " + (index + 1);
        img.loading = "lazy";
        img.decoding = "async";
        img.src = url;
        remove.type = "button";
        remove.className = "image-preview__remove";
        remove.setAttribute("aria-label", "Quitar foto " + (index + 1));
        remove.textContent = "×";
        remove.addEventListener("click", function () {
          selectedFiles.splice(index, 1);
          renderPreviews();
        });
        wrap.appendChild(img);
        wrap.appendChild(remove);
        grid.appendChild(wrap);
      });
    }

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
      }
      renderPreviews();
    });
    form.addEventListener("submit", function (event) {
      syncSelectedFilesToInput();
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
      if (event.target && event.target.id === "id_location") syncPropertyTitle(form);
    }, true);

    document.addEventListener("change", function (event) {
      var target = event.target;
      var form = editorFor(target);
      handleItemTypeChange(target);
      handleBrandChange(target);
      if (target && (target.id === "id_brand_fk" || target.id === "id_model_fk" || target.id === "id_year")) {
        syncVehicleTitle(form);
      }
      if (target && (target.id === "id_property_type" || target.id === "id_rooms" || target.id === "id_location")) {
        syncPropertyTitle(form);
      }
    }, true);

    document.addEventListener("blur", function (event) {
      var target = event.target;
      if (!target || (target.id !== "id_year" && target.id !== "id_mileage")) return;
      validateVehicleNumberFields(editorFor(target));
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
      if (model) model.disabled = false;
      if (validateVehicleNumberFields(form)) return;
      event.preventDefault();
      var first = form.querySelector(".is-invalid");
      if (first && first.focus) first.focus({ preventScroll: false });
    }, true);

    document.body.addEventListener("htmx:load", function (event) {
      initListingControls(event.target || document);
      initEditorEnhancements(event.target || document);
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
    });

    document.body.addEventListener("htmx:afterSettle", function (event) {
      var target = event.detail && event.detail.elt ? event.detail.elt : event.target;
      initListingControls(target || document);
      initEditorEnhancements(target || document);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
