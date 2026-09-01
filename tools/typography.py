#!/usr/bin/env python3
"""Apply the site's Russian typography rules to HTML text nodes.

Rules (see site_decisions.md):
  1. em dash → en dash
  2. "ё" → "е"
  3. short prepositions/conjunctions are glued to the next word with &nbsp;

Only text between tags is touched: attributes, <script>, <style> and <svg>
are left alone. Running it twice changes nothing.

Usage:
    python3 tools/typography.py           # write
    python3 tools/typography.py --check   # report only, exit 1 if work is due
"""

from __future__ import annotations

import json
from collections import OrderedDict
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]

def partials() -> list:
    """Все партиалы, без списка руками.

    Список подвёл дважды: сначала со страницами, потом с партиалами — реплика
    сайта Verba Mayr осталась без типографики, и сборка зациклилась, потому что
    страницу правили, а источник нет. Партиал без текста правило просто не
    заденет, так что перечислять «где есть текст» незачем.
    """
    root = SITE / "partials"
    return sorted(str(f.relative_to(SITE)) for f in root.glob("*.html"))


def targets() -> list:
    """Страницы берём из реестра, а не из списка в этом файле.

    Список руками уже подвёл однажды: новая страница кейса собралась, но
    осталась без типографики, потому что её забыли сюда вписать, и обе
    сборки при этом отчитались, что всё чисто.
    """
    manifest = json.loads((SITE / "tools/pages.json").read_text(encoding="utf-8"))
    # Здесь только страницы основного языка: их текст лежит прямо в файлах.
    # Английский и украинский текст живёт в словарях перевода, поэтому им
    # занимается fix_dicts() — правка в словаре расходится по всем страницам
    # языка сама, а файл, набранный заново, её не теряет.
    pages = [p["path"] for p in manifest["pages"] if p.get("lang", "ru") == "ru"]
    return pages + partials()


TARGETS = None  # заполняется в main(); прямых обращений быть не должно

SHORT = [
    "и", "а", "в", "о", "у", "к", "с", "я", "же", "ли", "бы", "но",
    "на", "за", "по", "до", "от", "из", "об", "со", "во", "не", "ни",
    "то", "что", "как", "или", "для", "при", "над", "под", "без", "про",
]

# Короткие слова по языкам: висеть в конце строки им не положено нигде,
# но список у каждого языка свой. Английский добавляет артикли и «I»,
# украинский — свои прийменники.
SHORT_BY_LANG = {
    "ru": SHORT,
    "en": [
        "a", "an", "the", "I", "in", "on", "at", "to", "of", "by", "up",
        "as", "or", "and", "for", "is", "it", "no", "so", "we",
    ],
    "uk": [
        "і", "й", "у", "в", "з", "зі", "із", "та", "до", "на", "за", "по",
        "від", "під", "над", "без", "про", "для", "як", "що", "або",
        "не", "ні", "а", "о", "це", "ще",
    ],
}

# skip anything inside these elements entirely
SKIP_BLOCKS = re.compile(r"<(script|style|svg)\b[\s\S]*?</\1>", re.I)
# a run of text sitting between two tags
TEXT_NODE = re.compile(r">([^<>]+)<")
SHORT_WORD = re.compile(
    r"(?<![\w&])(" + "|".join(SHORT) + r")(\s+)(?=[«\"(]?[А-Яа-яЁёA-Za-z0-9])",
    re.IGNORECASE,
)


def short_word_re(lang: str) -> re.Pattern:
    words = sorted(SHORT_BY_LANG[lang], key=len, reverse=True)
    return re.compile(
        r"(?<![\w&])(" + "|".join(words) + r")(\s+)(?=[«\"(]?[А-Яа-яЁёІіЇїЄєҐґA-Za-z0-9])",
        re.IGNORECASE,
    )


# Число и то, что оно считает, не разрывают: «6 inner pages», «300 dpi».
NUMBER_UNIT = re.compile(r"(?<![\w&])(\d+)(\s+)(?=[A-Za-zА-Яа-яІіЇїЄєҐґ])")
# Амперсанд в «Web & digital» не должен уезжать на свою строку один.
AMPERSAND = re.compile(r"\s+(&amp;|&(?!\w+;))\s+")


# <!-- component:ilink text="…" --> — видимая надпись, а не служебное поле
SLOT_TEXT = re.compile(r'(<!--\s*component:[a-z0-9-]+[^>]*?\stext=")([^"]+)(")')


def fix_text(text: str, lang: str = "ru") -> str:
    text = text.replace("—", "–")
    if lang == "ru":
        # правило автора: буквы «ё» на сайте нет
        text = text.replace("ё", "е").replace("Ё", "Е")
    text = NUMBER_UNIT.sub(lambda m: f"{m.group(1)}&nbsp;", text)
    text = AMPERSAND.sub(lambda m: f"&nbsp;{m.group(1)}&nbsp;", text)
    return short_word_re(lang).sub(lambda m: f"{m.group(1)}&nbsp;", text)


def process(html: str, lang: str = "ru") -> str:
    # carve out script/style/svg so their contents are never rewritten
    holes: list[str] = []

    def stash(match: re.Match) -> str:
        holes.append(match.group(0))
        return f"\x00{len(holes) - 1}\x00"

    guarded = SKIP_BLOCKS.sub(stash, html)
    guarded = TEXT_NODE.sub(lambda m: ">" + fix_text(m.group(1), lang) + "<", guarded)
    # текст инлайн-слота живёт в атрибуте: на странице он станет видимым
    # текстом, и без этой строки сборка и типографика правили его по кругу
    guarded = SLOT_TEXT.sub(
        lambda m: m.group(1) + fix_text(m.group(2), lang) + m.group(3), guarded
    )
    return re.sub(r"\x00(\d+)\x00", lambda m: holes[int(m.group(1))], guarded)


