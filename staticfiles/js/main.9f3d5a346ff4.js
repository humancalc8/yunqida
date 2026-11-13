(function () {
  'use strict';

  // Header: transparent over the hero on the home page, solid elsewhere or once scrolled
  var header = document.getElementById('header');
  var isHome = document.body.classList.contains('page-home');
  function onScroll() {
    if (!isHome) { header.classList.add('solid'); return; }
    header.classList.toggle('scrolled', window.scrollY > 40);
  }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // Mobile menu
  var btn = document.getElementById('menuBtn');
  var nav = document.getElementById('nav');
  if (btn && nav) {
    btn.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open);
      btn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      if (isHome && open) header.classList.add('scrolled');
      else onScroll();
    });
    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') { nav.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { nav.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
    });
  }

  // Hero video: pause/play control, and respect reduced-motion
  var video = document.getElementById('heroVideo');
  var toggle = document.getElementById('videoToggle');
  if (video && toggle) {
    function setState(paused) {
      toggle.setAttribute('aria-pressed', paused);
      toggle.setAttribute('aria-label', paused ? 'Play background video' : 'Pause background video');
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { video.pause(); setState(true); }
    toggle.addEventListener('click', function () {
      if (video.paused) { video.play(); setState(false); } else { video.pause(); setState(true); }
    });
  }
})();
