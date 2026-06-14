(function () {
  function getGap(track) {
    var styles = window.getComputedStyle(track);
    return parseFloat(styles.columnGap || styles.gap || "0") || 0;
  }

  function getStep(track) {
    var slide = track.querySelector(".listing-detail__similar-slide");
    if (!slide) return track.clientWidth;
    return slide.getBoundingClientRect().width + getGap(track);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(value, max));
  }

  function nearestSlideLeft(track) {
    var slides = Array.prototype.slice.call(track.querySelectorAll(".listing-detail__similar-slide"));
    var current = track.scrollLeft;
    var nearest = current;
    var nearestDistance = Infinity;

    slides.forEach(function (slide) {
      var left = slide.offsetLeft - track.offsetLeft;
      var distance = Math.abs(left - current);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearest = left;
      }
    });

    return nearest;
  }

  function initCarousel(root) {
    var track = root.querySelector("[data-carousel-track]");
    var prev = root.querySelector("[data-carousel-prev]");
    var next = root.querySelector("[data-carousel-next]");
    if (!track) return;

    var dragging = false;
    var dragged = false;
    var startX = 0;
    var startScrollLeft = 0;
    var suppressClick = false;
    var rafId = null;

    function getMaxScroll() {
      return Math.max(0, track.scrollWidth - track.clientWidth);
    }

    function update() {
      var maxScroll = getMaxScroll();
      var hasOverflow = maxScroll > 2;
      var scrollLeft = clamp(track.scrollLeft, 0, maxScroll);

      root.classList.toggle("has-carousel-overflow", hasOverflow);
      if (prev) prev.disabled = !hasOverflow || scrollLeft <= 2;
      if (next) next.disabled = !hasOverflow || scrollLeft >= maxScroll - 2;
    }

    function requestUpdate() {
      if (rafId) return;
      rafId = window.requestAnimationFrame(function () {
        rafId = null;
        update();
      });
    }

    function scrollBySlide(direction) {
      track.scrollBy({
        left: getStep(track) * direction,
        behavior: "smooth",
      });
    }

    function finishDrag() {
      if (!dragging) return;
      dragging = false;
      track.classList.remove("is-dragging");

      if (dragged) {
        suppressClick = true;
        track.scrollTo({
          left: nearestSlideLeft(track),
          behavior: "smooth",
        });
        window.setTimeout(function () {
          suppressClick = false;
        }, 120);
      }
    }

    if (prev) {
      prev.addEventListener("click", function () {
        scrollBySlide(-1);
      });
    }

    if (next) {
      next.addEventListener("click", function () {
        scrollBySlide(1);
      });
    }

    track.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        scrollBySlide(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        scrollBySlide(1);
      }
    });

    track.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || event.target.closest("button, input, select, textarea")) return;
      dragging = true;
      dragged = false;
      startX = event.clientX;
      startScrollLeft = track.scrollLeft;
      track.setPointerCapture(event.pointerId);
    });

    track.addEventListener("pointermove", function (event) {
      if (!dragging) return;
      var deltaX = event.clientX - startX;
      if (Math.abs(deltaX) > 4) {
        dragged = true;
        track.classList.add("is-dragging");
      }
      if (!dragged) return;
      event.preventDefault();
      track.scrollLeft = startScrollLeft - deltaX;
    });

    track.addEventListener("pointerup", finishDrag);
    track.addEventListener("pointercancel", finishDrag);
    track.addEventListener("lostpointercapture", finishDrag);

    track.addEventListener(
      "click",
      function (event) {
        if (!suppressClick) return;
        event.preventDefault();
        event.stopPropagation();
      },
      true
    );

    track.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);

    if (window.ResizeObserver) {
      new window.ResizeObserver(requestUpdate).observe(track);
    }

    update();
  }

  function boot() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-listing-carousel]"), initCarousel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
