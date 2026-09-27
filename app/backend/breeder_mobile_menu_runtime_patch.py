from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = '<script src="/mobile-global-nav.js?v=20260927m4"></script><script src="/attention-alerts.js?v=20260927a2"></script>'

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
for path in ROOT.glob('*.html'):
    text = path.read_text(encoding='utf-8')
    if '/mobile-global-nav.js' in text:
        skipped.append(path.name)
        continue
    if '</body>' not in text:
        skipped.append(path.name + ':no-body')
        continue
    # Inject one shared mobile navigation and one shared attention-alert layer on every page.
    path.write_text(text.replace('</body>', TAG + '</body>', 1), encoding='utf-8')
    patched.append(path.name)

print('GLOBAL_MOBILE_MENU_OK|roles=public_buyer_breeder_operator|menu=hamburger_drawer|touch=enabled|alerts=red_badges|patched=' + str(len(patched)) + '|skipped=' + str(len(skipped)) + '|parent_health_ui_removed=' + str(parent_health_patched))
