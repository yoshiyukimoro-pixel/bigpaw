(()=>{
  if(!/\/parent-dogs\.html$/.test(location.pathname))return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  const layout=d=>({
    x:num(d?.image_pos_x??d?.imagePosX,50),
    y:num(d?.image_pos_y??d?.imagePosY,50),
    z:num(d?.image_zoom??d?.imageZoom,1)
  });
  const imgStyle=d=>{
    const a=layout(d);
    return `width:100%;height:100%;object-fit:cover;object-position:${a.x}% ${a.y}%;transform:scale(${a.z});transform-origin:${a.x}% ${a.y}%;display:block`;
  };
  const photoHtml=d=>d&&d.image_url
    ?`<img src="${esc(d.image_url)}" alt="${esc(d.name||'親犬')}" style="${imgStyle(d)}">`
    :'🐩';

  function attachTouchAdjust(frame,getState,setState,apply){
    if(!frame||frame.dataset.touchAdjust==='1')return;
    frame.dataset.touchAdjust='1';
    frame.style.touchAction='none';
    frame.style.userSelect='none';
    frame.style.webkitUserSelect='none';
    frame.style.cursor='grab';

    const points=new Map();
    let lastSingle=null;
    let pinchStartDistance=0;
    let pinchStartZoom=1;

    const pointDistance=()=>{
      const a=[...points.values()];
      if(a.length<2)return 0;
      return Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y);
    };

    frame.addEventListener('pointerdown',e=>{
      if(e.pointerType==='mouse'&&e.button!==0)return;
      points.set(e.pointerId,{x:e.clientX,y:e.clientY});
      try{frame.setPointerCapture(e.pointerId)}catch(_){ }
      if(points.size===1){
        lastSingle={x:e.clientX,y:e.clientY};
        frame.style.cursor='grabbing';
      }else if(points.size===2){
        pinchStartDistance=pointDistance()||1;
        pinchStartZoom=getState().z;
        lastSingle=null;
      }
      e.preventDefault();
    },{passive:false});

    frame.addEventListener('pointermove',e=>{
      if(!points.has(e.pointerId))return;
      points.set(e.pointerId,{x:e.clientX,y:e.clientY});

      if(points.size===1&&lastSingle){
        const dx=e.clientX-lastSingle.x;
        const dy=e.clientY-lastSingle.y;
        const rect=frame.getBoundingClientRect();
        const s=getState();
        const factor=Math.max(1,s.z);
        setState({
          x:clamp(s.x-(dx/Math.max(1,rect.width))*100/factor,0,100),
          y:clamp(s.y-(dy/Math.max(1,rect.height))*100/factor,0,100),
          z:s.z
        });
        lastSingle={x:e.clientX,y:e.clientY};
        apply();
      }else if(points.size>=2){
        const d=pointDistance();
        if(d>0&&pinchStartDistance>0){
          const s=getState();
          setState({x:s.x,y:s.y,z:clamp(pinchStartZoom*(d/pinchStartDistance),1,3)});
          apply();
        }
      }
      e.preventDefault();
    },{passive:false});

    const release=e=>{
      points.delete(e.pointerId);
      if(points.size===1){
        const p=[...points.values()][0];
        lastSingle={x:p.x,y:p.y};
        pinchStartDistance=0;
      }else if(points.size===0){
        lastSingle=null;
        pinchStartDistance=0;
        frame.style.cursor='grab';
      }else if(points.size===2){
        pinchStartDistance=pointDistance()||1;
        pinchStartZoom=getState().z;
      }
    };
    frame.addEventListener('pointerup',release);
    frame.addEventListener('pointercancel',release);

    frame.addEventListener('wheel',e=>{
      e.preventDefault();
      const s=getState();
      setState({x:s.x,y:s.y,z:clamp(s.z+(e.deltaY<0?0.08:-0.08),1,3)});
      apply();
    },{passive:false});
  }

  let createX=50,createY=50,createZ=1;
  const createState=()=>({x:createX,y:createY,z:createZ});
  const setCreateState=s=>{createX=s.x;createY=s.y;createZ=s.z};

  function applyCreatePreview(){
    const im=document.getElementById('pdPhotoPreviewImg');
    if(!im)return;
    im.style.width='100%';
    im.style.height='100%';
    im.style.objectFit='cover';
    im.style.objectPosition=`${createX}% ${createY}%`;
    im.style.transform=`scale(${createZ})`;
    im.style.transformOrigin=`${createX}% ${createY}%`;
    im.style.display='block';
  }

  function resetCreate(){
    createX=50;createY=50;createZ=1;
    applyCreatePreview();
  }

  function installCreateControls(){
    const preview=document.getElementById('pdPhotoPreview');
    const im=document.getElementById('pdPhotoPreviewImg');
    if(!preview||!im||document.getElementById('pdPhotoAdjustControls'))return;

    let frame=document.getElementById('pdCreateGestureFrame');
    if(!frame){
      frame=document.createElement('div');
      frame.id='pdCreateGestureFrame';
      frame.style.cssText='width:260px;height:260px;max-width:100%;margin:12px auto 0;border-radius:18px;overflow:hidden;background:#e7f1ff;position:relative;touch-action:none';
      preview.insertBefore(frame,im);
      frame.appendChild(im);
    }

    const c=document.createElement('div');
    c.id='pdPhotoAdjustControls';
    c.style.cssText='margin-top:12px;padding:12px;border:1px solid #cfe0f4;border-radius:14px;background:#f7fbff;text-align:center';
    c.innerHTML='<b style="display:block;margin-bottom:6px">写真を指で調整</b><div style="font-size:14px;line-height:1.7">☝️ 1本指で上下左右に移動<br>🤏 2本指でピンチして拡大・縮小</div><button type="button" class="btn btn-sub" id="pdCreateReset" style="margin-top:10px">中央に戻す</button><small class="muted" style="display:block;margin-top:8px">ここで合わせた見え方が子犬ページにも使われます。</small>';
    preview.appendChild(c);

    document.getElementById('pdCreateReset').onclick=resetCreate;
    attachTouchAdjust(frame,createState,setCreateState,applyCreatePreview);

    const file=document.getElementById('pdPhoto');
    if(file)file.addEventListener('change',()=>{resetCreate();setTimeout(applyCreatePreview,0)});

    if(window.BigPawAPI&&!BigPawAPI.__parentLayoutWrapped){
      const orig=BigPawAPI.addParentDog.bind(BigPawAPI);
      BigPawAPI.addParentDog=v=>orig({...v,imagePosX:createX,imagePosY:createY,imageZoom:createZ});
      BigPawAPI.__parentLayoutWrapped=true;
    }

    const oldClear=window.clearPhotoPreview;
    if(typeof oldClear==='function')window.clearPhotoPreview=function(){oldClear.apply(this,arguments);resetCreate()};
  }

  function enhancedCard(d){
    const photoButtons=`<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0 4px"><button type="button" class="btn btn-sub" onclick="BigPawParentPhoto.pickPhoto('${esc(d.id)}')">📷 ${d.image_url?'写真を変更':'写真を追加'}</button>${d.image_url?`<button type="button" class="btn btn-main" onclick="BigPawParentPhoto.openAdjust('${esc(d.id)}')">↔ 表示を調整</button>`:'<span></span>'}</div>`;
    return `<div class="card"><div class="parentpic">${photoHtml(d)}</div><div class="pad">${photoButtons}<div class="chips" style="margin-top:12px"><span class="chip">${esc(d.sex)}</span><span class="chip">${esc(d.color||'')}</span></div><h2>${esc(d.name)}</h2><div class="fact-grid"><div class="fact"><span>犬種</span><b>${esc(d.breed||'-')}</b></div><div class="fact"><span>体高</span><b>${d.height_cm||'-'}cm</b></div><div class="fact"><span>体重</span><b>${d.weight_kg||'-'}kg</b></div><div class="fact"><span>健康情報</span><b>${esc(d.health_summary||'未登録')}</b></div></div><p class="muted">${esc(d.genetics||'')}</p><a class="btn btn-sub btn-wide" style="margin-top:9px" href="health-records.html?parentDogId=${encodeURIComponent(d.id)}">健康・検査記録を見る</a></div></div>`;
  }

  async function enhancedLoad(){
    const listEl=document.getElementById('parentList');
    if(!listEl)return;
    try{
      const list=await BigPawAPI.parentDogs();
      window.__BIGPAW_PARENT_DOGS=list||[];
      listEl.innerHTML=list.length?list.map(enhancedCard).join(''):'<div class="card empty" style="grid-column:1/-1"><h2>親犬はまだ登録されていません</h2><p class="muted">「＋ 親犬を登録」から登録できます。</p></div>';
    }catch(e){
      listEl.innerHTML='<div class="card empty" style="grid-column:1/-1"><h2>親犬情報を読み込めませんでした</h2><button class="btn btn-sub" onclick="BigPawParentPhoto.reload()">再読み込み</button></div>';
    }
  }

  let replaceDogId='';
  function ensureReplaceInput(){
    let input=document.getElementById('pdReplacePhoto');
    if(input)return input;
    input=document.createElement('input');
    input.id='pdReplacePhoto';
    input.type='file';
    input.accept='image/jpeg,image/png,image/webp';
    input.style.display='none';
    document.body.appendChild(input);
    input.addEventListener('change',async()=>{
      const f=input.files&&input.files[0];
      const id=replaceDogId;
      input.value='';
      if(!f||!id)return;
      if(f.size>8*1024*1024){alert('写真は8MB以下を選んでください。');return}
      try{
        const up=await BigPawAPI.upload(f);
        if(!up.url)throw new Error('upload_failed');
        await BigPawAPI.updateParentDog(id,{imageUrl:up.url,imagePosX:50,imagePosY:50,imageZoom:1});
        await enhancedLoad();
        setTimeout(()=>openAdjust(id),0);
      }catch(e){
        alert(e&&e.status===415?'JPG・PNG・WebPの写真を選んでください。':'写真を変更できませんでした。');
      }
    });
    return input;
  }
  function pickPhoto(id){
    replaceDogId=id;
    ensureReplaceInput().click();
  }

  let editDog=null,editX=50,editY=50,editZ=1;
  const editState=()=>({x:editX,y:editY,z:editZ});
  const setEditState=s=>{editX=s.x;editY=s.y;editZ=s.z};

  function ensureAdjustModal(){
    if(document.getElementById('pdAdjustModal'))return;
    const m=document.createElement('div');
    m.className='modal';
    m.id='pdAdjustModal';
    m.innerHTML='<div class="box"><h2>親犬写真の表示調整</h2><div id="pdAdjustFrame" style="width:280px;height:280px;max-width:100%;margin:0 auto 14px;border-radius:18px;overflow:hidden;background:#e7f1ff;position:relative;touch-action:none"><img id="pdAdjustImg" alt="親犬写真" style="width:100%;height:100%;object-fit:cover;display:block"></div><div style="padding:12px;border:1px solid #cfe0f4;border-radius:14px;background:#f7fbff;text-align:center"><b style="display:block;margin-bottom:6px">写真を直接動かしてください</b><div style="font-size:14px;line-height:1.7">☝️ 1本指で上下左右に移動<br>🤏 2本指でピンチして拡大・縮小</div><button type="button" class="btn btn-sub" id="pdAdjustReset" style="margin-top:10px">中央に戻す</button><small class="muted" style="display:block;margin-top:8px">この見え方が子犬登録画面と一般公開の子犬詳細にも反映されます。</small></div><div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button type="button" class="btn btn-sub" id="pdAdjustCancel">キャンセル</button><button type="button" class="btn btn-main" id="pdAdjustSave">この位置で保存</button></div></div>';
    document.body.appendChild(m);
    document.getElementById('pdAdjustCancel').onclick=()=>m.classList.remove('show');
    document.getElementById('pdAdjustSave').onclick=saveEdit;
    document.getElementById('pdAdjustReset').onclick=()=>{editX=50;editY=50;editZ=1;applyEdit()};
    attachTouchAdjust(document.getElementById('pdAdjustFrame'),editState,setEditState,applyEdit);
  }

  function applyEdit(){
    const im=document.getElementById('pdAdjustImg');
    if(!im)return;
    im.style.objectPosition=`${editX}% ${editY}%`;
    im.style.transform=`scale(${editZ})`;
    im.style.transformOrigin=`${editX}% ${editY}%`;
  }

  function openAdjust(id){
    ensureAdjustModal();
    editDog=(window.__BIGPAW_PARENT_DOGS||[]).find(x=>String(x.id)===String(id));
    if(!editDog||!editDog.image_url)return;
    const a=layout(editDog);
    editX=a.x;editY=a.y;editZ=a.z;
    document.getElementById('pdAdjustImg').src=editDog.image_url;
    applyEdit();
    document.getElementById('pdAdjustModal').classList.add('show');
  }

  async function saveEdit(){
    if(!editDog)return;
    const btn=document.getElementById('pdAdjustSave');
    btn.disabled=true;
    try{
      await BigPawAPI.updateParentDog(editDog.id,{imagePosX:editX,imagePosY:editY,imageZoom:editZ});
      document.getElementById('pdAdjustModal').classList.remove('show');
      await enhancedLoad();
    }catch(e){
      alert('写真の表示調整を保存できませんでした。');
    }finally{
      btn.disabled=false;
    }
  }

  window.BigPawParentPhoto={openAdjust,pickPhoto,reload:enhancedLoad};
  window.load=enhancedLoad;

  function start(){
    installCreateControls();
    ensureReplaceInput();
    ensureAdjustModal();
    enhancedLoad();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
