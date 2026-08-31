#!/usr/bin/env python3
"""Render shared components from partials/ into the pages listed in pages.json.

Each page marks a component slot with a pair of HTML comments:

    <!-- component:site-footer -->
    ...generated markup, never edit by hand...
    <!-- /component:site-footer -->

The renderer replaces everything between the markers. It is idempotent:
running it twice produces byte-identical files.

Usage:
    python3 tools/render_partials.py          # write changes
    python3 tools/render_partials.py --check  # verify pages are up to date
"""

from __future__ import annotations

import json
import re
import sys
import hashlib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
PARTIALS = SITE / "partials"
MANIFEST = Path(__file__).with_name("pages.json")

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
INCLUDE = re.compile(r"(?P<indent>[ \t]*)\{\{>\s*(?P<name>[\w-]+)\s*\}\}")


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# Файлы, которым браузер обязан верить только после изменения содержимого.
# Число руками уже подводило: правишь файл, забываешь поднять версию —
# и у человека остаётся старая версия из кеша. Отпечаток забыть нельзя.
VERSIONED = ["assets/css/style.css", "assets/js/main.js", "assets/icons/favicon.svg"]

ASSET_LINK = re.compile(
    r'((?:href|src)="[^"]*?assets/(?:css/style\.css|js/main\.js|icons/favicon\.svg))'
    r'\?v=[^"]*(")'
)


def asset_versions() -> dict:
    """Версия файла = отпечаток его содержимого.

    Строка `?v=N` стоит в каждой странице, и раньше её поднимали руками.
    Забыть — значит отдать читателю старый файл из кэша; ошибиться — значит
    сбросить кэш без причины. Так уже вышло со скриптом: стилям отпечаток
    сделали, а `main.js?v=36` остался ручным. Теперь считаются все три.
    """
    out = {}
    for rel in VERSIONED:
        f = SITE / rel
        if not f.is_file():
            raise SystemExit(f"[render_partials] нет файла для версии: {rel}")
        out[rel.rsplit("/", 1)[1]] = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
    return out


IMG_TAG = re.compile(r"<img\b[^>]*>")


_DIM_CACHE: dict = {}


def image_dimensions(html: str, page_path: str) -> str:
    """Проставляет width/height по реальному файлу.

    Без них браузер не знает пропорцию до загрузки и верстка дергается, пока
    картинки подтягиваются: на длинных кейсах это заметный прыжок. CSS всё
    равно задаёт `width:100%; height:auto`, атрибуты нужны только чтобы
    заранее зарезервировать место.
    """
    page_dir = (SITE / page_path).parent
    out, last = [], 0
    for m in IMG_TAG.finditer(html):
        tag = m.group(0)
        if "width=" in tag:
            continue
        src = re.search(r'src="([^"]+)"', tag)
        if not src or src.group(1).startswith(("http://", "https://", "data:")):
            continue
        rel = src.group(1)
        if rel.lower().endswith(".svg"):
            continue                      # у svg размер задаёт viewBox
        f = (page_dir / rel).resolve()
        if f not in _DIM_CACHE:
            _DIM_CACHE[f] = image_size(f) if f.is_file() else None
        size = _DIM_CACHE[f]
        if not size:
            raise SystemExit(
                f"[render_partials] {page_path}: не читается картинка {rel}"
            )
        out.append((m.start(), m.end(),
                    tag[:-1].rstrip() + f' width="{size[0]}" height="{size[1]}">'))

    if not out:
        return html
    parts = []
    for start, end, tag in out:
        parts.append(html[last:start]); parts.append(tag); last = end
    parts.append(html[last:])
    return "".join(parts)


