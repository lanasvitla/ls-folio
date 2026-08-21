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


def main() -> int:
    check_only = "--check" in sys.argv
    manifest = load_manifest()
    defaults = manifest.get("defaults", {})

    changed: list[str] = []

    for page in manifest["pages"]:
        page_path = page["path"]
        target = SITE / page_path
        if not target.exists():
            raise SystemExit(f"[render_partials] missing page: {page_path}")

        data = {**defaults, **page}
        original = target.read_text(encoding="utf-8")
        html = original

        for component in page.get("components", []):
            html = apply_component(html, component, render_component(component, data), page_path)

        if html != original:
            changed.append(page_path)
            if not check_only:
                target.write_text(html, encoding="utf-8")

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
