#!/usr/bin/env python3
from pathlib import Path

ROOT=Path('/app')
page_path=ROOT/'puppy-detail.html'
asset_path=ROOT/'assets'/'puppy-sales-handover-public.js'
gallery_path=ROOT/'assets'/'puppy-detail-stable-gallery.js'
s=page_path.read_text(encoding='utf-8')
asset=asset_path.read_text(encoding='utf-8')
gallery_before=gallery_path.read_text(encoding='utf-8')

tag='<script src="assets/puppy-sales-handover-public.js?v=20260928a"></script>'
legacy='<script src="assets/sales-handover-public.js"></script>'

# The renderer itself must stay independent and use the existing public breeder settings API.
assert 'お迎えについて' in asset, 'renderer_heading_missing'
assert '/sales-handover-settings' in asset, 'renderer_public_api_missing'
assert 'breederId' in asset, 'renderer_breeder_link_missing'
assert 'bigpawRealGallery' not in asset, 'renderer_must_not_touch_gallery'

# Safari's known-good gallery is a separate stable asset at runtime.
# This feature must never alter that file or its swipe handlers.
assert "stage.addEventListener('touchstart'" in gallery_before, 'stable_gallery_touchstart_missing'
assert "stage.addEventListener('touchend'" in gallery_before, 'stable_gallery_touchend_missing'
assert 'puppy-detail-stable-gallery.js' in s, 'stable_gallery_script_tag_missing'
assert 'puppy-detail-swipe-fix.js' not in s, 'legacy_swipe_fix_must_stay_removed'

assert legacy not in s, 'legacy_breeder_renderer_must_not_be_loaded_on_puppy_detail'
if tag not in s:
    assert s.count('</body>')==1, ('body_close_count',s.count('</body>'))
    s=s.replace('</body>',tag+'</body>',1)

assert gallery_path.read_text(encoding='utf-8')==gallery_before, 'known_good_gallery_asset_changed'
assert s.count(tag)==1, ('puppy_sales_handover_tag_count',s.count(tag))
assert 'puppy-detail-stable-gallery.js' in s, 'stable_gallery_script_tag_lost'

page_path.write_text(s,encoding='utf-8')
print('PUPPY_SALES_HANDOVER_PUBLIC_OK|renderer=isolated|source=breeder_sales_handover_settings|stable_gallery_asset=byte_preserved|swipe_handlers=preserved|photos=untouched',flush=True)