def lazy_images(html: str) -> str:
    """Отложенная загрузка проставляется сборкой, а не руками.

    Первая картинка страницы стоит в первом экране — её откладывать вредно,
    она и есть то, чего читатель ждёт. Все остальные ниже сгиба и грузятся
    по мере прокрутки. Раньше это добавлялось вручную и держалось на памяти:
    на страницах кейсов из 14 картинок отложенных было ноль.
    """
    # счётчик пикселей аналитики не касается: он лежит в <noscript>, невидим
    # и «первой картинкой» страницы не является — иначе обложка уезжает
    # в отложенные, а трекер грузится сразу.
    hidden = [(m.start(), m.end()) for m in re.finditer(r"<noscript\b.*?</noscript>", html, re.S)]

    out, last, first = [], 0, True
    for m in IMG_TAG.finditer(html):
        tag = m.group(0)
        if any(a <= m.start() < b for a, b in hidden):
            continue
        if first:
            first = False
            # первая картинка не должна быть отложенной, даже если так написали руками
            if "loading=" in tag:
                out.append((m.start(), m.end(),
                            re.sub(r'\s+(loading|decoding)="[^"]*"', "", tag)))
            continue
        if "loading=" in tag:
            continue
        out.append((m.start(), m.end(), tag[:-1].rstrip() + ' loading="lazy" decoding="async">'))
    if not out:
        return html
    buf = []
    for a, b, new in out:
        buf.append(html[last:a])
        buf.append(new)
        last = b
    buf.append(html[last:])
    return "".join(buf)


def cv_size(rel_path: str) -> str:
    """Вес файла резюме — считается при сборке, а не пишется руками.

    Рядом со ссылкой стоит «PDF · N КБ», и это обещание должно оставаться
    правдой: заменили файл, пересобрали — цифра поехала следом.
    """
    f = SITE / rel_path
    if not f.is_file():
        raise SystemExit(f"[render_partials] нет файла резюме: {rel_path}")
    return f"{round(f.stat().st_size / 1024)}&nbsp;КБ"


def build_directions(page: dict, directions: dict) -> dict:
    """Переключатель направлений и блок «Другие направления».

    Три направления равноправны, поэтому имя, ссылка и описание каждого лежат
    в реестре один раз: страница называет только своё `direction`. Порядок
    в реестре — он же порядок на экране, менять его в одном месте.
    """
    if not directions:
        return {}
    current = page.get("direction")
    if current and current not in directions:
        raise SystemExit(f"[render_partials] unknown direction '{current}' in {page['path']}")
    root = page.get("root", "")

    items, others, every = [], [], []
    for key, d in directions.items():
        is_current = key == current
        cls = " is-current" if is_current else ""
        aria = ' aria-current="page"' if is_current else ""
        items.append(
            f'  <a class="switch__item{cls}" href="{root}{d["path"]}"{aria}>{d["name"]}</a>'
        )
        rows = "".join(
            f'\n        <span class="dcard__row">{r}</span>' for r in d.get("rows", [])
        )
        # разметка карточки — та же, что на главной: направление везде выглядит
        # одинаково, а «Подробнее» остаётся общим компонентом ссылки
        card = (
            f'      <a class="dcard reveal" href="{root}{d["path"]}">\n'
            f'        <span class="dcard__fill" aria-hidden="true"></span>\n'
            f'        <span class="dcard__title">{d["name"]}</span>'
            f'{rows}\n'
            f'        <span class="dcard__spacer"></span>\n'
            f'        <span class="dcard__action">'
            f'<!-- component:ilink text="Подробнее" --><!-- /component:ilink --></span>\n'
            f'      </a>'
        )
        every.append(card)
        if is_current:
            continue
        others.append(card)
    star = ('      <svg class="directions__star directions__star--{mod}" viewBox="0 0 44 44" '
            'aria-hidden="true"><use href="#i-star"/></svg>')
    # звёзды стоят на стыках карточек: у трёх стыка два, у двух — один
    stars_all = "\n".join(star.format(mod=m) for m in ("one", "two"))
    values = {"allDirections": "\n".join(every) + "\n" + stars_all}
    if not current:
        return values
    d = directions[current]
    # три компетенции на самой странице направления — тот же список `rows`,
    # что и в карточках, только без обёртки карточки и без маркеров
    skills = "\n".join(
        f'  <li>{r}</li>' for r in d.get("rows", [])
    )
    # цепочка шагов со стрелками между ними — те же `steps`, что и на «Процессе»
    arrow = ('\n  <svg class="ic" viewBox="0 0 22 22" aria-hidden="true">'
             '<use href="#i-arrow-right"/></svg>')
    steps = arrow.join(
        f'\n  <span class="chip">{c}</span>' for c in d.get("steps", [])
    )
    # компетенции чипсами, теми же, что под кейсами: один сплошной список без
    # деления на группы. Восклицательный знак в начале пункта делает чипс
    # акцентным.
    chips = []
    for c in d.get("expertise", []):
        cls = "chip chip--accent" if c.startswith("!") else "chip"
        chips.append(f'        <li class="{cls}">{c.lstrip("!")}</li>')
    groups = (
        ['      <ul class="tag-chips reveal">\n' + "\n".join(chips) + "\n      </ul>"]
        if chips
        else []
    )
    values.update({
        "directionExpertise": "\n".join(groups),
        "switchItems": "\n".join(items),
        "otherDirections": "\n".join(others) + "\n" + star.format(mod="mid"),
        "directionName": d["name"],
        "directionTitle": d.get("pageTitle", d["name"]),
        "directionLead": d.get("pageLead", d.get("desc", "")),
        "directionSkills": skills,
        "directionSteps": steps,
        "directionProcessLead": d.get("processLead", ""),
        "directionProcess": root + d["process"],
        "directionCv": root + d["cv"],
        "directionCvSize": cv_size(d["cv"]),
    })
    return values


