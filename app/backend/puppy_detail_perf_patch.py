from pathlib import Path
import re

# Deduplicate puppy-detail API requests for the lifetime of the page.
bridge=Path('/app/assets/bridge.js')
s=bridge.read_text(encoding='utf-8')
marker='  window.BigPawBridge={'
helper="""  const puppyInflight=new Map();
  const puppyCache=new Map();
  function sharedPuppy(id){
    const key=String(id||'');
    if(puppyCache.has(key))return Promise.resolve(puppyCache.get(key));
    if(puppyInflight.has(key))return puppyInflight.get(key);
    const req=Promise.resolve().then(()=>fallbackable(()=>BigPawAPI.puppy(id),()=>BigPaw.getPuppy(id))).then(value=>{puppyCache.set(key,value);return value});
    puppyInflight.set(key,req);
    req.finally(()=>{if(puppyInflight.get(key)===req)puppyInflight.delete(key)});
    return req;
  }
"""
if helper not in s:
    assert s.count(marker)==1,('bridge_marker_count',s.count(marker))
    s=s.replace(marker,helper+marker,1)
old="    puppy(id){return fallbackable(()=>BigPawAPI.puppy(id),()=>BigPaw.getPuppy(id))},"
new="    puppy(id){return sharedPuppy(id)},"
assert s.count(old)==1,('bridge_puppy_method_count',s.count(old))
s=s.replace(old,new,1)
bridge.write_text(s,encoding='utf-8')

# First paint must request only the hero image. Non-hero URLs are kept in data-src
# so Safari cannot eagerly download the whole gallery before the hero is visible.
hp=Path('/app/puppy-detail.html')
html=hp.read_text(encoding='utf-8')
old_img="var im=document.createElement('img');im.src=u;im.alt=p.breed||'子犬';"
new_img="var im=document.createElement('img');im.alt=p.breed||'子犬';im.decoding='async';if(i===0){im.loading='eager';im.fetchPriority='high';im.src=u}else{im.loading='lazy';im.fetchPriority='low';im.dataset.src=u}"
assert html.count(old_img)==1,('gallery_image_create_count',html.count(old_img))
html=html.replace(old_img,new_img,1)

# Puppy payload already contains photos, so do not request the same photo list a second time.
extra_fetch="try{var r=await fetch('/api/puppies/'+encodeURIComponent(id)+'/photos',{credentials:'same-origin'});if(r.ok){var j=await r.json();var a=Array.isArray(j)?j:(j.photos||j.items||j.images||[]);a.forEach(function(x){add(typeof x==='string'?x:(x&&(x.url||x.imageUrl||x.path)))})}}catch(_e){}"
assert html.count(extra_fetch)==1,('duplicate_photo_fetch_count',html.count(extra_fetch))
html=html.replace(extra_fetch,'',1)

# Public detail enhancement and rescue blocks were reading birthDate/birth_date only,
# while the API's canonical field is birth. Include birth first everywhere.
birth_legacy_count=html.count('p.birthDate||p.birth_date')
assert birth_legacy_count>=1,('birth_lookup_count',birth_legacy_count)
html=html.replace('p.birthDate||p.birth_date','p.birth||p.birthDate||p.birth_date')
assert html.count('p.birth||p.birthDate||p.birth_date')>=birth_legacy_count

# Prioritize the first legacy hero image too.
legacy="mainPhoto.innerHTML=p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" alt=\"${BigPaw.esc(p.breed)}\">`:dogEmoji(p);"
legacy_new="mainPhoto.innerHTML=p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" fetchpriority=\"high\" loading=\"eager\" decoding=\"async\" alt=\"${BigPaw.esc(p.breed)}\">`:dogEmoji(p);"
assert html.count(legacy)==1,('legacy_hero_count',html.count(legacy))
html=html.replace(legacy,legacy_new,1)

# Force Safari to pick up the optimized scripts after deploy.
html=html.replace('<script src="assets/bridge.js"></script>','<script src="assets/bridge.js?v=20260925perf4"></script>',1)
html=html.replace('assets/public-parent-dogs.js?v=20260925c','assets/public-parent-dogs.js?v=20260925perf4')
html=html.replace('assets/public-parent-genetics.js?v=20260925a','assets/public-parent-genetics.js?v=20260925perf4')

# Add a prominent inquiry CTA directly under the photo gallery, next to the favorite action.
top_cta='<script src="assets/puppy-detail-top-inquiry.js?v=20260925a"></script>'
if top_cta not in html:
    assert '</body>' in html,'body_close_missing'
    html=html.replace('</body>',top_cta+'</body>',1)

hp.write_text(html,encoding='utf-8')

print('PUPPY_DETAIL_PERF_OK|api_requests=page_cached|photo_fetch=single|gallery=hero_only_first|hero=priority|birth=canonical|top_inquiry=enabled',flush=True)
