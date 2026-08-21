#!/usr/bin/env python3
"""Re-export both CVs from Google Docs into assets/cv as PDF.

The site links to local PDFs, not to Google: a local file opens for everyone,
needs no Google account, survives a change of sharing settings and gets served
from the same domain as the site. The price is that the file can go stale, so
this script pulls the current version straight from the document.

Run it whenever a CV is edited, and always before deploying.

Usage:
    python3 tools/refresh_cv.py           # download and overwrite
    python3 tools/refresh_cv.py --check   # report only, exit 1 if a file differs
"""

from __future__ import annotations

import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
CV_DIR = SITE / "assets" / "cv"

# doc id -> target file name. Both documents must stay shared as
# "anyone with the link — viewer", otherwise the export returns HTML.
DOCS = {
    "1rUtABdOX2A04D0rRUPDJjVK-F6mXRVKx": "lana-svitla-cv-product-designer.pdf",
    "1Tq7ogEq4cgxMjYaAJFJutYDRs6x-64rj": "lana-svitla-cv-brand-designer.pdf",
}

EXPORT = "https://docs.google.com/document/d/{doc_id}/export?format=pdf"


def fetch(doc_id: str) -> bytes:
    with urllib.request.urlopen(EXPORT.format(doc_id=doc_id), timeout=60) as response:
        data = response.read()
    # a doc that lost its sharing setting answers with a sign-in page, not a PDF
    if not data.startswith(b"%PDF"):
        raise ValueError("ответ не PDF — проверьте, открыт ли документ по ссылке")
    return data


def main() -> int:
    check = "--check" in sys.argv
    stale: list[str] = []

    for doc_id, name in DOCS.items():
        path = CV_DIR / name
        try:
            data = fetch(doc_id)
        except (urllib.error.URLError, ValueError) as error:
            print(f"[cv] не удалось скачать {name}: {error}")
            return 1

        current = path.read_bytes() if path.exists() else b""
        if hashlib.sha256(data).digest() == hashlib.sha256(current).digest():
            print(f"[cv] {name} — актуален ({len(data)} байт)")
            continue

        stale.append(name)
        if check:
            print(f"[cv] {name} — устарел")
        else:
            path.write_bytes(data)
            print(f"[cv] {name} — обновлен ({len(current)} -> {len(data)} байт)")

    if check and stale:
        print("[cv] нужен прогон: python3 tools/refresh_cv.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
