/* Mark the document as scripted, so CSS can show controls that only work with
   JavaScript. First statement in the file: the script sits at the end of body,
   so the class lands before the reader can notice. */
document.documentElement.classList.add('js');

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

/* Work grid filter.
   The filter is a view of one and the same set, not a change of positioning:
   «Все» is first and is the default, so anyone arriving without a goal sees
   everything before touching anything. The chosen value lives in the URL, so a
   filtered grid can be linked to and Back/Forward behave the way the browser
   promises. A card may belong to more than one niche — data-niche holds a
   space-separated list. */
(function(){
  var bar = document.querySelector('.filters');
  var grid = document.getElementById('work-grid');
  if(!bar || !grid) return;

  var buttons = bar.querySelectorAll('.filters__btn');
  var cards = grid.querySelectorAll('[data-niche]');
  var status = document.querySelector('.filters__status');
  var LABELS = { all: 'все проекты', product: 'продукт и UX/UI', brand: 'бренд', web: 'web и digital' };

  function matches(card, value){
    if(value === 'all') return true;
    return (' ' + card.dataset.niche + ' ').indexOf(' ' + value + ' ') !== -1;
  }

  function apply(value, focusGrid){
    var shown = 0;
    Array.prototype.forEach.call(cards, function(card){
      var on = matches(card, value);
      card.hidden = !on;
      if(on){
        // a card hidden at first paint never intersected, so the observer never
        // revealed it; showing it later has to bring it in explicitly
        card.classList.add('is-visible');
        shown++;
      }
    });
    Array.prototype.forEach.call(buttons, function(btn){
      var on = btn.dataset.filter === value;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    if(status){
      status.textContent = shown + ' ' + plural(shown) + ' – ' + LABELS[value];
    }
    if(focusGrid){
      // keep the grid in view: filtering out the tall cards can otherwise leave
      // the reader staring at empty space below the fold
      var top = grid.getBoundingClientRect().top + window.scrollY;
      if(window.scrollY > top) window.scrollTo({ top: top - 120, behavior: 'smooth' });
    }
  }

  function plural(n){
    var d = n % 10, dd = n % 100;
    if(d === 1 && dd !== 11) return 'проект';
    if(d >= 2 && d <= 4 && (dd < 10 || dd >= 20)) return 'проекта';
    return 'проектов';
  }

  function fromUrl(){
    var value = new URLSearchParams(location.search).get('filter');
    return LABELS[value] ? value : 'all';
  }

  Array.prototype.forEach.call(buttons, function(btn){
    btn.addEventListener('click', function(){
      var value = btn.dataset.filter;
      var url = value === 'all'
        ? location.pathname + location.hash
        : location.pathname + '?filter=' + value + location.hash;
      history.pushState({ filter: value }, '', url);
      apply(value, true);
    });
  });

  window.addEventListener('popstate', function(){ apply(fromUrl(), false); });

  apply(fromUrl(), false);
})();

/* Portrait height follows the headline beside it.
   The number cannot be written in CSS: it depends on how many lines the Russian
   copy wraps to, which changes with viewport width and with the text itself. */
(function(){
  var portrait = document.querySelector('.home-about__portrait');
  var text = document.querySelector('.home-about__text');
  if(!portrait || !text) return;

  function sync(){
    if(window.innerWidth <= 720){
      portrait.style.removeProperty('--portrait-h');   // one column: no pairing
      return;
    }
    portrait.style.setProperty('--portrait-h', Math.round(text.getBoundingClientRect().height) + 'px');
  }

  sync();
  window.addEventListener('load', sync);
  window.addEventListener('resize', sync);
  if(document.fonts && document.fonts.ready) document.fonts.ready.then(sync);
})();

/* DESIGN -> WORKS lockup, ported from V1.
   The word morphs as the projects section approaches, and the two shapes wipe
   out ahead of it. Both are driven by scroll position, not by a timer, so the
   reader controls the pace. */
(function(){
  var word = document.querySelector('.lockup__word');
  var forms = document.querySelector('.lockup__forms');
  var work = document.getElementById('work');
  if(!word || !work) return;

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var clamp = function(v, a, b){ return Math.min(Math.max(v, a), b); };
  var ease = function(t){ return t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3)/2; };

  var INK = [67, 67, 67];        // #434343 — тот же базовый ink
  var FADE = [230, 230, 230];    // #e6e6e6 — тот же тон, что и линии (--line)
  function mix(a, b, t){
    return 'rgb(' + a.map(function(v, i){ return Math.round(v + (b[i] - v) * t); }).join(',') + ')';
  }

  function render(){
    var viewport = window.innerHeight || 1;
    var top = work.getBoundingClientRect().top + window.scrollY;
    var start = top - viewport * 0.78;
    var end = top - viewport * 0.38;
    var raw = clamp((window.scrollY - start) / Math.max(end - start, 1), 0, 1);
    var eased = reduced ? Math.round(raw) : ease(raw);

    var split = eased * 100;
    // a slight overlap of the two masks hides the seam mid-morph
    var gap = reduced ? 0 : Math.sin(eased * Math.PI) * 3.2;
    word.style.setProperty('--morph-from-clip', 'inset(0 0 ' + clamp(split + gap * .5, 0, 100).toFixed(2) + '% 0)');
    word.style.setProperty('--morph-to-clip', 'inset(' + clamp(100 - split + gap * .5, 0, 100).toFixed(2) + '% 0 0 0)');
    word.style.setProperty('--morph-from-y', (-8 * eased).toFixed(2) + 'px');
    word.style.setProperty('--morph-to-y', (10 * (1 - eased)).toFixed(2) + 'px');

    // tone crossfade, as in V1: the outgoing word lightens while the incoming
    // one gains weight of colour. The swap is concentrated around the middle of
    // the morph, so the two never look equally present.
    var shift = reduced ? (eased > .5 ? 1 : 0) : ease(clamp((eased - 0.44) / 0.12, 0, 1));
    word.style.setProperty('--morph-from-color', mix(INK, FADE, shift));
    word.style.setProperty('--morph-to-color', mix(FADE, INK, shift));

    word.setAttribute('aria-label', eased > 0.55 ? 'Works' : 'Design');
    word.dataset.word = eased > 0.55 ? 'works' : 'design';

    if(forms){
      var span = 0.64;
      var two = reduced ? eased : ease(clamp(eased / span, 0, 1));
      var one = reduced ? eased : ease(clamp((eased - span * .5) / span, 0, 1));
      forms.style.setProperty('--form-two-clip', 'inset(0 ' + (two * 100).toFixed(2) + '% 0 0)');
      forms.style.setProperty('--form-one-clip', 'inset(0 ' + (one * 100).toFixed(2) + '% 0 0)');
    }
  }

  var ticking = false;
  function onScroll(){
    if(ticking) return;
    ticking = true;
    requestAnimationFrame(function(){ render(); ticking = false; });
  }

  render();
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
})();

/* Shape swap, ported from V1 brand-forms.js: every few seconds one of the two
   shapes turns edge-on, is replaced, and turns back. The pair never shows the
   same file twice. */
(function(){
  var root = document.querySelector('[data-form-root]');
  if(!root) return;
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // Vector-20 — вертикально-горизонтальная сетка, из ротации исключена
  var SKIP = ['Vector-20.svg'];

  // Пары, которые глазом читаются как одна форма. Посчитано один раз: каждый SVG
  // отрисован в canvas 32x32 и сравнён с остальными по косинусной близости
  // силуэта; в семьи попало всё, что выше 0.85. Две формы из одной семьи рядом
  // выглядят как повтор, даже когда это разные файлы.
  var FAMILIES = [
    ['Vector-2.svg', 'Vector-14.svg'],
    ['Vector-4.svg', 'Vector-25.svg'],
    ['Vector-27.svg', 'Vector-35.svg'],
    ['Vector-16.svg', 'Vector-21.svg'],
    ['Vector-19.svg', 'Vector-22.svg']
  ];
  function kin(file){
    for(var i = 0; i < FAMILIES.length; i++){
      if(FAMILIES[i].indexOf(file) !== -1) return FAMILIES[i];
    }
    return [file];
  }
  var files = [];
  for(var i = 1; i <= 38; i++) files.push('Vector-' + i + '.svg');
  files.push('Vector.svg', 'Union.svg');
  files = files.filter(function(f){ return SKIP.indexOf(f) === -1; });

  var flip = root.querySelector('[data-form-slot="flip"]');
  var spin = root.querySelector('[data-form-slot="spin"]');
  var flipImg = flip && flip.querySelector('img');
  var spinImg = spin && spin.querySelector('img');
  if(!flipImg || !spinImg) return;

  var base = root.dataset.formsPath || 'assets/images/forms/';
  var current = { flip: 'Union.svg', spin: 'Vector-33.svg' };

  // Reserved as soon as it is drawn, not when it lands: the two timers overlap,
  // and without a reservation both could draw the same file in the gap between
  // choosing and swapping — the pair would show one shape twice.
  var pending = [];
  function pick(){
    var taken = [current.flip, current.spin].concat(pending);
    // не сам файл, а вся его семья: похожая форма рядом читается как та же
    taken = taken.reduce(function(acc, f){ return acc.concat(kin(f)); }, []);
    var pool = files.filter(function(f){ return taken.indexOf(f) === -1; });
    var next = pool[Math.floor(Math.random() * pool.length)];
    pending.push(next);
    return next;
  }
  function release(file){
    var i = pending.indexOf(file);
    if(i !== -1) pending.splice(i, 1);
  }

  function cycle(frame, img, slot, cls, swapAt, endAt){
    var next = pick();
    frame.classList.add(cls);
    setTimeout(function(){ current[slot] = next; release(next); img.src = base + next; }, swapAt);
    setTimeout(function(){ frame.classList.remove(cls); }, endAt);
  }

  setInterval(function(){ cycle(flip, flipImg, 'flip', 'is-flipping', 360, 740); }, 6800);
  setInterval(function(){ cycle(spin, spinImg, 'spin', 'is-flipping-reverse', 460, 920); }, 15980);
})();
