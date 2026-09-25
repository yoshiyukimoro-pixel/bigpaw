from pathlib import Path
import re

# Share and cache a puppy response for the lifetime of one page. The public
# detail page has more than one renderer; without a page-local resolved cache a
# second renderer can issue another GET just after the first request completes.
bridge=Path('/app/assets/bridge.js')
s=bridge.read_text(encoding='utf-8')
marker='  window.BigPawBridge={'
helper="""  const puppyInflight=new Map();
  const puppyPageCache=new Map();
  function sharedPuppy(id){
    const key=String(id||'');
    if(puppyPageCache.has(key))return Promise.resolve(puppyPageCache.get(key));
    if(puppyInflight.has(key))return puppyInflight.get(key);
    const req=Promise.resolve().then(()=>fallbackable(()=>BigPawAPI.puppy(id),()=>BigPaw.getPuppy(id))).then(v=>{puppyPageCache.set(key,v);return v});
    puppyInflight.set(key,req);
    req.finally(()=>{if(puppyInflight.get(key)===req)puppyInflight.delete(key)});
    return req;
  }
"""
# Replace either the old inflight-only helper or inject a fresh helper.
old_helper="""  const puppyInflight=new Map();
  function sharedPuppy(id){
    const key=String(id||'');
    if(puppyInflight.has(key))return puppyInflight.get(key);
    const req=Promise.resolve().then(()=>fallbackable(()=>BigPawAPI.puppy(id),()=>BigPaw.getPuppy(id)));
    puppyInflight.set(key,req);
    req.finally(()=>{if(puppyInflight.get(key)===req)puppyInflight.delete(key)});
    return req;
  }
"""
if old_helper in s:
    s=s.replace(old_helper,helper,1)
elif helper not in s:
    assert s.count(marker)==1,('bridge_marker_count',s.count(marker))
    s=s.replace(marker,helper+marker,1)
old="    puppy(id){return fallbackable(()=>BigPawAPI.puppy(id),()=>BigPaw.getPuppy(id))},"
new="    puppy(id){return sharedPuppy(id)},"
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit(('bridge_puppy_method_missing',s.count(old),s.count(new)))
bridge.write_text(s,encoding='utf-8')

# Restore the stable gallery behavior. Every photo keeps a real src so iPhone
# Safari never shows broken placeholders. Native loading=lazy handles non-hero photos.
hp=Path('/app/puppy-detail.html')
html=hp.read_text(encoding='utf-8')
old_img="var im=document.createElement('img');im.src=u;im.alt=p.breed||'子犬';"
new_img="var im=document.createElement('img');im.alt=p.breed||'子犬';im.decoding='async';if(i===0){im.loading='eager';im.fetchPriority='high'}else{im.loading='lazy';im.fetchPriority='low'}im.src=u;"
if old_img in html:
    html=html.replace(old_img,new_img,1)
elif new_img not in html:
    raise SystemExit(('gallery_image_create_missing',html.count(old_img),html.count(new_img)))

# Puppy payload already contains photos, so do not request the same list a second time.
extra_fetch="try{var r=await fetch('/api/puppies/'+encodeURIComponent(id)+'/photos',{credentials:'same-origin'});if(r.ok){var j=await r.json();var a=Array.isArray(j)?j:(j.photos||j.items||j.images||[]);a.forEach(function(x){add(typeof x==='string'?x:(x&&(x.url||x.imageUrl||x.path)))})}}catch(_e){}"
if extra_fetch in html:
    html=html.replace(extra_fetch,'',1)

# Public detail enhancement and rescue blocks must use the canonical birth field.
if 'p.birthDate||p.birth_date' in html:
    html=html.replace('p.birthDate||p.birth_date','p.birth||p.birthDate||p.birth_date')

# Always show kg for current-weight displays, including the fallback/rescue renderer.
old_detail_weight="<div class=\"detailfact\"><span>現在体重</span><b>'+v(p.weight||p.currentWeight)+'</b></div>"
new_detail_weight="<div class=\"detailfact\"><span>現在体重</span><b>'+(((p.weight||p.currentWeight)===undefined||(p.weight||p.currentWeight)===null||(p.weight||p.currentWeight)==='')?'-':v(p.weight||p.currentWeight)+'kg')+'</b></div>"
if old_detail_weight in html:
    html=html.replace(old_detail_weight,new_detail_weight,1)
rescue_old="p.weight||p.currentWeight||'-'"
rescue_new="(((p.weight||p.currentWeight)===undefined||(p.weight||p.currentWeight)===null||(p.weight||p.currentWeight)==='')?'-':String(p.weight||p.currentWeight)+'kg')"
if rescue_old in html:
    html=html.replace(rescue_old,rescue_new,1)

# Prioritize the first legacy hero image too.
legacy="mainPhoto.innerHTML=p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" alt=\"${BigPaw.esc(p.breed)}\">`:dogEmoji(p);"
legacy_new="mainPhoto.innerHTML=p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" fetchpriority=\"high\" loading=\"eager\" decoding=\"async\" alt=\"${BigPaw.esc(p.breed)}\">`:dogEmoji(p);"
if legacy in html:
    html=html.replace(legacy,legacy_new,1)
elif legacy_new not in html:
    raise SystemExit(('legacy_hero_missing',html.count(legacy),html.count(legacy_new)))

# Never install the experimental replacement carousel. It raced the built-in
# gallery on iPhone Safari. Remove direct tags and disable any stale/dynamic load.
html=re.sub(r'<script src="/?puppy-gallery-carousel-fix\.js(?:\?v=[^"]*)?"></script>','',html)
disable='<script id="bigpaw-disable-experimental-gallery">window.__BIGPAW_PUPPY_GALLERY_CAROUSEL_FIX__=true;</script>'
if disable not in html:
    html=html.replace('</head>',disable+'</head>',1)

# Force Safari to pick up restored scripts after deploy.
html=re.sub(r'<script src="assets/bridge\.js(?:\?v=[^"]*)?"></script>','<script src="assets/bridge.js?v=20260925stablephotos2"></script>',html,count=1)
html=re.sub(r'<script src="/?puppy-detail-favorites-fix\.js(?:\?v=[^"]*)?"></script>','<script src="/puppy-detail-favorites-fix.js?v=20260925stablephotos2"></script>',html,count=1)
html=html.replace('assets/public-parent-dogs.js?v=20260925c','assets/public-parent-dogs.js?v=20260925stablephotos2')
html=html.replace('assets/public-parent-dogs.js?v=20260925stablephotos1','assets/public-parent-dogs.js?v=20260925stablephotos2')
html=html.replace('assets/public-parent-genetics.js?v=20260925a','assets/public-parent-genetics.js?v=20260925stablephotos2')
html=html.replace('assets/public-parent-genetics.js?v=20260925stablephotos1','assets/public-parent-genetics.js?v=20260925stablephotos2')

# Add a prominent inquiry CTA directly under the photo gallery.
top_cta='<script src="assets/puppy-detail-top-inquiry.js?v=20260925a"></script>'
if top_cta not in html:
    assert '</body>' in html,'body_close_missing'
    html=html.replace('</body>',top_cta+'</body>',1)

hp.write_text(html,encoding='utf-8')

print('PUPPY_DETAIL_PERF_OK|api_requests=page_cached|photo_fetch=single|gallery=stable_native_lazy|experimental_carousel=disabled|hero=priority|birth=canonical|weight_unit=kg|top_inquiry=enabled',flush=True)
