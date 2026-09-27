from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = '<script src="/breeder-mobile-nav.js?v=20260927m1"></script>'
TARGETS = [
    'admin.html',
    'breeder-puppy-new.html',
    'breeder-inquiries.html',
    'breeder-deal-report.html',
    'breeder-billing.html',
    'breeder-invoice.html',
    'breeder-fees.html',
    'breeder-profile-edit.html',
    'parent-dogs.html',
    'health-records.html',
    'messages.html',
    'online-visit.html',
    'visit-confirm.html',
    'deal.html',
    'reservation.html',
    'contract.html',
    'pickup.html',
    'review.html',
    'report.html',
    'breeder-fee-agreement.html',
]

patched = []
missing = []
for name in TARGETS:
    path = ROOT / name
    if not path.exists():
        missing.append(name)
        continue
    text = path.read_text(encoding='utf-8')
    if '/breeder-mobile-nav.js' in text:
        continue
    if '</body>' not in text:
        missing.append(name + ':no-body')
        continue
    path.write_text(text.replace('</body>', TAG + '</body>', 1), encoding='utf-8')
    patched.append(name)

print('BREEDER_MOBILE_MENU_OK|menu=hamburger_drawer|touch=enabled|pages=' + str(len(TARGETS)) + '|patched=' + str(len(patched)) + '|missing=' + str(len(missing)))
