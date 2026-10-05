/* Сцены кейса, которые ведет скролл.

   1. Стеклянный шарик, который катится по изогнутой ленте блока 04.

   Траектория взята из исходника ленты: тот же path, что рисует саму форму
   в research-ribbon.svg, в системе координат 2800 x 1800. Лента растянута
   по боксу неравномерно, поэтому координаты точки переводятся в проценты
   этого бокса, а не в пиксели: так шарик остается круглым на любой ширине.

   Прогресс считает скролл. Ноль в момент, когда лента входит в экран снизу,
   единица чуть раньше, чем она уходит вверх за край. Поворот шарика привязан
   к пройденному пути, поэтому видно, что он катится, а не едет. */
(function () {
  var stage = document.querySelector('[data-ball-stage]');
  if (!stage) return;
  var ball = stage.querySelector('.g-ball');
  var path = stage.querySelector('[data-ball-path]');
  var ribbon = stage.querySelector('.g-ribbon');
  if (!ball || !path || !ribbon || !path.getPointAtLength) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var VB_W = 2800;          // ширина системы координат ленты
  var VB_H = 1800;          // ее высота
  var END = 0.6;            // весь путь проходится за 0.6 прохода блока по экрану
  var TURNS = 7;            // оборотов шарика за весь путь
  var FADE = 0.08;          // доля пути на появление и на уход

  var total = path.getTotalLength();
  var ticking = false;
  // Шарик живет только на широком коллаже: ниже 1100 блок перестраивается
  // в сетку карточек, и катиться становится не по чему.
  var wide = window.matchMedia('(min-width: 1101px)');

  function clamp(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

  /* Точка пути переводится в координаты сцены через фактический бокс ленты.
     Лента на разных ширинах лежит по-разному: то во всю ширину окна, то шире
     сцены, и масштабируется то fill, то cover. Поэтому бокс и способ вписывания
     читаются из самого элемента, а не задаются числами. */
  function place(pt) {
    var sr = stage.getBoundingClientRect();
    var rr = ribbon.getBoundingClientRect();
    if (!sr.width || !rr.width) return;
    var fit = window.getComputedStyle(ribbon).objectFit;
    var sx, sy, ox = 0, oy = 0;
    if (fit === 'cover' || fit === 'contain') {
      var kx = rr.width / VB_W, ky = rr.height / VB_H;
      var k = fit === 'cover' ? Math.max(kx, ky) : Math.min(kx, ky);
      sx = sy = k;
      ox = (rr.width - VB_W * k) / 2;
      oy = (rr.height - VB_H * k) / 2;
    } else {
      sx = rr.width / VB_W;
      sy = rr.height / VB_H;
    }
    var x = (rr.left - sr.left) + ox + pt.x * sx;
    var y = (rr.top - sr.top) + oy + pt.y * sy;
    ball.style.setProperty('--ball-x', (x / sr.width * 100).toFixed(3) + '%');
    ball.style.setProperty('--ball-y', (y / sr.height * 100).toFixed(3) + '%');
  }

  function apply() {
    ticking = false;
    if (!wide.matches) return;
    var r = stage.getBoundingClientRect();
    var vh = window.innerHeight || document.documentElement.clientHeight;
    var raw = (vh - r.top) / (r.height + vh);
    var p = clamp(raw / END);

    place(path.getPointAtLength(p * total));
    ball.style.setProperty('--ball-rot', (p * TURNS * 360).toFixed(1) + 'deg');

    var o = Math.min(p / FADE, (1 - p) / FADE, 1);
    ball.style.setProperty('--ball-o', clamp(o).toFixed(3));
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(apply);
  }

  stage.classList.add('has-ball');
  apply();
  window.addEventListener('scroll', request, { passive: true });
  window.addEventListener('resize', request);
})();

/* 2. Две линейки вайрфреймов блока 10 едут навстречу друг другу.

   Один и тот же прогресс читается как смещение от центра экрана: верхняя
   линейка идет слева направо, нижняя справа налево. В середине экрана обе
   стоят на нуле и совпадают, дальше по странице расходятся в противоположные
   стороны. Шаг смещения задан в css переменной, поэтому зависит от ширины. */
(function () {
  var wire = document.querySelector('[data-wire-scene]');
  if (!wire) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var tracks = wire.querySelectorAll('.g-wire-track');
  if (tracks.length < 2) return;

  var ticking = false;

  function apply() {
    ticking = false;
    var r = wire.getBoundingClientRect();
    var vh = window.innerHeight || document.documentElement.clientHeight;
    var center = r.top + r.height / 2;
    var half = (vh + r.height) / 2;
    var t = (vh / 2 - center) / half;
    if (t < -1) t = -1;
    if (t > 1) t = 1;
    tracks[0].style.setProperty('--wire-t', t.toFixed(4));
    tracks[1].style.setProperty('--wire-t', (-t).toFixed(4));
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(apply);
  }

  wire.classList.add('has-wire-scene');
  apply();
  window.addEventListener('scroll', request, { passive: true });
  window.addEventListener('resize', request);
})();

/* 3. Лучи наклонного блока поворачиваются по часовой стрелке вместе со скроллом.

   Шаг между соседними лучами 15 градусов, поэтому полный проход блока по экрану
   поворачивает связку ровно на два шага: рисунок приходит в то же положение,
   с которого начал, и поворот не читается как сбой сетки. */
(function () {
  var block = document.querySelector('[data-rays-scene]');
  if (!block) return;
  var spin = block.querySelector('.g-rays-spin');
  if (!spin) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var SWEEP = 30;   // градусов за весь проход блока по экрану
  var ticking = false;

  function apply() {
    ticking = false;
    var r = block.getBoundingClientRect();
    var vh = window.innerHeight || document.documentElement.clientHeight;
    var p = (vh - r.top) / (r.height + vh);
    if (p < 0) p = 0;
    if (p > 1) p = 1;
    spin.style.setProperty('--rays-rot', (p * SWEEP).toFixed(2) + 'deg');
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(apply);
  }

  apply();
  window.addEventListener('scroll', request, { passive: true });
  window.addEventListener('resize', request);
})();

/* 4. Девайсы блока 01 приезжают на свое место по скроллу.

   Отсчет идет от самой композиции, а не от секции: ноль в момент, когда она
   входит в экран снизу, единица когда ее середина проходит центр экрана и
   уходит выше еще на треть экрана. К этому моменту девайсы стоят ровно там,
   где стояли раньше без движения, и дальше по странице уже не шевелятся. */
(function () {
  var block = document.querySelector('[data-about-scene]');
  if (!block) return;
  var shot = block.querySelector('[data-about-shot]');
  if (!shot) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var PAST = 0.3;   // насколько середина уходит выше центра экрана, доля экрана
  var LAG = 0.18;   // дальний телефон отстает от ближнего на эту долю пути
  var ticking = false;
  // Мягкое замедление к концу: движение идет почти вровень со скроллом
  // и только у самого места сходит на нет.
  var ease = function (t) { return 1 - Math.pow(1 - t, 2); };

  function apply() {
    ticking = false;
    var r = shot.getBoundingClientRect();
    var vh = window.innerHeight || document.documentElement.clientHeight;
    var mid = r.top + r.height / 2;
    var from = vh + r.height / 2;          // композиция только входит снизу
    var to = vh * (0.5 - PAST);            // центр экрана плюс треть экрана
    var p = (from - mid) / (from - to);
    if (p < 0) p = 0;
    if (p > 1) p = 1;
    // Дальний телефон идет тем же путем, но с задержкой. Из-за этого он всегда
    // ниже и правее ближнего, и место их стыка остается закрытым.
    var q = (p - LAG) / (1 - LAG);
    if (q < 0) q = 0;
    shot.style.setProperty('--about-p', ease(p).toFixed(4));
    shot.style.setProperty('--about-q', ease(q).toFixed(4));
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(apply);
  }

  block.classList.add('has-about-scene');
  apply();
  window.addEventListener('scroll', request, { passive: true });
  window.addEventListener('resize', request);
})();