def build_services(page: dict, directions: dict) -> dict:
    """Блоки услуг на «Процессе»: по блоку на направление.

    Всё содержимое приходит из того же реестра, что кормит карточки
    направлений и сами страницы направлений. Раньше эти блоки были
    написаны отдельной разметкой, и списки услуг успели разойтись с реестром.
    """
    if not page.get("servicesFromDirections"):
        return {}
    root = page.get("root", "")
    blocks = []
    for key, d in directions.items():
        rows = "\n".join(f'              <li>{r}</li>' for r in d.get("rows", []))
        chips = "\n".join(
            f'              <span class="chip">{c}</span>' for c in d.get("steps", [])
        )
        blocks.append(
            '        <li class="process-services__item reveal">\n'
            '          <span class="process-services__ph">\n'
            f'            <img src="{root}{d["previewImg"]}" alt="{d["previewAlt"]}" '
            'width="440" height="340" loading="lazy" decoding="async">\n'
            '          </span>\n'
            '          <div class="process-services__text">\n'
            f'            <h3 class="process-services__title">{d["name"]}</h3>\n'
            '            <ul class="process-services__list">\n'
            f'{rows}\n'
            '            </ul>\n'
            '            <span class="process-services__more">'
            f'<!-- component:ilink text="Подробнее" href="{root}{d["path"]}" -->'
            '<!-- /component:ilink --></span>\n'
            '          </div>\n'
            '          <div class="process-services__flow">\n'
            f'            <span class="process-services__caption">{d["stepsCaption"]}</span>\n'
            '            <div class="process-services__chips">\n'
            f'{chips}\n'
            '            </div>\n'
            '          </div>\n'
            '        </li>'
        )
    return {"serviceBlocks": "\n".join(blocks)}


def build_metrics(page: dict, metrics: dict) -> dict:
    """Блок цифр: «Достижения» на about и «Результаты» на направлениях.

    Одна цифра живёт в реестре один раз. Страница перечисляет ключи в том
    порядке, в каком показывает, — раньше один и тот же результат был
    переписан руками в двух-трёх файлах и мог разойтись при правке.
    """
    keys = page.get("metricList")
    if not keys:
        return {}
    items = []
    for key in keys:
        if key not in metrics:
            raise SystemExit(
                f"[render_partials] {page['path']}: неизвестная метрика '{key}'. "
                f"Есть: {', '.join(sorted(metrics))}"
            )
        m = metrics[key]
        # Источник идет хвостом внутри текста, а не отдельной строкой: так его
        # и просили. Он может быть пустым — метрика не всегда привязана к одному
        # проекту, тогда хвоста просто нет.
        source = m.get("source", "")
        tail = f' <i>{source}</i>' if source else ""
        items.append(
            '        <li class="reveal">\n'
            f'          <b>{m["value"]}</b>\n'
            f'          <span>{m["text"]}{tail}</span>\n'
            '        </li>'
        )
    return {"metricsItems": "\n".join(items)}


