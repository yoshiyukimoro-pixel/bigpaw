(()=>{
  if(window.__BIGPAW_PUPPY_GALLERY_CAROUSEL_FIX__) return;
  window.__BIGPAW_PUPPY_GALLERY_CAROUSEL_FIX__=true;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function install(){
    const g=document.getElementById('bigpawRealGallery');
    if(!g || g.dataset.carouselFixed==='1') return false;
    const imgs=[...g.querySelectorAll('img')];
    const urls=[];
    imgs.forEach(img=>{
      const u=img.currentSrc||img.getAttribute('src')||'';
      if(u && !urls.includes(u)) urls.push(u);
    });
    if(!urls.length) return false;

    g.dataset.carouselFixed='1';
    const puppy=window.__BIGPAW_DETAIL_PUPPY||{};
    const alt=esc(puppy.breed||'子犬');
    g.innerHTML='';
    g.className='bigpaw-simple-carousel';

    const stage=document.createElement('div');
    stage.className='bp-carousel-stage';
    stage.innerHTML=`<img class="bp-carousel-main" alt="${alt}"><button type="button" class="bp-carousel-arrow bp-carousel-prev" aria-label="前の写真">‹</button><button type="button" class="bp-carousel-arrow bp-carousel-next" aria-label="次の写真">›</button><div class="bp-carousel-count"></div>`;

    const thumbs=document.createElement('div');
    thumbs.className='bp-carousel-thumbs';
    urls.forEach((u,i)=>{
      const b=document.createElement('button');
      b.type='button';
      b.className='bp-carousel-thumb';
      b.setAttribute('aria-label',`${i+1}枚目の写真を表示`);
      const im=document.createElement('img');
      im.src=u;
      im.alt=`${puppy.breed||'子犬'} ${i+1}`;
      im.loading=i<4?'eager':'lazy';
      b.appendChild(im);
      thumbs.appendChild(b);
    });
    g.append(stage,thumbs);

    const main=stage.querySelector('.bp-carousel-main');
    const count=stage.querySelector('.bp-carousel-count');
    const prev=stage.querySelector('.bp-carousel-prev');
    const next=stage.querySelector('.bp-carousel-next');
    const thumbButtons=[...thumbs.querySelectorAll('.bp-carousel-thumb')];
    let index=0;

    function show(n){
      index=(n+urls.length)%urls.length;
      main.src=urls[index];
      count.textContent=`${index+1} / ${urls.length}`;
      thumbButtons.forEach((b,i)=>{
        b.classList.toggle('active',i===index);
        b.setAttribute('aria-current',i===index?'true':'false');
      });
      const active=thumbButtons[index];
      if(active && active.scrollIntoView){
        try{ active.scrollIntoView({block:'nearest',inline:'nearest'}); }catch(_e){}
      }
    }

    function move(delta,e){
      if(e){e.preventDefault();e.stopPropagation();if(e.stopImmediatePropagation)e.stopImmediatePropagation();}
      show(index+delta);
    }
    prev.addEventListener('click',e=>move(-1,e),true);
    next.addEventListener('click',e=>move(1,e),true);
    thumbButtons.forEach((b,i)=>b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();show(i);},true));

    let startX=null;
    stage.addEventListener('touchstart',e=>{if(e.touches&&e.touches.length===1)startX=e.touches[0].clientX;},{passive:true});
    stage.addEventListener('touchend',e=>{
      if(startX===null||!e.changedTouches||!e.changedTouches.length)return;
      const dx=e.changedTouches[0].clientX-startX; startX=null;
      if(Math.abs(dx)>45) show(index+(dx<0?1:-1));
    },{passive:true});

    document.getElementById('bigpawPhotoViewer')?.remove();
    show(0);
    return true;
  }

  const style=document.createElement('style');
  style.id='bigpaw-simple-carousel-style';
  style.textContent=`
    #bigpawRealGallery.bigpaw-simple-carousel{display:block!important;margin:0 0 20px!important}
    .bp-carousel-stage{position:relative;width:100%;overflow:hidden;border-radius:18px;background:#f8e9ef;touch-action:pan-y}
    .bp-carousel-main{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;background:#f8e9ef}
    .bp-carousel-arrow{position:absolute;top:50%;transform:translateY(-50%);z-index:3;width:48px;height:48px;border:0;border-radius:50%;background:rgba(255,255,255,.94);color:#1593f3;font-size:36px;line-height:1;display:grid;place-items:center;box-shadow:0 2px 10px rgba(0,0,0,.12);cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
    .bp-carousel-prev{left:10px}.bp-carousel-next{right:10px}
    .bp-carousel-count{position:absolute;left:12px;bottom:10px;z-index:2;padding:4px 9px;border-radius:999px;background:rgba(0,0,0,.55);color:#fff;font-size:13px;font-weight:800}
    .bp-carousel-thumbs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}
    .bp-carousel-thumb{display:block;padding:0;border:2px solid transparent;border-radius:16px;background:transparent;overflow:hidden;cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
    .bp-carousel-thumb.active{border-color:#ef7fa8}
    .bp-carousel-thumb img{display:block;width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:13px;background:#f8e9ef}
    @media(min-width:821px){.bp-carousel-thumbs{grid-template-columns:repeat(4,minmax(0,1fr))}}
  `;
  document.head.appendChild(style);

  if(install()) return;
  const mo=new MutationObserver(()=>{if(install())mo.disconnect();});
  mo.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(()=>{if(install())mo.disconnect();},300);
  setTimeout(()=>{if(install())mo.disconnect();},1000);
  setTimeout(()=>{mo.disconnect();},5000);
})();
