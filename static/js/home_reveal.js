(function () {
  var REVEAL_SELECTOR = "[data-home-reveal]";
  var REVEALED_CLASS = "is-home-revealed";
  var READY_CLASS = "home-reveal-ready";
  var reducedMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function reveal(element) {
    element.classList.add(REVEALED_CLASS);
  }

  function isInitiallyVisible(element) {
    var rect = element.getBoundingClientRect();
    var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    return rect.top < viewportHeight * 0.92;
  }

  function boot() {
    var sections = Array.prototype.slice.call(document.querySelectorAll(REVEAL_SELECTOR));
    if (!sections.length) return;

    if (reducedMotion || !("IntersectionObserver" in window)) {
      sections.forEach(reveal);
      return;
    }

    sections.filter(isInitiallyVisible).forEach(reveal);
    document.documentElement.classList.add(READY_CLASS);

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        reveal(entry.target);
        observer.unobserve(entry.target);
      });
    }, {
      rootMargin: "0px 0px -12% 0px",
      threshold: 0.12,
    });

    sections.forEach(function (section) {
      if (!section.classList.contains(REVEALED_CLASS)) {
        observer.observe(section);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