BASE_URL = "https://lanasvitla.github.io/ls-folio/"


def canonical_url(page: dict) -> str:
    """Публичный адрес страницы. index.html канонизируется в адрес каталога:
    так его отдаёт GitHub Pages, и именно этот адрес люди копируют и шлют."""
    path = page["path"]
    if path == "index.html":
        return BASE_URL
    return BASE_URL + path


def seo_fields(page: dict) -> dict:
    """og:image требует абсолютный URL — относительный краулеры не читают."""
    robots = (
        '<meta name="robots" content="noindex, nofollow">'
        if page.get("noindex") else ""
    )
    return {
        "canonicalUrl": canonical_url(page),
        "ogImageAbs": BASE_URL + page["ogImage"],
        "robotsMeta": robots,
    }


def build_robots(pages: list[dict]) -> str:
    lines = ["User-agent: *", "Allow: /"]
    for page in pages:
        if page.get("noindex"):
            lines.append(f'Disallow: /{page["path"]}')
    lines.append("")
    lines.append(f"Sitemap: {BASE_URL}sitemap.xml")
    return "\n".join(lines) + "\n"


def build_sitemap(pages: list[dict]) -> str:
    entries = []
    for page in pages:
        if page.get("noindex"):
            continue
        entries.append(f"  <url><loc>{canonical_url(page)}</loc></url>")
    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def build_case_slots(page: dict, cases: dict) -> dict:
    """A page may show more than one grid — brand.html has a brand row and a web
    row. Every `caseList<Suffix>` key on the page fills `{{caseCards<Suffix>}}`.
    """
    slots = {"caseCards": ""}
    slots.update(
        {
            "caseCards" + key[len("caseList"):]: build_case_cards(page, cases, key)
            for key in page
            if key.startswith("caseList")
        }
    )
    return slots


def build_home_cases(page: dict, cases: dict) -> dict:
    """Render the home hero — the big preview plus the numbered index — from the
    same case registry the cards use, so a cover or a title has one home only.
    `heroList` names the cases in order; `heroSelected` is the one shown first.
    """
    ids = page.get("heroList")
    if not ids:
        return {}
    root = page.get("root", "")
    selected = page.get("heroSelected", 0)
    images, rows = [], []
    for i, case_id in enumerate(ids):
        if case_id not in cases:
            raise SystemExit(f"[render_partials] unknown case id '{case_id}' in {page['path']}")
        case = cases[case_id]
        title = case.get("shortTitle", case["title"])
        current = " is-current" if i == selected else ""
        images.append(
            f'        <img class="featured__img{current}" src="{root}{case["cover"]}" '
            f'alt="{case["alt"]}" width="760" height="340" data-case="{i}">'
        )
        rows.append(
            f'        <a class="crow reveal{" is-selected" if i == selected else ""}" '
            f'href="{root}{case["path"]}" data-case="{i}">\n'
            f'          <span class="crow__num">{i + 1:02d}</span>\n'
            f'          <span class="crow__title">{title}</span>\n'
            f'          <span class="crow__type">{case["type"]}</span>\n'
            f'          <span class="crow__arrow"><svg class="ic" viewBox="0 0 22 22" aria-hidden="true"><use href="#i-arrow-right"/></svg></span>\n'
            f'        </a>'
        )
    hero = cases[ids[selected]]
    return {
        "heroImages": "\n".join(images),
        "heroRows": "\n".join(rows),
        "heroHref": root + hero["path"],
        "heroNum": f"{selected + 1:02d}",
        "heroTitle": hero.get("shortTitle", hero["title"]),
        "heroType": hero["type"],
    }


