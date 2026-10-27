(()=>{
  'use strict';
  let cachedVideo=null;
  let rerenderTimer=0;
  let attempts=0;

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

  function insert(p){
    if(document.getElementById('bigpawPuppyVideoSection'))return true;
    if(!p||!p.videoEmbedUrl)return false;
    const section=document.createElement('section');
    section.id='bigpawPuppyVideoSection';
    // The public video belongs after the photo gallery, before the puppy
    // information/title card. Keep video transport, UID, and player untouched.
    section.className='card pad bigpaw-video-feature';
    section.style.cssText='margin:0 0 20px;width:100%;box-sizing:border-box';
    section.innerHTML='<h2>動画</h2><p class="muted" style="margin-top:-4px">この子の様子を動画でご覧いただけます。</p><div style="aspect-ratio:16/9;width:100%;background:#111;border-radius:16px;overflow:hidden"><iframe src="'+esc(p.videoEmbedUrl)+'" title="子犬の動画" loading="lazy" style="width:100%;height:100%;border:0;display:block" allow="accelerometer; gyroscope; encrypted-media; picture-in-picture" allowfullscreen></iframe></div>';
    const slot=document.getElementById('bigpawPuppyVideoSlot');
    if(slot){
      slot.appendChild(section);
    }else{
      // Backward-compatible placement if the older HTML is cached.
      const gallery=document.getElementById('bigpawRealGallery')||document.querySelector('.gallery');
      if(gallery)gallery.insertAdjacentElement('afterend',section);
      else return false;
    }
    return true;
  }

  async function render(){
    try{
      if(document.getElementById('bigpawPuppyVideoSection'))return true;
      const id=new URLSearchParams(location.search).get('id');
      if(!id||!window.BigPawBridge)return false;
      let p=cachedVideo;
      if(!p){
        p=await BigPawBridge.puppy(id);
        if(!p)return false;
        const uid=String(p.videoUid||'');
        const embed=String(p.videoEmbedUrl||(uid&&/^[A-Za-z0-9_-]{8,64}$/.test(uid)?'https://videodelivery.net/'+uid+'/iframe':''));
        if(!embed)return false;
        cachedVideo={id:p.id||id,videoEmbedUrl:embed};
      }
      return insert(cachedVideo);
    }catch(e){
      return false;
    }
  }

  function schedule(delay=120){
    clearTimeout(rerenderTimer);
    rerenderTimer=setTimeout(()=>{render()},delay);
  }

  function watch(){
    if(!document.body)return;
    const observer=new MutationObserver(()=>{
      if(cachedVideo && !document.getElementById('bigpawPuppyVideoSection'))schedule(80);
    });
    observer.observe(document.body,{childList:true,subtree:true});
  }

  window.BigPawPuppyVideoPublic={render};

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',()=>{
      watch();
      schedule(250);
      setTimeout(()=>schedule(0),900);
      [2000,5000,10000].forEach(ms=>setTimeout(()=>schedule(0),ms));
    });
  }else{
    watch();
    schedule(250);
    setTimeout(()=>schedule(0),900);
  }
  window.addEventListener('pageshow',()=>schedule(350));
})();