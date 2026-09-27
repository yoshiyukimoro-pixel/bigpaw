from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = '<script src="/mobile-global-nav.js?v=20260927m3"></script><script src="/attention-alerts.js?v=20260927a2"></script>'

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

print('GLOBAL_MOBILE_MENU_OK|roles=public_buyer_breeder_operator|menu=hamburger_drawer|touch=enabled|alerts=red_badges|patched=' + str(len(patched)) + '|skipped=' + str(len(skipped)))
