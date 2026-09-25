(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  let parents=[];
  function imageOf(d){return d&&(d.image_url||d.imageUrl)||''}
  function layoutOf(d){return {x:num(d&&(d.image_pos_x??d.imagePosX),50),y:num(d&&(d.image_pos_y??d.imagePosY),50),z:num(d&&(d.image_zoom??d.imageZoom),1)}}
  function renderFocal(frame,img,x,y,z){if(!frame||!img)return;if(!img.complete||!img.naturalWidth){img.addEventListener('load',()=>renderFocal(frame,img,x,y,z),{once:true});return}const W=Math.max(1,frame.clientWidth||72),H=Math.max(1,frame.clientHeight||72),nw=Math.max(1,img.naturalWidth),nh=Math.max(1,img.naturalHeight),base=Math.max(W/nw,H/nh),rw=nw*base*z,rh=nh*base*z;let left=W/2-(clamp(x,0,100)/100)*rw,top=H/2-(clamp(y,0,100)/100)*rh;left=clamp(left,W-rw,0);top=clamp(top,H-rh,0);Object.assign(img.style,{position:'absolute',width:rw+'px',height:rh+'px',maxWidth:'none',maxHeight:'none',left:left+'px',top:top+'px',objectFit:'fill',transform:'none',display:'block'})}
  function makePreview(id,label){const box=document.createElement('div');box.id=id;box.style.cssText='display:none;margin-top:10px;padding:10px;border:1px solid #cfe0f7;border-radius:14px;background:#f7fbff;align-items:center;gap:12px';box.innerHTML=`<div data-parent-photo style="width:72px;height:72px;flex:0 0 72px;border-radius:12px;background:#e7f1ff;display:grid;place-items:center;font-size:34px;overflow:hidden;position:relative">🐩</div><div><b data-parent-name>${esc(label)}</b><div class="muted" data-parent-meta style="font-size:12px"></div><div class="muted" data-parent-note style="font-size:11px;margin-top:3px"></div></div>`;return box}
  function renderPreview(select,box){const id=select.selectedOptions[0]?.dataset?.parentId||'',dog=parents.find(x=>String(x.id)===String(id));if(!dog){box.style.display='none';return}box.style.display='flex';box.querySelector('[data-parent-name]').textContent=dog.name||'';box.querySelector('[data-parent-meta]').textContent=[dog.breed,dog.color].filter(Boolean).join('・');const photo=box.querySelector('[data-parent-photo]'),url=imageOf(dog),a=layoutOf(dog);if(url){photo.innerHTML=`<img src="${esc(url)}" alt="${esc(dog.name||'親犬')}">`;requestAnimationFrame(()=>renderFocal(photo,photo.querySelector('img'),a.x,a.y,a.z))}else photo.innerHTML='🐩';box.querySelector('[data-parent-note]').textContent=url?'親犬管理で保存した切り取り位置を表示':'写真未登録（写真は任意です）'}
  function populate(select,sex,currentValue){const list=parents.filter(x=>String(x.sex||'')===sex),keep=String(currentValue||select.value||'').trim();select.innerHTML='';const blank=document.createElement('option');blank.value='未登録';blank.textContent='未登録';select.appendChild(blank);list.forEach(d=>{const o=document.createElement('option');o.value=d.name||'';o.textContent=d.name||'名称未登録';o.dataset.parentId=d.id||'';select.appendChild(o)});if(keep&&keep!=='未登録'&&!list.some(d=>String(d.name)===keep)){const legacy=document.createElement('option');legacy.value=keep;legacy.textContent=keep+'（既存登録）';select.appendChild(legacy)}select.value=keep||'未登録';if(!select.value)select.value='未登録'}
  function populateBreedOptions(editId){
    const select=document.getElementById('breed');
    const breeds=Array.isArray(window.BIGPAW_BREEDS)?window.BIGPAW_BREEDS:[];
    if(!select||!breeds.length)return;
    const keep=editId?String(select.value||'').trim():'';
    select.innerHTML='';
    const ph=document.createElement('option');ph.value='';ph.textContent='選択してください';select.appendChild(ph);
    breeds.forEach(b=>{const o=document.createElement('option');o.value=b.ja||'';o.textContent=b.ja||'';o.dataset.breedKey=b.key||'';select.appendChild(o)});
    if(keep&&!breeds.some(b=>String(b.ja)===keep)){const legacy=document.createElement('option');legacy.value=keep;legacy.textContent=keep+'（既存登録）';select.appendChild(legacy)}
    select.value=keep||'';
    if(!editId)select.value='';
  }
  function prepareNewListingDefaults(editId){
    if(editId)return;
    ['color','birth','price','weight','adultMin','adultMax','desc'].forEach(id=>{const el=document.getElementById(id);if(el)el.value=''});
    ['gender'].forEach(id=>{const el=document.getElementById(id);if(!el)return;let ph=[...el.options].find(o=>o.value==='');if(!ph){ph=document.createElement('option');ph.value='';ph.textContent='選択してください';el.insertBefore(ph,el.firstChild)}ph.selected=true;el.value=''});
    const father=document.getElementById('father'),mother=document.getElementById('mother');
    if(father)father.value='未登録';
    if(mother)mother.value='未登録';
  }
  async function install(){if(!/breeder-puppy-new\.html$/.test(location.pathname))return;const father=document.getElementById('father'),mother=document.getElementById('mother');if(!father||!mother||!window.BigPawAPI)return;const editId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId')||'';populateBreedOptions(editId);prepareNewListingDefaults(editId);const fBox=makePreview('fatherParentPreview','父犬'),mBox=makePreview('motherParentPreview','母犬');father.closest('.field')?.appendChild(fBox);mother.closest('.field')?.appendChild(mBox);try{parents=await BigPawAPI.parentDogs();let currentFather=editId?father.value:'未登録',currentMother=editId?mother.value:'未登録';if(editId&&window.BigPawBridge){try{const ds=await BigPawBridge.breederPuppies();const d=(ds||[]).find(x=>String(x.id)===String(editId));if(d){currentFather=d.father||currentFather;currentMother=d.mother||currentMother}}catch(_e){}}populate(father,'父犬',currentFather);populate(mother,'母犬',currentMother);renderPreview(father,fBox);renderPreview(mother,mBox);father.addEventListener('change',()=>renderPreview(father,fBox));mother.addEventListener('change',()=>renderPreview(mother,mBox));const help=document.createElement('div');help.className='notice';help.style.margin='12px 0 18px';help.innerHTML='父犬・母犬は「親犬管理」に登録した犬から選べます。写真がある場合は、親犬管理で保存した切り取り位置をそのまま表示します。 <a href="parent-dogs.html" style="font-weight:800;text-decoration:underline">親犬管理を開く →</a>';const target=mother.closest('.field')?.parentElement;if(target)target.insertAdjacentElement('afterend',help)}catch(_e){}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
