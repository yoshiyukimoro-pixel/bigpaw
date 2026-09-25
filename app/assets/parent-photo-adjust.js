(()=>{
  if(!/\/parent-dogs\.html$/.test(location.pathname))return;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
  const layout=d=>({x:num(d?.image_pos_x??d?.imagePosX,50),y:num(d?.image_pos_y??d?.imagePosY,50),z:num(d?.image_zoom??d?.imageZoom,1)});
  const imgStyle=d=>{const a=layout(d);return `width:100%;height:100%;object-fit:cover;object-position:${a.x}% ${a.y}%;transform:scale(${a.z});transform-origin:${a.x}% ${a.y}%;display:block`};
  const photoHtml=d=>d&&d.image_url?`<img src="${esc(d.image_url)}" alt="${esc(d.name||'親犬')}" style="${imgStyle(d)}">`:'🐩';

  let createX=50,createY=50,createZ=1;
  function applyCreatePreview(){
    const im=document.getElementById('pdPhotoPreviewImg');
    if(!im)return;
    im.style.width='220px';im.style.height='220px';im.style.objectFit='cover';im.style.objectPosition=`${createX}% ${createY}%`;im.style.transform=`scale(${createZ})`;im.style.transformOrigin=`${createX}% ${createY}%`;im.style.display='block';
    const vx=document.getElementById('pdPosXValue'),vy=document.getElementById('pdPosYValue'),vz=document.getElementById('pdZoomValue');
    if(vx)vx.textContent=Math.round(createX)+'%';if(vy)vy.textContent=Math.round(createY)+'%';if(vz)vz.textContent=createZ.toFixed(2)+'倍';
  }
  function resetCreate(){createX=50;createY=50;createZ=1;['pdPosX','pdPosY'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=50});const z=document.getElementById('pdZoom');if(z)z.value=1;applyCreatePreview()}
  function installCreateControls(){
    const preview=document.getElementById('pdPhotoPreview');
    if(!preview||document.getElementById('pdPhotoAdjustControls'))return;
    const c=document.createElement('div');c.id='pdPhotoAdjustControls';c.style.cssText='margin-top:12px;padding:12px;border:1px solid #cfe0f4;border-radius:14px;background:#f7fbff';
    c.innerHTML='<b style="display:block;margin-bottom:8px">写真の表示調整</b><label style="display:grid;grid-template-columns:72px 1fr 44px;gap:8px;align-items:center;margin:8px 0"><span>左右位置</span><input id="pdPosX" type="range" min="0" max="100" value="50"><small id="pdPosXValue">50%</small></label><label style="display:grid;grid-template-columns:72px 1fr 44px;gap:8px;align-items:center;margin:8px 0"><span>上下位置</span><input id="pdPosY" type="range" min="0" max="100" value="50"><small id="pdPosYValue">50%</small></label><label style="display:grid;grid-template-columns:72px 1fr 52px;gap:8px;align-items:center;margin:8px 0"><span>拡大</span><input id="pdZoom" type="range" min="1" max="2.5" step="0.05" value="1"><small id="pdZoomValue">1.00倍</small></label><small class="muted">顔や全身が見やすい位置に合わせてください。登録後も変更できます。</small>';
    preview.appendChild(c);
    document.getElementById('pdPosX').addEventListener('input',e=>{createX=num(e.target.value,50);applyCreatePreview()});
    document.getElementById('pdPosY').addEventListener('input',e=>{createY=num(e.target.value,50);applyCreatePreview()});
    document.getElementById('pdZoom').addEventListener('input',e=>{createZ=num(e.target.value,1);applyCreatePreview()});
    const file=document.getElementById('pdPhoto');if(file)file.addEventListener('change',()=>setTimeout(applyCreatePreview,0));
    if(window.BigPawAPI&&!BigPawAPI.__parentLayoutWrapped){
      const orig=BigPawAPI.addParentDog.bind(BigPawAPI);
      BigPawAPI.addParentDog=v=>orig({...v,imagePosX:createX,imagePosY:createY,imageZoom:createZ});
      BigPawAPI.__parentLayoutWrapped=true;
    }
    const oldClear=window.clearPhotoPreview;
    if(typeof oldClear==='function')window.clearPhotoPreview=function(){oldClear.apply(this,arguments);resetCreate()};
  }

  function enhancedCard(d){
    const adjust=d.image_url?`<button class="btn btn-sub btn-wide" style="margin-top:9px" onclick="BigPawParentPhoto.openAdjust('${esc(d.id)}')">写真表示を調整</button>`:'';
    return `<div class="card"><div class="parentpic">${photoHtml(d)}</div><div class="pad"><div class="chips"><span class="chip">${esc(d.sex)}</span><span class="chip">${esc(d.color||'')}</span></div><h2>${esc(d.name)}</h2><div class="fact-grid"><div class="fact"><span>犬種</span><b>${esc(d.breed||'-')}</b></div><div class="fact"><span>体高</span><b>${d.height_cm||'-'}cm</b></div><div class="fact"><span>体重</span><b>${d.weight_kg||'-'}kg</b></div><div class="fact"><span>健康情報</span><b>${esc(d.health_summary||'未登録')}</b></div></div><p class="muted">${esc(d.genetics||'')}</p>${adjust}<a class="btn btn-sub btn-wide" style="margin-top:9px" href="health-records.html?parentDogId=${encodeURIComponent(d.id)}">健康・検査記録を見る</a></div></div>`;
  }
  async function enhancedLoad(){
    const listEl=document.getElementById('parentList');if(!listEl)return;
    try{const list=await BigPawAPI.parentDogs();window.__BIGPAW_PARENT_DOGS=list||[];listEl.innerHTML=list.length?list.map(enhancedCard).join(''):'<div class="card empty" style="grid-column:1/-1"><h2>親犬はまだ登録されていません</h2><p class="muted">「＋ 親犬を登録」から登録できます。</p></div>'}
    catch(e){listEl.innerHTML='<div class="card empty" style="grid-column:1/-1"><h2>親犬情報を読み込めませんでした</h2><button class="btn btn-sub" onclick="BigPawParentPhoto.reload()">再読み込み</button></div>'}
  }

  let editDog=null,editX=50,editY=50,editZ=1;
  function ensureAdjustModal(){
    if(document.getElementById('pdAdjustModal'))return;
    const m=document.createElement('div');m.className='modal';m.id='pdAdjustModal';m.innerHTML='<div class="box"><h2>親犬写真の表示調整</h2><div style="width:260px;height:260px;max-width:100%;margin:0 auto 16px;border-radius:18px;overflow:hidden;background:#e7f1ff"><img id="pdAdjustImg" alt="親犬写真" style="width:100%;height:100%;object-fit:cover;display:block"></div><label style="display:grid;grid-template-columns:72px 1fr 44px;gap:8px;align-items:center;margin:10px 0"><span>左右位置</span><input id="pdAdjustX" type="range" min="0" max="100"><small id="pdAdjustXV"></small></label><label style="display:grid;grid-template-columns:72px 1fr 44px;gap:8px;align-items:center;margin:10px 0"><span>上下位置</span><input id="pdAdjustY" type="range" min="0" max="100"><small id="pdAdjustYV"></small></label><label style="display:grid;grid-template-columns:72px 1fr 52px;gap:8px;align-items:center;margin:10px 0"><span>拡大</span><input id="pdAdjustZ" type="range" min="1" max="2.5" step="0.05"><small id="pdAdjustZV"></small></label><small class="muted">この見え方が子犬登録画面と一般公開の子犬詳細にも反映されます。</small><div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button type="button" class="btn btn-sub" id="pdAdjustCancel">キャンセル</button><button type="button" class="btn btn-main" id="pdAdjustSave">保存する</button></div></div>';
    document.body.appendChild(m);
    ['pdAdjustX','pdAdjustY','pdAdjustZ'].forEach(id=>document.getElementById(id).addEventListener('input',applyEdit));
    document.getElementById('pdAdjustCancel').onclick=()=>m.classList.remove('show');
    document.getElementById('pdAdjustSave').onclick=saveEdit;
  }
  function applyEdit(){
    editX=num(document.getElementById('pdAdjustX')?.value,50);editY=num(document.getElementById('pdAdjustY')?.value,50);editZ=num(document.getElementById('pdAdjustZ')?.value,1);
    const im=document.getElementById('pdAdjustImg');if(im){im.style.objectPosition=`${editX}% ${editY}%`;im.style.transform=`scale(${editZ})`;im.style.transformOrigin=`${editX}% ${editY}%`}
    document.getElementById('pdAdjustXV').textContent=Math.round(editX)+'%';document.getElementById('pdAdjustYV').textContent=Math.round(editY)+'%';document.getElementById('pdAdjustZV').textContent=editZ.toFixed(2)+'倍';
  }
  function openAdjust(id){
    ensureAdjustModal();editDog=(window.__BIGPAW_PARENT_DOGS||[]).find(x=>String(x.id)===String(id));if(!editDog||!editDog.image_url)return;
    const a=layout(editDog);editX=a.x;editY=a.y;editZ=a.z;document.getElementById('pdAdjustImg').src=editDog.image_url;document.getElementById('pdAdjustX').value=editX;document.getElementById('pdAdjustY').value=editY;document.getElementById('pdAdjustZ').value=editZ;applyEdit();document.getElementById('pdAdjustModal').classList.add('show');
  }
  async function saveEdit(){
    if(!editDog)return;const btn=document.getElementById('pdAdjustSave');btn.disabled=true;
    try{await BigPawAPI.updateParentDog(editDog.id,{imagePosX:editX,imagePosY:editY,imageZoom:editZ});document.getElementById('pdAdjustModal').classList.remove('show');await enhancedLoad()}
    catch(e){alert('写真の表示調整を保存できませんでした。')}
    finally{btn.disabled=false}
  }
  window.BigPawParentPhoto={openAdjust,reload:enhancedLoad};
  window.load=enhancedLoad;
  function start(){installCreateControls();ensureAdjustModal();enhancedLoad()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
