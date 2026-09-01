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
      // подпись живёт в отдельном span: у кнопки внутри ещё стрелка и линия,
      // и запись в textContent самой кнопки стёрла бы их
      var label = btn.querySelector('[data-label]') || btn;
      label.textContent = open ? btn.dataset.less : btn.dataset.more;
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

/* Каталог: фильтр по направлениям.
   Фильтр — это вид на один и тот же набор, а не смена позиционирования.
   «Все» стоит первой и активна по умолчанию, состояние живёт в адресе, поэтому
   отфильтрованный каталог можно отправить ссылкой, а Back и Forward ведут себя
   так, как обещает браузер. Карточка может принадлежать нескольким нишам —
   data-niche хранит список через пробел. */
(function(){
  var bar = document.querySelector('.portfolio__filters');
  var grid = document.getElementById('portfolio-grid');
  if(!bar || !grid) return;

  /* Каталог идёт двумя рядами внимания: крупные карточки и мелкие. Фильтр
     работает поверх обоих — иначе выбранное направление показывало бы только
     часть работ. Блок второго ряда прячется целиком, когда в нём после
     фильтрации ничего не осталось: иначе от него остаётся голая линия. */
  var more = document.getElementById('portfolio-more');
  var gridSmall = document.getElementById('portfolio-grid-small');

  var buttons = bar.querySelectorAll('.pfilter');
  var cards = document.querySelectorAll('#portfolio-grid [data-niche], #portfolio-grid-small [data-niche]');
  var status = document.querySelector('.filters__status');
  var empty = document.querySelector('.portfolio__empty');
  var LABELS = { all: 'все работы', product: 'продукт и UX/UI', brand: 'бренд', web: 'web и digital' };

  function matches(card, value){
    if(value === 'all') return true;
    return (' ' + card.dataset.niche + ' ').indexOf(' ' + value + ' ') !== -1;
  }

  function plural(n){
    var d = n % 10, dd = n % 100;
    if(d === 1 && dd !== 11) return 'работа';
    if(d >= 2 && d <= 4 && (dd < 10 || dd >= 20)) return 'работы';
    return 'работ';
  }

  function apply(value){
    var shown = 0;
    Array.prototype.forEach.call(cards, function(card){
      var on = matches(card, value);
      card.hidden = !on;
      if(on){ card.classList.add('is-visible'); shown++; }
    });
    Array.prototype.forEach.call(buttons, function(btn){
      var on = btn.dataset.filter === value;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    if(more && gridSmall){
      var left = gridSmall.querySelectorAll('[data-niche]:not([hidden])').length;
      more.hidden = left === 0;
    }
    if(empty) empty.hidden = shown !== 0;
    if(status) status.textContent = shown + ' ' + plural(shown) + ' – ' + LABELS[value];
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
      apply(value);
    });
  });

  window.addEventListener('popstate', function(){ apply(fromUrl()); });
  apply(fromUrl());
})();

/* Первый экран: три строки управляют большой карточкой.
   Автопереключение идёт по кругу; наведение или клавиатурный фокус временно
   выбирает свою строку и останавливает цикл, уход возобновляет. Изображения
   лежат стопкой в фиксированном контейнере, поэтому смена не двигает вёрстку. */
(function(){
  var AUTO_MS = 5000;

  var index = document.querySelector('[data-cindex]');
  var featured = document.querySelector('[data-featured]');
  if(!index || !featured) return;

  var rows = Array.prototype.slice.call(index.querySelectorAll('.crow'));
  var imgs = Array.prototype.slice.call(featured.querySelectorAll('.featured__img'));
  var num = featured.querySelector('.featured__num');
  var title = featured.querySelector('.featured__title');
  var type = featured.querySelector('.featured__type');
  if(!rows.length || !imgs.length) return;

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var current = rows.findIndex(function(r){ return r.classList.contains('is-selected'); });
  if(current < 0) current = 0;
  var timer = null;
  var held = false;

  function select(i){
    if(i === current) return;
    var from = imgs[current], to = imgs[i], row = rows[i];

    from.classList.remove('is-current');
    from.classList.add('is-leaving');
    to.classList.remove('is-leaving');
    to.classList.add('is-current');
    window.setTimeout(function(){ from.classList.remove('is-leaving'); }, 320);

    rows[current].classList.remove('is-selected');
    row.classList.add('is-selected');

    // подпись меняется с задержкой, чтобы не спорить с кроссфейдом
    window.setTimeout(function(){
      num.textContent = row.querySelector('.crow__num').textContent;
      title.textContent = row.querySelector('.crow__title').textContent;
      type.textContent = row.querySelector('.crow__type').textContent;
      featured.setAttribute('href', row.getAttribute('href'));
    }, reduced ? 0 : 40);

    current = i;
  }

  function start(){
    // скрытая вкладка: таймер не заводим вовсе, а не полагаемся на троттлинг браузера
    if(reduced || held || timer || document.hidden) return;
    timer = window.setInterval(function(){ select((current + 1) % rows.length); }, AUTO_MS);
  }
  function stop(){
    if(!timer) return;
    window.clearInterval(timer);
    timer = null;
  }

  rows.forEach(function(row, i){
    // наведение и фокус выбирают кейс сразу и держат цикл на паузе
    ['mouseenter', 'focus'].forEach(function(evt){
      row.addEventListener(evt, function(){ held = true; stop(); select(i); }, true);
    });
    ['mouseleave', 'blur'].forEach(function(evt){
      row.addEventListener(evt, function(){ held = false; start(); }, true);
    });
  });

  // вкладка скрыта — цикл незачем крутить
  document.addEventListener('visibilitychange', function(){
    if(document.hidden) stop(); else start();
  });

  start();
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

  var INK = [67, 67, 67];        // #434343 — тон знака (--mark), не ink
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

/* Год в подвале: строка в HTML — то, что было верно на момент последней
   сборки (tools/pages.json → {{year}}), а не то, что верно сейчас. Статика
   не пересобирается сама 1 января — без этой правки год просто застынет
   на «2026» навсегда. Подменяем на настоящий текущий год при каждой
   загрузке страницы, независимо от того, когда её в последний раз собрали. */
(function(){
  var nodes = document.querySelectorAll('.js-year');
  if(!nodes.length) return;
  var year = String(new Date().getFullYear());
  nodes.forEach(function(el){ el.textContent = year; });
})();

/* Превью чужого сайта в рамке-браузере (кейсы Mark'n'Post и Svitla Embroidery).
   Копия свёрстана в натуральную ширину 1400px и ужимается под ширину колонки
   через scale. Высоту рамки ставим здесь же: scale не меняет геометрию для
   потока, поэтому без явной высоты рамка не знает, где кончается копия, и
   снизу оставалось пустое поле. */
(function(){
  var frames = document.querySelectorAll('[data-preview-frame]');
  if(!frames.length) return;

  function fit(frame){
    var stage = frame.querySelector('[data-preview-stage]');
    if(!stage) return;
    var scale = frame.clientWidth / 1400;
    stage.style.transform = 'scale(' + scale + ')';
    frame.style.height = (stage.offsetHeight * scale) + 'px';
  }
  function fitAll(){ Array.prototype.forEach.call(frames, fit); }

  fitAll();
  window.addEventListener('resize', fitAll);
  // шрифты и картинки внутри копии меняют её высоту уже после первого прохода
  window.addEventListener('load', fitAll);
  if(document.fonts && document.fonts.ready) document.fonts.ready.then(fitAll);
})();
