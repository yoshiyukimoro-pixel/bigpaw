(()=>{
  if(window.__BIGPAW_BREEDER_EDITOR_SAFETY__) return;
  window.__BIGPAW_BREEDER_EDITOR_SAFETY__=true;

  const byId=id=>document.getElementById(id);
  const value=id=>byId(id)?.value??'';
  const num=id=>Number(value(id)||0);
  const checked=id=>!!byId(id)?.checked;
  const breedKey=name=>{
    const a=Array.isArray(window.BIGPAW_BREEDS)?window.BIGPAW_BREEDS:[];
    const b=a.find(v=>v.ja===name);
    return b?b.key:({'スタンダードプードル':'standard-poodle','ゴールデンレトリバー':'golden-retriever','ラブラドールレトリバー':'labrador-retriever'}[name]||name);
  };
  const editId=()=>new URLSearchParams(location.search).get('id')||'';
  const payload=()=>({
    name:value('color')+'の'+value('gender'),
    status:value('status')||'募集中',
    breed:value('breed'),
    breedKey:breedKey(value('breed')),
    gender:value('gender'),
    color:value('color'),
    birth:value('birth'),
    price:num('price'),
    weight:num('weight'),
    adultMin:num('adultMin'),
    adultMax:num('adultMax'),
    father:value('father'),
    mother:value('mother'),
    health:checked('health'),
    desc:value('desc')
  });
  async function deletePhoto(pid,photoId){
    return BigPawAPI.request('/puppies/'+encodeURIComponent(pid)+'/photos/'+encodeURIComponent(photoId),{method:'DELETE'});
  }
  async function cleanupNew(pid,uploaded){
    for(const p of uploaded){try{await deletePhoto(pid,p.id)}catch(e){}}
  }
  async function replacePhotos(pid,files){
    if(!files.length) return null;
    let old=[];
    try{old=await BigPawAPI.request('/puppies/'+encodeURIComponent(pid)+'/photos')}catch(e){old=[]}
    const uploaded=[];
    try{
      for(const f of files){
        const up=await BigPawBridge.upload(f,pid);
        if(!up||!up.id||!up.url) throw new Error('photo_upload_failed');
        uploaded.push(up);
      }
    }catch(e){
      await cleanupNew(pid,uploaded);
      throw e;
    }
    await BigPawBridge.updatePuppy(pid,{imageUrl:uploaded[0].url});
    const failed=[];
    for(const p of old){
      if(!p?.id) continue;
      try{await deletePhoto(pid,p.id)}catch(e){
        try{await deletePhoto(pid,p.id)}catch(e2){failed.push(p.id)}
      }
    }
    if(failed.length) throw new Error('old_photo_cleanup_failed');
    await BigPawAPI.request('/puppies/'+encodeURIComponent(pid)+'/photos/order',{method:'PATCH',body:{ids:uploaded.map(x=>String(x.id))}});
    window.persistedPhotos=uploaded.map((x,i)=>({id:x.id,url:x.url,isMain:i===0}));
    if(typeof window.renderPersistedPhotos==='function') window.renderPersistedPhotos();
    return uploaded;
  }

  window.savePuppy=async function(e){
    e.preventDefault();
    const btn=e.submitter||e.target?.querySelector('button[type="submit"],button:not([type])');
    const original=btn?.textContent||'';
    if(btn){btn.disabled=true;btn.textContent='保存中…'}
    const pid=editId();
    try{
      let puppy=pid?await BigPawBridge.updatePuppy(pid,payload()):await BigPawBridge.addPuppy(payload());
      const targetId=String(puppy?.id||pid||'');
      if(!targetId) throw new Error('puppy_id_missing');
      const files=[...(byId('photo')?.files||[])].slice(0,10);
      if(files.length){
        await replacePhotos(targetId,files);
      }else if(pid&&window.removeExistingMainRequested){
        await BigPawBridge.updatePuppy(targetId,{imageUrl:''});
      }
      sessionStorage.removeItem('bigpawEditPuppyId');
      alert(pid?'変更を保存しました。':'子犬情報を掲載しました。');
      location.href='admin.html';
    }catch(x){
      const msg=x?.message==='old_photo_cleanup_failed'?'新しい写真は保存されましたが、古い写真の整理に失敗しました。画面を再読み込みして写真を確認してください。':(x?.status===401?'ブリーダーとしてログインしてください。':'保存できませんでした：'+(x?.message||''));
      alert(msg);
    }finally{
      if(btn){btn.disabled=false;btn.textContent=original||'保存する'}
    }
  };
})();
