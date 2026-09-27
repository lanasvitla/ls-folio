/* Case choreography: independent pieces, with the site's reveal easing. */
(function () {
  var root = document.querySelector('.garden-case');
  if (!root) return;
  var groups = [
    ['.g-heading', ':scope > h2, :scope > p'],
    ['.g-meta', ':scope > div'],
    ['.g-stages', '.g-stage'],
    ['.g-products', ':scope > div'],
    ['.g-legend', ':scope > span'],
    ['.g-research-stage', '.g-avatar, .g-count, .g-person'],
    ['.g-guide-stage', ':scope > h2, .g-planner, .g-float'],
    ['.g-cjm-visual', ':scope > div, :scope > figure > img, figcaption > span'],
    ['.g-ia-home', ':scope > aside, :scope > img'],
    ['.g-branches', ':scope > article'],
    ['.g-ia-shared', ':scope > *'],
    ['.g-flow-board', '.g-flow-node'],
    ['.g-flow-continuation', ':scope > *'],
    ['.g-wire-track', ':scope > figure']
  ];
  function part(el) { el.classList.add('g-part'); }
  groups.forEach(function (group) {
    root.querySelectorAll(group[0]).forEach(function (container) {
      container.classList.remove('reveal');
      container.querySelectorAll(group[1]).forEach(part);
    });
  });
  root.querySelectorAll('.g-scroll').forEach(function (el) {
    el.classList.remove('reveal');
    el.querySelectorAll('thead, tbody > tr').forEach(part);
  });
  root.querySelectorAll('.g-cover-bubble, .g-cover-caption, .g-cover-mark, #garden-title').forEach(part);
  root.querySelectorAll('.reveal').forEach(function (el) {
    el.classList.remove('reveal'); part(el);
  });
  var parts = Array.from(root.querySelectorAll('.g-part'));
  // A moving parent already carries its children; avoid compounded animation.
  parts.forEach(function (el) {
    if (el.parentElement.closest('.g-part')) el.classList.remove('g-part');
  });
  parts = Array.from(root.querySelectorAll('.g-part'));
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var observer;
  function showAll() {
    if (observer) observer.disconnect();
    parts.forEach(function (el) { el.classList.add('g-part-visible'); });
  }
  if (reduced.matches || !('IntersectionObserver' in window)) { showAll(); return; }
  root.classList.add('g-motion-ready');
  var order = new Map(parts.map(function (el, i) { return [el, i]; }));
  observer = new IntersectionObserver(function (entries) {
    entries.filter(function (entry) { return entry.isIntersecting; })
      .sort(function (a, b) {
        return a.boundingClientRect.top - b.boundingClientRect.top || order.get(a.target) - order.get(b.target);
      }).forEach(function (entry, i) {
        entry.target.style.setProperty('--g-part-delay', Math.min(i, 4) * 60 + 'ms');
        entry.target.classList.add('g-part-visible');
        observer.unobserve(entry.target);
      });
  }, { threshold: 0.08 });
  parts.forEach(function (el) { observer.observe(el); });
  reduced.addEventListener('change', function (event) { if (event.matches) showAll(); });
})();
