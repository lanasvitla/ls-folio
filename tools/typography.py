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

import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]

TARGETS = [
    "index.html", "portfolio.html", "about.html", "product.html", "brand.html",
    "process.html", "process-product.html", "process-brand.html", "contacts.html",
    "work/mark-n-post/index.html", "work/eqlio/index.html",
    "work/togas/index.html", "work/visual-brand-identity/index.html",
    "work/svitla-embroidery/index.html", "web.html", "404.html",
    "partials/site-header.html", "partials/site-footer.html",
    "partials/social-links.html", "partials/role-switch.html",
    "partials/process-switch.html", "partials/icons.html",
]

SHORT = [
    "и", "а", "в", "о", "у", "к", "с", "я", "же", "ли", "бы", "но",
    "на", "за", "по", "до", "от", "из", "об", "со", "во", "не", "ни",
    "то", "что", "как", "или", "для", "при", "над", "под", "без", "про",
]

# skip anything inside these elements entirely
SKIP_BLOCKS = re.compile(r"<(script|style|svg)\b[\s\S]*?</\1>", re.I)
# a run of text sitting between two tags
TEXT_NODE = re.compile(r">([^<>]+)<")
SHORT_WORD = re.compile(
    r"(?<![\w&])(" + "|".join(SHORT) + r")(\s+)(?=[«\"(]?[А-Яа-яЁёA-Za-z0-9])",
    re.IGNORECASE,
)


def fix_text(text: str) -> str:
    text = text.replace("—", "–")
    text = text.replace("ё", "е").replace("Ё", "Е")
    return SHORT_WORD.sub(lambda m: f"{m.group(1)}&nbsp;", text)


def process(html: str) -> str:
    # carve out script/style/svg so their contents are never rewritten
    holes: list[str] = []

    def stash(match: re.Match) -> str:
        holes.append(match.group(0))
        return f"\x00{len(holes) - 1}\x00"

    guarded = SKIP_BLOCKS.sub(stash, html)
    guarded = TEXT_NODE.sub(lambda m: ">" + fix_text(m.group(1)) + "<", guarded)
    return re.sub(r"\x00(\d+)\x00", lambda m: holes[int(m.group(1))], guarded)


def main() -> int:
    check = "--check" in sys.argv
    pending: list[str] = []

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
