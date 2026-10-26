(()=>{
  'use strict';
  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  async function render(){
    try{
      if(document.getElementById('bigpawPuppyVideoSection'))return;
      const id=new URLSearchParams(location.search).get('id');
      if(!id||!window.BigPawBridge)return;
      const p=await BigPawBridge.puppy(id);
      if(!p||!p.videoEmbedUrl)return;
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
    }catch(e){}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(render,250));
  else setTimeout(render,250);
  window.addEventListener('pageshow',()=>setTimeout(render,350));
})();