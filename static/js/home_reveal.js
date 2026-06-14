(function () {
  var REVEAL_SELECTOR = "[data-home-reveal]";
  var LAUNCH_MARQUEE_SELECTOR = "[data-home-launch-marquee]";
  var LAUNCH_MARQUEE_READY_CLASS = "is-home-marquee-ready";
  var LAUNCH_MARQUEE_QUERY = "(max-width: 899px)";
  var REVEALED_CLASS = "is-home-revealed";
  var READY_CLASS = "home-reveal-ready";
  var mobileMarquee = window.matchMedia && window.matchMedia(LAUNCH_MARQUEE_QUERY);
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

  function initLaunchMarquee() {
    var marquees = Array.prototype.slice.call(document.querySelectorAll(LAUNCH_MARQUEE_SELECTOR));
    if (!marquees.length) return;

    marquees.forEach(function (marquee) {
      var clones = Array.prototype.slice.call(marquee.querySelectorAll("[data-marquee-clone]"));
      if (!mobileMarquee || !mobileMarquee.matches || reducedMotion) {
        clones.forEach(function (clone) {
          clone.remove();
        });
        marquee.classList.remove(LAUNCH_MARQUEE_READY_CLASS);
        return;
      }

      if (marquee.classList.contains(LAUNCH_MARQUEE_READY_CLASS)) return;

      var items = Array.prototype.slice.call(marquee.children).filter(function (item) {
        return !item.hasAttribute("data-marquee-clone");
      });
      items.forEach(function (item) {
        var clone = item.cloneNode(true);
        clone.setAttribute("aria-hidden", "true");
        clone.setAttribute("data-marquee-clone", "");
        marquee.appendChild(clone);
      });

      marquee.classList.add(LAUNCH_MARQUEE_READY_CLASS);
    });
  }

  if (mobileMarquee) {
    if (mobileMarquee.addEventListener) {
      mobileMarquee.addEventListener("change", initLaunchMarquee);
    } else if (mobileMarquee.addListener) {
      mobileMarquee.addListener(initLaunchMarquee);
    }
  }

  function boot() {
    var sections = Array.prototype.slice.call(document.querySelectorAll(REVEAL_SELECTOR));
    initLaunchMarquee();

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