# Поля реестра, попадающие на страницу текстом. Остальное — пути, ключи,
# классы — трогать нельзя.
# «type» сюда не входит: это служебное значение для фильтра, а не текст.
REGISTRY_TEXT = ("title", "desc", "alt", "task", "solution", "name", "chips",
                 "expertise", "stepsCaption",
                 "metricLabel", "pageTitle", "description", "ogTitle")


def fix_registry() -> bool:
    """Приводит тексты в реестре к той же форме, что и на страницах.

    Иначе выходит петля: пишешь текст в реестр, сборка ставит его на страницу,
    типографика правит страницу, а реестр остаётся прежним — и следующая сборка
    возвращает всё назад. Раньше это разбиралось руками после каждой правки
    текста; теперь реестр правится здесь, в одном месте с самими правилами.
    """
    f = SITE / "tools/pages.json"
    raw = f.read_text(encoding="utf-8")
    data = json.loads(raw)

    def walk(node, key=None):
        if isinstance(node, dict):
            return {k: walk(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, key) for v in node]
        if isinstance(node, str) and key in REGISTRY_TEXT:
            return fix_text(node)
        return node

    # Подписи в meta и gallery лежат парами [ключ, значение] без имени поля.
    # Ключи создавать нельзя: у авторских кейсов их нет, и пустой gallery
    # заставил бы сборку считать такой кейс шаблонным.
    for case in data.get("cases", {}).values():
        if "meta" in case:
            case["meta"] = [[a, fix_text(b)] for a, b in case["meta"]]
        # hero — пара [файл, подпись]: править можно только вторую половину
        if len(case.get("hero", [])) == 2:
            case["hero"] = [case["hero"][0], fix_text(case["hero"][1])]
        if "gallery" in case:
            case["gallery"] = [[[src, fix_text(alt)] for src, alt in row]
                               for row in case["gallery"]]

    fixed = json.dumps(walk(data), ensure_ascii=False, indent=2) + "\n"
    if fixed != raw:
        f.write_text(fixed, encoding="utf-8")
        return True
    return False


def norm_key(text: str) -> str:
    """Ключ без типографских тонкостей — по нему словари и сверяются."""
    return " ".join(text.replace("&nbsp;", " ").replace("\u00a0", " ")
                        .replace("–", "—").split())


def source_strings() -> dict:
    """Все русские строки, какие сейчас стоят на страницах и в реестре.

    Нужны, чтобы ключи словарей выглядели ровно так же. Иначе выходит, что
    en.json хранит ключ без неразрывных пробелов, uk.json — с ними, оба
    работают только благодаря нормализации, а глазами их уже не сверить.
    """
    found = {}
    for name in targets():
        html = (SITE / name).read_text(encoding="utf-8")
        clean = SKIP_BLOCKS.sub("", html)
        chunks = TEXT_NODE.findall(clean)
        # подписи картинок живут в атрибутах, а переводятся так же, как текст
        chunks += re.findall(r'(?:alt|title|aria-label|content)="([^"]+)"', clean)
        for chunk in chunks:
            text = chunk.strip()
            if text:
                found.setdefault(norm_key(text), text)
    data = json.loads((SITE / "tools/pages.json").read_text(encoding="utf-8"))

    def walk(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and key in REGISTRY_TEXT:
            found.setdefault(norm_key(node), node)

    walk(data)
    return found


def fix_dicts(check: bool = False) -> list:
    """Правит переводы в словарях по правилам их собственного языка.

    Английский и украинский текст на страницы попадает только отсюда, поэтому
    и типографика ему нужна здесь: страницу языковой версии набирают заново
    из основной, и правка, сделанная в файле, не пережила бы пересборку.
    Ключи — русские исходники — не трогаем, по ним идёт поиск.
    """
    changed = []
    canon = source_strings()
    for f in sorted((SITE / "tools/i18n").glob("*.json")):
        lang = f.stem.split("-")[0]
        if lang not in SHORT_BY_LANG or lang == "ru":
            continue
        raw = f.read_text(encoding="utf-8")
        data = json.loads(raw, object_pairs_hook=OrderedDict)
        fixed = OrderedDict()
        for k, v in data.items():
            key = canon.get(norm_key(k), k)
            if key in fixed:
                continue  # два написания одной строки — держим одно
            fixed[key] = fix_text(v, lang) if isinstance(v, str) else v
        out = json.dumps(fixed, ensure_ascii=False, indent=2) + "\n"
        if out != raw:
            changed.append(f.name)
            if not check:
                f.write_text(out, encoding="utf-8")
    return changed


def main() -> int:
    global TARGETS
    check = "--check" in sys.argv
    pending: list[str] = []
    TARGETS = targets()

    # реестр правим до страниц: иначе сборка тут же вернёт старую форму
    if fix_registry():
        print("[typography] тексты в реестре приведены к правилам")

    touched = fix_dicts(check)
    if touched:
        print("[typography] словари перевода: " + ", ".join(touched))

    for name in TARGETS:
        path = SITE / name
        if not path.exists():
            print(f"[typography] missing: {name}")
            return 1
        original = path.read_text(encoding="utf-8")
        fixed = process(original)
        if fixed != original:
            pending.append(name)
            if not check:
                path.write_text(fixed, encoding="utf-8")

    if check:
        if pending:
            print("[typography] needs a pass:")
            for name in pending:
                print(f"  - {name}")
            return 1
        print(f"[typography] all {len(TARGETS)} files clean")
        return 0

    print(f"[typography] updated {len(pending)} file(s)" if pending
          else f"[typography] no changes ({len(TARGETS)} files checked)")
    for name in pending:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
