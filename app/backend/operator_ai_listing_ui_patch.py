#!/usr/bin/env python3
"""Append operator-only AI assistance after legacy puppy page transformations."""
from pathlib import Path
page=Path(__file__).resolve().parents[1]/"breeder-puppy-new.html"
html=page.read_text(encoding="utf-8")
marker="OPERATOR_AI_LISTING_UI_V1"
if marker not in html:
    old="</body>"
    assert html.count(old)==1, "OPERATOR_AI_UI_INSTALL_FAILED"
    html=html.replace(old,
      '<!-- '+marker+' --><script src="assets/operator-ai-listing.js"></script></body>',1)
    page.write_text(html,encoding="utf-8")
print("OPERATOR_AI_UI_OK|operator_only=1|photos=existing_ten_limit|review_before_publish=1",flush=True)
