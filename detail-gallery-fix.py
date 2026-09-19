from pathlib import Path
p=Path('puppy-detail.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 marker='</body>'
 js=r'''<style id="bigpaw-detail-real-gallery">
#bigpawRealGallery{margin:0 0 20px;display:grid;grid-template-columns:1fr 1fr;gap:8px}
#bigpawRealGallery .main{grid-column:1/-1}
#bigpawRealGallery img{display:block;width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:18px;background:#f8e9ef}
#bigpawRealGallery .main img{aspect-ratio:4/3}
</style>
<script id="bigpaw-detail-real-gallery-js">
(function(){async function run(){try{var id=new URLSearchParams(location.search).get('id');if(!id)return;var p=await BigPawBridge.puppy(id);window.__BIGPAW_DETAIL_PUPPY=p;var old=document.querySelector('.gallery');if(!old)return;var urls=[];if(p.imageUrl)urls.push(p.imageUrl);if(Array.isArray(p.images))p.images.forEach(function(u){if(u&&urls.indexOf(u)<0)urls.push(u)});var g=document.createElement('div');g.id='bigpawRealGallery';if(!urls.length){g.innerHTML='<div class="main" style="aspect-ratio:4/3;border-radius:18px;background:#f8e9ef;display:grid;place-items:center;font-size:70px">🐩</div>'}else urls.forEach(function(u,i){var d=document.createElement('div');if(i===0)d.className='main';var im=document.createElement('img');im.src=u;im.alt=p.breed||'子犬';d.appendChild(im);g.appendChild(d)});old.replaceWith(g)}catch(e){}}function go(){if(window.BigPawBridge)run();else setTimeout(go,50)}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go()})();
</script>'''
 if 'bigpaw-detail-real-gallery' not in s:s=s.replace(marker,js+marker,1)
 # Replace the legacy detail loader: it expects an obsolete API response shape and overwrites valid data with an error.
 oldloader="const p=await BigPawBridge.puppy(id);"
 # Keep gallery loader, but patch legacy catch/error text after real data arrives.
 rescue=r'''<script id="bigpaw-detail-data-rescue">
(function(){async function fix(){try{var id=new URLSearchParams(location.search).get('id');if(!id)return;var p=await BigPawBridge.puppy(id);var h=document.querySelector('.detail-title,.puppy-title,h1');if(h&&/読み込めません/.test(h.textContent))h.textContent=(p.breed||'')+(p.gender?'｜'+p.gender:'');var cards=document.querySelectorAll('.fact');var vals=[p.birthDate||p.birth_date||'-',p.gender||'-',p.color||'-',p.weight||p.currentWeight||'-',((p.adultMin||p.adult_min||'')&& (p.adultMax||p.adult_max||''))?String(p.adultMin||p.adult_min)+'〜'+String(p.adultMax||p.adult_max)+'kg':'-',p.area||p.location||'-'];cards.forEach(function(c,i){if(i<vals.length){var b=c.querySelector('b');if(b)b.textContent=vals[i]}});document.querySelectorAll('h1,h2,.puppy-title').forEach(function(e){if(/子犬情報を読み込めませんでした/.test(e.textContent))e.textContent=(p.breed||'子犬')+(p.gender?'｜'+p.gender:'')});}catch(e){}}setTimeout(fix,300);window.addEventListener('pageshow',function(){setTimeout(fix,300)})})();
</script>'''
 if 'bigpaw-detail-data-rescue' not in s:s=s.replace(marker,rescue+marker,1)
 p.write_text(s,encoding='utf-8')
