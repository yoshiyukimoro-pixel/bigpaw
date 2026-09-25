(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
  let parents=[];

  function imageOf(d){return d&&(d.image_url||d.imageUrl)||''}
  function layoutOf(d){return {x:num(d&&(d.image_pos_x??d.imagePosX),50),y:num(d&&(d.image_pos_y??d.imagePosY),50),z:num(d&&(d.image_zoom??d.imageZoom),1)}}
  function makePreview(id,label){
    const box=document.createElement('div');
    box.id=id;
    box.style.cssText='display:none;margin-top:10px;padding:10px;border:1px solid #cfe0f7;border-radius:14px;background:#f7fbff;align-items:center;gap:12px';
    box.innerHTML=`<div data-parent-photo style="width:72px;height:72px;flex:0 0 72px;border-radius:12px;background:#e7f1ff;display:grid;place-items:center;font-size:34px;overflow:hidden">🐩</div><div><b data-parent-name>${esc(label)}</b><div class="muted" data-parent-meta style="font-size:12px"></div><div class="muted" data-parent-note style="font-size:11px;margin-top:3px"></div></div>`;
    return box;
  }
  function renderPreview(select,box){
    const id=select.selectedOptions[0]?.dataset?.parentId||'';
    const dog=parents.find(x=>String(x.id)===String(id));
    if(!dog){box.style.display='none';return}
    box.style.display='flex';
    box.querySelector('[data-parent-name]').textContent=dog.name||'';
    box.querySelector('[data-parent-meta]').textContent=[dog.breed,dog.color].filter(Boolean).join('・');
    const photo=box.querySelector('[data-parent-photo]'),url=imageOf(dog),a=layoutOf(dog);
    photo.innerHTML=url?`<img src="${esc(url)}" alt="${esc(dog.name||'親犬')}" style="width:100%;height:100%;object-fit:cover;object-position:${a.x}% ${a.y}%;transform:scale(${a.z});transform-origin:${a.x}% ${a.y}%;display:block">`:'🐩';
    box.querySelector('[data-parent-note]').textContent=url?'親犬管理に登録された写真':'写真未登録（写真は任意です）';
  }
  function populate(select,sex,currentValue){
    const list=parents.filter(x=>String(x.sex||'')===sex);
    const keep=String(currentValue||select.value||'').trim();
    select.innerHTML='';
    const blank=document.createElement('option');blank.value='未登録';blank.textContent='未登録';select.appendChild(blank);
    list.forEach(d=>{const o=document.createElement('option');o.value=d.name||'';o.textContent=d.name||'名称未登録';o.dataset.parentId=d.id||'';select.appendChild(o)});
    if(keep&&keep!=='未登録'&&!list.some(d=>String(d.name)===keep)){
      const legacy=document.createElement('option');legacy.value=keep;legacy.textContent=keep+'（既存登録）';select.appendChild(legacy);
    }
    select.value=keep||'未登録';
    if(!select.value)select.value='未登録';
  }
  async function install(){
    if(!/breeder-puppy-new\.html$/.test(location.pathname))return;
    const father=document.getElementById('father'),mother=document.getElementById('mother');
    if(!father||!mother||!window.BigPawAPI)return;
    const fBox=makePreview('fatherParentPreview','父犬'),mBox=makePreview('motherParentPreview','母犬');
    father.closest('.field')?.appendChild(fBox);mother.closest('.field')?.appendChild(mBox);
    try{
      parents=await BigPawAPI.parentDogs();
      let currentFather=father.value,currentMother=mother.value;
      const editId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId')||'';
      if(editId&&window.BigPawBridge){
        try{const ds=await BigPawBridge.breederPuppies();const d=(ds||[]).find(x=>String(x.id)===String(editId));if(d){currentFather=d.father||currentFather;currentMother=d.mother||currentMother}}catch(_e){}
      }
      populate(father,'父犬',currentFather);populate(mother,'母犬',currentMother);
      renderPreview(father,fBox);renderPreview(mother,mBox);
      father.addEventListener('change',()=>renderPreview(father,fBox));mother.addEventListener('change',()=>renderPreview(mother,mBox));
      const help=document.createElement('div');help.className='notice';help.style.margin='12px 0 18px';help.innerHTML='父犬・母犬は「親犬管理」に登録した犬から選べます。写真を登録してある場合は、親犬管理で調整した位置・拡大率のまま表示されます。写真登録は任意です。 <a href="parent-dogs.html" style="font-weight:800;text-decoration:underline">親犬管理を開く →</a>';
      const target=mother.closest('.field')?.parentElement;if(target)target.insertAdjacentElement('afterend',help);
    }catch(_e){
      // Existing static selections remain usable if parent-dog API is temporarily unavailable.
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
