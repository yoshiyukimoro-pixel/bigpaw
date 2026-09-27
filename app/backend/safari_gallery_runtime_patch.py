#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'backend' / 'server.py'
GALLERY = ROOT / 'assets' / 'puppy-detail-stable-gallery.js'
DETAIL = ROOT / 'puppy-detail.html'
AUTH = ROOT / 'auth-return-fix.js'

MARKER = 'SAFARI_DETAIL_GALLERY_HARDENING_v1'
PUBLIC_API_MARKER = 'BIGPAW_PUBLIC_PUPPY_DETAIL_API_V2'
ROLE_PREVIEW_MARKER = 'BIGPAW_PUBLIC_PREVIEW_ROLE_GUARD_V1'
MEDIA_VERSION = '20260926safari1'
ASSET_VERSION = '20260927restore3'

# ---------------------------------------------------------------------------
# Public puppy detail API.
# This endpoint is intentionally independent of the current login session.
# A breeder/operator viewing the public site must receive the same public
# puppy/photo payload as a logged-out visitor or buyer.
# ---------------------------------------------------------------------------
server = SERVER.read_text(encoding='utf-8')
if PUBLIC_API_MARKER not in server:
    anchor = """        m=re.fullmatch(r'/api/puppies/([^/]+)',path)
        if m:
            con=db();"""
    assert server.count(anchor) == 1, ('public_puppy_get_anchor_count', server.count(anchor))
    route = f"""        # {PUBLIC_API_MARKER}
        mpublic=re.fullmatch(r'/api/public/puppies/([^/]+)',path)
        if mpublic:
            con=db(); sync_breeder_billing_suspension(con); con.commit()
            r=con.execute("SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='approved' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)",(mpublic.group(1),)).fetchone()
            if not r:
                con.close(); return self.send_json({{'error':'not_found'}},404)
            out=public_puppy_json(r)
            ph=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(r['id'],)).fetchall()
            out['photos']=['/uploads/'+x['stored_name'] for x in ph]
            con.close(); return self.send_json(out,200)
"""
    server = server.replace(anchor, route + anchor, 1)
    SERVER.write_text(server, encoding='utf-8')

# ---------------------------------------------------------------------------
# Stable public gallery.
# ---------------------------------------------------------------------------
g = GALLERY.read_text(encoding='utf-8')

# Always use the explicitly public endpoint. Never fall back to authenticated
# bridge data for gallery state.
old_fetch = "fetch('/api/puppies/'+encodeURIComponent(puppyId),{credentials:'omit',cache:'no-store'})"
new_fetch = "fetch('/api/public/puppies/'+encodeURIComponent(puppyId),{credentials:'omit',cache:'no-store'})"
if old_fetch in g:
    g = g.replace(old_fetch, new_fetch, 1)
elif new_fetch not in g:
    raise RuntimeError('PUBLIC_GALLERY_FETCH_PATCH_FAIL')

old_catch = """  }catch(_e){
    if(!window.BigPawBridge){setTimeout(init,40);return}
    try{p=await BigPawBridge.puppy(puppyId)}catch(_e2){return}
  }
"""
new_catch = """  }catch(_e){
    try{
      const r=await fetch('/api/puppies/'+encodeURIComponent(puppyId),{credentials:'omit',cache:'no-store'});
      if(!r.ok)return;
      p=await r.json();
    }catch(_e2){return}
  }
"""
if old_catch in g:
    g = g.replace(old_catch, new_catch, 1)
elif new_catch not in g:
    raise RuntimeError('PUBLIC_GALLERY_FALLBACK_PATCH_FAIL')

# Do not depend on the legacy .gallery node surviving other page scripts.
old_mount = """  const old=document.querySelector('.gallery,#bigpawRealGallery');
  if(!old)return;
"""
new_mount = """  const old=document.querySelector('.gallery,#bigpawRealGallery');
  const fallbackMount=document.querySelector('main .wrap > .section')||document.querySelector('main .section');
  if(!old&&!fallbackMount)return;
"""
if old_mount in g:
    g = g.replace(old_mount, new_mount, 1)
elif new_mount not in g:
    raise RuntimeError('PUBLIC_GALLERY_MOUNT_PATCH_FAIL')

replacement = "if(old)old.replaceWith(root);else fallbackMount.insertAdjacentElement('beforebegin',root);"
count_old = g.count('old.replaceWith(root);')
if count_old:
    g = g.replace('old.replaceWith(root);', replacement)
