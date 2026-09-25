(()=>{
  if(!/\/puppy-detail\.html$/.test(location.pathname))return;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  const layout=d=>({x:num(d?.imagePosX??d?.image_pos_x,50),y:num(d?.imagePosY??d?.image_pos_y,50),z:num(d?.imageZoom??d?.image_zoom,1)});

  function renderFocal(frame,img,x,y,z){
    if(!frame||!img)return;
    if(!img.complete||!img.naturalWidth){img.addEventListener('load',()=>renderFocal(frame,img,x,y,z),{once:true});return}
    const W=Math.max(1,frame.clientWidth||frame.getBoundingClientRect().width||1),H=Math.max(1,frame.clientHeight||frame.getBoundingClientRect().height||1);
    const nw=Math.max(1,img.naturalWidth),nh=Math.max(1,img.naturalHeight),base=Math.max(W/nw,H/nh),rw=nw*base*z,rh=nh*base*z;
    let left=W/2-(clamp(x,0,100)/100)*rw,top=H/2-(clamp(y,0,100)/100)*rh;
    left=clamp(left,W-rw,0);top=clamp(top,H-rh,0);
    Object.assign(img.style,{position:'absolute',width:rw+'px',height:rh+'px',maxWidth:'none',maxHeight:'none',left:left+'px',top:top+'px',objectFit:'fill',objectPosition:'50% 50%',transform:'none',transformOrigin:'50% 50%',display:'block'});
  }

  function card(label,d,fallback){
    const name=(d&&d.name)||fallback||'登録情報を掲載',a=layout(d),url=d&&(d.imageUrl||d.image_url)||'';
    const photo=url?`<div class="bp-parent-photo"><img src="${esc(url)}" alt="${esc(name)}" data-focal-x="${a.x}" data-focal-y="${a.y}" data-focal-z="${a.z}"></div>`:`<div class="bp-parent-photo bp-parent-empty">🐩<small>写真未登録</small></div>`;
    const meta=[d&&d.breed,d&&d.color].filter(Boolean).map(esc).join('・');
    return `<div class="bp-parent-card"><span class="bp-parent-label">${esc(label)}</span>${photo}<h3>${esc(name)}</h3>${meta?`<div class="bp-parent-meta">${meta}</div>`:''}</div>`;
  }
  function ensureCss(){if(document.getElementById('bpPublicParentCss'))return;const s=document.createElement('style');s.id='bpPublicParentCss';s.textContent='.bp-parent-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.bp-parent-card{border:1px solid #f0dbe5;border-radius:18px;padding:12px;background:#fff8fc;min-width:0}.bp-parent-label{display:inline-block;font-size:12px;font-weight:900;color:#b85d82;background:#fff1f7;border-radius:999px;padding:5px 9px;margin-bottom:9px}.bp-parent-photo{aspect-ratio:1/1;border-radius:14px;overflow:hidden;background:#f7eef2;display:grid;place-items:center;position:relative}.bp-parent-photo img{display:block}.bp-parent-empty{font-size:54px;color:#8f8195}.bp-parent-empty small{display:block;font-size:11px;margin-top:-12px}.bp-parent-card h3{font-size:17px;margin:10px 0 4px}.bp-parent-meta{font-size:13px;color:#8f8195}@media(max-width:520px){.bp-parent-card{padding:10px}.bp-parent-card h3{font-size:16px}}';document.head.appendChild(s)}
  function applyLayouts(root=document){root.querySelectorAll('.bp-parent-photo img[data-focal-x]').forEach(im=>renderFocal(im.parentElement,im,num(im.dataset.focalX,50),num(im.dataset.focalY,50),num(im.dataset.focalZ,1)))}
  async function latestPuppy(id){try{const headers={'Cache-Control':'no-cache'};if(window.BigPawAPI&&BigPawAPI.token&&BigPawAPI.token())headers.Authorization='Bearer '+BigPawAPI.token();const r=await fetch('/api/puppies/'+encodeURIComponent(id)+'?parentLayoutTs='+Date.now(),{cache:'no-store',headers});if(r.ok)return await r.json()}catch(_e){}return window.BigPawBridge?BigPawBridge.puppy(id):null}
  async function run(){try{ensureCss();const id=new URLSearchParams(location.search).get('id');if(!id)return;const p=await latestPuppy(id);if(!p)return;const parents=p.parentDogs||p.parent_dogs||{};const h=[...document.querySelectorAll('h2')].find(x=>x.textContent.trim()==='父犬・母犬');if(!h)return;const sec=h.closest('.card.pad')||h.parentElement;if(!sec)return;sec.innerHTML=`<h2>父犬・母犬</h2><div class="bp-parent-grid">${card('父犬',parents.father,p.father)}${card('母犬',parents.mother,p.mother)}</div>`;requestAnimationFrame(()=>applyLayouts(sec))}catch(_e){}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(run,0));else setTimeout(run,0);
  window.addEventListener('pageshow',()=>setTimeout(run,0));window.addEventListener('resize',()=>applyLayouts(document));
})();