CASE_TEMPLATE = SITE / "tools/case-page.template.html"


def ensure_case_page(page: dict) -> None:
    """Страница кейса заводится сборкой, а не копированием соседнего файла.

    Копирование образца уже стоило одного разъехавшегося заголовка: у нового
    кейса в <title> осталось имя того, с кого копировали. Каркас одинаковый
    у всех, руками в нём делать нечего.
    """
    target = SITE / page["path"]
    if target.exists() or not page.get("case"):
        return
    skeleton = CASE_TEMPLATE.read_text(encoding="utf-8")
    skeleton = skeleton.replace("{{root}}", page.get("root", ""))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(skeleton, encoding="utf-8")
    print(f"[render_partials] заведена страница кейса: {page['path']}")


def build_case_intro(page: dict, cases: dict) -> dict:
    """Заголовок, лид и шапка страницы кейса — из реестра.

    Раньше это писалось руками в каждой странице и дублировало карточку в
    каталоге: два места с одним смыслом, и ничто не проверяло, что они
    совпадают. Теперь текст один, и карточка с шапкой не могут разойтись.
    """
    case_id = page.get("case")
    if not case_id:
        return {}
    if case_id not in cases:
        raise SystemExit(
            f"[render_partials] unknown case id '{case_id}' in {page['path']}"
        )
    case = cases[case_id]
    rows = "\n".join(
        f"  <div><dt>{label}</dt><dd>{value}</dd></div>"
        for label, value in case.get("meta", [])
    )
    return {
        "caseTitle": case["title"],
        "caseDesc": case["desc"],
        "caseMetaRows": rows,
    }


def build_case_body(page: dict, cases: dict) -> dict:
    """Тело страницы кейса: обложка, «Задача», «Решение» и галерея.

    Ряд галереи с двумя картинками получает `--two`, с одной — обычный.
    Класс выводится из числа картинок, а не хранится в реестре: иначе легко
    записать «две в ряд» и положить туда три.
    """
    case_id = page.get("case")
    if not case_id or "gallery" not in cases.get(case_id, {}):
        return {}
    case = cases[case_id]
    root = page.get("root", "")

    rows = []
    for images in case["gallery"]:
        two = " case-gallery--two" if len(images) == 2 else ""
        tags = "\n".join(
            f'  <img class="reveal" src="{root}{src}" alt="{alt}">' for src, alt in images
        )
        rows.append(
            f'<section class="case-gallery{two} case-gallery--tight-bottom">\n'
            f"{tags}\n</section>"
        )

    return {
        "caseHeroSrc": root + case["hero"][0],
        "caseHeroAlt": case["hero"][1],
        "caseTask": case["task"],
        "caseSolution": case["solution"],
        "caseGallery": "\n\n".join(rows),
    }


def build_case_cards(page: dict, cases: dict, key: str = "caseList") -> str:
    """Render `caseList` — the ids of the cases a page shows — into cards.

    The case registry in pages.json is the single place where a case's title,
    cover, tags and metric live. A page only names the ids it needs, so the
    same case shown on several pages cannot drift apart.

    Paths in the registry are written from the site root; `root` on the page
    turns them into links that work from that page's depth.
    """
    ids = page.get(key)
    if not ids:
        return ""

    root = page.get("root", "./")
    with_niche = page.get("caseNiche")  # only the filtered catalogue needs it
    # the catalogue is driven by the filter, so it opts out of the reveal animation
    reveal = "" if with_niche else " reveal"
    template = (PARTIALS / "case-card.html").read_text(encoding="utf-8").rstrip("\n")

    cards = []
    for case_id in ids:
        if case_id not in cases:
            raise SystemExit(
                f"[render_partials] unknown case id '{case_id}' in {page['path']}"
            )
        case = cases[case_id]
        chips = "".join(f'<span class="chip">{c}</span>' for c in case["chips"])
        values = {
            "caseHref": root + case["path"],
            "caseCover": root + case["cover"],
            "caseAlt": case["alt"],
            "caseChips": chips,
            "caseTitle": case["title"],
            "caseDesc": case["desc"],
            # метрика необязательна: не у каждой работы есть честная цифра,
            # а придуманная хуже, чем никакой
            "caseMetric": (
                '\n    <span class="pcase__metric">'
                f'<b>{case["metricValue"]}</b><span>{case["metricLabel"]}</span></span>'
                if case.get("metricValue") else ""
            ),
            "caseNiche": f' data-niche="{case["niche"]}"' if with_niche else "",
            "caseReveal": reveal,
        }
        cards.append(PLACEHOLDER.sub(lambda m: values[m.group(1)], template))

    return "\n".join(cards)


