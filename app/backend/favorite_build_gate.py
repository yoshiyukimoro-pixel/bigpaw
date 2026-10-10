"""Checks the fully transformed code inside the built BIG PAW Docker image."""
from pathlib import Path

s=Path('/app/backend/server.py').read_text(encoding='utf-8')
compile(s,'server.py','exec')
required=(
    "if path=='/api/breeder/engagement':",
    "if path=='/api/favorite-notifications/settings':",
    "queue_favorite_change(con,puppy_id,'photo'",
    'record_puppy_view(',
    'deliver_favorite_updates(db,PUBLIC_BASE_URL)',
)
for marker in required:
    assert marker in s,marker
admin=Path('/app/admin.html').read_text(encoding='utf-8')
assert 'favoriteCount' in admin and 'viewerCount' in admin
detail=Path('/app/puppy-detail.html').read_text(encoding='utf-8')
assert 'puppy-view-tracker.js' in detail
account=Path('/app/account.html').read_text(encoding='utf-8')
assert 'favoriteUpdateMail' in account
print('FEATURE_BUILD_MARKERS_OK')
