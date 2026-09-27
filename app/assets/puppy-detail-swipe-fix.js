(()=>{
'use strict';
if(!/\/puppy-detail\.html$/.test(location.pathname))return;

const THRESHOLD=24;

function gallery(){return document.getElementById('bigpawStableGallery')}
function thumbs(root){return root?[...root.querySelectorAll('.bpsg-thumb')]:[]}
function go(delta){
  const root=gallery(),items=thumbs(root);
  if(items.length<2)return;
  let index=items.findIndex(b=>b.classList.contains('active'));
  if(index<0)index=0;
  const next=(index+delta+items.length)%items.length;
  items[next]?.click();
}

function install(){
  const root=gallery(),stage=root?.querySelector('.bpsg-stage');
  if(!stage||stage.dataset.bigpawSwipeFix==='2')return false;
  stage.dataset.bigpawSwipeFix='2';
  stage.style.touchAction='pan-y';
  stage.style.webkitUserSelect='none';
  stage.style.userSelect='none';
  stage.setAttribute('draggable','false');
  const hero=stage.querySelector('img');if(hero)hero.setAttribute('draggable','false');

  let startX=null,startY=null,horizontal=false;
  const reset=()=>{startX=null;startY=null;horizontal=false};

  // Capture-phase touch handlers intentionally own mobile swiping.  The
  // gallery's older bubbling touch handlers are stopped so one gesture can
  // never advance twice or cancel itself on iOS Safari/Chrome.
  stage.addEventListener('touchstart',e=>{
    if(e.touches.length!==1){reset();return}
    startX=e.touches[0].clientX;startY=e.touches[0].clientY;horizontal=false;
    e.stopImmediatePropagation();
  },{capture:true,passive:true});

  stage.addEventListener('touchmove',e=>{
    if(startX==null||e.touches.length!==1)return;
    const dx=e.touches[0].clientX-startX,dy=e.touches[0].clientY-startY;
    if(!horizontal&&Math.abs(dx)>7&&Math.abs(dx)>Math.abs(dy)*1.08)horizontal=true;
    if(horizontal){
      e.stopImmediatePropagation();
      if(e.cancelable)e.preventDefault();
    }
  },{capture:true,passive:false});

  stage.addEventListener('touchend',e=>{
    if(startX==null||!e.changedTouches.length){reset();return}
    const dx=e.changedTouches[0].clientX-startX,dy=e.changedTouches[0].clientY-startY;
    e.stopImmediatePropagation();
    reset();
    if(Math.abs(dx)>=THRESHOLD&&Math.abs(dx)>Math.abs(dy)*1.05)go(dx<0?1:-1);
  },{capture:true,passive:true});

  stage.addEventListener('touchcancel',e=>{e.stopImmediatePropagation();reset()},{capture:true,passive:true});
  stage.addEventListener('dragstart',e=>e.preventDefault());
  return true;
}

function boot(){
  if(install())return;
  const obs=new MutationObserver(()=>{if(install())obs.disconnect()});
  obs.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(()=>{install();obs.disconnect()},8000);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
