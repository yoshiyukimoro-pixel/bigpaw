(()=>{
'use strict';
if(!/breeder-puppy-new\.html$/.test(location.pathname))return;
let previewUrls=[];
function revoke(){previewUrls.forEach(u=>{try{URL.revokeObjectURL(u)}catch(_e){}});previewUrls=[]}
function button(row,label,fn){const b=document.createElement('button');b.type='button';b.className='btn btn-sub';b.textContent=label;b.onclick=fn;row.appendChild(b)}
function preview(src,alt){const frame=document.createElement('div');frame.style.cssText='width:100%;aspect-ratio:1/1;background:#fff;border-radius:10px;overflow:hidden;display:grid;place-items:center';const im=document.createElement('img');im.src=src;im.alt=alt||'';im.style.cssText='width:100%;height:100%;object-fit:contain;display:block';frame.appendChild(im);return frame}
function renderAll(){
  const host=document.getElementById('photoPreview');if(!host)return;
  revoke();host.innerHTML='';
  const saved=Array.isArray(window.persistedPhotos)?window.persistedPhotos:[];
  const pending=(typeof selectedPhotos!=='undefined'&&Array.isArray(selectedPhotos))?selectedPhotos:[];
  saved.forEach((p,i)=>{
    const card=document.createElement('div');card.style.cssText='border:1px solid #eee;border-radius:14px;padding:8px';
    card.appendChild(preview(p.url,'登録済み写真 '+(i+1)));
    const small=document.createElement('small');small.style.display='block';small.textContent=p.isMain?'メイン写真':'登録済み写真';card.appendChild(small);
    const row=document.createElement('div');row.style.cssText='display:flex;gap:6px;flex-wrap:wrap;margin-top:6px';
    if(!p.isMain&&typeof setPersistedMain==='function')button(row,'メインにする',()=>setPersistedMain(i));
    if(typeof window.openPersistedAdjust==='function')button(row,'写真を調整',()=>window.openPersistedAdjust(i));
    if(typeof deletePersistedPhoto==='function')button(row,'削除',()=>deletePersistedPhoto(i));
    card.appendChild(row);host.appendChild(card);
  });
  pending.forEach((f,i)=>{
    const card=document.createElement('div');card.style.cssText='border:1px solid #efbfd1;border-radius:14px;padding:8px;background:#fffafd';
    const u=URL.createObjectURL(f);previewUrls.push(u);card.appendChild(preview(u,'追加予定写真 '+(i+1)));
    const small=document.createElement('small');small.style.cssText='display:block;font-weight:700';small.textContent=saved.length?'追加予定 '+(i+1):(i===0?'メイン写真':'写真 '+(i+1));card.appendChild(small);
    const row=document.createElement('div');row.style.cssText='display:flex;gap:6px;flex-wrap:wrap;margin-top:6px';
    if(i>0&&typeof movePhoto==='function')button(row,'←',()=>movePhoto(i,-1));
    if(i<pending.length-1&&typeof movePhoto==='function')button(row,'→',()=>movePhoto(i,1));
    if(!saved.length&&i>0&&typeof makeMain==='function')button(row,'メインにする',()=>makeMain(i));
    if(typeof window.openPhotoAdjust==='function')button(row,'写真を調整',()=>window.openPhotoAdjust(i));
    if(typeof removePhoto==='function')button(row,'追加を取り消す',()=>removePhoto(i));
    card.appendChild(row);host.appendChild(card);
  });
  if(!saved.length&&!pending.length){const n=document.createElement('div');n.className='muted';n.style.cssText='grid-column:1/-1;padding:8px';n.textContent='写真はまだ登録されていません。';host.appendChild(n)}
}
function install(){
  window.renderAllPuppyPhotos=renderAll;
  window.renderSelectedPhotos=renderAll;
  window.renderPersistedPhotos=renderAll;
  const note=document.getElementById('bigpawPhotoNormalizeNote');
  if(note)note.textContent='編集時は登録済み写真を残したまま、新しく選んだ写真だけを追加できます。登録済み＋追加予定の合計で最大10枚です。「写真を調整」で位置・拡大縮小も変更できます。';
  if((Array.isArray(window.persistedPhotos)&&window.persistedPhotos.length)||(typeof selectedPhotos!=='undefined'&&selectedPhotos.length))renderAll();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
setTimeout(install,300);setTimeout(install,1000);addEventListener('pageshow',install);
})();