elif replacement not in g:
    raise RuntimeError('PUBLIC_GALLERY_REPLACE_PATCH_FAIL')

# Existing iPhone/Safari hardening.
if MARKER not in g:
    needle = "'use strict';\n"
    assert g.count(needle) == 1, ('strict_marker_count', g.count(needle))
    g = g.replace(needle, needle + f"// {MARKER}\n", 1)

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
    new_lazy = """  let thumbObserver=null;
  function setupLazyThumbs(){
    loadThumb(0,0);
    if(urls.length>1)loadThumb(1,30);
    if('IntersectionObserver' in window){
      thumbObserver=new IntersectionObserver(entries=>{
        entries.forEach(entry=>{
          if(!entry.isIntersecting)return;
          const i=Number(entry.target.dataset.thumbIndex);
          if(Number.isFinite(i))loadThumb(i,0);
          thumbObserver.unobserve(entry.target);
        });
      },{root:thumbs,rootMargin:'0px 180px'});
      thumbButtons.forEach((b,i)=>{b.dataset.thumbIndex=String(i);thumbObserver.observe(b)});
      return;
    }
    const loadVisible=()=>{
      const rr=thumbs.getBoundingClientRect();
      thumbButtons.forEach((b,i)=>{
        const r=b.getBoundingClientRect();
        if(r.right>=rr.left-160&&r.left<=rr.right+160)loadThumb(i,0);
      });
    };
    loadVisible();
    thumbs.addEventListener('scroll',loadVisible,{passive:true});
  }
  function releaseStageImage(){
    ++loadToken;
    img.onload=null;img.onerror=null;
    img.removeAttribute('src');
  }
"""
    assert g.count(old_all) == 1, ('load_all_thumbs_count', g.count(old_all))
    g = g.replace(old_all, new_lazy, 1)

    old_src = "    img.src=mediaUrl(urls[index],mobile?'card':'hero',mobile);"
    new_src = "    img.src=mediaUrl(urls[index],mobile?'card':'hero');"
    assert g.count(old_src) == 1, ('mobile_media_src_count', g.count(old_src))
    g = g.replace(old_src, new_src, 1)

    old_tail = "  show(0);\n  setTimeout(loadAllThumbs,40);\n"
    new_tail = """  show(0);
  setupLazyThumbs();
  window.addEventListener('pagehide',releaseStageImage);
  window.addEventListener('pageshow',e=>{if(e.persisted&&!img.getAttribute('src'))show(index)});
"""
    assert g.count(old_tail) == 1, ('gallery_tail_count', g.count(old_tail))
    g = g.replace(old_tail, new_tail, 1)

GALLERY.write_text(g, encoding='utf-8')

# ---------------------------------------------------------------------------
# Public preview mode for breeder/operator sessions.
# Public content stays public; buyer-only actions do not run.
# ---------------------------------------------------------------------------
auth = AUTH.read_text(encoding='utf-8')
if ROLE_PREVIEW_MARKER not in auth:
    old_block = """  if(p.endsWith('/puppy-detail.html')){
    const s=document.createElement('script');
    s.src='/puppy-detail-favorites-fix.js';
    s.async=true;
    document.head.appendChild(s);
  }
"""
    new_block = f"""  if(p.endsWith('/puppy-detail.html')){{
    // {ROLE_PREVIEW_MARKER}
    currentRole().then(role=>{{
      if(role==='breeder'||role==='operator'){{
        document.documentElement.setAttribute('data-bigpaw-public-preview-role',role);
        const apply=()=>{{
          ['#bigpawFavButton','#favBtn','#inq','#bigpawTopInquiry','a[href$="favorites.html"]','a[href$="mypage.html"]'].forEach(sel=>{{
            document.querySelectorAll(sel).forEach(el=>{{el.style.display='none';el.setAttribute('aria-hidden','true')}});
          }});
          if(!document.getElementById('bigpawPublicPreviewNotice')){{
            const host=document.querySelector('.breadcrumb')||document.querySelector('main .wrap');
            if(host){{
              const n=document.createElement('div');
              n.id='bigpawPublicPreviewNotice';
              n.style.cssText='margin:10px 0 14px;padding:10px 12px;border:1px solid #c5dced;border-radius:12px;background:#f3f8ff;color:#315f89;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:space-between;gap:10px';
              const label=document.createElement('span');
              label.textContent=role==='operator'?'運営として一般公開ページを表示中':'ブリーダーとして一般公開ページを表示中';
              const a=document.createElement('a');
              a.href=role==='operator'?'/operator-admin.html':'/admin.html';
              a.textContent=role==='operator'?'運営管理へ戻る':'ブリーダー管理へ戻る';
              a.style.cssText='color:#315f89;text-decoration:underline;white-space:nowrap';
              n.append(label,a);
              host.insertAdjacentElement('afterend',n);
            }}
          }}
        }};
        apply();
        const mo=new MutationObserver(apply);
        mo.observe(document.documentElement,{{childList:true,subtree:true}});
        return;
      }}
      const s=document.createElement('script');
      s.src='/puppy-detail-favorites-fix.js?v=20260927preview1';
      s.async=true;
      document.head.appendChild(s);
    }});
  }}
"""
    assert auth.count(old_block) == 1, ('auth_detail_favorite_block_count', auth.count(old_block))
    auth = auth.replace(old_block, new_block, 1)
    AUTH.write_text(auth, encoding='utf-8')

