(()=>{
  if(!/\/parent-dogs\.html$/.test(location.pathname))return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  const layout=d=>({x:num(d?.image_pos_x??d?.imagePosX,50),y:num(d?.image_pos_y??d?.imagePosY,50),z:num(d?.image_zoom??d?.imageZoom,1)});

  function focalMetrics(frame,img,z){
    const W=Math.max(1,frame.clientWidth||frame.getBoundingClientRect().width||1);
    const H=Math.max(1,frame.clientHeight||frame.getBoundingClientRect().height||1);
    const nw=Math.max(1,img.naturalWidth||W),nh=Math.max(1,img.naturalHeight||H);
    const base=Math.max(W/nw,H/nh);
    return {W,H,rw:nw*base*z,rh:nh*base*z};
  }
  function renderFocal(frame,img,x,y,z){
    if(!frame||!img)return;
    if(!img.complete||!img.naturalWidth){img.addEventListener('load',()=>renderFocal(frame,img,x,y,z),{once:true});return}
    const m=focalMetrics(frame,img,z);
    let left=m.W/2-(clamp(x,0,100)/100)*m.rw;
    let top=m.H/2-(clamp(y,0,100)/100)*m.rh;
    left=clamp(left,m.W-m.rw,0);top=clamp(top,m.H-m.rh,0);
    Object.assign(img.style,{position:'absolute',width:m.rw+'px',height:m.rh+'px',maxWidth:'none',maxHeight:'none',left:left+'px',top:top+'px',objectFit:'fill',objectPosition:'50% 50%',transform:'none',transformOrigin:'50% 50%',display:'block'});
  }

  function attachTouchAdjust(frame,img,getState,setState,apply){
    if(!frame||!img||frame.dataset.touchAdjust==='2')return;
    frame.dataset.touchAdjust='2';
    frame.style.touchAction='none';frame.style.userSelect='none';frame.style.webkitUserSelect='none';frame.style.cursor='grab';
    const points=new Map();let lastSingle=null,pinchStartDistance=0,pinchStartZoom=1;
    const pointDistance=()=>{const a=[...points.values()];return a.length<2?0:Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y)};
    frame.addEventListener('pointerdown',e=>{
      if(e.pointerType==='mouse'&&e.button!==0)return;
      points.set(e.pointerId,{x:e.clientX,y:e.clientY});try{frame.setPointerCapture(e.pointerId)}catch(_){ }
      if(points.size===1){lastSingle={x:e.clientX,y:e.clientY};frame.style.cursor='grabbing'}
      else if(points.size===2){pinchStartDistance=pointDistance()||1;pinchStartZoom=getState().z;lastSingle=null}
      e.preventDefault();
    },{passive:false});
    frame.addEventListener('pointermove',e=>{
      if(!points.has(e.pointerId))return;points.set(e.pointerId,{x:e.clientX,y:e.clientY});
      if(points.size===1&&lastSingle){
        const dx=e.clientX-lastSingle.x,dy=e.clientY-lastSingle.y,s=getState(),m=focalMetrics(frame,img,s.z);
        setState({x:clamp(s.x-(dx/m.rw)*100,0,100),y:clamp(s.y-(dy/m.rh)*100,0,100),z:s.z});
        lastSingle={x:e.clientX,y:e.clientY};apply();
      }else if(points.size>=2){
        const d=pointDistance();if(d>0&&pinchStartDistance>0){const s=getState();setState({x:s.x,y:s.y,z:clamp(pinchStartZoom*(d/pinchStartDistance),1,3)});apply()}
      }
      e.preventDefault();
    },{passive:false});
    const release=e=>{points.delete(e.pointerId);if(points.size===1){const p=[...points.values()][0];lastSingle={x:p.x,y:p.y};pinchStartDistance=0}else if(points.size===0){lastSingle=null;pinchStartDistance=0;frame.style.cursor='grab'}else if(points.size===2){pinchStartDistance=pointDistance()||1;pinchStartZoom=getState().z}};
    frame.addEventListener('pointerup',release);frame.addEventListener('pointercancel',release);
    frame.addEventListener('wheel',e=>{e.preventDefault();const s=getState();setState({x:s.x,y:s.y,z:clamp(s.z+(e.deltaY<0?0.08:-0.08),1,3)});apply()},{passive:false});
  }

  let createX=50,createY=50,createZ=1;
  const createState=()=>({x:createX,y:createY,z:createZ});
  const setCreateState=s=>{createX=s.x;createY=s.y;createZ=s.z};
  function applyCreatePreview(){const frame=document.getElementById('pdCreateGestureFrame'),im=document.getElementById('pdPhotoPreviewImg');if(frame&&im)renderFocal(frame,im,createX,createY,createZ)}
  function resetCreate(){createX=50;createY=50;createZ=1;applyCreatePreview()}

  function installCreateControls(){
    const preview=document.getElementById('pdPhotoPreview'),im=document.getElementById('pdPhotoPreviewImg');
    if(!preview||!im||document.getElementById('pdPhotoAdjustControls'))return;
    let frame=document.getElementById('pdCreateGestureFrame');
    if(!frame){frame=document.createElement('div');frame.id='pdCreateGestureFrame';frame.style.cssText='width:260px;height:260px;max-width:100%;margin:12px auto 0;border-radius:18px;overflow:hidden;background:#e7f1ff;position:relative;touch-action:none';preview.insertBefore(frame,im);frame.appendChild(im)}
    const c=document.createElement('div');c.id='pdPhotoAdjustControls';c.style.cssText='margin-top:12px;padding:12px;border:1px solid #cfe0f4;border-radius:14px;background:#f7fbff;text-align:center';
    c.innerHTML='<b style="display:block;margin-bottom:6px">写真を指で調整</b><div style="font-size:14px;line-height:1.7">☝️ 1本指で上下左右に移動<br>🤏 2本指でピンチして拡大・縮小</div><button type="button" class="btn btn-sub" id="pdCreateReset" style="margin-top:10px">中央に戻す</button><small class="muted" style="display:block;margin-top:8px">ここで見えている切り取りを、そのまま子犬詳細にも表示します。</small>';
    preview.appendChild(c);document.getElementById('pdCreateReset').onclick=resetCreate;attachTouchAdjust(frame,im,createState,setCreateState,applyCreatePreview);
    const file=document.getElementById('pdPhoto');if(file)file.addEventListener('change',()=>{resetCreate();setTimeout(applyCreatePreview,30)});
    if(window.BigPawAPI&&!BigPawAPI.__parentLayoutWrapped){const orig=BigPawAPI.addParentDog.bind(BigPawAPI);BigPawAPI.addParentDog=v=>orig({...v,imagePosX:createX,imagePosY:createY,imageZoom:createZ});BigPawAPI.__parentLayoutWrapped=true}
    const oldClear=window.clearPhotoPreview;if(typeof oldClear==='function')window.clearPhotoPreview=function(){oldClear.apply(this,arguments);resetCreate()};
  }

  function photoHtml(d){
    if(!d?.image_url)return '🐩';const a=layout(d);
    return `<img src="${esc(d.image_url)}" alt="${esc(d.name||'親犬')}" data-focal-x="${a.x}" data-focal-y="${a.y}" data-focal-z="${a.z}">`;
  }
  function renderManagedCards(){document.querySelectorAll('.parentpic img[data-focal-x]').forEach(im=>renderFocal(im.parentElement,im,num(im.dataset.focalX,50),num(im.dataset.focalY,50),num(im.dataset.focalZ,1)))}
  function enhancedCard(d){
    const photoButtons=`<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0 4px"><button type="button" class="btn btn-sub" onclick="BigPawParentPhoto.pickPhoto('${esc(d.id)}')">📷 ${d.image_url?'写真を変更':'写真を追加'}</button>${d.image_url?`<button type="button" class="btn btn-main" onclick="BigPawParentPhoto.openAdjust('${esc(d.id)}')">↔ 表示を調整</button>`:'<span></span>'}</div>`;
    return `<div class="card"><div class="parentpic" style="position:relative;overflow:hidden">${photoHtml(d)}</div><div class="pad">${photoButtons}<div class="chips" style="margin-top:12px"><span class="chip">${esc(d.sex)}</span><span class="chip">${esc(d.color||'')}</span></div><h2>${esc(d.name)}</h2><div class="fact-grid"><div class="fact"><span>犬種</span><b>${esc(d.breed||'-')}</b></div><div class="fact"><span>体高</span><b>${d.height_cm||'-'}cm</b></div><div class="fact"><span>体重</span><b>${d.weight_kg||'-'}kg</b></div><div class="fact"><span>健康情報</span><b>${esc(d.health_summary||'未登録')}</b></div></div><p class="muted">${esc(d.genetics||'')}</p><a class="btn btn-sub btn-wide" style="margin-top:9px" href="health-records.html?parentDogId=${encodeURIComponent(d.id)}">健康・検査記録を見る</a></div></div>`;
  }
  async function enhancedLoad(){
    const listEl=document.getElementById('parentList');if(!listEl)return;
    try{const list=await BigPawAPI.parentDogs();window.__BIGPAW_PARENT_DOGS=list||[];listEl.innerHTML=list.length?list.map(enhancedCard).join(''):'<div class="card empty" style="grid-column:1/-1"><h2>親犬はまだ登録されていません</h2><p class="muted">「＋ 親犬を登録」から登録できます。</p></div>';requestAnimationFrame(renderManagedCards)}
    catch(e){listEl.innerHTML='<div class="card empty" style="grid-column:1/-1"><h2>親犬情報を読み込めませんでした</h2><button class="btn btn-sub" onclick="BigPawParentPhoto.reload()">再読み込み</button></div>'}
  }

  let replaceDogId='';
  function ensureReplaceInput(){
    let input=document.getElementById('pdReplacePhoto');if(input)return input;
    input=document.createElement('input');input.id='pdReplacePhoto';input.type='file';input.accept='image/jpeg,image/png,image/webp';input.style.display='none';document.body.appendChild(input);
    input.addEventListener('change',async()=>{const f=input.files&&input.files[0],id=replaceDogId;input.value='';if(!f||!id)return;if(f.size>8*1024*1024){alert('写真は8MB以下を選んでください。');return}try{const up=await BigPawAPI.upload(f);if(!up.url)throw new Error('upload_failed');await BigPawAPI.updateParentDog(id,{imageUrl:up.url,imagePosX:50,imagePosY:50,imageZoom:1});await enhancedLoad();setTimeout(()=>openAdjust(id),0)}catch(e){alert(e&&e.status===415?'JPG・PNG・WebPの写真を選んでください。':'写真を変更できませんでした。')}});
    return input;
  }
  function pickPhoto(id){replaceDogId=id;ensureReplaceInput().click()}

  let editDog=null,editX=50,editY=50,editZ=1;
  const editState=()=>({x:editX,y:editY,z:editZ});const setEditState=s=>{editX=s.x;editY=s.y;editZ=s.z};
  function ensureAdjustModal(){
    if(document.getElementById('pdAdjustModal'))return;
    const m=document.createElement('div');m.className='modal';m.id='pdAdjustModal';
    m.innerHTML='<div class="box"><h2>親犬写真の表示調整</h2><div id="pdAdjustFrame" style="width:280px;height:280px;max-width:100%;margin:0 auto 14px;border-radius:18px;overflow:hidden;background:#e7f1ff;position:relative;touch-action:none"><img id="pdAdjustImg" alt="親犬写真" style="display:block"></div><div style="padding:12px;border:1px solid #cfe0f4;border-radius:14px;background:#f7fbff;text-align:center"><b style="display:block;margin-bottom:6px">写真を直接動かしてください</b><div style="font-size:14px;line-height:1.7">☝️ 1本指で上下左右に移動<br>🤏 2本指でピンチして拡大・縮小</div><button type="button" class="btn btn-sub" id="pdAdjustReset" style="margin-top:10px">中央に戻す</button><small class="muted" style="display:block;margin-top:8px">この四角の中に見えている位置を、そのまま一般公開ページにも使います。</small></div><div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button type="button" class="btn btn-sub" id="pdAdjustCancel">キャンセル</button><button type="button" class="btn btn-main" id="pdAdjustSave">この位置で保存</button></div></div>';
    document.body.appendChild(m);const frame=document.getElementById('pdAdjustFrame'),im=document.getElementById('pdAdjustImg');
    document.getElementById('pdAdjustCancel').onclick=()=>m.classList.remove('show');document.getElementById('pdAdjustSave').onclick=saveEdit;document.getElementById('pdAdjustReset').onclick=()=>{editX=50;editY=50;editZ=1;applyEdit()};attachTouchAdjust(frame,im,editState,setEditState,applyEdit);
  }
  function applyEdit(){const frame=document.getElementById('pdAdjustFrame'),im=document.getElementById('pdAdjustImg');if(frame&&im)renderFocal(frame,im,editX,editY,editZ)}
  function openAdjust(id){ensureAdjustModal();editDog=(window.__BIGPAW_PARENT_DOGS||[]).find(x=>String(x.id)===String(id));if(!editDog||!editDog.image_url)return;const a=layout(editDog);editX=a.x;editY=a.y;editZ=a.z;const im=document.getElementById('pdAdjustImg');im.src=editDog.image_url;document.getElementById('pdAdjustModal').classList.add('show');setTimeout(applyEdit,20)}
  async function saveEdit(){if(!editDog)return;const btn=document.getElementById('pdAdjustSave');btn.disabled=true;try{await BigPawAPI.updateParentDog(editDog.id,{imagePosX:editX,imagePosY:editY,imageZoom:editZ});document.getElementById('pdAdjustModal').classList.remove('show');await enhancedLoad()}catch(e){alert('写真の表示調整を保存できませんでした。')}finally{btn.disabled=false}}

  window.BigPawParentPhoto={openAdjust,pickPhoto,reload:enhancedLoad};window.load=enhancedLoad;
  function start(){installCreateControls();ensureReplaceInput();ensureAdjustModal();enhancedLoad()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
  window.addEventListener('resize',()=>{renderManagedCards();applyCreatePreview();applyEdit()});
})();
