/* CarbonLens theme motion
   Uses Motion (motion.dev, vanilla build in /static/vendor/motion.js).
   Presentation only: if Motion fails to load the page still works. */
(function () {
  'use strict';
  const M = window.Motion || null;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const can = !!M && !reduce;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  window.CL_CAN_ANIMATE = can;

  /* ---------- swap form (sign in / sign up) ---------- */
  window.swapAnimate = function (el, change) {
    if (!can || !el) { change(); return Promise.resolve(); }
    return M.animate(el, { opacity: 0, y: -30, scale: 0.97, filter: 'blur(4px)' }, { duration: 0.22, ease: 'easeIn' }).finished.then(() => {
      change();
      return M.animate(el, { opacity: [0, 1], y: [-30, 0], scale: [0.97, 1], filter: ['blur(4px)', 'blur(0px)'] }, { duration: 0.3, ease: 'easeOut' }).finished;
    });
  };

  /* ---------- modals spring in ---------- */
  function springModal(ov) {
    if (!can) return;
    const card = ov.querySelector('.modal, .forgot-card');
    M.animate(ov, { opacity: [0, 1] }, { duration: 0.2 });
    if (card) M.animate(card, { opacity: [0, 1], scale: [0.9, 1], y: [20, 0] }, { type: M.spring, stiffness: 320, damping: 26 });
  }
  const mo = new MutationObserver(list => list.forEach(m => {
    const was = (m.oldValue || '').split(' ').includes('show');
    if (m.target.classList.contains('show') && !was) springModal(m.target);
  }));

  /* ---------- assistant panel ---------- */
  window.chatAnimateOpen = function (panel) {
    if (!can || !panel) return;
    M.animate(panel, { opacity: [0, 1], scale: [0.85, 1], y: [24, 0], filter: ['blur(6px)', 'blur(0px)'] }, { type: M.spring, stiffness: 300, damping: 26 });
    M.animate($$('#clChatBody > *', panel).slice(-4), { opacity: [0, 1], y: [10, 0] }, { duration: 0.35, delay: M.stagger(0.05, { startDelay: 0.12 }) });
    M.animate($$('.ch-sugg button', panel), { opacity: [0, 1], scale: [0.9, 1] }, { duration: 0.3, delay: M.stagger(0.05, { startDelay: 0.25 }) });
  };
  window.chatAnimateClose = function (panel, done) {
    if (!can || !panel) { done(); return; }
    M.animate(panel, { opacity: 0, scale: 0.9, y: 20 }, { duration: 0.18, ease: 'easeIn' }).finished.then(done);
  };
  window.chatAnimateMsg = function (el, fromUser) {
    if (!can || !el) return;
    M.animate(el, { opacity: [0, 1], y: [12, 0], x: [fromUser ? 14 : -14, 0], scale: [0.96, 1] }, { type: M.spring, stiffness: 380, damping: 28 });
  };

  /* ---------- press feedback ---------- */
  function wirePress() {
    if (!can || !M.press) return;
    M.press('.swap-submit, .btn-cta, .btn-primary, .cx-pill, #clChatSend', el => {
      M.animate(el, { scale: 0.96 }, { type: M.spring, stiffness: 400, damping: 25 });
      return () => M.animate(el, { scale: 1 }, { type: M.spring, stiffness: 400, damping: 25 });
    });
  }

  /* ---------- scroll reveal ---------- */
  function reveal(root) {
    const els = $$('.rv:not(.in)', root);
    if (!('IntersectionObserver' in window)) { els.forEach(e => e.classList.add('in')); return; }
    const io = new IntersectionObserver(entries => entries.forEach(e => {
      if (!e.isIntersecting) return;
      const sibs = Array.from(e.target.parentElement ? e.target.parentElement.children : []).filter(x => x.classList.contains('rv'));
      e.target.style.transitionDelay = (Math.max(0, sibs.indexOf(e.target)) * 70) + 'ms';
      e.target.classList.add('in');
      io.unobserve(e.target);
    }), { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });
    els.forEach(e => io.observe(e));
  }
  window.revealIn = reveal;

  /* ---------- hero: cotton to carbon ---------- */
  let heroPlayed = false;
  window.playHero = function () {
    if (!$('#hxArt') || heroPlayed) return;
    heroPlayed = true;
    const donut = (id, frac, delay) => {
      const c = document.getElementById(id); if (!c) return;
      const len = parseFloat(c.getAttribute('stroke-dasharray')), to = len * (1 - frac);
      if (!can) { c.setAttribute('stroke-dashoffset', to); return; }
      M.animate(c, { strokeDashoffset: [len, to] }, { duration: 1.3, delay, ease: [0.2, 0.8, 0.2, 1] });
    };
    $$('#ilBars .ilBar rect, #ilColsB rect').forEach(r => { r.style.transformBox = 'fill-box'; r.style.transformOrigin = '50% 100%'; });
    if (!can) { donut('ilDonutB', .62, 0); donut('ilDonutB2', .2, 0); donut('ilDonutC', .74, 0); return; }
    M.animate(['.hx-eyebrow', '.hx-title', '.hx-lead', '.hx-cta'].map(s => $(s)).filter(Boolean),
      { opacity: [0, 1], y: [24, 0], filter: ['blur(6px)', 'blur(0px)'] }, { duration: 0.7, delay: M.stagger(0.09), ease: [0.2, 0.8, 0.2, 1] });
    if ($('.hx-rule')) M.animate('.hx-rule', { scaleX: [0, 1] }, { duration: 0.9, delay: 0.35, ease: [0.2, 0.8, 0.2, 1] });
    M.animate('.hx-blob-top', { opacity: [0, 1], scale: [0.94, 1] }, { duration: 1.1, ease: [0.2, 0.8, 0.2, 1] });
    M.animate('#ilBlob', { opacity: [0, 1], scale: [0.86, 1] }, { duration: 0.9, ease: [0.2, 0.8, 0.2, 1] });
    M.animate('#ilLeaves', { opacity: [0, 1] }, { duration: 1, delay: 0.3 });
    M.animate('.ill-in', { opacity: [0, 1], y: [30, 0], filter: ['blur(4px)', 'blur(0px)'] }, { duration: 0.6, delay: M.stagger(0.14, { startDelay: 0.35 }), ease: 'easeOut' });
    M.animate('#ilBars .ilBar rect', { scaleY: [0, 1] }, { type: M.spring, stiffness: 180, damping: 18, delay: M.stagger(0.05, { startDelay: 0.75 }) });
    M.animate('#ilColsB rect', { scaleY: [0, 1] }, { type: M.spring, stiffness: 180, damping: 16, delay: M.stagger(0.1, { startDelay: 1.0 }) });
    M.animate('#ilPlant', { opacity: [0, 1], y: [30, 0] }, { duration: 0.8, delay: 0.55, ease: 'easeOut' });
    M.animate('#ilPlus', { scale: [0, 1] }, { type: M.spring, stiffness: 300, damping: 14, delay: 1.3 });
    donut('ilDonutB', .62, 0.9); donut('ilDonutB2', .2, 1.1); donut('ilDonutC', .74, 1.0);
  };

  /* ---------- emission-source flow: six sources into one farm-gate total ---------- */
  let flowPlayed = false;
  function playFlow() {
    const svg = $('#flowSvg'); if (!svg || flowPlayed) return;
    flowPlayed = true;
    if (!can) return;
    M.animate('#flowCore', { opacity: [0, 1], scale: [0.6, 1] }, { type: M.spring, stiffness: 160, damping: 16 });
    M.animate('#flowSvg .fnode', { opacity: [0, 1], scale: [0.4, 1] }, { type: M.spring, stiffness: 240, damping: 18, delay: M.stagger(0.09, { startDelay: 0.25 }) });
    $$('#flowSvg .fline').forEach((p, i) => {
      const len = p.getTotalLength();
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      M.animate(p, { strokeDashoffset: [len, 0] }, { duration: 0.9, delay: 0.35 + i * 0.09, ease: [0.2, 0.8, 0.2, 1] });
    });
    $$('#flowSvg .fseg').forEach((c, i) => {
      const full = parseFloat(c.dataset.len), off = parseFloat(c.dataset.off);
      M.animate(c, { strokeDasharray: [`0 ${full}`, `${c.dataset.seg} ${full}`] }, { duration: 0.8, delay: 1 + i * 0.12, ease: 'easeOut' });
      c.style.strokeDashoffset = off;
    });
  }
  function watchFlow() {
    const el = $('#flowSvg'); if (!el) return;
    if (!('IntersectionObserver' in window)) { playFlow(); return; }
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { playFlow(); io.disconnect(); } }), { threshold: 0.3 });
    io.observe(el);
  }

  /* ---------- page change hook ---------- */
  window.onScreenShown = function (id) {
    const el = document.getElementById(id); if (!el) return;
    reveal(el);
    if (id === 'scHome') { window.playHero(); watchFlow(); }
    if (can && (id === 'scAbout' || id === 'scContact')) {
      M.animate(el.querySelectorAll('.ph h1, .ph p, .ph-crumb'), { opacity: [0, 1], y: [20, 0] }, { duration: 0.6, delay: M.stagger(0.08), ease: 'easeOut' });
      const b = el.querySelector('.ph-blob');
      if (b) M.animate(b, { opacity: [0, 0.95], x: [60, 0] }, { duration: 0.9, ease: [0.2, 0.8, 0.2, 1] });
      const lg = el.querySelector('.ph-logo');
      if (lg) M.animate(lg, { opacity: [0, 1], scale: [0.5, 1], rotate: [-8, 0] }, { type: M.spring, stiffness: 200, damping: 14, delay: 0.35 });
      M.animate(el.querySelectorAll('.ph-chip'), { opacity: [0, 1], scale: [0.7, 1] }, { type: M.spring, stiffness: 220, damping: 16, delay: M.stagger(0.12, { startDelay: 0.6 }) });
    }
    if (can && id === 'scLogin') {
      M.animate('#swapCard', { opacity: [0, 1], y: [24, 0], scale: [0.98, 1] }, { type: M.spring, stiffness: 260, damping: 26 });
      M.animate('.auth-art-body > *', { opacity: [0, 1], y: [20, 0] }, { duration: 0.6, delay: M.stagger(0.1, { startDelay: 0.1 }) });
    }
    if (can && id === 'scResults') {
      M.animate('#resInner .res-hero, #resInner .rcard, #resInner .res-grid .card', { opacity: [0, 1], y: [18, 0] }, { duration: 0.5, delay: M.stagger(0.05), ease: 'easeOut' });
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    $$('.overlay, #forgotOverlay').forEach(o => mo.observe(o, { attributes: true, attributeFilter: ['class'], attributeOldValue: true }));
    wirePress();
    document.addEventListener('click', e => {
      const l = document.getElementById('cxLinks');
      if (l && !e.target.closest('.cx-burger')) l.classList.remove('open');
    });
  });
})();
