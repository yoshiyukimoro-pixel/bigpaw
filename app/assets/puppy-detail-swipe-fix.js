(()=>{
'use strict';
if(!/\/puppy-detail\.html$/.test(location.pathname))return;
if(!window.matchMedia||!window.matchMedia('(max-width:700px)').matches)return;

const puppyId=new URLSearchParams(location.search).get('id');
if(!puppyId)return;
const MEDIA_V='20260927native1';

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
function mediaUrl(url){
  const s=String(url||'');
  if(!s)return s;
  if(s.startsWith('/media/')){
    const base=s.split('?')[0];
    return base+'?kind=card&v='+MEDIA_V;
  }
  if(s.startsWith('/uploads/')){
    return '/media/'+encodeURIComponent(s.split('/').pop())+'?kind=card&v='+MEDIA_V;
  }
  return s;
}
function root(){return document.getElementById('bigpawStableGallery')}

async function install(){
  const g=root();
  if(!g)return false;
  if(g.dataset.bigpawNativeSwipe==='3')return true;
  if(!window.BigPawBridge)return false;

  let p;
  try{p=await BigPawBridge.puppy(puppyId)}catch(_e){return false}
  const urls=collectUrls(p||{});
  if(urls.length<2){g.dataset.bigpawNativeSwipe='3';return true}

  const oldStage=g.querySelector('.bpsg-stage');
  const thumbs=g.querySelector('.bpsg-thumbs');
  if(!oldStage||!thumbs)return false;

  // Replace the old stage entirely. This removes every legacy touch/pointer
  // listener from the mobile hero so Safari/Chrome can handle horizontal
  // scrolling natively instead of JavaScript interpreting finger gestures.
  const stage=document.createElement('div');
  stage.className='bpsg-stage';
  stage.dataset.bigpawNativeStage='1';
  stage.style.position='relative';
  stage.style.overflow='hidden';
  stage.style.touchAction='auto';

  const track=document.createElement('div');
  track.className='bpsg-native-track';
  track.setAttribute('aria-label','子犬の写真を左右にスクロール');
  track.style.cssText='position:absolute;inset:0;display:flex;width:100%;height:100%;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;scroll-behavior:smooth;-webkit-overflow-scrolling:touch;touch-action:pan-x pan-y;overscroll-behavior-x:contain;';

  urls.forEach((u,i)=>{
    const slide=document.createElement('div');
    slide.className='bpsg-native-slide';
    slide.style.cssText='flex:0 0 100%;width:100%;height:100%;scroll-snap-align:start;scroll-snap-stop:always;';
    const img=document.createElement('img');
    img.alt=(p&&p.breed?p.breed:'子犬')+'の写真 '+(i+1);
    img.draggable=false;
    img.loading=i===0?'eager':'lazy';
    img.decoding='async';
    img.style.cssText='display:block;width:100%;height:100%;object-fit:cover;object-position:center;pointer-events:none;-webkit-user-drag:none;user-select:none;';
    img.src=mediaUrl(u);
    slide.appendChild(img);track.appendChild(slide);
  });

  const count=document.createElement('div');
  count.className='bpsg-count';
  count.textContent='1 / '+urls.length;
  stage.append(track,count);
  oldStage.replaceWith(stage);

  // Clone thumbnails to remove the legacy click handlers tied to the detached
  // stage, then make them control the native scroller directly.
  const oldButtons=[...thumbs.querySelectorAll('.bpsg-thumb')];
  const buttons=oldButtons.map((old,i)=>{
    const b=old.cloneNode(true);
    b.classList.toggle('active',i===0);
    old.replaceWith(b);
    b.addEventListener('click',e=>{
      e.preventDefault();e.stopPropagation();
      const w=track.clientWidth||1;
      track.scrollTo({left:w*i,behavior:'smooth'});
    });
    return b;
  });

  let current=0,raf=0,settle=0;
  const paint=i=>{
    const n=Math.max(0,Math.min(urls.length-1,i));
    if(n===current&&count.textContent===(n+1)+' / '+urls.length)return;
    current=n;
    count.textContent=(n+1)+' / '+urls.length;
    buttons.forEach((b,j)=>b.classList.toggle('active',j===n));
    const b=buttons[n];
    if(b&&typeof b.scrollIntoView==='function')b.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
  };
  const readIndex=()=>{
    raf=0;
    const w=track.clientWidth||1;
    paint(Math.round(track.scrollLeft/w));
  };
  track.addEventListener('scroll',()=>{
    if(!raf)raf=requestAnimationFrame(readIndex);
    clearTimeout(settle);settle=setTimeout(readIndex,90);
  },{passive:true});
  window.addEventListener('resize',()=>{
    const w=track.clientWidth||1;
    track.scrollTo({left:w*current,behavior:'auto'});
  },{passive:true});

  g.dataset.bigpawNativeSwipe='3';
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