def expand_includes(template: str, name: str, seen: tuple[str, ...] = ()) -> str:
    """Expand `{{> other-partial }}` so components can be composed of components.

    The include keeps the indentation of the line it sits on, so nested markup
    stays readable in the generated pages.
    """
    if name in seen:
        raise SystemExit(
            "[render_partials] circular include: " + " -> ".join(seen + (name,))
        )

    def replace(match: re.Match) -> str:
        indent, included = match.group("indent"), match.group("name")
        path = PARTIALS / f"{included}.html"
        if not path.exists():
            raise SystemExit(
                f"[render_partials] component '{name}': unknown include '{included}'"
            )
        body = expand_includes(
            path.read_text(encoding="utf-8").rstrip("\n"), included, seen + (name,)
        )
        return indent_block(body, indent)

    return INCLUDE.sub(replace, template)


def render_component(name: str, data: dict) -> str:
    template = (PARTIALS / f"{name}.html").read_text(encoding="utf-8").rstrip("\n")
    template = expand_includes(template, name)

    missing: list[str] = []

    def substitute(match: re.Match) -> str:
        key = match.group(1)
        if key not in data:
            missing.append(key)
            return match.group(0)
        value = str(data[key])
        if "\n" not in value:
            return value
        # Многострочное значение: продолжения надо отбить так же, как отбита
        # строка с плейсхолдером, иначе первая строка встаёт по месту, а все
        # следующие уезжают влево. На вложенных партиалах это особенно заметно.
        line_start = template.rfind("\n", 0, match.start()) + 1
        indent = template[line_start:match.start()]
        if indent.strip():
            return value
        return value.replace("\n", "\n" + indent)

    rendered = PLACEHOLDER.sub(substitute, template)
    if missing:
        raise SystemExit(
            f"[render_partials] component '{name}': missing keys in pages.json: "
            + ", ".join(sorted(set(missing)))
        )
    return rendered


def indent_block(block: str, indent: str) -> str:
    lines = block.split("\n")
    return "\n".join(indent + line if line.strip() else line for line in lines)


def apply_component(html: str, name: str, rendered: str, page_path: str) -> str:
    pattern = re.compile(
        r"(?P<indent>[ \t]*)(?P<open><!--\s*component:" + re.escape(name) + r"\s*-->)"
        r".*?"
        r"(?P<close><!--\s*/component:" + re.escape(name) + r"\s*-->)",
        re.DOTALL,
    )

    match = pattern.search(html)
    if not match:
        raise SystemExit(
            f"[render_partials] {page_path}: no slot for component '{name}'. "
            f"Add:\n    <!-- component:{name} -->\n    <!-- /component:{name} -->"
        )

    indent = match.group("indent")
    body = indent_block(rendered, indent)
    replacement = f"{indent}{match.group('open')}\n{body}\n{indent}{match.group('close')}"
    return html[: match.start()] + replacement + html[match.end() :]


