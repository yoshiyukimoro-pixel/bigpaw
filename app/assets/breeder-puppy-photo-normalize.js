(()=>{
'use strict';
if(!/breeder-puppy-new\.html$/.test(location.pathname))return;
const TARGET=1400,QUALITY=.82;
let previewUrls=[];
function revokePreviews(){previewUrls.forEach(u=>{try{URL.revokeObjectURL(u)}catch(_e){}});previewUrls=[]}
function installRender(){
  if(typeof window.renderSelectedPhotos!=='function')return;
  window.renderSelectedPhotos=function(){
    const host=document.getElementById('photoPreview');if(!host)return;
    revokePreviews();host.innerHTML='';
    selectedPhotos.forEach((f,i)=>{
      const card=document.createElement('div');card.style.cssText='border:1px solid #eee;border-radius:14px;padding:8px';
      const im=document.createElement('img');const u=URL.createObjectURL(f);previewUrls.push(u);im.src=u;im.alt='登録写真 '+(i+1);im.style.cssText='width:100%;aspect-ratio:1/1;object-fit:contain;border-radius:10px;background:#f7edf2';card.appendChild(im);
      const small=document.createElement('small');small.style.display='block';small.textContent=i===0?'メイン写真':'写真 '+(i+1);card.appendChild(small);
      const row=document.createElement('div');row.style.cssText='display:flex;gap:6px;flex-wrap:wrap;margin-top:6px';
      const btn=(label,fn)=>{const b=document.createElement('button');b.type='button';b.className='btn btn-sub';b.textContent=label;b.onclick=fn;row.appendChild(b)};
      btn('写真を調整',()=>openPhotoAdjust(i));
      if(i>0)btn('←',()=>movePhoto(i,-1));
      if(i<selectedPhotos.length-1)btn('→',()=>movePhoto(i,1));
      if(i>0)btn('メインにする',()=>makeMain(i));
      btn('削除',()=>removePhoto(i));
      card.appendChild(row);host.appendChild(card);
    });
  };
}
async function decodeImage(file){
  if('createImageBitmap'in window){const b=await createImageBitmap(file,{imageOrientation:'from-image'}).catch(()=>createImageBitmap(file));return{width:b.width,height:b.height,draw:(ctx,...args)=>ctx.drawImage(b,...args),close:()=>b.close&&b.close()}}
  return await new Promise((resolve,reject)=>{const u=URL.createObjectURL(file),im=new Image();im.onload=()=>resolve({width:im.naturalWidth,height:im.naturalHeight,draw:(ctx,...args)=>ctx.drawImage(im,...args),close:()=>URL.revokeObjectURL(u)});im.onerror=()=>{URL.revokeObjectURL(u);reject(new Error('image_decode_failed'))};im.src=u})
}
async function preserveAspectForUpload(file){
  if(!(file instanceof Blob)||!String(file.type||'').startsWith('image/'))return file;
  const d=await decodeImage(file);try{
    const scale=Math.min(1,TARGET/Math.max(d.width,d.height));
    const w=Math.max(1,Math.round(d.width*scale)),h=Math.max(1,Math.round(d.height*scale));
    const c=document.createElement('canvas');c.width=w;c.height=h;
    const ctx=c.getContext('2d',{alpha:false});ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);d.draw(ctx,0,0,d.width,d.height,0,0,w,h);
    const blob=await new Promise((resolve,reject)=>c.toBlob(b=>b?resolve(b):reject(new Error('image_encode_failed')),'image/jpeg',QUALITY));
    return new File([blob],'bigpaw-'+Date.now()+'-'+Math.random().toString(36).slice(2,7)+'.jpg',{type:'image/jpeg',lastModified:Date.now()});
  }finally{d.close()}
}
function installUploadOptimizer(){
  if(!window.BigPawBridge||typeof BigPawBridge.upload!=='function'||BigPawBridge.__photoNormalizeInstalled)return;
  const original=BigPawBridge.upload.bind(BigPawBridge);
  BigPawBridge.upload=async function(file,puppyId){
    let prepared=file;
    try{prepared=await preserveAspectForUpload(file)}catch(e){console.warn('BIGPAW photo optimize fallback',e)}
    return original(prepared,puppyId);
  };
  BigPawBridge.__photoNormalizeInstalled=true;
}
function installPersistedOriginalAdjust(){
  if(typeof window.openPersistedAdjust!=='function'||window.openPersistedAdjust.__bigpawOriginalGuard)return;
  const original=window.openPersistedAdjust;
  const wrapped=function(i){
    const p=window.persistedPhotos&&window.persistedPhotos[i];
    if(!p||!String(p.url||'').startsWith('/uploads/'))return original(i);
    const old=p.url;p.url=old+(old.includes('?')?'&':'?')+'original=1';
    try{return original(i)}finally{p.url=old}
  };
  wrapped.__bigpawOriginalGuard=true;window.openPersistedAdjust=wrapped;
}
function installNote(){
  const box=document.querySelector('.photo-box');if(!box||document.getElementById('bigpawPhotoNormalizeNote'))return;
  const n=document.createElement('div');n.id='bigpawPhotoNormalizeNote';n.className='notice';n.style.cssText='margin-top:12px;text-align:left';n.textContent='元の写真は切り取らず縦横比を保ったまま軽量化して保存します。公開画面では用途に合わせて全体表示または正方形表示を使い分けます。';box.appendChild(n)
}
function install(){installRender();installUploadOptimizer();installPersistedOriginalAdjust();installNote();if(typeof window.renderSelectedPhotos==='function'&&typeof selectedPhotos!=='undefined'&&selectedPhotos.length)renderSelectedPhotos()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
setTimeout(install,200);setTimeout(install,900);
addEventListener('pageshow',install);
})();