# ---------------------------------------------------------------------------
# Cache-bust the stable gallery asset in the final detail HTML.
# ---------------------------------------------------------------------------
html = DETAIL.read_text(encoding='utf-8')
html = re.sub(
    r'<script src="assets/puppy-detail-swipe-fix\.js(?:\?v=[^"]*)?"></script>',
    '',
    html,
)
html, n = re.subn(
    r'<script src="assets/puppy-detail-stable-gallery\.js(?:\?v=[^"]*)?"></script>',
    f'<script src="assets/puppy-detail-stable-gallery.js?v={ASSET_VERSION}"></script>',
    html,
    count=1,
)
assert n == 1, ('stable_gallery_tag_count', n)
DETAIL.write_text(html, encoding='utf-8')

# ---------------------------------------------------------------------------
# Regression gates.
# ---------------------------------------------------------------------------
verify = GALLERY.read_text(encoding='utf-8')
verify_html = DETAIL.read_text(encoding='utf-8')
verify_server = SERVER.read_text(encoding='utf-8')
verify_auth = AUTH.read_text(encoding='utf-8')
checks = {
    'marker': MARKER in verify,
    'public_api_route': PUBLIC_API_MARKER in verify_server and "/api/public/puppies/" in verify_server,
    'public_gallery_endpoint': "/api/public/puppies/" in verify,
    'public_fetch_without_auth': "credentials:'omit'" in verify and "cache:'no-store'" in verify,
    'no_authenticated_gallery_fallback': 'BigPawBridge.puppy(puppyId)' not in verify,
    'mount_fallback': 'fallbackMount' in verify and "insertAdjacentElement('beforebegin',root)" in verify,
    'media_cache_bust': f"const MEDIA_V='{MEDIA_VERSION}';" in verify,
    'lazy_thumbs': 'function setupLazyThumbs()' in verify and 'setTimeout(loadAllThumbs,40);' not in verify,
    'pagehide_release': "window.addEventListener('pagehide',releaseStageImage)" in verify,
    'bfcache_restore': "window.addEventListener('pageshow'" in verify,
    'mobile_versioned_media': "mediaUrl(urls[index],mobile?'card':'hero');" in verify,
    'swipe_preserved': "stage.addEventListener('touchstart'" in verify and "stage.addEventListener('touchend'" in verify,
    'thumb_tap_preserved': "b.onclick=e=>{e.preventDefault();show(i)}" in verify,
    'extra_swipe_bridge_removed': 'puppy-detail-swipe-fix.js' not in verify_html,
    'role_preview_guard': ROLE_PREVIEW_MARKER in verify_auth,
    'breeder_buyer_actions_disabled': "#bigpawFavButton" in verify_auth and "#bigpawTopInquiry" in verify_auth,
}
failed = [k for k, ok in checks.items() if not ok]
if failed:
    raise RuntimeError('SAFARI_GALLERY_HARDENING_FAIL|' + ','.join(failed))

print(
    'SAFARI_GALLERY_HARDENING_OK|known_good_restore=20260926|swipe=original|thumb_tap=preserved'
    '|gallery_data=explicit_public_api|auth_role_independent=1|mount_fallback=1'
    '|breeder_public_preview=1|buyer_actions_hidden_for_breeder=1'
    f'|asset={ASSET_VERSION}|media_cache_bust={MEDIA_VERSION}',
    flush=True,
)
