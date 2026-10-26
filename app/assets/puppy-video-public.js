(()=>{
  'use strict';
  let cachedVideo=null;
  let rerenderTimer=0;

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

  function insert(p){
    if(document.getElementById('bigpawPuppyVideoSection'))return true;
    if(!p||!p.videoEmbedUrl)return false;
    const section=document.createElement('section');
    section.id='bigpawPuppyVideoSection';
    section.className='detailsection';
    section.style.marginTop='20px';
    section.innerHTML='<h2>動画</h2><p class="muted" style="margin-top:-4px">この子の様子を動画でご覧いただけます。</p><div style="aspect-ratio:16/9;width:100%;background:#111;border-radius:16px;overflow:hidden"><iframe src="'+esc(p.videoEmbedUrl)+'" title="子犬の動画" loading="lazy" style="width:100%;height:100%;border:0;display:block" allow="accelerometer; gyroscope; encrypted-media; picture-in-picture" allowfullscreen></iframe></div>';
    const more=document.getElementById('bigpawDetailMore');
    if(more)more.insertBefore(section,more.firstChild);
    else{
      const main=document.querySelector('main')||document.body;
      main.appendChild(section);
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
        if(!p||!p.videoEmbedUrl)return false;
        cachedVideo={id:p.id||id,videoEmbedUrl:p.videoEmbedUrl};
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
    });
  }else{
    watch();
    schedule(250);
    setTimeout(()=>schedule(0),900);
  }
  window.addEventListener('pageshow',()=>schedule(350));
})();