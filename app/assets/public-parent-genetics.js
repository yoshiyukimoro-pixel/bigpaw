(()=>{
  if(!/\/puppy-detail\.html$/.test(location.pathname))return;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function parse(value){
    const text=String(value||'').trim();if(!text)return [];
    return text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{
      let parts=line.split('｜');if(parts.length<2)parts=line.split(/\s*\|\s*/);
      if(parts.length<2)return {name:line,result:''};
      return {name:String(parts.shift()||'').trim(),result:String(parts.join('｜')||'').trim()};
    }).filter(x=>x.name);
  }
  function ensureCss(){
    if(document.getElementById('bpPublicParentGeneticsCss'))return;
    const s=document.createElement('style');s.id='bpPublicParentGeneticsCss';
    s.textContent='.bp-public-genetics{margin-top:10px;padding-top:9px;border-top:1px solid #f0e3ea}.bp-public-genetics-title{font-size:12px;font-weight:900;color:#765d69;margin-bottom:6px}.bp-public-gen-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;padding:6px 0;border-top:1px solid #f3e8ed;font-size:11px;line-height:1.4}.bp-public-gen-row:first-of-type{border-top:0}.bp-public-gen-row span{min-width:0}.bp-public-gen-row b{white-space:nowrap;color:#b85d82;font-size:12px}@media(max-width:520px){.bp-public-gen-row{font-size:10px;gap:5px}.bp-public-gen-row b{font-size:11px}}';
    document.head.appendChild(s);
  }
  function render(value){
    const rows=parse(value);if(!rows.length)return '';
    return `<div class="bp-public-genetics"><div class="bp-public-genetics-title">遺伝子検査</div>${rows.map(r=>`<div class="bp-public-gen-row"><span>${esc(r.name)}</span><b>${esc(r.result||'')}</b></div>`).join('')}</div>`;
  }
  async function latestPuppy(id){try{const r=await fetch('/api/puppies/'+encodeURIComponent(id)+'?parentGeneticsTs='+Date.now(),{cache:'no-store',headers:{'Cache-Control':'no-cache'}});if(r.ok)return await r.json()}catch(_e){}return null}
  function decorate(p){
    const grid=document.querySelector('.bp-parent-grid');if(!grid)return false;
    const cards=[...grid.querySelectorAll('.bp-parent-card')],parents=p?.parentDogs||p?.parent_dogs||{};
    const data=[parents.father,parents.mother];
    cards.forEach((card,i)=>{card.querySelector('.bp-public-genetics')?.remove();const html=render(data[i]?.genetics);if(!html)return;const meta=card.querySelector('.bp-parent-meta'),h=card.querySelector('h3');(meta||h||card).insertAdjacentHTML('afterend',html)});
    return true;
  }
  async function run(){
    ensureCss();const id=new URLSearchParams(location.search).get('id');if(!id)return;const p=await latestPuppy(id);if(!p)return;
    if(decorate(p))return;
    let n=0;const t=setInterval(()=>{n++;if(decorate(p)||n>30)clearInterval(t)},100);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
  window.addEventListener('pageshow',run);
})();
