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
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
PARTIALS = SITE / "partials"
MANIFEST = Path(__file__).with_name("pages.json")

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
INCLUDE = re.compile(r"(?P<indent>[ \t]*)\{\{>\s*(?P<name>[\w-]+)\s*\}\}")


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


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
    values.update({
        "switchItems": "\n".join(items),
        "otherDirections": "\n".join(others) + "\n" + star.format(mod="mid"),
        "directionName": d["name"],
        "directionProcess": root + d["process"],
        "directionCv": root + d["cv"],
        "directionCvLabel": d["cvLabel"],
    })
    return values


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
            "caseMetricValue": case["metricValue"],
            "caseMetricLabel": case["metricLabel"],
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
        return str(data[key])

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


def main() -> int:
    check_only = "--check" in sys.argv
    manifest = load_manifest()
    defaults = manifest.get("defaults", {})
    cases = manifest.get("cases", {})
    directions = manifest.get("directions", {})

    changed: list[str] = []

    for page in manifest["pages"]:
        page_path = page["path"]
        target = SITE / page_path
        if not target.exists():
            raise SystemExit(f"[render_partials] missing page: {page_path}")

        data = {
            **defaults,
            **page,
            **build_case_slots(page, cases),
            **build_home_cases(page, cases),
            **build_directions(page, directions),
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
