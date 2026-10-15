#!/usr/bin/env python3
"""Append the no-cost ChatGPT field importer after existing page patches.

This patch intentionally leaves all legacy dog/photo/upload/health/save logic
untouched, and is used only for operator-assisted new listings.
"""
from pathlib import Path

page = Path(__file__).resolve().parents[1] / "breeder-puppy-new.html"
html = page.read_text(encoding="utf-8")
marker = "OPERATOR_CHATGPT_FREE_IMPORT_V1"
if marker not in html:
    assert html.count("</body>") == 1, "CHATGPT_FREE_IMPORT_UI_ANCHOR_MISSING"
    html = html.replace(
        "</body>",
        '<!-- ' + marker + ' --><script src="assets/operator-chatgpt-free-import.js"></script></body>',
        1,
    )
    page.write_text(html, encoding="utf-8")
print("CHATGPT_FREE_IMPORT_INSTALLED|operator_only=1|no_external_ai=1|review_required=1", flush=True)
