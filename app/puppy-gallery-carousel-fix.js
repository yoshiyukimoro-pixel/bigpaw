(()=>{
  if(window.__BIGPAW_PUPPY_GALLERY_CAROUSEL_FIX__) return;
  window.__BIGPAW_PUPPY_GALLERY_CAROUSEL_FIX__=true;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function variant(u,kind){
    try{
      const x=new URL(u,location.origin);
      if(x.pathname.startsWith('/media/')){x.searchParams.set('kind',kind);return x.pathname+x.search}
      if(x.pathname.startsWith('/uploads/'))return '/media/'+encodeURIComponent(x.pathname.split('/').pop())+'?kind='+encodeURIComponent(kind);
    }catch(_e){}
    return u;
  }

  function install(){
    const old=document.getElementById('bigpawRealGallery');
    if(!old || old.dataset.carouselFixed==='1') return false;
    const imgs=[...old.querySelectorAll('img')];
    const urls=[];
    imgs.forEach(img=>{
      const u=img.getAttribute('data-src')||img.currentSrc||img.getAttribute('src')||'';
      if(u && !urls.includes(u)) urls.push(u);
    });
    if(!urls.length) return false;

    const puppy=window.__BIGPAW_DETAIL_PUPPY||{};
    const alt=esc(puppy.breed||'子犬');
    const g=document.createElement('div');
    g.id='bigpawRealGallery';
    g.dataset.carouselFixed='1';
    g.className='bigpaw-simple-carousel';

    const stage=document.createElement('div');
    stage.className='bp-carousel-stage';
    stage.innerHTML=`<img class="bp-carousel-main" alt="${alt}" decoding="async" fetchpriority="high"><button type="button" class="bp-carousel-arrow bp-carousel-prev" aria-label="前の写真">‹</button><button type="button" class="bp-carousel-arrow bp-carousel-next" aria-label="次の写真">›</button><div class="bp-carousel-count"></div>`;

    const thumbs=document.createElement('div');
    thumbs.className='bp-carousel-thumbs';
    urls.forEach((u,i)=>{
      const b=document.createElement('button');
      b.type='button';
      b.className='bp-carousel-thumb';
      b.setAttribute('aria-label',`${i+1}枚目の写真を表示`);
      const im=document.createElement('img');
      im.dataset.src=variant(u,'thumb');
      im.alt=`${puppy.breed||'子犬'} ${i+1}`;
      im.decoding='async';
      b.appendChild(im);
      thumbs.appendChild(b);
    });
    g.append(stage,thumbs);
    old.replaceWith(g);

    const main=stage.querySelector('.bp-carousel-main');
    const count=stage.querySelector('.bp-carousel-count');
    const prev=stage.querySelector('.bp-carousel-prev');
    const next=stage.querySelector('.bp-carousel-next');
    const thumbButtons=[...thumbs.querySelectorAll('.bp-carousel-thumb')];
    let index=0,thumbTimer=null;

    function loadThumb(i){
      const im=thumbButtons[i]?.querySelector('img');
      if(im && !im.src && im.dataset.src) im.src=im.dataset.src;
    }
    function scheduleThumbs(){
      let i=0;
      clearTimeout(thumbTimer);
      const step=()=>{
        if(i>=thumbButtons.length)return;
        loadThumb(i++);
        thumbTimer=setTimeout(step,350);
      };
      thumbTimer=setTimeout(step,250);
    }
    function show(n){
      index=(n+urls.length)%urls.length;
      const hero=variant(urls[index],'hero');
      if(main.getAttribute('src')!==hero)main.src=hero;
      count.textContent=`${index+1} / ${urls.length}`;
      loadThumb(index);
      thumbButtons.forEach((b,i)=>{
        b.classList.toggle('active',i===index);
        b.setAttribute('aria-current',i===index?'true':'false');
      });
    }

    function move(delta,e){
      if(e){
        e.preventDefault();
        e.stopPropagation();
        if(e.stopImmediatePropagation)e.stopImmediatePropagation();
      }
      show(index+delta);
    }
    prev.addEventListener('click',e=>move(-1,e),true);
    next.addEventListener('click',e=>move(1,e),true);
    thumbButtons.forEach((b,i)=>b.addEventListener('click',e=>{
      e.preventDefault();
      e.stopPropagation();
      if(e.stopImmediatePropagation)e.stopImmediatePropagation();
      show(i);
    },true));

    let startX=null;
    stage.addEventListener('touchstart',e=>{
      if(e.touches&&e.touches.length===1)startX=e.touches[0].clientX;
    },{passive:true});
    stage.addEventListener('touchend',e=>{
      if(startX===null||!e.changedTouches||!e.changedTouches.length)return;
      const dx=e.changedTouches[0].clientX-startX;
      startX=null;
      if(Math.abs(dx)>45)show(index+(dx<0?1:-1));
    },{passive:true});

    document.getElementById('bigpawPhotoViewer')?.remove();
    document.documentElement.style.overflow='';
    main.addEventListener('load',()=>scheduleThumbs(),{once:true});
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
    .bp-carousel-thumb{display:block;padding:0;border:2px solid transparent;border-radius:16px;background:#f8e9ef;overflow:hidden;cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation;aspect-ratio:1/1}
    .bp-carousel-thumb.active{border-color:#ef7fa8}
    .bp-carousel-thumb img{display:block;width:100%;height:100%;object-fit:cover;border-radius:13px;background:#f8e9ef}
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
