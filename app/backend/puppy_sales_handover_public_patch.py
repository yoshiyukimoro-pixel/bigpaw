#!/usr/bin/env python3
from pathlib import Path

ROOT=Path('/app')
page_path=ROOT/'puppy-detail.html'
s=page_path.read_text(encoding='utf-8')

tag='<script src="assets/puppy-sales-handover-public.js?v=20260928a"></script>'
legacy='<script src="assets/sales-handover-public.js"></script>'

# Protect the known-good gallery block byte-for-byte. This patch may only append
# one independent renderer script before </body>.
start_marker='<script id="bigpaw-detail-real-gallery-js">'
assert s.count(start_marker)==1, ('gallery_script_marker_count',s.count(start_marker))
start=s.index(start_marker)
end=s.index('</script>',start)+len('</script>')
gallery_before=s[start:end]
assert '#bigpawRealGallery' in gallery_before, 'gallery_root_marker_missing'
assert 'touchstart' in s and 'touchend' in s, 'gallery_swipe_markers_missing'

assert legacy not in s, 'legacy_breeder_renderer_must_not_be_loaded_on_puppy_detail'
if tag not in s:
    assert s.count('</body>')==1, ('body_close_count',s.count('</body>'))
    s=s.replace('</body>',tag+'</body>',1)

start2=s.index(start_marker)
end2=s.index('</script>',start2)+len('</script>')
gallery_after=s[start2:end2]
assert gallery_after==gallery_before, 'known_good_gallery_block_changed'
assert s.count(tag)==1, ('puppy_sales_handover_tag_count',s.count(tag))
assert 'touchstart' in s and 'touchend' in s, 'gallery_swipe_markers_lost'

page_path.write_text(s,encoding='utf-8')
print('PUPPY_SALES_HANDOVER_PUBLIC_OK|renderer=isolated|source=breeder_sales_handover_settings|gallery_core=byte_preserved|swipe_markers=preserved|photos=untouched',flush=True)
