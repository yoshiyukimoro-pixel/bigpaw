#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'breeder-sales-handover.html'
NAV = ROOT / 'mobile-global-nav.js'

# This patch is presentation-only. Preserve the sales/handover save form and API code.
page = PAGE.read_text(encoding='utf-8')
protected_markers = [
    "fetch('/api/breeder/sales-handover-settings'",
    "method:'POST'",
    "id=\"saveBtn\"",
    "class=\"bigpaw-breeder-theme\"",
]
for marker in protected_markers:
    if marker not in page:
        raise RuntimeError('BREEDER_HANDOVER_BLUE_THEME_PROTECTED_MARKER_MISSING|' + marker)

style = '''<style id="bigpaw-breeder-handover-blue-theme">
body.bigpaw-breeder-theme{--ink:#405a73;--muted:#708397;--pink:#5f8fc3;--pink2:#e7f1fb;--cream:#f7fbff;--bg:#f3f8ff;--line:#d6e3f0;--card:#fff;--shadow:0 14px 40px rgba(67,101,138,.12);background:#f3f8ff!important;color:#405a73}
body.bigpaw-breeder-theme .card{border-color:#d6e3f0;box-shadow:0 6px 20px rgba(67,101,138,.08)}
body.bigpaw-breeder-theme .btn-main{background:linear-gradient(135deg,#5f8fc3,#7da9d4);color:#fff}
body.bigpaw-breeder-theme .btn-sub{border-color:#cbddeb;color:#426789}
body.bigpaw-breeder-theme .notice{background:#edf5ff;border-color:#c9dff2;color:#456987}
body.bigpaw-breeder-theme .field input,body.bigpaw-breeder-theme .field select,body.bigpaw-breeder-theme .field textarea{border-color:#d6e3f0}
body.bigpaw-breeder-theme .choice-row input,body.bigpaw-breeder-theme .org-item input{accent-color:#5f8fc3}
body.bigpaw-breeder-theme .success{background:#edf6ff;border-color:#bdd5eb;color:#315f89}
body.bigpaw-breeder-theme .savebar{background:rgba(243,248,255,.96)}
</style>'''

if 'id="bigpaw-breeder-handover-blue-theme"' not in page:
    if '</head>' not in page:
        raise RuntimeError('BREEDER_HANDOVER_BLUE_THEME_HEAD_MISSING')
    page = page.replace('</head>', style + '</head>', 1)
PAGE.write_text(page, encoding='utf-8')

# Make the global mobile menu recognize this page as a breeder page so its menu is blue too.
nav = NAV.read_text(encoding='utf-8')
old = "'/breeder-profile-edit.html','/parent-dogs.html','/breeder-fee-agreement.html'"
new = "'/breeder-profile-edit.html','/parent-dogs.html','/breeder-fee-agreement.html','/breeder-sales-handover.html'"
if old in nav:
    if nav.count(old) != 1:
        raise RuntimeError('BREEDER_HANDOVER_BLUE_THEME_NAV_MARKER_COUNT')
    nav = nav.replace(old, new, 1)
elif "'/breeder-sales-handover.html'" not in nav:
    raise RuntimeError('BREEDER_HANDOVER_BLUE_THEME_NAV_MARKER_MISSING')
NAV.write_text(nav, encoding='utf-8')

final_page = PAGE.read_text(encoding='utf-8')
final_nav = NAV.read_text(encoding='utf-8')
checks = {
    'blue_theme_style': 'id="bigpaw-breeder-handover-blue-theme"' in final_page,
    'blue_button': '#5f8fc3' in final_page,
    'blue_background': 'background:#f3f8ff!important' in final_page,
    'save_api_preserved': "fetch('/api/breeder/sales-handover-settings'" in final_page and "method:'POST'" in final_page,
    'save_button_preserved': 'id="saveBtn"' in final_page,
    'breeder_mobile_tone': "'/breeder-sales-handover.html'" in final_nav,
}
failed = [k for k,v in checks.items() if not v]
if failed:
    raise RuntimeError('BREEDER_HANDOVER_BLUE_THEME_FAIL|' + '|'.join(failed))

print('BREEDER_HANDOVER_BLUE_THEME_OK|page=blue|mobile_menu=breeder_blue|save_logic=preserved|data=untouched', flush=True)
