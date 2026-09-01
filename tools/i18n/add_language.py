#!/usr/bin/env python3
"""Заводит языковую версию: записи страниц, файлы, отчёт о непереведённом.

Английскую версию я собирал полуручными скриптами и наступил на четыре
ошибки подряд: переписал ссылки, которые менять не следовало; заменил текст
по подстроке и испортил фразы; не заметил, что половина текста живёт в файлах
страниц; не увидел подписи кнопок в атрибутах слотов. Инструмент повторяет
только правильную часть.

  python3 tools/i18n/add_language.py uk          завести язык
  python3 tools/i18n/add_language.py uk --check  только отчёт, ничего не менять
"""
from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
REG = SITE / "tools/pages.json"
CYR = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")

# Ссылки со страницы на страницу внутри языка менять НЕЛЬЗЯ: дерево языка
# повторяет корень, поэтому относительный путь тот же. Меняется только путь
# к общим файлам — они лежат на уровень выше.
ASSET_HREF = re.compile(r'(href|src)="(?:\./)?((?:\.\./)*(?:assets|tools)/[^"]+)"')


def load() -> dict:
    return json.loads(REG.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)


def save(data: dict) -> None:
    REG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_entries(data: dict, lang: str) -> list:
    """Записи страниц для языка — по одной на каждую страницу основного языка."""
    base = [p for p in data["pages"] if p.get("lang", "ru") == "ru"]
    made = []
    for ru in base:
        path = f"{lang}/{ru['path']}"
        if any(p["path"] == path for p in data["pages"]):
            continue
        page = OrderedDict(ru)
        page["path"] = path
        page["lang"] = lang
        page["translationOf"] = ru["path"]
        page["root"] = ru.get("root", "") + "../"
        data["pages"].append(page)
        made.append(path)
    return made


def make_files(data: dict, lang: str, force: bool = False) -> int:
    """Создаёт файлы языковой версии из страниц основного языка.

    `force` пересоздаёт и существующие: нужен, когда правило путей изменилось.
    Переводы после этого надо накатить заново — они живут в словарях.
    """
    made = 0
    for page in data["pages"]:
        if page.get("lang") != lang:
            continue
        dst = SITE / page["path"]
        if dst.exists() and not force:
            continue
        src = SITE / page["translationOf"]
        html = ASSET_HREF.sub(r'\1="../\2"', src.read_text(encoding="utf-8"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(html, encoding="utf-8")
        made += 1
    return made


def own_markup(html: str) -> str:
    """Текст самой страницы — без содержимого слотов и скриптов."""
    html = re.sub(r"(<!--\s*component:([a-z0-9-]+)\s*-->).*?(<!--\s*/component:\2\s*-->)",
                  "", html, flags=re.S)
    return re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)


def report(data: dict, lang: str) -> dict:
    """Сводный отчёт: и строки компонентов, и тексты страниц в одном списке."""
    sys.path.insert(0, str(SITE / "tools"))
    import render_partials as rp

    rp.missing_translations.clear()
    rp.main()
    from_components = {k: sorted(v) for k, v in rp.missing_translations.get(lang, {}).items()}

    # Непереведённой считается строка, совпавшая с исходной страницей.
    # По алфавиту это не определить: украинский — та же кириллица, и проверка
    # «есть ли кириллица» объявляла верный украинский текст непереведённым.
    RU = re.compile(r"[А-Яа-яЁё]")
    # Часть слов збігається законно: «Бренд», «Дизайн», «Структура», назви
    # і марки. Якщо рядок є у словнику — переклад зроблено, навіть коли він
    # дорівнює вихідному.
    known = set()
    f = SITE / f"tools/i18n/{lang}-pages.json"
    if f.is_file():
        known = {k for k in json.loads(f.read_text(encoding="utf-8")) if not k.startswith("_")}

    from_pages: dict = {}
    for page in data["pages"]:
        if page.get("lang") != lang:
            continue
        own = own_markup((SITE / page["path"]).read_text(encoding="utf-8"))
        src = own_markup((SITE / page["translationOf"]).read_text(encoding="utf-8"))
        src_text = set(x.strip() for x in re.findall(r">([^<>]+)<", src))
        src_text |= set(re.findall(r'(?:alt|aria-label|title)="([^"]+)"', src))
        src_text |= set(re.findall(r'component:[a-z0-9-]+[^>]*\btext="([^"]+)"', src))

        found = [x.strip() for x in re.findall(r">([^<>]+)<", own)]
        found += re.findall(r'(?:alt|aria-label|title)="([^"]+)"', own)
        found += re.findall(r'component:[a-z0-9-]+[^>]*\btext="([^"]+)"', own)
        for t in found:
            if t in src_text and RU.search(t) and t not in known:
                from_pages.setdefault(t, []).append(page["path"])

    return {"компоненты": from_components, "страницы": from_pages}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    lang = sys.argv[1]
    check = "--check" in sys.argv

    data = load()
    if not check:
        made = make_entries(data, lang)
        save(data)
        files = make_files(data, lang, force="--force" in sys.argv)
        print(f"[{lang}] записей страниц заведено: {len(made)}")
        print(f"[{lang}] файлов создано: {files}")

    left = report(data, lang)
    total = len(left["компоненты"]) + len(left["страницы"])
    print()
    print(f"[{lang}] СВОДНЫЙ ОТЧЁТ: строк без перевода {total}")
    print(f"  из компонентов и реестра: {len(left['компоненты'])} "
          f"→ tools/i18n/{lang}.json")
    print(f"  из текстов страниц:       {len(left['страницы'])} "
          f"→ tools/i18n/{lang}-pages.json")

    out = SITE / f"tools/i18n/{lang}-todo.json"
    out.write_text(json.dumps(left, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  полный список: {out.relative_to(SITE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
