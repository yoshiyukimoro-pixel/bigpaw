from pathlib import Path
import re

# Share and cache a puppy response for the lifetime of one page.
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

hp=Path('/app/puppy-detail.html')
html=hp.read_text(encoding='utf-8')

# The puppy payload already contains the complete photo list. Never issue a
# second photos request from the detail page.
extra_fetch="try{var r=await fetch('/api/puppies/'+encodeURIComponent(id)+'/photos',{credentials:'same-origin'});if(r.ok){var j=await r.json();var a=Array.isArray(j)?j:(j.photos||j.items||j.images||[]);a.forEach(function(x){add(typeof x==='string'?x:(x&&(x.url||x.imageUrl||x.path)))})}}catch(_e){}"
if extra_fetch in html:
    html=html.replace(extra_fetch,'',1)

# Dedicated favorite integration owns favorite state; avoid a duplicate request.
legacy_fav="try{const favs=await BigPawBridge.favorites();faved=favs.some(x=>String(x.id)===String(p.id))}catch(e){faved=false}refreshFav()"
if legacy_fav in html:
    html=html.replace(legacy_fav,'faved=false;refreshFav()',1)

if 'p.birthDate||p.birth_date' in html:
    html=html.replace('p.birthDate||p.birth_date','p.birth||p.birthDate||p.birth_date')

old_detail_weight="<div class=\"detailfact\"><span>現在体重</span><b>'+v(p.weight||p.currentWeight)+'</b></div>"
new_detail_weight="<div class=\"detailfact\"><span>現在体重</span><b>'+(((p.weight||p.currentWeight)===undefined||(p.weight||p.currentWeight)===null||(p.weight||p.currentWeight)==='')?'-':v(p.weight||p.currentWeight)+'kg')+'</b></div>"
if old_detail_weight in html:
    html=html.replace(old_detail_weight,new_detail_weight,1)
rescue_old="p.weight||p.currentWeight||'-'"
rescue_new="(((p.weight||p.currentWeight)===undefined||(p.weight||p.currentWeight)===null||(p.weight||p.currentWeight)==='')?'-':String(p.weight||p.currentWeight)+'kg')"
if rescue_old in html:
    html=html.replace(rescue_old,rescue_new,1)

# The stable gallery is the only code allowed to load the hero image. The base
# renderer keeps an emoji placeholder, eliminating duplicate image decode work.
legacy="mainPhoto.innerHTML=p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" alt=\"${BigPaw.esc(p.breed)}\">`:dogEmoji(p);"
legacy_eager="mainPhoto.innerHTML=p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" fetchpriority=\"high\" loading=\"eager\" decoding=\"async\" alt=\"${BigPaw.esc(p.breed)}\">`:dogEmoji(p);"
legacy_safe="mainPhoto.innerHTML=dogEmoji(p);"
if legacy in html:
    html=html.replace(legacy,legacy_safe,1)
elif legacy_eager in html:
    html=html.replace(legacy_eager,legacy_safe,1)
elif legacy_safe not in html:
    raise SystemExit(('legacy_hero_missing',html.count(legacy),html.count(legacy_eager),html.count(legacy_safe)))

# Remove the old grid and experimental carousel.
removed=len(re.findall(r'<script id="bigpaw-detail-real-gallery-js">.*?</script>',html,flags=re.S))
html=re.sub(r'<script id="bigpaw-detail-real-gallery-js">.*?</script>','',html,flags=re.S)
if removed!=1:
    raise SystemExit(('legacy_detail_gallery_script_count',removed))
html=re.sub(r'<script src="/?puppy-gallery-carousel-fix\.js(?:\?v=[^"]*)?"></script>','',html)
disable='<script id="bigpaw-disable-experimental-gallery">window.__BIGPAW_PUPPY_GALLERY_CAROUSEL_FIX__=true;</script>'
if disable not in html:
    html=html.replace('</head>',disable+'</head>',1)

# iPhone Safari was showing 1/6 but never requesting the other five thumbnail
# files. Do not wait for requestIdleCallback or viewport detection: there are at
# most ten tiny thumbnails, so load every one in a short stagger after the hero.
gallery=Path('/app/assets/puppy-detail-stable-gallery.js')
g=gallery.read_text(encoding='utf-8')
g=g.replace("const MEDIA_V='20260926j1';","const MEDIA_V='20260926j2';",1)
idle_old="setTimeout(()=>{'requestIdleCallback'in window?requestIdleCallback(run,{timeout:1000}):run()},delay);"
idle_new="setTimeout(run,delay);"
assert idle_old in g,('gallery_idle_marker_missing',g.count(idle_old))
g=g.replace(idle_old,idle_new,1)
visible_old="""  function loadVisibleThumbs(){
    const r=thumbs.getBoundingClientRect();let step=0;
    thumbButtons.forEach((b,i)=>{const br=b.getBoundingClientRect();if(br.right>=r.left-40&&br.left<=r.right+40){loadThumb(i,step*120);step++}});
  }
  function scheduleVisibleThumbs(){clearTimeout(thumbBatchTimer);thumbBatchTimer=setTimeout(loadVisibleThumbs,650)}"""
visible_new="""  function loadVisibleThumbs(){
    thumbButtons.forEach((_b,i)=>loadThumb(i,i*70));
  }
  function scheduleVisibleThumbs(){clearTimeout(thumbBatchTimer);thumbBatchTimer=setTimeout(loadVisibleThumbs,120)}"""
assert visible_old in g,('gallery_thumb_scheduler_marker_missing',g.count(visible_old))
g=g.replace(visible_old,visible_new,1)
gallery.write_text(g,encoding='utf-8')

version='20260926gallery6'
html=re.sub(r'<script src="assets/bridge\.js(?:\?v=[^"]*)?"></script>',f'<script src="assets/bridge.js?v={version}"></script>',html,count=1)
html=re.sub(r'<script src="/?puppy-detail-favorites-fix\.js(?:\?v=[^"]*)?"></script>',f'<script src="/puppy-detail-favorites-fix.js?v={version}"></script>',html,count=1)
html=re.sub(r'assets/public-parent-dogs\.js(?:\?v=[^"\']*)?',f'assets/public-parent-dogs.js?v={version}',html)
html=re.sub(r'assets/public-parent-genetics\.js(?:\?v=[^"\']*)?',f'assets/public-parent-genetics.js?v={version}',html)

# Replace any older stable-gallery asset tag with the current cache-busted tag.
html=re.sub(r'<script src="assets/puppy-detail-stable-gallery\.js(?:\?v=[^"]*)?"></script>','',html)
stable_gallery=f'<script src="assets/puppy-detail-stable-gallery.js?v={version}"></script>'
assert '</body>' in html,'body_close_missing_for_stable_gallery'
html=html.replace('</body>',stable_gallery+'</body>',1)

top_cta='<script src="assets/puppy-detail-top-inquiry.js?v=20260925a"></script>'
if top_cta not in html:
    assert '</body>' in html,'body_close_missing'
    html=html.replace('</body>',top_cta+'</body>',1)

hp.write_text(html,encoding='utf-8')
print('PUPPY_DETAIL_PERF_OK|api_requests=page_cached|photo_fetch=payload_only|favorites=single_owner|gallery=single_hero_plus_staggered_all_thumbnails|max_photos=10|media_cache_busted=20260926j2|hero_duplicate=disabled|hero_prefetch=disabled|thumbs=all_small_no_idle_callback|swipe=enabled|mobile_arrows=hidden|breeder_editor=separate|experimental_carousel=disabled|birth=canonical|weight_unit=kg|top_inquiry=enabled',flush=True)
