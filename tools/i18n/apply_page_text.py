#!/usr/bin/env python3
"""Подставляет перевод в тексты самих страниц языковой версии.

Тексты компонентов переводит сборка через словарь. Но у страницы есть и
собственная разметка — заголовки разделов, абзацы «Обо мне», шаги процесса.
Она живёт в файле языковой версии, и переводится один раз, здесь.

  python3 tools/i18n/apply_page_text.py en
"""
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
CYR = re.compile(r"[А-Яа-яЁё]")


def main() -> int:
    lang = sys.argv[1] if len(sys.argv) > 1 else "en"
    table = json.loads((SITE / f"tools/i18n/{lang}-pages.json").read_text(encoding="utf-8"))
    # Ключ без типографских тонкостей: неразрывный пробел и вид тире —
    # забота типографики, а не перевода.
    def norm(x):
        return " ".join(x.replace("&nbsp;", " ").replace("\u00a0", " ")
                         .replace("–", "—").split())

    table = {norm(k): v for k, v in table.items() if not k.startswith("_")}
    manifest = json.loads((SITE / "tools/pages.json").read_text(encoding="utf-8"))

    # Замена идёт по целому текстовому узлу, а не по подстроке. Иначе короткий
    # ключ вроде «Процесс» подменяется внутри длинной фразы, и получается
    # «Process подстраиваю под задачу» — так уже вышло.
    changed, left = 0, {}

    def swap(m):
        head, body, tail = m.group(1), m.group(2), m.group(3)
        key = norm(body)
        if key in table:
            return head + body.replace(body.strip(), table[key]) + tail
        return m.group(0)

    def swap_attr(m):
        attr, val = m.group(1), m.group(2)
        return f'{attr}="{table.get(norm(val), val)}"'

    for page in manifest["pages"]:
        if page.get("lang") != lang:
            continue
        f = SITE / page["path"]
        s = original = f.read_text(encoding="utf-8")
        s = re.sub(r"(>)([^<>]+)(<)", swap, s)
        s = re.sub(r'\b(alt|aria-label|title)="([^"]+)"', swap_attr, s)
        # подписи кнопок живут атрибутом внутри слота компонента:
        # <!-- component:ilink text="Подробнее" -->
        s = re.sub(r'(component:[a-z0-9-]+[^>]*\btext=")([^"]+)(")',
                   lambda m: m.group(1) + table.get(norm(m.group(2)), m.group(2)) + m.group(3), s)
        if s != original:
            f.write_text(s, encoding="utf-8")
            changed += 1
        own = re.sub(r"(<!--\s*component:([a-z0-9-]+)\s*-->).*?(<!--\s*/component:\2\s*-->)",
                     "", s, flags=re.S)
        own = re.sub(r"<(script|style)\b.*?</\1>", "", own, flags=re.S)
        src = re.sub(r"(<!--\s*component:([a-z0-9-]+)\s*-->).*?(<!--\s*/component:\2\s*-->)",
                     "", (SITE / page["translationOf"]).read_text(encoding="utf-8"), flags=re.S)
        src_text = set(x.strip() for x in re.findall(r">([^<>]+)<", src))
        for x in re.findall(r">([^<>]+)<", own):
            # непереведённое = совпавшее с исходником, а не «содержит кириллицу»
            if x.strip() in src_text and re.search(r"[А-Яа-яЁё]", x):
                left.setdefault(x.strip(), []).append(page["path"])

    print(f"[i18n] правлено файлов: {changed}")
    if left:
        print(f"[i18n] без перевода осталось фрагментов: {len(left)}")
        for k in sorted(left)[:10]:
            print(f"  - {k[:70]}")
    else:
        print("[i18n] русского текста в страницах не осталось")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
