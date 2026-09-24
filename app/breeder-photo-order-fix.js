(()=>{
  if(window.__BIGPAW_PHOTO_ORDER_FIX__) return;
  window.__BIGPAW_PHOTO_ORDER_FIX__=true;
  const puppyId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId')||'';
  if(!puppyId) return;
  let lastServerSig=null;
  let saving=false;
  let installed=false;
  const esc=s=>String(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  function list(){return Array.isArray(window.persistedPhotos)?window.persistedPhotos:null}
  function sig(){const a=list();return a?a.map(x=>String(x.id)).join('|'):''}
  async function persistOrder(showError=true){
    const a=list(); if(!a||saving) return;
    const ids=a.map(x=>String(x.id));
    saving=true;
    try{
      await BigPawAPI.request('/puppies/'+encodeURIComponent(puppyId)+'/photos/order',{method:'PATCH',body:{ids}});
      a.forEach((x,i)=>x.isMain=i===0);
      lastServerSig=ids.join('|');
    }catch(e){
      if(showError) alert('写真の並び順を保存できませんでした');
    }finally{saving=false}
  }
  function render(){
    const a=list(),host=document.getElementById('photoPreview');
    if(!a||!host) return;
    a.forEach((x,i)=>x.isMain=i===0);
    host.innerHTML=a.map((p,i)=>'<div style="border:1px solid #eee;border-radius:14px;padding:8px"><img src="'+esc(p.url)+'" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px"><small style="display:block">'+(i===0?'メイン写真':'登録済み写真 '+(i+1))+'</small><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">'+(i>0?'<button type="button" onclick="movePersistedPhoto('+i+',-1)">←</button>':'')+(i<a.length-1?'<button type="button" onclick="movePersistedPhoto('+i+',1)">→</button>':'')+(i>0?'<button type="button" onclick="setPersistedMain('+i+')">メインにする</button>':'')+'<button type="button" onclick="openPersistedAdjust('+i+')">写真を調整</button><button type="button" onclick="deletePersistedPhoto('+i+')">削除</button></div></div>').join('');
    const current=sig();
    if(lastServerSig===null) lastServerSig=current;
    else if(current!==lastServerSig&&!saving) persistOrder(false);
  }
  window.movePersistedPhoto=async(i,delta)=>{
    const a=list(); if(!a) return; const j=i+delta; if(j<0||j>=a.length) return;
    [a[i],a[j]]=[a[j],a[i]]; render(); await persistOrder(true); render();
  };
  window.setPersistedMain=async i=>{
    const a=list(); if(!a||i<0||i>=a.length) return;
    const p=a.splice(i,1)[0]; a.unshift(p); render(); await persistOrder(true); render();
  };
  function install(){
    if(typeof window.renderPersistedPhotos!=='function') return;
    if(window.renderPersistedPhotos!==render){window.renderPersistedPhotos=render;installed=true}
    if(list()&&lastServerSig===null) render();
  }
  const timer=setInterval(()=>{install();if(installed&&list())render()},700);
  setTimeout(()=>clearInterval(timer),15000);
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',install):install();
  addEventListener('pageshow',install);
})();
