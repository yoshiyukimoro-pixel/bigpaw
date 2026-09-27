(()=>{
'use strict';
if(!/\/puppy-detail\.html$/.test(location.pathname))return;
if(!window.matchMedia||!window.matchMedia('(max-width:700px)').matches)return;

const puppyId=new URLSearchParams(location.search).get('id');
if(!puppyId)return;
const MEDIA_V='20260927native2';

function collectUrls(p){
  const out=[],seen=new Set();
  const add=u=>{
    if(out.length>=10||typeof u!=='string'||!u.trim())return;
    const s=u.trim(),k=s.split('?')[0];
    if(seen.has(k))return;
    seen.add(k);out.push(s);
  };
  add(p&&p.imageUrl);
  [p&&p.photos,p&&p.images,p&&p.imageUrls,p&&p.photoUrls].forEach(a=>{
    if(!Array.isArray(a))return;
    a.forEach(x=>add(typeof x==='string'?x:(x&&(x.url||x.imageUrl||x.path))));
  });
  return out;
}
function mediaUrl(url,kind='card'){
  const s=String(url||'');
  if(!s)return s;
  if(s.startsWith('/media/')){
    const base=s.split('?')[0];
    return base+'?kind='+encodeURIComponent(kind)+'&v='+MEDIA_V;
  }
  if(s.startsWith('/uploads/')){
    return '/media/'+encodeURIComponent(s.split('/').pop())+'?kind='+encodeURIComponent(kind)+'&v='+MEDIA_V;
  }
  return s;
}
function gallery(){return document.getElementById('bigpawStableGallery')}
function preload(url){
  return new Promise(resolve=>{
    const im=new Image();
    let done=false;
    const finish=()=>{if(done)return;done=true;resolve()};
    im.onload=finish;im.onerror=finish;im.src=url;
    if(im.complete)finish();
    setTimeout(finish,5000);
  });
}

async function install(){
  const g=gallery();
  if(!g)return false;
  if(g.dataset.bigpawNativeSwipe==='4')return true;
  if(!window.BigPawBridge)return false;

  let p;
  try{p=await BigPawBridge.puppy(puppyId)}catch(_e){return false}
  const urls=collectUrls(p||{});
  if(urls.length<2){g.dataset.bigpawNativeSwipe='4';return true}

  const oldStage=g.querySelector('.bpsg-stage');
  const oldThumbs=g.querySelector('.bpsg-thumbs');
  if(!oldStage||!oldThumbs)return false;

  // Prepare every mobile hero image before replacing the working first image.
  // Max 10 photos, card-size delivery. This prevents blank slides when the user
  // swipes quickly in iOS Safari or Chrome.
  const heroUrls=urls.map(u=>mediaUrl(u,'card'));
  await Promise.all(heroUrls.map(preload));

  const stage=document.createElement('div');
  stage.className='bpsg-stage';
  stage.dataset.bigpawNativeStage='2';
  stage.style.cssText='position:relative;overflow:hidden;touch-action:auto;';

  const track=document.createElement('div');
  track.className='bpsg-native-track';
  track.setAttribute('aria-label','子犬の写真を左右にスワイプ');
  track.style.cssText='position:absolute;inset:0;display:flex;width:100%;height:100%;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;touch-action:auto;overscroll-behavior-x:contain;scrollbar-width:none;';
  track.style.webkitOverflowScrolling='touch';

  const slides=heroUrls.map((src,i)=>{
    const slide=document.createElement('div');
    slide.className='bpsg-native-slide';
    slide.dataset.index=String(i);
    slide.style.cssText='position:relative;flex:0 0 100%;width:100%;height:100%;scroll-snap-align:start;scroll-snap-stop:always;';
    const img=document.createElement('img');
    img.alt=(p&&p.breed?p.breed:'子犬')+'の写真 '+(i+1);
    img.draggable=false;
    img.loading='eager';
    img.decoding='async';
    img.style.cssText='display:block;width:100%;height:100%;object-fit:cover;object-position:center;pointer-events:none;-webkit-user-drag:none;user-select:none;';
    img.src=src;
    slide.appendChild(img);track.appendChild(slide);return slide;
  });

  const count=document.createElement('div');
  count.className='bpsg-count';
  count.textContent='1 / '+urls.length;
  stage.append(track,count);
  oldStage.replaceWith(stage);

  // Rebuild thumbnails from the actual photo URLs. Do not clone placeholder
  // dots from the older gallery.
  const thumbs=document.createElement('div');
  thumbs.className='bpsg-thumbs';
  thumbs.setAttribute('aria-label','写真一覧');
  const buttons=urls.map((u,i)=>{
    const b=document.createElement('button');
    b.type='button';b.className='bpsg-thumb'+(i===0?' active':'');
    b.setAttribute('aria-label','写真 '+(i+1)+' を表示');
    const ti=document.createElement('img');ti.alt='';ti.loading='eager';ti.decoding='async';ti.src=mediaUrl(u,'thumb');
    b.appendChild(ti);
    b.addEventListener('click',e=>{
      e.preventDefault();e.stopPropagation();
      const w=track.clientWidth||1;
      track.scrollTo({left:w*i,behavior:'smooth'});
    });
    thumbs.appendChild(b);return b;
  });
  oldThumbs.replaceWith(thumbs);

  let current=0,raf=0,settle=0;
  const paint=i=>{
    const n=Math.max(0,Math.min(urls.length-1,i));
    current=n;
    count.textContent=(n+1)+' / '+urls.length;
    buttons.forEach((b,j)=>b.classList.toggle('active',j===n));
    const b=buttons[n];
    if(b){
      const left=Math.max(0,b.offsetLeft-(thumbs.clientWidth-b.clientWidth)/2);
      thumbs.scrollTo({left,behavior:'smooth'});
    }
  };
  const readIndex=()=>{
    raf=0;
    const w=track.clientWidth||1;
    paint(Math.round(track.scrollLeft/w));
  };
  track.addEventListener('scroll',()=>{
    if(!raf)raf=requestAnimationFrame(readIndex);
    clearTimeout(settle);settle=setTimeout(readIndex,80);
  },{passive:true});

  if('IntersectionObserver' in window){
    const io=new IntersectionObserver(entries=>{
      let best=null;
      entries.forEach(e=>{if(e.isIntersecting&&(!best||e.intersectionRatio>best.intersectionRatio))best=e});
      if(best)paint(Number(best.target.dataset.index)||0);
    },{root:track,threshold:[0.55,0.7,0.9]});
    slides.forEach(s=>io.observe(s));
  }

  window.addEventListener('resize',()=>{
    const w=track.clientWidth||1;
    track.scrollTo({left:w*current,behavior:'auto'});
  },{passive:true});

  const help=g.querySelector('.bpsg-help');
  if(help)help.textContent='写真を左右にスワイプ、または下の写真をタップして切り替え';
  g.dataset.bigpawNativeSwipe='4';
  paint(0);
  return true;
}

function boot(){
  install().then(ok=>{
    if(ok)return;
    const obs=new MutationObserver(()=>{install().then(done=>{if(done)obs.disconnect()})});
    obs.observe(document.documentElement,{childList:true,subtree:true});
    setTimeout(()=>{install();obs.disconnect()},10000);
  });
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
