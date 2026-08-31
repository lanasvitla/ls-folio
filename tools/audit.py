#!/usr/bin/env python3
"""Проверка собранного сайта по списку, который лежит здесь, а не в памяти.

Каждый раз, когда что-то находится вручную, сюда добавляется проверка — тогда
одна и та же ошибка не может вернуться незамеченной. Список открытый: пустой
результат значит «прошли все проверки, которые здесь описаны», а не «всё
хорошо вообще».

  python3 tools/audit.py          отчёт
  python3 tools/audit.py --strict любая находка роняет запуск
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
IMG = re.compile(r"<img\b[^>]*>")
RASTER = (".webp", ".jpg", ".jpeg", ".png")

# Осознанно принятые решения. Лежат здесь, а не в переписке: иначе на каждом
# аудите я снова предлагаю то, от чего уже отказались.
ACCEPTED = [
    ("CSS и JS не минифицируются",
     "172 КБ на двоих и один раз, дальше из кэша. Минификация развела бы "
     "исходник с отдаваемым файлом ради экономии, которой никто не заметит. "
     "Решено 31.08.2026."),
    ("работы вышивки идут по 300–460 КБ на мегапиксель",
     "пережимал под бюджет — PSNR падал до 32 дБ, на плотной вышивке разница "
     "видна. Качество работ дороже килобайтов. Решено 31.08.2026."),
    ("lana-svitla-portrait-hover.webp лежит неиспользованным",
     "68 КБ, оставлен намеренно до отдельного решения. Решено 31.08.2026."),
]

findings: list[tuple[str, str]] = []
checks: list[str] = []


def check(name):
    def wrap(fn):
        checks.append(name)
        fn.title = name
        return fn
    return wrap


def pages() -> list[str]:
    m = json.loads((SITE / "tools/pages.json").read_text(encoding="utf-8"))
    return [p["path"] for p in m["pages"]]


def page_images(html: str) -> list[str]:
    """Картинки страницы без пикселя аналитики: он невидим и не в счёт."""
    hidden = [(m.start(), m.end())
              for m in re.finditer(r"<noscript\b.*?</noscript>", html, re.S)]
    return [m.group(0) for m in IMG.finditer(html)
            if not any(a <= m.start() < b for a, b in hidden)]


@check("у каждой картинки есть width/height")
def dimensions():
    for p in pages():
        html = (SITE / p).read_text(encoding="utf-8")
        for tag in page_images(html):
            src = re.search(r'src="([^"]+)"', tag)
            if not src or src.group(1).lower().endswith(".svg"):
                continue
            if src.group(1).startswith(("http", "data:")):
                continue
            if "width=" not in tag:
                findings.append((p, f"нет width/height: {src.group(1)}"))


@check("у каждой картинки есть alt")
def alts():
    for p in pages():
        html = (SITE / p).read_text(encoding="utf-8")
        for tag in page_images(html):
            if "alt=" not in tag:
                src = re.search(r'src="([^"]+)"', tag)
                findings.append((p, f"нет alt: {src.group(1) if src else tag[:60]}"))


@check("первая картинка страницы грузится сразу, остальные отложены")
def lazy():
    for p in pages():
        imgs = page_images((SITE / p).read_text(encoding="utf-8"))
        if not imgs:
            continue
        if 'loading="lazy"' in imgs[0]:
            findings.append((p, "первая картинка отложена — тормозит первый экран"))
        late = [t for t in imgs[1:] if 'loading="lazy"' not in t]
        for tag in late:
            src = re.search(r'src="([^"]+)"', tag)
            findings.append((p, f"не отложена: {src.group(1) if src else '?'}"))


@check("нет картинок тяжелее 260 КБ и шире 2200 px")
def heavy():
    sys.path.insert(0, str(SITE / "tools"))
    from render_partials import image_size, MAX_KB, MAX_WIDTH
    for f in sorted((SITE / "assets").rglob("*")):
        if f.suffix.lower() not in RASTER or "_archive" in f.parts:
            continue
        kb = f.stat().st_size / 1024
        rel = f.relative_to(SITE)
        if kb > MAX_KB:
            findings.append((str(rel), f"{kb:.0f} КБ, потолок {MAX_KB}"))
        s = image_size(f)
        if s and s[0] > MAX_WIDTH:
            findings.append((str(rel), f"ширина {s[0]} px, потолок {MAX_WIDTH}"))


@check("нет картинок, на которые никто не ссылается")
def orphans():
    text = "\n".join((SITE / p).read_text(encoding="utf-8") for p in pages())
    text += (SITE / "tools/pages.json").read_text(encoding="utf-8")
    for j in (SITE / "assets/js").glob("*.js"):
        text += j.read_text(encoding="utf-8")
    text += (SITE / "assets/css/style.css").read_text(encoding="utf-8")
    for f in sorted((SITE / "assets").rglob("*")):
        if f.suffix.lower() not in RASTER or "_archive" in f.parts:
            continue
        if f.name not in text:
            findings.append((str(f.relative_to(SITE)),
                             f"не используется нигде, {f.stat().st_size/1024:.0f} КБ"))


@check("у каждой страницы есть title, description, canonical и og:image")
def meta():
    for p in pages():
        html = (SITE / p).read_text(encoding="utf-8")
        for what, pattern in (
            ("title", r"<title>[^<]+</title>"),
            ("description", r'name="description" content="[^"]+"'),
            ("canonical", r'rel="canonical" href="[^"]+"'),
            ("og:image", r'property="og:image" content="[^"]+"'),
        ):
            if not re.search(pattern, html):
                findings.append((p, f"нет {what}"))


@check("на страницу приходится ровно один заголовок первого уровня")
def single_h1():
    for p in pages():
        n = len(re.findall(r"<h1\b", (SITE / p).read_text(encoding="utf-8")))
        if n != 1:
            findings.append((p, f"заголовков первого уровня: {n}"))


@check("текст карточки и лид страницы кейса — один и тот же")
def lead_matches_card():
    m = json.loads((SITE / "tools/pages.json").read_text(encoding="utf-8"))
    for k, c in m["cases"].items():
        html = (SITE / c["path"]).read_text(encoding="utf-8")
        sub = re.search(r'case-hero__subtitle reveal">(.*?)</p>', html, re.S)
        if not sub:
            findings.append((c["path"], "не найден лид"))
        elif sub.group(1) != c["desc"]:
            findings.append((c["path"], f"лид разошёлся с карточкой ({k})"))


@check("версии файлов считаются от содержимого, а не пишутся руками")
def asset_versions_hashed():
    for p in pages():
        html = (SITE / p).read_text(encoding="utf-8")
        for m in re.finditer(r'(?:href|src)="([^"]+)\?v=([^"]*)"', html):
            if not re.fullmatch(r"[0-9a-f]{8}", m.group(2)):
                findings.append((p, f"версия проставлена руками: {m.group(1)}?v={m.group(2)}"))


@check("стили и шрифты приходят со своего домена")
def no_external_css():
    """Счётчики на чужих доменах — сознательный выбор, они здесь ни при чём.
    Речь только о том, что блокирует первую отрисовку: стили и шрифты."""
    for p in pages():
        html = (SITE / p).read_text(encoding="utf-8")
        for m in re.finditer(r'<link\b[^>]*>', html):
            tag = m.group(0)
            if 'rel="stylesheet"' not in tag and 'as="font"' not in tag:
                continue
            href = re.search(r'href="([^"]+)"', tag)
            if href and href.group(1).startswith(("http://", "https://", "//")):
                findings.append((p, f"внешний ресурс на пути к отрисовке: {href.group(1)}"))


def main() -> int:
    strict = "--strict" in sys.argv
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "title", None):
            fn()
    print(f"[audit] проверок в списке: {len(checks)}")
    for c in checks:
        print(f"  · {c}")
    print()
    print(f"[audit] принято как есть: {len(ACCEPTED)}")
    for what, why in ACCEPTED:
        print(f"  · {what}")
        print(f"      {why}")
    print()
    if not findings:
        print("[audit] находок нет")
        return 0
    print(f"[audit] находок: {len(findings)}")
    for where, what in findings:
        print(f"  - {where}: {what}")
    return 1 if strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
