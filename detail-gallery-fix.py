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
(function(){async function run(){try{var id=new URLSearchParams(location.search).get('id');if(!id)return;var p=await BigPawBridge.puppy(id);var old=document.querySelector('.gallery');if(!old)return;var urls=[];if(p.imageUrl)urls.push(p.imageUrl);if(Array.isArray(p.images))p.images.forEach(function(u){if(u&&urls.indexOf(u)<0)urls.push(u)});var g=document.createElement('div');g.id='bigpawRealGallery';if(!urls.length){g.innerHTML='<div class="main" style="aspect-ratio:4/3;border-radius:18px;background:#f8e9ef;display:grid;place-items:center;font-size:70px">🐩</div>'}else urls.forEach(function(u,i){var d=document.createElement('div');if(i===0)d.className='main';var im=document.createElement('img');im.src=u;im.alt=p.breed||'子犬';d.appendChild(im);g.appendChild(d)});old.replaceWith(g)}catch(e){}}function go(){if(window.BigPawBridge)run();else setTimeout(go,50)}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go()})();
</script>'''
 if 'bigpaw-detail-real-gallery' not in s:s=s.replace(marker,js+marker,1)
 p.write_text(s,encoding='utf-8')
