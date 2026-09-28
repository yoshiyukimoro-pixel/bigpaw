from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent.parent
NAV_TAG = '<script src="/mobile-global-nav.js?v=20260928m6"></script>'
ALERT_TAG = '<script src="/attention-alerts.js?v=20260927a2"></script>'

# The parent photo enhancement script redraws parent cards after page load.
# Keep its photo/genetics features, but permanently remove the obsolete health summary box
# and the link to the disabled health-records page.
parent_photo = ROOT / 'assets' / 'parent-photo-adjust.js'
parent_health_patched = 0
if parent_photo.exists():
    text = parent_photo.read_text(encoding='utf-8')
    health_fact = '''<div class="fact"><span>健康情報</span><b>${esc(d.health_summary||'未登録')}</b></div>'''
    health_link = '''<a class="btn btn-sub btn-wide" style="margin-top:9px" href="health-records.html?parentDogId=${encodeURIComponent(d.id)}">健康・検査記録を見る</a>'''
    before = text
    text = text.replace(health_fact, '')
    text = text.replace(health_link, '')
    if text != before:
        parent_photo.write_text(text, encoding='utf-8')
        parent_health_patched = 1

patched = []
skipped = []
alert_excluded = []
for path in ROOT.glob('*.html'):
    text = path.read_text(encoding='utf-8')
    if '/mobile-global-nav.js' in text:
        skipped.append(path.name)
        continue
    if '</body>' not in text:
        skipped.append(path.name + ':no-body')
        continue

    # The public puppy detail gallery was stable before attention-alerts.js was
    # injected globally. Keep the shared mobile menu there, but do not run the
    # alert observer/network layer on the photo-detail page.
    tag = NAV_TAG
    if path.name != 'puppy-detail.html':
        tag += ALERT_TAG
    else:
        alert_excluded.append(path.name)

    path.write_text(text.replace('</body>', tag + '</body>', 1), encoding='utf-8')
    patched.append(path.name)

# Add the sales/handover renderer only after the global menu patch has finished.
# The dedicated patch verifies the known-good gallery JS block is byte-identical
# before and after the new script tag is appended.
runpy.run_path(str(ROOT / 'backend' / 'puppy_sales_handover_public_patch.py'), run_name='__main__')

# Keep the medical-cost UI change isolated from the photo/gallery code.
# This patch merges vaccine, microchip and health-exam display while enforcing
# microchip cost as included, and verifies the stable Safari gallery is unchanged.
runpy.run_path(str(ROOT / 'backend' / 'sales_handover_medical_merge_runtime_patch.py'), run_name='__main__')

# Refine only the public vaccine wording after the medical merge has completed.
# Saved settings and the known-good Safari gallery remain untouched.
runpy.run_path(str(ROOT / 'backend' / 'sales_handover_vaccine_copy_runtime_patch.py'), run_name='__main__')

# Separate reservation money from the remaining balance on public pages.
# Stored breeder settings remain unchanged and the stable Safari gallery stays byte-identical.
runpy.run_path(str(ROOT / 'backend' / 'sales_handover_reservation_balance_runtime_patch.py'), run_name='__main__')

# Keep breeder-only sales/handover settings visually in the breeder (blue) theme.
# This patch changes presentation and mobile-menu role detection only; save/data logic is preserved.
runpy.run_path(str(ROOT / 'backend' / 'breeder_handover_blue_theme_runtime_patch.py'), run_name='__main__')

# Allow a prospective breeder to begin from the breeder application page directly.
# It reuses the existing account/register/login/application APIs; only the verification
# email gets a breeder-flow return marker. Existing buyer registration remains unchanged.
runpy.run_path(str(ROOT / 'backend' / 'direct_breeder_signup_runtime_patch.py'), run_name='__main__')

print(
    'GLOBAL_MOBILE_MENU_OK|roles=public_buyer_breeder_operator|menu=hamburger_drawer|touch=enabled'
    '|alerts=red_badges|alert_excluded=' + ','.join(alert_excluded)
    + '|patched=' + str(len(patched)) + '|skipped=' + str(len(skipped))
    + '|parent_health_ui_removed=' + str(parent_health_patched)
)