# Слот с атрибутами — это компонент, который встречается на странице много раз
# с разными значениями: `<!-- component:ilink text="Подробнее" href="about.html" -->`.
# Обычные слоты без атрибутов остаются как были: один на страницу, значения из
# pages.json. Здесь значения приходят прямо из разметки, потому что у каждой
# ссылки свой текст, и держать их в манифесте было бы дальше от места правки.
INLINE_SLOT = re.compile(
    # атрибуты обязательны: слот без них — обычный блочный компонент
    r'(?P<open><!--\s*component:(?P<name>[a-z0-9-]+)\s+'
    r'(?P<attrs>[a-zA-Z][\w-]*="[^"]*"[^>]*?)\s*-->)'
    r'.*?'
    r'<!--\s*/component:(?P=name)\s*-->',
    re.DOTALL,
)
ATTR = re.compile(r'(?P<key>[a-zA-Z][\w-]*)="(?P<value>[^"]*)"')


def apply_inline_components(html: str, page_path: str) -> str:
    def render(match: "re.Match[str]") -> str:
        name = match.group("name")
        template_file = PARTIALS / f"{name}.html"
        if not template_file.exists():
            raise SystemExit(
                f"[render_partials] {page_path}: no partial for inline component '{name}'"
            )
        values = {m.group("key"): m.group("value") for m in ATTR.finditer(match.group("attrs"))}
        # ссылка получает <a href>, всё остальное — нейтральный <span>
        values["tag"] = "a" if values.get("href") else "span"
        values["href"] = f' href="{values["href"]}"' if values.get("href") else ""
        template = template_file.read_text(encoding="utf-8").strip("\n")

        def sub(m: "re.Match[str]") -> str:
            key = m.group(1)
            if key not in values:
                raise SystemExit(
                    f"[render_partials] {page_path}: component '{name}' needs "
                    f'attribute {key}="..." on its slot'
                )
            return values[key]

        body = PLACEHOLDER.sub(sub, template)
        return f'{match.group("open")}{body}<!-- /component:{name} -->'

    return INLINE_SLOT.sub(render, html)


# Потолки для картинок. Пережимать молча нельзя — это работы автора, и потеря
# качества дороже сэкономленных килобайт (проверено: пережатие до бюджета
# по КБ/Мпикс роняло PSNR ниже 40 дБ, разница видна). Поэтому сборка не трогает
# файлы, а не даёт положить в репозиторий заведомо тяжёлую картинку.
MAX_WIDTH = 2200          # шире не нужно даже на retina
MAX_KB = 260              # потолок веса одного файла


