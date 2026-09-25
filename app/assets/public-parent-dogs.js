(()=>{
  if(!/\/puppy-detail\.html$/.test(location.pathname))return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
  const layout=d=>({
    x:num(d?.imagePosX??d?.image_pos_x,50),
    y:num(d?.imagePosY??d?.image_pos_y,50),
    z:num(d?.imageZoom??d?.image_zoom,1)
  });

  function card(label,d,fallback){
    const name=(d&&d.name)||fallback||'登録情報を掲載';
    const a=layout(d);
    const photo=d&&(d.imageUrl||d.image_url)
      ?`<div class="bp-parent-photo"><img src="${esc(d.imageUrl||d.image_url)}" alt="${esc(name)}" style="object-position:${a.x}% ${a.y}%;transform:scale(${a.z});transform-origin:${a.x}% ${a.y}%"></div>`
      :`<div class="bp-parent-photo bp-parent-empty">🐩<small>写真未登録</small></div>`;
    const meta=[d&&d.breed,d&&d.color].filter(Boolean).map(esc).join('・');
    return `<div class="bp-parent-card"><span class="bp-parent-label">${esc(label)}</span>${photo}<h3>${esc(name)}</h3>${meta?`<div class="bp-parent-meta">${meta}</div>`:''}</div>`;
  }

  function ensureCss(){
    if(document.getElementById('bpPublicParentCss'))return;
    const s=document.createElement('style');
    s.id='bpPublicParentCss';
    s.textContent='.bp-parent-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.bp-parent-card{border:1px solid #f0dbe5;border-radius:18px;padding:12px;background:#fff8fc;min-width:0}.bp-parent-label{display:inline-block;font-size:12px;font-weight:900;color:#b85d82;background:#fff1f7;border-radius:999px;padding:5px 9px;margin-bottom:9px}.bp-parent-photo{aspect-ratio:1/1;border-radius:14px;overflow:hidden;background:#f7eef2;display:grid;place-items:center;position:relative}.bp-parent-photo img{width:100%;height:100%;object-fit:cover;display:block;will-change:transform}.bp-parent-empty{font-size:54px;color:#8f8195}.bp-parent-empty small{display:block;font-size:11px;margin-top:-12px}.bp-parent-card h3{font-size:17px;margin:10px 0 4px}.bp-parent-meta{font-size:13px;color:#8f8195}@media(max-width:520px){.bp-parent-card{padding:10px}.bp-parent-card h3{font-size:16px}}';
    document.head.appendChild(s);
  }

  async function latestPuppy(id){
    try{
      const headers={'Cache-Control':'no-cache'};
      if(window.BigPawAPI&&BigPawAPI.token&&BigPawAPI.token())headers.Authorization='Bearer '+BigPawAPI.token();
      const r=await fetch('/api/puppies/'+encodeURIComponent(id),{cache:'no-store',headers});
      if(r.ok)return await r.json();
    }catch(_e){}
    return window.BigPawBridge?BigPawBridge.puppy(id):null;
  }

  async function run(){
    try{
      ensureCss();
      const id=new URLSearchParams(location.search).get('id');
      if(!id)return;
      const p=await latestPuppy(id);
      if(!p)return;
      const parents=p.parentDogs||p.parent_dogs||{};
      const h=[...document.querySelectorAll('h2')].find(x=>x.textContent.trim()==='父犬・母犬');
      if(!h)return;
      const sec=h.closest('.card.pad')||h.parentElement;
      if(!sec)return;
      sec.innerHTML=`<h2>父犬・母犬</h2><div class="bp-parent-grid">${card('父犬',parents.father,p.father)}${card('母犬',parents.mother,p.mother)}</div>`;
    }catch(_e){}
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(run,0));
  else setTimeout(run,0);
  window.addEventListener('pageshow',()=>setTimeout(run,0));
})();
