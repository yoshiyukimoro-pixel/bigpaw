(()=>{
'use strict';
const puppyId=new URLSearchParams(location.search).get('id');
if(!puppyId)return;
const MEDIA_V='20260926j3';
function collectUrls(p){
  const out=[],seen=new Set();
  const key=u=>String(u||'').split('?')[0];
  const add=u=>{
    if(out.length>=10||typeof u!=='string'||!u.trim())return;
    const s=u.trim(),k=key(s);if(seen.has(k))return;seen.add(k);out.push(s)
  };
  add(p&&p.imageUrl);
  [p&&p.photos,p&&p.images,p&&p.imageUrls,p&&p.photoUrls].forEach(a=>{
    if(!Array.isArray(a))return;
    a.forEach(x=>add(typeof x==='string'?x:(x&&(x.url||x.imageUrl||x.path))));
  });
  return out;
}
function setParam(s,name,value){
  const rx=new RegExp('([?&])'+name+'=[^&]*');
  if(rx.test(s))return s.replace(rx,'$1'+name+'='+encodeURIComponent(value));
  return s+(s.includes('?')?'&':'?')+name+'='+encodeURIComponent(value);
}
function mediaUrl(url,kind,preserveVersion=false){
  let s=String(url||'');
  if(!s)return s;
  if(s.startsWith('/media/')){
    s=setParam(s,'kind',kind);
    return preserveVersion?s:setParam(s,'v',MEDIA_V)
  }
  if(s.startsWith('/uploads/'))return '/media/'+encodeURIComponent(s.split('/').pop())+'?kind='+kind+'&v='+MEDIA_V;
  return s;
}
function installStyle(){
  if(document.getElementById('bigpawStableGalleryStyle'))return;
  const st=document.createElement('style');st.id='bigpawStableGalleryStyle';st.textContent=`
#bigpawStableGallery{margin:0 0 16px;width:100%}
#bigpawStableGallery .bpsg-stage{position:relative;width:min(100%,680px);aspect-ratio:1/1;margin:0 auto;border-radius:16px;overflow:hidden;background:#f7edf2;box-shadow:0 3px 14px rgba(70,45,58,.08);touch-action:pan-y}
#bigpawStableGallery .bpsg-stage>img{display:block;width:100%;height:100%;object-fit:cover;object-position:center;background:#f7edf2}
#bigpawStableGallery .bpsg-arrow{position:absolute;z-index:4;top:50%;transform:translateY(-50%);width:44px;height:44px;border:0;border-radius:50%;background:rgba(255,255,255,.88);color:#604b57;font-size:28px;line-height:1;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(0,0,0,.14);-webkit-tap-highlight-color:transparent}
#bigpawStableGallery .bpsg-prev{left:9px}#bigpawStableGallery .bpsg-next{right:9px}
#bigpawStableGallery .bpsg-count{position:absolute;z-index:4;right:12px;bottom:12px;padding:6px 11px;border-radius:999px;background:rgba(255,255,255,.9);color:#5d4854;font-size:13px;font-weight:800}
#bigpawStableGallery .bpsg-status{position:absolute;z-index:3;left:50%;bottom:12px;transform:translateX(-50%);display:none;padding:7px 11px;border-radius:999px;background:rgba(255,255,255,.93);color:#7a6570;font-weight:800;font-size:12px;white-space:nowrap}
#bigpawStableGallery .bpsg-empty{display:grid;place-items:center;width:100%;height:100%;font-size:74px}
#bigpawStableGallery .bpsg-thumbs{display:flex;gap:10px;overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;scrollbar-width:thin;padding:12px 2px 9px;margin:0 auto;width:min(100%,680px);scroll-snap-type:x proximity}
#bigpawStableGallery .bpsg-thumb{position:relative;flex:0 0 76px;width:76px;height:76px;padding:0;border:3px solid transparent;border-radius:5px;overflow:hidden;background:#f3e8ed;-webkit-tap-highlight-color:transparent;scroll-snap-align:center}
#bigpawStableGallery .bpsg-thumb.active{border-color:#ef7fa8;box-shadow:0 0 0 1px #ef7fa8}
#bigpawStableGallery .bpsg-thumb img{display:block;width:100%;height:100%;object-fit:cover;background:#f3e8ed}
#bigpawStableGallery .bpsg-thumb-placeholder{position:absolute;inset:0;display:grid;place-items:center;color:#b8a9b0;font-size:18px;background:#f3e8ed}
#bigpawStableGallery .bpsg-help{text-align:center;color:#85727c;font-size:12px;margin-top:0}
#bigpawStableGallery + #bigpawFavButton{display:block;width:100%;margin:0 0 16px;padding:14px;border:1px solid #ef7fa8;border-radius:14px;background:#fff;color:#b85d82;font-weight:900;font-size:16px}
@media(max-width:700px){#bigpawStableGallery .bpsg-stage{width:100%;border-radius:4px}#bigpawStableGallery .bpsg-arrow{display:none!important}#bigpawStableGallery .bpsg-thumb{flex-basis:70px;width:70px;height:70px}}
`;
  document.head.appendChild(st);
}
async function init(){
  if(!window.BigPawBridge){setTimeout(init,40);return}
  if(document.getElementById('bigpawStableGallery'))return;
  let p;
  try{p=await BigPawBridge.puppy(puppyId)}catch(_e){return}
  const old=document.querySelector('.gallery,#bigpawRealGallery');
  if(!old)return;
  installStyle();
  const urls=collectUrls(p||{});
  const root=document.createElement('section');root.id='bigpawStableGallery';root.setAttribute('aria-label','子犬の写真');
  const stage=document.createElement('div');stage.className='bpsg-stage';
  if(!urls.length){stage.innerHTML='<div class="bpsg-empty">🐩</div>';root.appendChild(stage);old.replaceWith(root);return}

  const img=document.createElement('img');img.alt=(p&&p.breed?p.breed:'子犬')+'の写真';img.loading='eager';
  const status=document.createElement('div');status.className='bpsg-status';status.textContent='写真を読み込めませんでした';
  const prev=document.createElement('button');prev.type='button';prev.className='bpsg-arrow bpsg-prev';prev.setAttribute('aria-label','前の写真');prev.textContent='‹';
  const next=document.createElement('button');next.type='button';next.className='bpsg-arrow bpsg-next';next.setAttribute('aria-label','次の写真');next.textContent='›';
  const count=document.createElement('div');count.className='bpsg-count';
  stage.append(img,status,prev,next,count);root.appendChild(stage);

  const thumbs=document.createElement('div');thumbs.className='bpsg-thumbs';thumbs.setAttribute('aria-label','写真一覧');
  const thumbButtons=urls.map((u,i)=>{
    const b=document.createElement('button');b.type='button';b.className='bpsg-thumb';b.setAttribute('aria-label','写真 '+(i+1)+' を表示');
    const ph=document.createElement('span');ph.className='bpsg-thumb-placeholder';ph.textContent='•';b.appendChild(ph);
    b.onclick=e=>{e.preventDefault();show(i)};thumbs.appendChild(b);return b;
  });
  root.appendChild(thumbs);
  const help=document.createElement('div');help.className='bpsg-help';help.textContent=urls.length>1?'写真を左右にスワイプ、または下の写真をタップして切り替え':'メイン写真';root.appendChild(help);
  old.replaceWith(root);

  let index=0,loadToken=0,startX=null,startY=null,heroFallback=false;
  const loadedThumbs=new Set(),queuedThumbs=new Set();
  function loadThumb(i,delay=0){
    if(i<0||i>=urls.length||loadedThumbs.has(i)||queuedThumbs.has(i))return;
    queuedThumbs.add(i);
    setTimeout(()=>{
      if(loadedThumbs.has(i)){queuedThumbs.delete(i);return}
      const b=thumbButtons[i];if(!b){queuedThumbs.delete(i);return}
      const ti=document.createElement('img');ti.alt='';
      ti.onload=()=>{loadedThumbs.add(i);queuedThumbs.delete(i);const ph=b.querySelector('.bpsg-thumb-placeholder');if(ph)ph.remove()};
      ti.onerror=()=>{queuedThumbs.delete(i)};
      ti.src=mediaUrl(urls[i],'thumb');b.appendChild(ti);
    },delay);
  }
  function loadAllThumbs(){thumbButtons.forEach((_b,i)=>loadThumb(i,i*60))}
  function paintThumbs(){thumbButtons.forEach((b,i)=>b.classList.toggle('active',i===index))}
  function show(n){
    index=(n+urls.length)%urls.length;heroFallback=false;
    const token=++loadToken;
    status.style.display='none';
    count.textContent=(index+1)+' / '+urls.length;
    const one=urls.length<2;prev.style.display=one?'none':'flex';next.style.display=one?'none':'flex';
    paintThumbs();
    img.onload=()=>{if(token===loadToken)status.style.display='none'};
    img.onerror=()=>{
      if(token!==loadToken)return;
      if(!heroFallback){heroFallback=true;img.src=mediaUrl(urls[index],'card');return}
      status.style.display='block'
    };
    const mobile=window.matchMedia&&window.matchMedia('(max-width:700px)').matches;
    img.src=mediaUrl(urls[index],mobile?'card':'hero',mobile);
    loadThumb(index,0);
  }
  prev.onclick=e=>{e.preventDefault();e.stopPropagation();show(index-1)};
  next.onclick=e=>{e.preventDefault();e.stopPropagation();show(index+1)};
  stage.addEventListener('touchstart',e=>{if(e.touches.length!==1)return;startX=e.touches[0].clientX;startY=e.touches[0].clientY},{passive:true});
  stage.addEventListener('touchend',e=>{if(startX==null||!e.changedTouches.length)return;const dx=e.changedTouches[0].clientX-startX,dy=e.changedTouches[0].clientY-startY;startX=startY=null;if(Math.abs(dx)>34&&Math.abs(dx)>Math.abs(dy)*1.1)show(index+(dx<0?1:-1))},{passive:true});

  const fav=document.getElementById('bigpawFavButton')||document.createElement('button');
  if(!fav.id){fav.id='bigpawFavButton';fav.type='button';fav.textContent='♡ お気に入りに保存';root.insertAdjacentElement('afterend',fav)}
  show(0);
  setTimeout(loadAllThumbs,40);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
