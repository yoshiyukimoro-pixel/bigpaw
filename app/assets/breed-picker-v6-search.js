(function(){
'use strict';
const VERSION='20260918-multi2';
const breeds=Array.isArray(window.BIGPAW_BREEDS)?window.BIGPAW_BREEDS:[];
if(!breeds.length){console.error('BIG PAW breed data missing');return;}
let selectedKeys=new Set();
window.BIGPAW_SELECTED_BREEDS=[];
const $=(q,r=document)=>r.querySelector(q);
const $$=(q,r=document)=>Array.from(r.querySelectorAll(q));
function breedByKey(k){return breeds.find(b=>b.key===k)||null;}
function cardStyle(selected){return 'appearance:none;-webkit-appearance:none;width:100%;min-width:0;position:relative;display:flex;flex-direction:column;border:'+(selected?'4px solid #d978a0':'1px solid #eadfe5')+';border-radius:12px;background:'+(selected?'#fff0f6':'#fff')+';padding:0;overflow:hidden;box-shadow:'+(selected?'0 0 0 2px rgba(217,120,160,.18)':'0 2px 8px rgba(30,20,25,.08)')+';text-align:center;color:#222;opacity:1;visibility:visible;';}
function makeCard(b,onClick){
 const btn=document.createElement('button');btn.type='button';btn.className='bpv6-card';btn.dataset.key=b.key;const badge=document.createElement('span');badge.className='bpv6-check';badge.textContent='✓';badge.style.cssText='position:absolute;right:7px;top:7px;width:28px;height:28px;border-radius:50%;background:#d47fa3;color:#fff;display:none;align-items:center;justify-content:center;font-weight:900;font-size:18px;z-index:3;';btn.style.position='relative';btn.appendChild(badge);btn.dataset.name=b.ja;btn.style.cssText=cardStyle(false);
 const photo=document.createElement('span');photo.style.cssText='position:relative;display:block;width:100%;height:auto;aspect-ratio:1/1;min-height:96px;background:linear-gradient(145deg,#fff4f8,#f7e4ec);overflow:hidden;flex:0 0 auto;';
 const fallback=document.createElement('span');fallback.textContent='🐕';fallback.setAttribute('aria-hidden','true');fallback.style.cssText='position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:40px;line-height:1;background:linear-gradient(145deg,#fff4f8,#f7e4ec);';photo.appendChild(fallback);
 const img=document.createElement('img');img.alt=b.ja;img.loading='lazy';img.decoding='async';img.style.cssText='position:absolute;inset:0;width:100%;height:100%;display:block;object-fit:contain;object-position:center center;background:#f7e4ec;';
 img.onload=()=>{fallback.style.display='none';};img.onerror=()=>{img.remove();fallback.style.display='flex';};img.src='/api/breed-image?key='+encodeURIComponent(b.key)+'&v=7';photo.appendChild(img);
 const name=document.createElement('span');name.textContent=b.ja;name.style.cssText='display:flex!important;align-items:center;justify-content:center;width:100%;min-height:52px;height:auto;padding:7px 5px;box-sizing:border-box;background:#fff;color:#222!important;font-size:12px!important;line-height:1.35!important;font-weight:800!important;white-space:normal!important;word-break:break-word;opacity:1!important;visibility:visible!important;flex:0 0 auto;';
 btn.append(photo,name);btn.addEventListener('click',()=>onClick&&onClick(b,btn));return btn;
}
function destroyOld(){
 const m=document.getElementById('bpBreedModal');if(m)m.remove();
 $$('.bp-credit-note,.bp-photo-source').forEach(x=>x.remove());
}
function createModal(){
 destroyOld();
 const modal=document.createElement('div');modal.id='bpv6Modal';modal.dataset.version=VERSION;modal.setAttribute('role','dialog');modal.setAttribute('aria-modal','true');modal.style.cssText='position:fixed;inset:0;z-index:2147483000;background:#fff;display:none;flex-direction:column;color:#222;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;';
 const head=document.createElement('div');head.style.cssText='display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px 16px;border-bottom:1px solid #eee;background:#fff;flex:0 0 auto;';
 const back=document.createElement('button');back.type='button';back.textContent='←';back.style.cssText='appearance:none;border:0;background:transparent;color:#222;font-size:30px;line-height:1;padding:4px 8px;min-width:42px;';
 const h=document.createElement('h2');h.textContent='犬種を選ぶ';h.style.cssText='font-size:20px;font-weight:800;margin:0;color:#222;';
 const x=document.createElement('button');x.type='button';x.textContent='×';x.style.cssText=back.style.cssText;head.append(back,h,x);
 const sw=document.createElement('div');sw.style.cssText='display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid #eee;background:#fff;flex:0 0 auto;';
 const input=document.createElement('input');input.type='search';input.placeholder='犬種名を検索';input.style.cssText='flex:1;min-width:0;height:48px;border:1px solid #d9d9d9;border-radius:12px;background:#fff;padding:0 14px;font-size:16px;color:#222;outline:none;';
 const clear=document.createElement('button');clear.type='button';clear.textContent='クリア';clear.style.cssText='height:48px;border:1px solid #d9cbd1;border-radius:12px;background:#fff;padding:0 15px;font-size:15px;font-weight:700;color:#7a5061;';sw.append(input,clear);
 const scroll=document.createElement('div');scroll.style.cssText='flex:1 1 auto;overflow:auto;-webkit-overflow-scrolling:touch;padding:14px 14px 110px;background:#fff;';
 const grid=document.createElement('div');grid.id='bpv6Grid';grid.style.cssText='display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:10px!important;max-width:980px;margin:0 auto;align-items:start;';
 const selectedLabel=document.createElement('div');selectedLabel.style.cssText='min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;color:#665a60;';
 function refreshSelection(){ $$('.bpv6-card',grid).forEach(c=>{const on=selectedKeys.has(c.dataset.key);c.style.cssText=cardStyle(on);c.setAttribute('aria-pressed',on?'true':'false');const badge=c.querySelector('.bpv6-check');if(badge)badge.style.display=on?'flex':'none';});const names=[...selectedKeys].map(k=>(breedByKey(k)||{}).ja).filter(Boolean);selectedLabel.textContent=names.length?'選択中 '+names.length+'犬種：'+names.join('、'):'犬種を複数選択できます';confirm.textContent=names.length?'この'+names.length+'犬種で決定':'決定';}
 function mark(btn,b){if(selectedKeys.has(b.key)){selectedKeys.delete(b.key);}else{selectedKeys.add(b.key);}refreshSelection();}
 breeds.forEach(b=>grid.appendChild(makeCard(b,(breed,btn)=>mark(btn,breed))));scroll.appendChild(grid);
 const bottom=document.createElement('div');bottom.style.cssText='position:fixed;left:0;right:0;bottom:0;z-index:2147483001;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px calc(12px + env(safe-area-inset-bottom));border-top:1px solid #eee;background:rgba(255,255,255,.98);';
 const confirm=document.createElement('button');confirm.type='button';confirm.textContent='決定';confirm.style.cssText='appearance:none;border:0;border-radius:999px;background:#17211d;color:#fff;padding:13px 24px;font-size:16px;font-weight:800;flex:0 0 auto;';bottom.append(selectedLabel,confirm);modal.append(head,sw,scroll,bottom);document.body.appendChild(modal);
 function close(){modal.style.display='none';document.body.style.overflow='';}
 function filter(q){q=(q||'').trim().toLowerCase();$$('.bpv6-card',grid).forEach(c=>{c.style.display=(!q||c.dataset.name.toLowerCase().includes(q))?'flex':'none';});}
 back.onclick=close;x.onclick=close;clear.onclick=()=>{input.value='';filter('');input.focus();};input.addEventListener('input',()=>filter(input.value));confirm.onclick=()=>{applySelected();close();};
 refreshSelection();
 return modal;
}
function openModal(){const sel=document.getElementById('fBreed');if(!selectedKeys.size&&sel&&sel.value&&sel.value!=='all')selectedKeys.add(sel.value);const old=document.getElementById('bpv6Modal');if(old)old.remove();const m=createModal();m.style.display='flex';document.body.style.overflow='hidden';}
function applySelected(){const sel=document.getElementById('fBreed');const keys=[...selectedKeys];window.BIGPAW_SELECTED_BREEDS=keys;if(sel)sel.value=keys.length===1?keys[0]:'all';const t=document.getElementById('bpv6SearchTrigger');if(t)t.firstChild.nodeValue=keys.length?(keys.length===1?(breedByKey(keys[0])||{}).ja:keys.length+'犬種を選択中')+' ':'すべての大型犬種 ';if(typeof window.render==='function')window.render();}
function enhanceSelect(){const sel=document.getElementById('fBreed');if(!sel)return;sel.innerHTML='<option value="all">すべての大型犬種</option>'+breeds.map(b=>'<option value="'+b.key+'">'+b.ja+'</option>').join('');sel.style.cssText='position:absolute!important;opacity:0!important;pointer-events:none!important;width:1px!important;height:1px!important;';const old=document.getElementById('bpBreedTrigger');if(old)old.remove();const old2=document.getElementById('bpv6SearchTrigger');if(old2)old2.remove();const t=document.createElement('button');t.type='button';t.id='bpv6SearchTrigger';t.style.cssText='appearance:none;width:100%;min-height:48px;border:1px solid #eadfe5;border-radius:12px;background:#fff;padding:11px 42px 11px 12px;text-align:left;font-size:15px;color:#222;font-weight:700;position:relative;';t.append(document.createTextNode('すべての大型犬種 '));const ar=document.createElement('span');ar.textContent='⌄';ar.style.cssText='position:absolute;right:14px;top:8px;font-size:24px;color:#7d6b75;';t.appendChild(ar);t.onclick=openModal;sel.insertAdjacentElement('afterend',t);const q=new URLSearchParams(location.search).get('breed');if(q){q.split(',').filter(k=>breedByKey(k)).forEach(k=>selectedKeys.add(k));applySelected();}}
function enhanceHome(){const old=document.querySelector('#breeds .breed-grid');if(!old)return;old.innerHTML='';old.style.cssText='display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:10px!important;align-items:start;';breeds.slice(0,12).forEach(b=>old.appendChild(makeCard(b,(breed)=>{selectedKeys=new Set([breed.key]);const sel=document.getElementById('fBreed');if(sel)sel.value=breed.key;applySelected();openModal();})));const prev=document.getElementById('bpAllBreedsButton');if(prev)prev.remove();const btn=document.createElement('button');btn.type='button';btn.id='bpAllBreedsButton';btn.textContent='全60犬種を画像から選ぶ';btn.style.cssText='display:block;margin:18px auto 0;border:1px solid #d8a9bc;background:#fff;color:#8d4564;font-weight:800;border-radius:999px;padding:11px 20px;font-size:15px;';btn.onclick=openModal;old.insertAdjacentElement('afterend',btn);}
function enhanceGuide(){if(!/breed-guide\.html$/.test(location.pathname))return;const old=document.querySelector('.dog-cards');if(!old)return;old.innerHTML='';old.style.cssText='display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:10px!important;align-items:start;';breeds.forEach(b=>old.appendChild(makeCard(b,(breed)=>{location.href='search.html?breed='+encodeURIComponent(breed.key);})));}
function init(){destroyOld();enhanceSelect();enhanceHome();enhanceGuide();window.BigPawBreedPicker={open:openModal,breeds,version:VERSION,clear:function(){selectedKeys.clear();applySelected();}};}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
