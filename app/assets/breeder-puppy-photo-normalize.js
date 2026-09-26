(()=>{
'use strict';
if(!/breeder-puppy-new\.html$/.test(location.pathname))return;
const OUTPUT_SIZE=1000,QUALITY=.92;
let previewUrls=[],adjustObjectUrl=null,touchState=null;
function revokePreviews(){previewUrls.forEach(u=>{try{URL.revokeObjectURL(u)}catch(_e){}});previewUrls=[]}
function mark(obj,key,value){try{Object.defineProperty(obj,key,{value,writable:true,configurable:true})}catch(_e){try{obj[key]=value}catch(_e2){}}}
function sourceOf(file){return file&&file._bigpawOriginal instanceof Blob?file._bigpawOriginal:file}
function installRender(){
  if(typeof window.renderSelectedPhotos!=='function')return;
  window.renderSelectedPhotos=function(){
    const host=document.getElementById('photoPreview');if(!host)return;
    revokePreviews();host.innerHTML='';
    selectedPhotos.forEach((f,i)=>{
      const card=document.createElement('div');card.style.cssText='border:1px solid #eee;border-radius:14px;padding:8px';
      const frame=document.createElement('div');frame.style.cssText='width:100%;aspect-ratio:1/1;background:#fff;border-radius:10px;overflow:hidden;display:grid;place-items:center';
      const im=document.createElement('img'),u=URL.createObjectURL(f);previewUrls.push(u);im.src=u;im.alt='登録写真 '+(i+1);im.style.cssText='width:100%;height:100%;object-fit:contain;display:block';frame.appendChild(im);card.appendChild(frame);
      const small=document.createElement('small');small.style.display='block';small.textContent=i===0?'メイン写真':'写真 '+(i+1);card.appendChild(small);
      const row=document.createElement('div');row.style.cssText='display:flex;gap:6px;flex-wrap:wrap;margin-top:6px';
      const btn=(label,fn)=>{const b=document.createElement('button');b.type='button';b.className='btn btn-sub';b.textContent=label;b.onclick=fn;row.appendChild(b)};
      if(i>0)btn('←',()=>movePhoto(i,-1));
      if(i<selectedPhotos.length-1)btn('→',()=>movePhoto(i,1));
      if(i>0)btn('メインにする',()=>makeMain(i));
      btn('写真を調整',()=>window.openPhotoAdjust(i));
      btn('削除',()=>removePhoto(i));
      card.appendChild(row);host.appendChild(card);
    });
  };
}
async function decodeImage(file){
  if('createImageBitmap'in window){const b=await createImageBitmap(file,{imageOrientation:'from-image'}).catch(()=>createImageBitmap(file));return{width:b.width,height:b.height,draw:(ctx,...args)=>ctx.drawImage(b,...args),close:()=>b.close&&b.close()}}
  return await new Promise((resolve,reject)=>{const u=URL.createObjectURL(file),im=new Image();im.onload=()=>resolve({width:im.naturalWidth,height:im.naturalHeight,draw:(ctx,...args)=>ctx.drawImage(im,...args),close:()=>URL.revokeObjectURL(u)});im.onerror=()=>{URL.revokeObjectURL(u);reject(new Error('image_decode_failed'))};im.src=u})
}
async function centeredSquare(file){
  if(file&&file._bigpawSquareReady)return file;
  const original=sourceOf(file);if(!(original instanceof Blob)||!String(original.type||'').startsWith('image/'))return original;
  const d=await decodeImage(original);try{
    const c=document.createElement('canvas');c.width=c.height=OUTPUT_SIZE;const ctx=c.getContext('2d',{alpha:false});ctx.fillStyle='#fff';ctx.fillRect(0,0,OUTPUT_SIZE,OUTPUT_SIZE);
    const sc=Math.min(OUTPUT_SIZE/d.width,OUTPUT_SIZE/d.height),w=d.width*sc,h=d.height*sc;d.draw(ctx,0,0,d.width,d.height,(OUTPUT_SIZE-w)/2,(OUTPUT_SIZE-h)/2,w,h);
    const blob=await new Promise((resolve,reject)=>c.toBlob(b=>b?resolve(b):reject(new Error('image_encode_failed')),'image/jpeg',QUALITY));
    const out=new File([blob],'bigpaw-square-'+Date.now()+'.jpg',{type:'image/jpeg',lastModified:Date.now()});mark(out,'_bigpawOriginal',original);mark(out,'_bigpawSquareReady',true);mark(out,'_bigpawAdjustState',{scale:1,x:0,y:0});return out;
  }finally{d.close()}
}
function installUploadOptimizer(){
  if(!window.BigPawBridge||typeof BigPawBridge.upload!=='function'||BigPawBridge.__photoNormalizeInstalled)return;
  const original=BigPawBridge.upload.bind(BigPawBridge);
  BigPawBridge.upload=async function(file,puppyId){let prepared=file;try{prepared=await centeredSquare(file)}catch(e){console.warn('BIGPAW square photo fallback',e)}return original(prepared,puppyId)};
  BigPawBridge.__photoNormalizeInstalled=true;
}
function ensureModal(){
  let m=document.getElementById('photoAdjustModal');if(m)m.remove();
  document.body.insertAdjacentHTML('beforeend','<div id="photoAdjustModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:9999;overflow:auto"><div style="max-width:560px;margin:0 auto;min-height:100%;background:#fff;color:#342d34;padding-bottom:18px"><div style="height:72px;background:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 18px"><button type="button" id="bpAdjustBack" style="border:0;border-radius:24px;background:#f1f1f4;padding:10px 18px;font-size:17px">‹ 戻る</button><b style="font-size:18px">画像の編集</b><button type="button" id="bpAdjustApply" style="border:0;border-radius:26px;background:#ef7da7;color:#fff;font-weight:700;padding:13px 22px;font-size:16px">適用</button></div><div style="padding:18px"><div id="adjustFrame" style="width:100%;aspect-ratio:1/1;overflow:hidden;background:#fff;touch-action:none;position:relative;border:1px solid #e6e0e3"><img id="adjustImg" style="position:absolute;left:50%;top:50%;max-width:none;max-height:none;transform-origin:center center;user-select:none;-webkit-user-drag:none"></div><div style="margin-top:14px;font-size:15px;color:#574d53">正方形の枠はこのままです。最初は写真全体を表示します。1本指で移動、2本指で拡大・縮小して構図を決めてください。</div><div style="display:flex;gap:10px;align-items:center;margin-top:14px"><button type="button" id="bpAdjustReset" class="btn btn-sub" style="white-space:nowrap">全体に戻す</button><input id="adjustZoom" type="range" min="1" max="5" step="0.01" value="1" style="width:100%;accent-color:#ef7da7"></div></div></div></div>');
  const fr=document.getElementById('adjustFrame'),zr=document.getElementById('adjustZoom');
  document.getElementById('bpAdjustBack').onclick=window.closePhotoAdjust;document.getElementById('bpAdjustApply').onclick=window.applyPhotoAdjust;
  document.getElementById('bpAdjustReset').onclick=()=>{adjustScale=1;adjustX=0;adjustY=0;draw()};
  zr.oninput=e=>{adjustScale=Math.max(1,Math.min(5,Number(e.target.value)||1));draw()};
  fr.addEventListener('touchstart',e=>{e.preventDefault();if(e.touches.length===2){const a=e.touches[0],b=e.touches[1];touchState={kind:'pinch',dist:Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY),scale:adjustScale,x:adjustX,y:adjustY,cx:(a.clientX+b.clientX)/2,cy:(a.clientY+b.clientY)/2}}else if(e.touches.length===1){const a=e.touches[0];touchState={kind:'pan',sx:a.clientX,sy:a.clientY,x:adjustX,y:adjustY}}},{passive:false});
  fr.addEventListener('touchmove',e=>{e.preventDefault();if(!touchState)return;if(e.touches.length===2&&touchState.kind==='pinch'){const a=e.touches[0],b=e.touches[1],dist=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);adjustScale=Math.max(1,Math.min(5,touchState.scale*dist/Math.max(1,touchState.dist)));adjustX=touchState.x+((a.clientX+b.clientX)/2-touchState.cx);adjustY=touchState.y+((a.clientY+b.clientY)/2-touchState.cy);draw()}else if(e.touches.length===1&&touchState.kind==='pan'){const a=e.touches[0];adjustX=touchState.x+a.clientX-touchState.sx;adjustY=touchState.y+a.clientY-touchState.sy;draw()}},{passive:false});
  fr.addEventListener('touchend',e=>{if(e.touches.length===0)touchState=null},{passive:false});
  fr.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse')return;adjustStart={x:e.clientX,y:e.clientY,ox:adjustX,oy:adjustY};fr.setPointerCapture(e.pointerId)});
  fr.addEventListener('pointermove',e=>{if(e.pointerType!=='mouse'||!adjustStart)return;adjustX=adjustStart.ox+e.clientX-adjustStart.x;adjustY=adjustStart.oy+e.clientY-adjustStart.y;draw()});
  fr.addEventListener('pointerup',()=>{adjustStart=null});
  fr.addEventListener('wheel',e=>{e.preventDefault();adjustScale=Math.max(1,Math.min(5,adjustScale+(e.deltaY<0?.08:-.08)));draw()},{passive:false});
}
function draw(){
  const fr=document.getElementById('adjustFrame'),im=document.getElementById('adjustImg'),zr=document.getElementById('adjustZoom');if(!fr||!im||!im.naturalWidth)return;
  const fit=Math.min(fr.clientWidth/im.naturalWidth,fr.clientHeight/im.naturalHeight),bw=im.naturalWidth*fit,bh=im.naturalHeight*fit;im.style.width=bw+'px';im.style.height=bh+'px';im.style.transform='translate(-50%,-50%) translate('+adjustX+'px,'+adjustY+'px) scale('+adjustScale+')';if(zr&&document.activeElement!==zr)zr.value=adjustScale;
}
function openWith(src,state,target){
  ensureModal();adjustTarget=target;adjustScale=state&&state.scale?state.scale:1;adjustX=0;adjustY=0;
  const fr=document.getElementById('adjustFrame'),im=document.getElementById('adjustImg');if(adjustObjectUrl){try{URL.revokeObjectURL(adjustObjectUrl)}catch(_e){}adjustObjectUrl=null}
  if(src instanceof Blob){adjustObjectUrl=URL.createObjectURL(src);im.src=adjustObjectUrl}else im.src=src;
  im.onload=()=>{if(state){adjustX=(state.x||0)*fr.clientWidth;adjustY=(state.y||0)*fr.clientHeight}draw()};document.getElementById('photoAdjustModal').style.display='block';
}
function installAdjuster(){
  if(typeof window.openPhotoAdjust!=='function')return;
  window.openPhotoAdjust=function(i){const f=selectedPhotos[i];if(!f)return;openWith(sourceOf(f),f._bigpawAdjustState||null,{kind:'new',i})};
  window.openPersistedAdjust=function(i){const p=window.persistedPhotos&&window.persistedPhotos[i];if(!p)return;let src=p.originalUrl||p.url;if(String(src).startsWith('/uploads/')&&!/[?&]original=1/.test(src))src+=src.includes('?')?'&original=1':'?original=1';openWith(src,null,{kind:'saved',i})};
  window.closePhotoAdjust=function(){const m=document.getElementById('photoAdjustModal');if(m)m.style.display='none';adjustTarget=null;touchState=null;if(adjustObjectUrl){try{URL.revokeObjectURL(adjustObjectUrl)}catch(_e){}adjustObjectUrl=null}};
  window.applyPhotoAdjust=async function(){
    const im=document.getElementById('adjustImg'),fr=document.getElementById('adjustFrame');if(!adjustTarget||!im||!im.complete||!im.naturalWidth)return;
    const c=document.createElement('canvas');c.width=c.height=OUTPUT_SIZE;const ctx=c.getContext('2d',{alpha:false});ctx.fillStyle='#fff';ctx.fillRect(0,0,OUTPUT_SIZE,OUTPUT_SIZE);
    const fit=Math.min(OUTPUT_SIZE/im.naturalWidth,OUTPUT_SIZE/im.naturalHeight),w=im.naturalWidth*fit*adjustScale,h=im.naturalHeight*fit*adjustScale,px=OUTPUT_SIZE/fr.clientWidth;
    ctx.drawImage(im,(OUTPUT_SIZE-w)/2+adjustX*px,(OUTPUT_SIZE-h)/2+adjustY*px,w,h);
    const blob=await new Promise((resolve,reject)=>c.toBlob(b=>b?resolve(b):reject(new Error('image_encode_failed')),'image/jpeg',QUALITY));const file=new File([blob],'adjusted-'+Date.now()+'.jpg',{type:'image/jpeg',lastModified:Date.now()});
    mark(file,'_bigpawSquareReady',true);mark(file,'_bigpawAdjustState',{scale:adjustScale,x:adjustX/fr.clientWidth,y:adjustY/fr.clientHeight});
    if(adjustTarget.kind==='new'){const prev=selectedPhotos[adjustTarget.i];mark(file,'_bigpawOriginal',sourceOf(prev));selectedPhotos[adjustTarget.i]=file;syncPhotoInput();renderSelectedPhotos();window.closePhotoAdjust();return}
    try{const old=window.persistedPhotos[adjustTarget.i];const up=await BigPawBridge.upload(file,editId);if(old.isMain&&up.url)await BigPawBridge.updatePuppy(editId,{imageUrl:up.url});await BigPawAPI.request('/puppies/'+encodeURIComponent(editId)+'/photos/'+encodeURIComponent(old.id),{method:'DELETE'});window.persistedPhotos[adjustTarget.i]={id:up.id,url:up.url,isMain:old.isMain};if(typeof renderPersistedPhotos==='function')renderPersistedPhotos();window.closePhotoAdjust()}catch(e){alert('写真の調整を保存できませんでした')}
  };
}
function installNote(){const box=document.querySelector('.photo-box');if(!box)return;let n=document.getElementById('bigpawPhotoNormalizeNote');if(!n){n=document.createElement('div');n.id='bigpawPhotoNormalizeNote';n.className='notice';n.style.cssText='margin-top:12px;text-align:left';box.appendChild(n)}n.textContent='掲載枠は正方形です。写真全体が入った状態から、ブリーダー様ご自身で「写真を調整」を開き、ピンチ拡大・縮小と位置移動で構図を決めて保存できます。'}
function install(){installRender();installUploadOptimizer();installAdjuster();installNote();if(typeof window.renderSelectedPhotos==='function'&&typeof selectedPhotos!=='undefined'&&selectedPhotos.length)renderSelectedPhotos()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();setTimeout(install,200);setTimeout(install,900);addEventListener('pageshow',install);
})();