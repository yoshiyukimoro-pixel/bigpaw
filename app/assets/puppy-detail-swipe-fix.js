(()=>{
'use strict';
if(!/\/puppy-detail\.html$/.test(location.pathname))return;

const THRESHOLD=28;

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
  if(!stage||stage.dataset.bigpawSwipeFix==='1')return false;
  stage.dataset.bigpawSwipeFix='1';
  stage.style.touchAction='pan-y';
  stage.style.webkitUserSelect='none';
  stage.style.userSelect='none';

  if(window.PointerEvent){
    let activeId=null,startX=0,startY=0,horizontal=false;
    stage.addEventListener('pointerdown',e=>{
      if(e.pointerType==='mouse'&&e.button!==0)return;
      activeId=e.pointerId;startX=e.clientX;startY=e.clientY;horizontal=false;
      try{stage.setPointerCapture(e.pointerId)}catch(_e){}
    });
    stage.addEventListener('pointermove',e=>{
      if(activeId!==e.pointerId)return;
      const dx=e.clientX-startX,dy=e.clientY-startY;
      if(!horizontal&&Math.abs(dx)>8&&Math.abs(dx)>Math.abs(dy)*1.12)horizontal=true;
      if(horizontal&&e.cancelable)e.preventDefault();
    },{passive:false});
    const finish=e=>{
      if(activeId!==e.pointerId)return;
      const dx=e.clientX-startX,dy=e.clientY-startY;
      activeId=null;
      if(Math.abs(dx)>=THRESHOLD&&Math.abs(dx)>Math.abs(dy)*1.05)go(dx<0?1:-1);
    };
    stage.addEventListener('pointerup',finish);
    stage.addEventListener('pointercancel',e=>{if(activeId===e.pointerId)activeId=null});
  }else{
    let startX=null,startY=null,horizontal=false;
    stage.addEventListener('touchstart',e=>{
      if(e.touches.length!==1)return;
      startX=e.touches[0].clientX;startY=e.touches[0].clientY;horizontal=false;
    },{passive:true});
    stage.addEventListener('touchmove',e=>{
      if(startX==null||e.touches.length!==1)return;
      const dx=e.touches[0].clientX-startX,dy=e.touches[0].clientY-startY;
      if(!horizontal&&Math.abs(dx)>8&&Math.abs(dx)>Math.abs(dy)*1.12)horizontal=true;
      if(horizontal&&e.cancelable)e.preventDefault();
    },{passive:false});
    stage.addEventListener('touchend',e=>{
      if(startX==null||!e.changedTouches.length)return;
      const dx=e.changedTouches[0].clientX-startX,dy=e.changedTouches[0].clientY-startY;
      startX=startY=null;
      if(Math.abs(dx)>=THRESHOLD&&Math.abs(dx)>Math.abs(dy)*1.05)go(dx<0?1:-1);
    },{passive:true});
    stage.addEventListener('touchcancel',()=>{startX=startY=null});
  }
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
