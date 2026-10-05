/* Обложка кейса: одна сцена, которую ведет скролл.

   Прогресс считается от положения верхней кромки обложки: 0 в самом верху
   страницы, 1 в момент, когда кромка доходит до меню. Дальше сцена стоит.

   Четыре движения читают один и тот же прогресс, но каждое заканчивается
   на своем пороге. Из-за этого окончания расходятся во времени, и верхушка
   собирается не одним рывком, а слоями — ради ощущения глубины.

   Вертикальное размытие сделано SVG-фильтром: css filter: blur() размывает
   по обеим осям, а feGaussianBlur принимает stdDeviation по осям отдельно. */
(function () {
  var scene = document.querySelector('[data-cover-scene]');
  if (!scene) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var photos = scene.querySelector('.g-cover-photos');
  var phone = scene.querySelector('.g-cover-phone');
  var blur = document.querySelector('#g-cover-blur feGaussianBlur');
  var header = document.querySelector('.site-header');

  // Пороги окончания. Телефон приходит первым, за ним строки, потом резкость,
  // плашки закрывают сцену.
  var ENDS = { phone: 0.55, roll: 0.72, sharp: 0.85 };
  // Плашки приходят с заметным разрывом: левая заметно раньше правой.
  var CHIP_A = { from: 0.58, to: 0.76 };
  var CHIP_B = { from: 0.84, to: 1 };
  var MAX_BLUR = 26; // в пикселях по вертикали, в начале сцены
  var GLASS_MIN = 0.55; // плотность плашки шильдика в первом кадре сцены

  var ease = function (t) { return 1 - Math.pow(1 - t, 3); };
  var part = function (p, from, to) {
    if (to <= from) return 1;
    return ease(Math.min(1, Math.max(0, (p - from) / (to - from))));
  };

  var span = 1;
  function measure() {
    var top = scene.getBoundingClientRect().top + window.scrollY;
    var h = header ? header.getBoundingClientRect().height : 0;
    span = Math.max(1, top - h);
  }

  var ticking = false;
  function apply() {
    ticking = false;
    var p = Math.min(1, Math.max(0, window.scrollY / span));

    var phoneP = part(p, 0, ENDS.phone);
    var rollP = part(p, 0, ENDS.roll);
    var sharpP = part(p, 0, ENDS.sharp);
    var chipA = part(p, CHIP_A.from, CHIP_A.to);
    var chipB = part(p, CHIP_B.from, CHIP_B.to);

    if (phone) phone.style.setProperty('--cover-phone', phoneP.toFixed(4));
    // Пульсация на метке живет отдельно от прогресса: она включается один раз,
    // когда телефон полностью вышел, и дальше идет сама по себе.
    scene.classList.toggle('is-phone-in', phoneP > 0.999);
    scene.style.setProperty('--cover-roll', rollP.toFixed(4));
    scene.style.setProperty('--cover-chip-a', chipA.toFixed(4));
    scene.style.setProperty('--cover-chip-b', chipB.toFixed(4));
    if (blur) blur.setAttribute('stdDeviation', '0 ' + ((1 - sharpP) * MAX_BLUR).toFixed(2));
    // Плашка шильдика прибита к верхней кромке фотографии и никуда не едет.
    // Вместе с резкостью она только набирает плотность: от GLASS_MIN до единицы.
    scene.style.setProperty('--cover-glass', (GLASS_MIN + (1 - GLASS_MIN) * sharpP).toFixed(4));
    // Наезд отдает в css переменной: масштабируются сами фотографии внутри
    // слоя, поэтому кадр не выходит за верхнюю кромку обложки.
    if (photos) photos.style.setProperty('--cover-zoom', (1.06 - 0.06 * sharpP).toFixed(4));
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(apply);
  }

  // Сцена берет плашку шильдика на себя только после того, как скрипт жив:
  // до этого она просто видна, без мигания.
  scene.classList.add('has-cover-scene');
  measure();
  apply();
  window.addEventListener('scroll', request, { passive: true });
  window.addEventListener('resize', function () { measure(); request(); });
})();
