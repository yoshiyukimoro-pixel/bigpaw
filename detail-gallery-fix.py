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

#bigpawDetailInfo{margin:20px 0;padding:20px;border:1px solid #f0dbe5;border-radius:22px;background:#fff;color:#5b4b62}
#bigpawDetailInfo h1{font-size:28px;line-height:1.35;margin:8px 0 16px}
#bigpawDetailInfo .tags{display:flex;gap:8px;flex-wrap:wrap}.detailtag{background:#fff1f7;border-radius:999px;padding:6px 10px;font-weight:800;font-size:13px}
#bigpawDetailInfo .facts{display:grid;grid-template-columns:1fr 1fr;gap:10px}.detailfact{background:#fff8fc;border:1px solid #f4dfe8;border-radius:13px;padding:12px}.detailfact span{display:block;font-size:12px;color:#8f8195}.detailfact b{font-size:15px}
</style>
<script id="bigpaw-detail-real-gallery-js">
(function(){async function run(){try{var id=new URLSearchParams(location.search).get('id');if(!id)return;var p=await BigPawBridge.puppy(id);window.__BIGPAW_DETAIL_PUPPY=p;window.__BIGPAW_DETAIL_PUPPY=p;var old=document.querySelector('.gallery');if(!old)return;var urls=[];if(p.imageUrl)urls.push(p.imageUrl);if(Array.isArray(p.images))p.images.forEach(function(u){if(u&&urls.indexOf(u)<0)urls.push(u)});var g=document.createElement('div');g.id='bigpawRealGallery';if(!urls.length){g.innerHTML='<div class="main" style="aspect-ratio:4/3;border-radius:18px;background:#f8e9ef;display:grid;place-items:center;font-size:70px">🐩</div>'}else urls.forEach(function(u,i){var d=document.createElement('div');if(i===0)d.className='main';var im=document.createElement('img');im.src=u;im.alt=p.breed||'子犬';d.appendChild(im);g.appendChild(d)});old.replaceWith(g);var cards=document.querySelectorAll('.card');var info=null;cards.forEach(function(c){if((c.textContent||'').indexOf('子犬情報を読み込めませんでした')>=0)info=c});if(info){var d=document.createElement('section');d.id='bigpawDetailInfo';var title=(p.breed||'')+(p.color?'｜'+p.color:'')+(p.gender?'の'+p.gender:'');function v(x){return (x===undefined||x===null||x==='')?'-':BigPaw.esc(String(x))}d.innerHTML='<div class="tags"><span class="detailtag">'+v(p.status||'募集中')+'</span><span class="detailtag">健康情報</span><span class="detailtag">大型犬サイズ情報</span></div><h1>'+BigPaw.esc(title)+'</h1><div class="facts"><div class="detailfact"><span>生年月日</span><b>'+v(p.birthDate||p.birth_date)+'</b></div><div class="detailfact"><span>性別</span><b>'+v(p.gender)+'</b></div><div class="detailfact"><span>毛色</span><b>'+v(p.color)+'</b></div><div class="detailfact"><span>現在体重</span><b>'+v(p.weight||p.currentWeight)+'</b></div><div class="detailfact"><span>成犬時予想</span><b>'+v((p.adultMin||'')+(p.adultMax?'〜'+p.adultMax+'kg':''))+'</b></div><div class="detailfact"><span>見学場所</span><b>'+v(p.area)+'</b></div></div>';info.replaceWith(d)}}catch(e){}}function go(){if(window.BigPawBridge)run();else setTimeout(go,50)}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go()})();
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