def image_size(path: Path):
    """Размеры картинки без сторонних библиотек."""
    raw = path.read_bytes()
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        fmt = raw[12:16]
        if fmt == b"VP8X":
            return (int.from_bytes(raw[24:27], "little") + 1,
                    int.from_bytes(raw[27:30], "little") + 1)
        if fmt == b"VP8 ":
            i = raw.find(b"\x9d\x01\x2a")
            if i > 0:
                return (int.from_bytes(raw[i+3:i+5], "little") & 0x3FFF,
                        int.from_bytes(raw[i+5:i+7], "little") & 0x3FFF)
        if fmt == b"VP8L":
            v = int.from_bytes(raw[21:25], "little")
            return ((v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1)
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return (int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big"))
    if raw[:2] == b"\xff\xd8":
        i = 2
        while i < len(raw) - 9:
            if raw[i] != 0xFF:
                i += 1
                continue
            m = raw[i+1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3):
                return (int.from_bytes(raw[i+7:i+9], "big"),
                        int.from_bytes(raw[i+5:i+7], "big"))
            i += 2 + int.from_bytes(raw[i+2:i+4], "big")
    return None


def check_images() -> list:
    """Картинки, которые нельзя отдавать как есть."""
    bad = []
    for f in sorted((SITE / "assets").rglob("*")):
        if f.suffix.lower() not in (".webp", ".jpg", ".jpeg", ".png"):
            continue
        if "_archive" in f.parts:
            continue
        kb = f.stat().st_size / 1024
        rel = f.relative_to(SITE)
        size = image_size(f)
        if size and size[0] > MAX_WIDTH:
            bad.append(f"{rel} — ширина {size[0]} px, потолок {MAX_WIDTH}")
        if kb > MAX_KB:
            bad.append(f"{rel} — {kb:.0f} КБ, потолок {MAX_KB} КБ")
    return bad


def main() -> int:
    check_only = "--check" in sys.argv
    manifest = load_manifest()
    defaults = manifest.get("defaults", {})
    cases = manifest.get("cases", {})
    directions = manifest.get("directions", {})

    VERSIONS = asset_versions()
    changed: list[str] = []

    for page in manifest["pages"]:
        page_path = page["path"]
        ensure_case_page(page)
        target = SITE / page_path
        if not target.exists():
            raise SystemExit(f"[render_partials] missing page: {page_path}")

        data = {
            **defaults,
            **page,
            **build_case_slots(page, cases),
            **build_home_cases(page, cases),
            **build_directions(page, directions),
            **build_metrics(page, manifest.get("metrics", {})),
            **build_services(page, directions),
            **build_case_intro(page, cases),
            **build_case_body(page, cases),
            **seo_fields(page),
        }
        original = target.read_text(encoding="utf-8")
        html = original

        # аналитика — не в списке components каждой страницы, а обязательна для
        # всех: если появится новая страница со слотом analytics в <head>, она
        # получит счётчики без единой правки в её собственном списке компонентов.
        # Если слота нет — сборка падает явной ошибкой, а не молча пропускает.
        components = ["seo", "analytics", *page.get("components", [])]
        for component in components:
            html = apply_component(html, component, render_component(component, data), page_path)

        # слоты с атрибутами обрабатываются после блочных: они могут стоять
        # и внутри отрендеренного компонента, и прямо в странице
        html = apply_inline_components(html, page_path)

        # отложенная загрузка для всего, что ниже первого экрана
        html = lazy_images(html)

        # размеры — из самих файлов, чтобы верстка не прыгала при загрузке
        html = image_dimensions(html, page_path)

        # версии стилей, скрипта и иконки — от содержимого, а не вручную
        html = ASSET_LINK.sub(
            lambda m: f'{m.group(1)}?v={VERSIONS[m.group(1).rsplit("/", 1)[1]]}{m.group(2)}',
            html,
        )

        # Плейсхолдеры подставляются только внутри слотов компонентов. Если
        # `{{ключ}}` написан прямо в теле страницы, он молча уезжает в вёрстку
        # и виден читателю — так на web.html в продакшен ушло «CV: {{...}}».
        leftover = sorted(set(PLACEHOLDER.findall(html)))
        if leftover:
            raise SystemExit(
                f"[render_partials] {page_path}: незаменённые плейсхолдеры в разметке: "
                + ", ".join("{{" + k + "}}" for k in leftover)
                + ". Значения подставляются только внутри слотов компонентов."
            )

        if html != original:
            changed.append(page_path)
            if not check_only:
                target.write_text(html, encoding="utf-8")

    # robots.txt и sitemap.xml — сгенерированы из того же manifest['pages'],
    # поэтому список страниц физически не может разъехаться с тем, что
    # реально есть на сайте.
    for name, content in (
        ("robots.txt", build_robots(manifest["pages"])),
        ("sitemap.xml", build_sitemap(manifest["pages"])),
    ):
        target = SITE / name
        original = target.read_text(encoding="utf-8") if target.exists() else ""
        if content != original:
            changed.append(name)
            if not check_only:
                target.write_text(content, encoding="utf-8")

    heavy = check_images()
    if heavy:
        print("[render_partials] картинки сверх потолка:")
        for line in heavy:
            print(f"  - {line}")
        print("  пережать вручную и сверить качество, молча сборка не трогает")
        return 1

    if check_only:
        if changed:
            print("[render_partials] out of date:")
            for path in changed:
                print(f"  - {path}")
            return 1
        print(f"[render_partials] all {len(manifest['pages'])} pages up to date")
        return 0

    if changed:
        print(f"[render_partials] updated {len(changed)} page(s):")
        for path in changed:
            print(f"  - {path}")
    else:
        print(f"[render_partials] no changes ({len(manifest['pages'])} pages checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
