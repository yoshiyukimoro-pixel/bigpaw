#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / 'assets' / 'puppy-detail-stable-gallery.js'
DETAIL = ROOT / 'puppy-detail.html'
MARKER = 'SAFARI_DETAIL_GALLERY_HARDENING_v1'
MEDIA_VERSION = '20260926safari1'
ASSET_VERSION = '20260926safari1'

g = GALLERY.read_text(encoding='utf-8')

if MARKER not in g:
    # Mark the runtime asset so this patch is idempotent.
    needle = "'use strict';\n"
    assert g.count(needle) == 1, ('strict_marker_count', g.count(needle))
    g = g.replace(needle, needle + f"// {MARKER}\n", 1)

    # Always cache-bust media URLs on iPhone/Safari as well. Previously mobile
    # preserved an older media URL/version, which could keep stale WebKit image
    # resources alive until website data was cleared.
    g, n = re.subn(r"const MEDIA_V='[^']+';", f"const MEDIA_V='{MEDIA_VERSION}';", g, count=1)
    assert n == 1, ('media_version_count', n)

    old_img = "const img=document.createElement('img');img.alt=(p&&p.breed?p.breed:'子犬')+'の写真';img.loading='eager';"
    new_img = old_img + "img.decoding='async';"
    assert g.count(old_img) == 1, ('hero_img_marker_count', g.count(old_img))
    g = g.replace(old_img, new_img, 1)

    old_thumb_img = "const ti=document.createElement('img');ti.alt='';"
    new_thumb_img = "const ti=document.createElement('img');ti.alt='';ti.loading='lazy';ti.decoding='async';"
    assert g.count(old_thumb_img) == 1, ('thumb_img_marker_count', g.count(old_thumb_img))
    g = g.replace(old_thumb_img, new_thumb_img, 1)

    old_all = "  function loadAllThumbs(){thumbButtons.forEach((_b,i)=>loadThumb(i,i*60))}\n"
    new_lazy = """  let thumbObserver=null;\n  function setupLazyThumbs(){\n    loadThumb(0,0);\n    if(urls.length>1)loadThumb(1,30);\n    if('IntersectionObserver' in window){\n      thumbObserver=new IntersectionObserver(entries=>{\n        entries.forEach(entry=>{\n          if(!entry.isIntersecting)return;\n          const i=Number(entry.target.dataset.thumbIndex);\n          if(Number.isFinite(i))loadThumb(i,0);\n          thumbObserver.unobserve(entry.target);\n        });\n      },{root:thumbs,rootMargin:'0px 180px'});\n      thumbButtons.forEach((b,i)=>{b.dataset.thumbIndex=String(i);thumbObserver.observe(b)});\n      return;\n    }\n    const loadVisible=()=>{\n      const rr=thumbs.getBoundingClientRect();\n      thumbButtons.forEach((b,i)=>{\n        const r=b.getBoundingClientRect();\n        if(r.right>=rr.left-160&&r.left<=rr.right+160)loadThumb(i,0);\n      });\n    };\n    loadVisible();\n    thumbs.addEventListener('scroll',loadVisible,{passive:true});\n  }\n  function releaseStageImage(){\n    ++loadToken;\n    img.onload=null;img.onerror=null;\n    img.removeAttribute('src');\n  }\n"""
    assert g.count(old_all) == 1, ('load_all_thumbs_count', g.count(old_all))
    g = g.replace(old_all, new_lazy, 1)

    old_src = "    img.src=mediaUrl(urls[index],mobile?'card':'hero',mobile);"
    new_src = "    img.src=mediaUrl(urls[index],mobile?'card':'hero');"
    assert g.count(old_src) == 1, ('mobile_media_src_count', g.count(old_src))
    g = g.replace(old_src, new_src, 1)

    old_tail = "  show(0);\n  setTimeout(loadAllThumbs,40);\n"
    new_tail = """  show(0);\n  setupLazyThumbs();\n  window.addEventListener('pagehide',releaseStageImage);\n  window.addEventListener('pageshow',e=>{if(e.persisted&&!img.getAttribute('src'))show(index)});\n"""
    assert g.count(old_tail) == 1, ('gallery_tail_count', g.count(old_tail))
    g = g.replace(old_tail, new_tail, 1)

    GALLERY.write_text(g, encoding='utf-8')

# Make Safari fetch this gallery revision instead of reusing an older JS resource.
html = DETAIL.read_text(encoding='utf-8')
html, n = re.subn(
    r'<script src="assets/puppy-detail-stable-gallery\.js(?:\?v=[^"]*)?"></script>',
    f'<script src="assets/puppy-detail-stable-gallery.js?v={ASSET_VERSION}"></script>',
    html,
    count=1,
)
assert n == 1, ('stable_gallery_tag_count', n)
DETAIL.write_text(html, encoding='utf-8')

# Final gate: preserve the existing UI while changing only resource lifecycle.
verify = GALLERY.read_text(encoding='utf-8')
checks = {
    'marker': MARKER in verify,
    'media_cache_bust': f"const MEDIA_V='{MEDIA_VERSION}';" in verify,
    'lazy_thumbs': 'function setupLazyThumbs()' in verify and 'setTimeout(loadAllThumbs,40);' not in verify,
    'pagehide_release': "window.addEventListener('pagehide',releaseStageImage)" in verify,
    'bfcache_restore': "window.addEventListener('pageshow'" in verify,
    'mobile_versioned_media': "mediaUrl(urls[index],mobile?'card':'hero');" in verify,
    'swipe_preserved': "stage.addEventListener('touchstart'" in verify and "stage.addEventListener('touchend'" in verify,
    'thumb_tap_preserved': "b.onclick=e=>{e.preventDefault();show(i)}" in verify,
}
failed = [k for k, ok in checks.items() if not ok]
if failed:
    raise RuntimeError('SAFARI_GALLERY_HARDENING_FAIL|' + ','.join(failed))

print(
    'SAFARI_GALLERY_HARDENING_OK|ui=unchanged|swipe=preserved|thumb_tap=preserved'
    '|thumbs=lazy_visible|stage_release=pagehide|bfcache_restore=enabled'
    f'|media_cache_bust={MEDIA_VERSION}',
    flush=True,
)
