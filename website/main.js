(function () {
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('reveal--visible'); });
  } else {
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('reveal--visible'); });
    } else {
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('reveal--visible');
            obs.unobserve(entry.target);
          }
        });
      }, { rootMargin: '0px 0px -5% 0px', threshold: 0.06 });
      document.querySelectorAll('.reveal').forEach(function (el) { obs.observe(el); });
    }
  }
  var lightbox = document.getElementById('lightbox');
  var lightboxImg = lightbox.querySelector('.lightbox-img');
  var backdrop = lightbox.querySelector('.lightbox-backdrop');
  var flyEase = 'cubic-bezier(0.22, 1, 0.36, 1)';
  var flyDurationMs = 520;
  var activeFlyGhost = null;
  var activeThumbImg = null;
  var lastOpenTrigger = null;
  var isCloseFlying = false;
  function removeGhost() {
    if (activeFlyGhost && activeFlyGhost.parentNode) {
      activeFlyGhost.parentNode.removeChild(activeFlyGhost);
    }
    activeFlyGhost = null;
    if (activeThumbImg) {
      activeThumbImg.style.opacity = '';
      activeThumbImg = null;
    }
    lightbox.classList.remove('lightbox--fly-surface');
  }
  function fitRectInViewport(nw, nh, fallbackW, fallbackH) {
    var vv = window.visualViewport;
    var vhPx = vv && vv.height ? vv.height : window.innerHeight;
    var maxW = Math.max(80, window.innerWidth - 32);
    var maxH = Math.max(80, Math.floor(vhPx * 0.9));
    var w = nw > 0 ? nw : fallbackW;
    var h = nh > 0 ? nh : fallbackH;
    var ratio = Math.min(maxW / w, maxH / h, 1);
    var rw = w * ratio;
    var rh = h * ratio;
    return {
      w: rw,
      h: rh,
      left: (window.innerWidth - rw) / 2,
      top: (window.innerHeight - rh) / 2
    };
  }
  function openLightboxSimple(src, alt) {
    removeGhost();
    lastOpenTrigger = null;
    isCloseFlying = false;
    lightbox.classList.remove('fly-active', 'lightbox--fly-surface');
    lightboxImg.src = src;
    lightboxImg.alt = alt || '';
    lightbox.hidden = false;
    document.body.classList.add('lightbox-open');
    lightbox.classList.add('backdrop-visible');
    backdrop.focus();
  }
  function openLightboxFromTrigger(btn) {
    var src = btn.getAttribute('data-lightbox-src');
    var alt = btn.getAttribute('data-lightbox-alt') || '';
    var thumbImg = btn.querySelector('img');
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      openLightboxSimple(src, alt);
      return;
    }
    removeGhost();
    isCloseFlying = false;
    function startFlip() {
      lastOpenTrigger = btn;
      var first = thumbImg.getBoundingClientRect();
      var nw = thumbImg.naturalWidth;
      var nh = thumbImg.naturalHeight;
      var last = fitRectInViewport(nw, nh, first.width, first.height);
      var lastW = last.w;
      var lastH = last.h;
      var lastLeft = last.left;
      var lastTop = last.top;
      var dx = first.left - lastLeft;
      var dy = first.top - lastTop;
      var sx = first.width / lastW;
      var sy = first.height / lastH;
      var ghost = document.createElement('img');
      ghost.src = src;
      ghost.alt = alt || '';
      ghost.className = 'lightbox-fly-img';
      ghost.decoding = 'sync';
      var brStart = getComputedStyle(thumbImg).borderRadius || '14px';
      var brEnd = getComputedStyle(document.documentElement).getPropertyValue('--radius-shot').trim() || '14px';
      ghost.style.position = 'fixed';
      ghost.style.zIndex = '260';
      ghost.style.left = lastLeft + 'px';
      ghost.style.top = lastTop + 'px';
      ghost.style.width = lastW + 'px';
      ghost.style.height = lastH + 'px';
      ghost.style.objectFit = 'contain';
      ghost.style.borderRadius = brStart;
      ghost.style.boxSizing = 'border-box';
      ghost.style.border = '1px solid rgba(255, 255, 255, 0.12)';
      ghost.style.boxShadow = '0 24px 80px rgba(0, 0, 0, 0.65)';
      ghost.style.pointerEvents = 'none';
      ghost.style.willChange = 'transform';
      ghost.style.transformOrigin = '0 0';
      thumbImg.style.opacity = '0';
      activeThumbImg = thumbImg;
      document.body.appendChild(ghost);
      activeFlyGhost = ghost;
      lightboxImg.removeAttribute('src');
      lightboxImg.alt = '';
      lightbox.hidden = false;
      lightbox.classList.add('fly-active');
      document.body.classList.add('lightbox-open');
      ghost.getBoundingClientRect();
      ghost.style.transition = 'none';
      ghost.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(' + sx + ',' + sy + ')';
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          ghost.style.borderRadius = brEnd;
          ghost.style.transition = 'transform ' + flyDurationMs + 'ms ' + flyEase;
          ghost.style.transform = 'translate(0,0) scale(1,1)';
          lightbox.classList.add('backdrop-visible');
        });
      });
      var done = false;
      function cleanup() {
        if (done) return;
        done = true;
        ghost.removeEventListener('transitionend', onTe);
        ghost.style.willChange = 'auto';
        lightbox.classList.remove('fly-active');
        lightbox.classList.add('lightbox--fly-surface');
        thumbImg.style.opacity = '';
        activeThumbImg = null;
        backdrop.focus();
      }
      function onTe(e) {
        if (e.propertyName !== 'transform') return;
        cleanup();
      }
      ghost.addEventListener('transitionend', onTe);
      window.setTimeout(cleanup, flyDurationMs + 100);
    }
    if (thumbImg.naturalWidth > 0) {
      startFlip();
    } else if (thumbImg.complete) {
      startFlip();
    } else {
      thumbImg.addEventListener('load', function () {
        startFlip();
      }, { once: true });
    }
  }
  function closeLightboxImmediate() {
    removeGhost();
    isCloseFlying = false;
    lightbox.classList.remove('backdrop-visible', 'fly-active', 'lightbox--fly-surface');
    lightbox.hidden = true;
    lightboxImg.removeAttribute('src');
    lightboxImg.alt = '';
    document.body.classList.remove('lightbox-open');
    lastOpenTrigger = null;
  }
  function closeLightbox() {
    if (lightbox.hidden) return;
    if (isCloseFlying) {
      closeLightboxImmediate();
      return;
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !lastOpenTrigger) {
      closeLightboxImmediate();
      return;
    }
    var thumbImg = lastOpenTrigger.querySelector('img');
    if (!thumbImg) {
      closeLightboxImmediate();
      return;
    }
    if (!activeFlyGhost || !activeFlyGhost.parentNode) {
      closeLightboxImmediate();
      return;
    }
    var ghost = activeFlyGhost;
    var from = ghost.getBoundingClientRect();
    var to = thumbImg.getBoundingClientRect();
    if (from.width < 2 || from.height < 2 || to.width < 2 || to.height < 2) {
      closeLightboxImmediate();
      return;
    }
    isCloseFlying = true;
    var brTo = getComputedStyle(thumbImg).borderRadius || '14px';
    thumbImg.style.opacity = '0';
    activeThumbImg = thumbImg;
    lightbox.classList.add('fly-active');
    lightbox.classList.remove('backdrop-visible');
    var dx = to.left - from.left;
    var dy = to.top - from.top;
    var sx = to.width / from.width;
    var sy = to.height / from.height;
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        ghost.style.borderRadius = brTo;
        ghost.style.transition = 'transform ' + flyDurationMs + 'ms ' + flyEase;
        ghost.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(' + sx + ',' + sy + ')';
      });
    });
    var doneClose = false;
    function finishCloseFly() {
      if (doneClose) return;
      doneClose = true;
      ghost.removeEventListener('transitionend', onCloseTe);
      ghost.style.willChange = 'auto';
      closeLightboxImmediate();
    }
    function onCloseTe(e) {
      if (e.propertyName !== 'transform') return;
      finishCloseFly();
    }
    ghost.addEventListener('transitionend', onCloseTe);
    window.setTimeout(finishCloseFly, flyDurationMs + 120);
  }
  document.querySelectorAll('.shot-trigger').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openLightboxFromTrigger(btn);
    });
  });
  backdrop.addEventListener('click', closeLightbox);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !lightbox.hidden) closeLightbox();
  });
})();
