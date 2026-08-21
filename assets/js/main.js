(function(){
  var els = document.querySelectorAll('.reveal');
  if(!('IntersectionObserver' in window) || !els.length){
    els.forEach(function(el){ el.classList.add('is-visible'); });
    return;
  }

  // `--i` is the element's position *within the batch that appears together*,
  // which CSS turns into a stagger. Indexing by document order instead would
  // give a lone element scrolled into view an arbitrary delay before it starts.
  // cap the cascade: on a full screen of blocks the tail would otherwise wait
  // far too long before it starts
  var MAX_STEP = 8;

  function show(el, index){
    el.style.setProperty('--i', Math.min(index || 0, MAX_STEP));
    el.classList.add('is-visible');
    io.unobserve(el);
  }

  // No negative bottom rootMargin: it creates a dead zone at the end of the
  // document, and anything sitting inside it (e.g. the footer copyright) can
  // never be scrolled far enough to trigger and would stay invisible.
  // Order the batch by document position, not by on-screen top: the footer is
  // pinned to the bottom of the viewport, so its blocks always intersect and
  // would otherwise interleave with the first screen and skew its cascade.
  var order = new Map();
  els.forEach(function(el, i){ order.set(el, i); });

  var io = new IntersectionObserver(function(entries){
    entries
      .filter(function(entry){ return entry.isIntersecting; })
      .sort(function(a, b){ return order.get(a.target) - order.get(b.target); })
      .forEach(function(entry, i){ show(entry.target, i); });
  }, { threshold: 0.15 });

  els.forEach(function(el){ io.observe(el); });

  // Safety net: at the very bottom of the page nothing can scroll further, so
  // reveal whatever is still hidden but already on screen.
  function revealAtPageEnd(){
    if(window.innerHeight + window.scrollY < document.documentElement.scrollHeight - 2) return;
    var pending = Array.prototype.filter.call(
      document.querySelectorAll('.reveal:not(.is-visible)'),
      function(el){ return el.getBoundingClientRect().top < window.innerHeight; }
    );
    pending.forEach(function(el, i){ show(el, i); });
  }

  window.addEventListener('scroll', revealAtPageEnd, { passive: true });
  window.addEventListener('resize', revealAtPageEnd);
  window.addEventListener('load', revealAtPageEnd);
})();

(function(){
  var footer = document.querySelector('.site-footer');
  var root = document.documentElement;
  if(!footer) return;

  // Reserve scroll distance equal to the footer height so the content can slide
  // up and uncover it. Pinning only works while the whole footer fits on
  // screen, so fall back to a normal static footer when it does not.
  function syncFooterReveal(){
    root.classList.remove('no-footer-reveal');
    var height = footer.offsetHeight;
    var fits = height < window.innerHeight;

    root.classList.toggle('no-footer-reveal', !fits);
    root.style.setProperty('--footer-h', fits ? height + 'px' : '0px');
  }

  syncFooterReveal();
  window.addEventListener('load', syncFooterReveal);
  window.addEventListener('resize', syncFooterReveal);
})();

/* The header pill now carries its tint permanently (as in the reference), so the
   former scroll-triggered `is-scrolled` state is gone — nothing to toggle. */

(function(){
  var header = document.querySelector('.site-header');
  var menuBtn = header && header.querySelector('.site-header__menu-btn');
  var nav = header && header.querySelector('.site-header__nav');
  if(!header || !menuBtn || !nav) return;

  function setOpen(open){
    header.classList.toggle('is-open', open);
    menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    menuBtn.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
  }

  menuBtn.addEventListener('click', function(){
    setOpen(!header.classList.contains('is-open'));
  });

  nav.addEventListener('click', function(e){
    if(e.target.tagName === 'A'){
      setOpen(false);
    }
  });

  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){
      setOpen(false);
    }
  });

  window.addEventListener('resize', function(){
    if(window.innerWidth > 720){
      setOpen(false);
    }
  });
})();

(function(){
  var buttons = document.querySelectorAll('[data-copy]');
  if(!buttons.length) return;

  function flash(btn){
    btn.textContent = btn.dataset.labelDone || 'Copied';
    btn.classList.add('is-done');
    clearTimeout(btn._resetTimer);
    btn._resetTimer = setTimeout(function(){
      btn.textContent = btn.dataset.labelIdle || 'Copy';
      btn.classList.remove('is-done');
    }, 1800);
  }

  // Clipboard API needs a secure context; fall back to a hidden textarea so the
  // button still works over plain http (local preview, some in-app browsers).
  function legacyCopy(text){
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch(e) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }

  buttons.forEach(function(btn){
    btn.addEventListener('click', function(){
      var text = btn.dataset.copy;
      if(navigator.clipboard && window.isSecureContext){
        navigator.clipboard.writeText(text).then(function(){ flash(btn); },
                                                 function(){ if(legacyCopy(text)) flash(btn); });
      } else if(legacyCopy(text)){
        flash(btn);
      }
    });
  });
})();

(function(){
  var buttons = document.querySelectorAll('.list-more');
  if(!buttons.length) return;

  Array.prototype.forEach.call(buttons, function(btn){
    var list = btn.previousElementSibling;
    if(!list) return;
    var extras = list.querySelectorAll('[data-extra]');
    if(!extras.length){ btn.hidden = true; return; }

    function setOpen(open){
      Array.prototype.forEach.call(extras, function(el){
        if(open){ el.removeAttribute('hidden'); }
        else { el.setAttribute('hidden', 'until-found'); }
      });
      btn.textContent = open ? btn.dataset.less : btn.dataset.more;
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    btn.addEventListener('click', function(){
      setOpen(btn.getAttribute('aria-expanded') !== 'true');
    });

    // find-in-page can reveal a row on its own; keep the button telling the truth
    Array.prototype.forEach.call(extras, function(el){
      el.addEventListener('beforematch', function(){ setOpen(true); });
    });
  });
})();
