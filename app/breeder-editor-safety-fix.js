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
    appealPoint:value('appealPoint').trim(),
    desc:value('desc')
  });
  async function verifyAppealPointPersistence(pid,expected){
    const rows=await BigPawBridge.breederPuppies();
    const row=Array.isArray(rows)?rows.find(x=>String(x?.id)===String(pid)):null;
    if(!row) throw new Error('appeal_point_readback_missing');
    const actual=String(row.appealPoint??'');
    if(actual!==String(expected??'')) throw new Error('appeal_point_persistence_mismatch');
    return row;
  }
  async function deletePhoto(pid,photoId){
    return BigPawAPI.request('/puppies/'+encodeURIComponent(pid)+'/photos/'+encodeURIComponent(photoId),{method:'DELETE'});
  }
  async function cleanupNew(pid,uploaded){
    for(const p of uploaded){try{await deletePhoto(pid,p.id)}catch(e){}}
  }
  async function appendPhotos(pid,files){
    if(!files.length) return null;
    const old=await BigPawAPI.request('/puppies/'+encodeURIComponent(pid)+'/photos');
    if(!Array.isArray(old)) throw new Error('existing_photo_state_unavailable');
    const room=Math.max(0,10-old.length);
    if(room===0) throw new Error('photo_limit_reached');
    if(files.length>room) throw new Error('photo_limit_exceeded');
    const uploaded=[];
    try{
      for(const f of files){
        const up=await BigPawBridge.upload(f,pid);
        if(!up||!up.id||!up.url) throw new Error('photo_upload_failed');
        uploaded.push(up);
      }
      const currentMain=old.find(p=>p&&p.isMain);
      const orderedOld=currentMain
        ? [currentMain,...old.filter(p=>p!==currentMain)]
        : old.slice();
      const combined=[...orderedOld,...uploaded];
      await BigPawAPI.request('/puppies/'+encodeURIComponent(pid)+'/photos/order',{
        method:'PATCH',
        body:{ids:combined.map(x=>String(x.id))}
      });
      window.persistedPhotos=combined.map((x,i)=>({
        ...x,
        isMain:i===0
      }));
      if(typeof window.renderPersistedPhotos==='function') window.renderPersistedPhotos();
      return uploaded;
    }catch(e){
      await cleanupNew(pid,uploaded);
      throw e;
    }
  }

  window.savePuppy=async function(e){
    e.preventDefault();
    const btn=e.submitter||e.target?.querySelector('button[type="submit"],button:not([type])');
    const original=btn?.textContent||'';
    if(btn){btn.disabled=true;btn.textContent='保存中…'}
    const pid=editId();
    try{
      const data=payload();
      let puppy=pid?await BigPawBridge.updatePuppy(pid,data):await BigPawBridge.addPuppy(data);
      const targetId=String(puppy?.id||pid||'');
      if(!targetId) throw new Error('puppy_id_missing');
      const files=[...(byId('photo')?.files||[])].slice(0,10);
      if(files.length){
        await appendPhotos(targetId,files);
      }else if(pid&&window.removeExistingMainRequested){
        await BigPawBridge.updatePuppy(targetId,{imageUrl:''});
      }
      await verifyAppealPointPersistence(targetId,data.appealPoint);
      sessionStorage.removeItem('bigpawEditPuppyId');
      alert(pid?'変更を保存しました。':'子犬情報を掲載しました。');
      location.href='admin.html';
    }catch(x){
      const msg=x?.message==='photo_limit_reached'?'写真は最大10枚まで登録できます。不要な写真を削除してから追加してください。':x?.message==='photo_limit_exceeded'?'追加すると写真が10枚を超えるため保存していません。登録済み写真を含めて最大10枚までです。':x?.message==='existing_photo_state_unavailable'?'現在の写真情報を確認できなかったため、写真は変更していません。画面を再読み込みしてからもう一度お試しください。':x?.message==='appeal_point_persistence_mismatch'||x?.message==='appeal_point_readback_missing'?'アピールポイントの保存確認ができませんでした。変更は完了扱いにしていません。もう一度お試しください。':(x?.status===401?'ブリーダーとしてログインしてください。':'保存できませんでした：'+(x?.message||''));
      alert(msg);
    }finally{
      if(btn){btn.disabled=false;btn.textContent=original||'保存する'}
    }
  };
})();
