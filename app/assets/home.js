(function(){
  const grid=document.getElementById('puppyGrid'); if(!grid||!window.BigPaw)return;
  let all=[]; let favIds=new Set();
  function icon(p){return p.breedKey==='golden'?'🐕':p.breedKey==='bernese'?'🐶':p.breedKey==='husky'?'🐺':p.breedKey==='samoyed'?'☁️':'🐩'}
  window.renderHomePuppies=function(list){
    grid.innerHTML='';
    list.forEach((p,i)=>{const fav=favIds.has(String(p.id));const el=document.createElement('article');el.className='puppy';el.dataset.gender=p.genderKey;el.dataset.breed=p.breedKey;el.dataset.area=p.areaKey;el.dataset.health=p.health?'yes':'no';const media=p.imageUrl?`<img src="${BigPaw.esc(p.imageUrl)}" alt="${BigPaw.esc(p.breed)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">`:icon(p);el.innerHTML=`<div class="puppy-img ${i%3===0?'img3':i%3===1?'img2':'img1'}" style="font-size:76px;align-items:center;overflow:hidden">${media}<span class="badge">${p.status==='募集中'?'NEW':BigPaw.esc(p.status)}</span><button class="fav ${fav?'on':''}" data-id="${BigPaw.esc(p.id)}">${fav?'♥':'♡'}</button></div><div class="puppy-body"><p class="puppy-title">${BigPaw.esc(p.breed)}｜${BigPaw.esc(p.gender)}</p><div class="meta">${BigPaw.esc(p.color)} ・ ${BigPaw.esc(p.area)}</div><div class="size-line">成犬時目安 ${p.adultMin||'-'}〜${p.adultMax||'-'}kg</div><div class="price">${BigPaw.currency(p.price)} <small>税込</small></div><div class="health"><span>親犬サイズ</span><span>健康診断</span><span>遺伝子検査</span></div><div class="breeder-line"><span>${BigPaw.esc(p.breeder)}</span><span>${BigPaw.esc(p.status)}</span></div></div>`;
      el.addEventListener('click',e=>{if(e.target.closest('.fav'))return;location.href='puppy-detail.html?id='+encodeURIComponent(p.id)});
      el.querySelector('.fav').addEventListener('click',async e=>{e.stopPropagation();try{const r=await BigPawBridge.toggleFavorite(p.id);if(r.favorite)favIds.add(String(p.id));else favIds.delete(String(p.id));e.currentTarget.classList.toggle('on',r.favorite);e.currentTarget.textContent=r.favorite?'♥':'♡'}catch(x){if(x.status===401)location.href='login.html'}});
      grid.appendChild(el)
    });
    const rt=document.getElementById('resultText'); if(rt)rt.textContent=list.length+'頭を表示中';
  }
  window.applySearch=function(){const b=document.getElementById('breed').value,g=document.getElementById('gender').value,a=document.getElementById('area').value;const qs=new URLSearchParams();const bs=Array.isArray(window.BIGPAW_SELECTED_BREEDS)?window.BIGPAW_SELECTED_BREEDS:[];if(bs.length)qs.set('breed',bs.join(','));else if(b!=='all')qs.set('breed',b);if(g!=='all')qs.set('gender',g);if(a!=='all')qs.set('area',a);location.href='search.html?'+qs.toString()}
  window.quickBreed=function(b){location.href='search.html?breed='+encodeURIComponent(b)}
  window.filterChip=function(btn,type){document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));btn.classList.add('active');let list=[...all];if(type==='male'||type==='female')list=list.filter(p=>p.genderKey===type);if(type==='health')list=list.filter(p=>p.health);renderHomePuppies(list.slice(0,6))}
  (async()=>{try{all=await BigPawBridge.puppies();try{const fs=await BigPawBridge.favorites();favIds=new Set(fs.map(x=>String(x.id)))}catch(e){}renderHomePuppies(all.slice(0,6))}catch(e){all=BigPaw.getPuppies();renderHomePuppies(all.slice(0,6))}})();
})();
