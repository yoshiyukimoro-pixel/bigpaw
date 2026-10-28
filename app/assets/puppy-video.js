(()=>{
  'use strict';
  const MAX_SECONDS=60;
  const durationAllowed=seconds=>Number.isFinite(Number(seconds))&&Number(seconds)>0&&Number(seconds)<=MAX_SECONDS;
  const MAX_BYTES=200*1024*1024;
  let selected=null;
  let pendingChoose=Promise.resolve(false);
  let selectionError=false;
  let pendingUpload=Promise.resolve(null);
  let uploadError=null;
  let uploadInProgress=false;
  let cancelRequested=false;
  let activeRequest=null;
  let currentPuppyId='';
  let previewEpoch=0;
  let previewTimer=0;
  const objectUrls=new Set();
  const $=id=>document.getElementById(id);

  function cleanupObjectUrls(){
    for(const url of objectUrls){try{URL.revokeObjectURL(url)}catch(e){}}
    objectUrls.clear();
  }
  function setStatus(message,isError=false){
    const el=$('puppyVideoStatus');
    if(!el)return;
    el.textContent=message||'';
    el.style.color=isError?'#b42318':'';
    el.style.fontWeight=isError?'700':'';
  }
  function showCancelButton(show){
    let b=$('cancelPuppyVideoUploadBtn');
    if(!b&&$('puppyVideoStatus')){
      b=document.createElement('button');
      b.type='button';
      b.id='cancelPuppyVideoUploadBtn';
      b.textContent='動画送信を中止して通常の保存に戻る';
      b.style.cssText='display:none;margin-top:8px;padding:8px 12px;border:1px solid #777;border-radius:8px;background:white';
      $('puppyVideoStatus').insertAdjacentElement('afterend',b);
      b.addEventListener('click',()=>{
        if(!uploadInProgress)return;
        cancelRequested=true;
        if(activeRequest)activeRequest.abort();
        setStatus('動画の送信を中止しています…');
      });
    }
    if(b)b.style.display=show?'inline-block':'none';
  }
  function setPreview(html){
    const el=$('puppyVideoPreview');
    if(el)el.innerHTML=html||'';
  }
  function escapeHtml(v){
    return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function durationOf(file){
    return new Promise((resolve,reject)=>{
      const v=document.createElement('video');
      const url=URL.createObjectURL(file);
      objectUrls.add(url);
      let done=false;
      const finish=(fn,value)=>{
        if(done)return;
        done=true;
        clearTimeout(timer);
        try{v.removeAttribute('src');v.load()}catch(e){}
        try{URL.revokeObjectURL(url)}catch(e){}
        objectUrls.delete(url);
        fn(value);
      };
      const timer=setTimeout(()=>finish(reject,new Error('metadata_timeout')),10000);
      v.preload='metadata';
      v.muted=true;
      v.playsInline=true;
      v.onloadedmetadata=()=>{
        const d=Number(v.duration);
        if(!Number.isFinite(d)||d<=0)return finish(reject,new Error('invalid_duration'));
        finish(resolve,d);
      };
      v.onerror=()=>finish(reject,new Error('metadata_error'));
      v.src=url;
    });
  }
  async function choose(file){
    selected=null;
    cleanupObjectUrls();
    if(!file){setPreview('');setStatus('');return false}
    if(file.size>MAX_BYTES){
      setPreview('');
      setStatus('動画の容量が大きすぎます。200MB以内の動画を選択してください。',true);
      return false;
    }
    if(file.type&&!String(file.type).startsWith('video/')){
      setPreview('');
      setStatus('動画ファイルを選択してください。',true);
      return false;
    }
    setStatus('動画の長さを確認しています…');
    let duration;
    try{duration=await durationOf(file)}
    catch(e){
      setPreview('');
      setStatus('動画の長さを確認できませんでした。MP4またはMOVの60秒以内の動画を選択してください。',true);
      return false;
    }
    if(!durationAllowed(duration)){
      setPreview('');
      setStatus('この動画は'+Math.ceil(duration)+'秒です。動画は60秒以内に編集してから、もう一度選択してください。',true);
      return false;
    }
    selected={file,duration};
    const url=URL.createObjectURL(file);
    objectUrls.add(url);
    setPreview('<video controls playsinline preload="metadata" src="'+escapeHtml(url)+'" style="width:100%;max-height:360px;border-radius:14px;background:#111"></video><div style="margin-top:8px;font-weight:700">選択中：'+duration.toFixed(1)+'秒</div>');
    setStatus('60秒以内です。保存すると動画を1本登録します。');
    return true;
  }
  function stopPreviewCheck(){
    previewEpoch+=1;
    if(previewTimer)clearTimeout(previewTimer);
    previewTimer=0;
  }
  async function checkExistingPreview(uid,epoch,attempt=0){
    if(epoch!==previewEpoch)return;
    const area=$('puppyVideoPlayback');
    if(!area)return;
    let response;
    try{
      response=await BigPawAPI.puppyVideoStatus(currentPuppyId);
    }catch(e){
      // Do not present a Cloudflare check failure as an upload failure.
      // A publicly playable video is left intact on the server.
      if(epoch!==previewEpoch)return;
      area.textContent='動画は登録済みです。再生の準備状況を確認しています…';
    }
    if(epoch!==previewEpoch)return;
    if(response){
      if(response.videoUid!==uid || !response.hasVideo){
        area.textContent='動画の状態が変わりました。編集画面を開き直して確認してください。';
        return;
      }
      if(response.readyToStream && response.videoEmbedUrl){
        const embed=String(response.videoEmbedUrl);
        area.innerHTML='<div style="aspect-ratio:16/9"><iframe src="'+escapeHtml(embed)+'" title="子犬の動画" loading="lazy" style="width:100%;height:100%;border:0;border-radius:14px" allow="accelerometer; gyroscope; encrypted-media; picture-in-picture" allowfullscreen></iframe></div>';
        return;
      }
      if(response.state==='error'){
        area.textContent='動画の再生準備状況を確認してください。動画は削除されていません。';
        return;
      }
      area.textContent='動画は登録済みです。再生できるようになるまで準備中です…';
    }
    // Bounded automatic checks, plus a manual retry that can be used later.
    if(attempt<23){
      previewTimer=setTimeout(()=>checkExistingPreview(uid,epoch,attempt+1),5000);
    }else{
      area.innerHTML='<div>動画は保存済みです。再生準備の確認が続いています。</div><button type="button" id="retryPuppyVideoPreviewBtn" class="btn btn-sub" style="margin-top:10px">再生できるか確認する</button>';
      const b=$('retryPuppyVideoPreviewBtn');
      if(b)b.onclick=()=>{
        stopPreviewCheck();
        const nextEpoch=previewEpoch;
        area.textContent='再生準備を確認しています…';
        checkExistingPreview(uid,nextEpoch,0);
      };
    }
  }
  function renderExisting(p){
    currentPuppyId=String((p&&p.id)||currentPuppyId||'');
    stopPreviewCheck();
    const box=$('puppyVideoExisting');
    if(!box)return;
    const uid=String((p&&p.videoUid)||'');
    if(!uid){box.innerHTML='';return}
    // Even when the DB has a video UID, Stream may still be transcoding.
    // Never auto-load its iframe before Cloudflare says readyToStream=true.
    box.innerHTML='<div style="margin-bottom:10px;font-weight:800">現在の動画</div><div id="puppyVideoPlayback" role="status" aria-live="polite" class="notice">動画は登録済みです。再生の準備状況を確認しています…</div><button type="button" id="deletePuppyVideoBtn" class="btn btn-sub" style="margin-top:10px">この動画を削除</button>';
    const b=$('deletePuppyVideoBtn');if(b)b.onclick=deleteExisting;
    checkExistingPreview(uid,previewEpoch,0);
  }
  async function deleteExisting(){
    if(!currentPuppyId||!confirm('登録中の動画を削除しますか？'))return;
    const btn=$('deletePuppyVideoBtn');
    if(btn){btn.disabled=true;btn.textContent='削除中…'}
    try{
      await BigPawAPI.deletePuppyVideo(currentPuppyId);
      stopPreviewCheck();
      const box=$('puppyVideoExisting');if(box)box.innerHTML='';
      setStatus('動画を削除しました。');
    }catch(e){
      setStatus('動画を削除できませんでした。',true);
      if(btn){btn.disabled=false;btn.textContent='この動画を削除'}
    }
  }
  async function uploadIfSelected(puppyId){
    await pendingChoose;
    if(!selected)return null;
    if(!window.BigPawAPI||!BigPawAPI.isLive())throw new Error('video_requires_live_server');
    const file=selected.file;
    currentPuppyId=String(puppyId||'');
    setStatus('動画のアップロードを準備しています…');
    const ticket=await BigPawAPI.createPuppyTusUpload(currentPuppyId,{fileName:file.name||'puppy-video',fileSize:file.size});
    if(!ticket||!ticket.uid||!ticket.uploadURL||ticket.protocol!=='tus'){
      throw new Error('動画のアップロード準備を確認できませんでした。');
    }
    const target=new URL(ticket.uploadURL);
    if(target.protocol!=='https:' ||
       !['upload.cloudflarestream.com','upload.videodelivery.net'].includes(target.hostname) ||
       target.username||target.password){
      throw new Error('動画の送信先を確認できませんでした。');
    }
    setStatus('動画をCloudflareへ送信中… 0%');
    // Cloudflare's resumable tus protocol gives a real HTTP status and offset.
    // Unlike the old hidden-iframe POST, failures cannot silently appear saved.
    // File bytes go from Safari straight to Cloudflare (never Railway).
    const chunkSize=5*1024*1024;
    const common={'Tus-Resumable':'1.0.0'};
    const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    let offset=0;
    while(offset<file.size){
      if(cancelRequested)throw new Error('video_upload_cancelled');
      const end=Math.min(file.size,offset+chunkSize);
      let success=false;
      for(let retry=0;retry<6&&!success;retry++){
        if(retry)await pause(Math.min(12000,1000*Math.pow(2,retry)));
        try{
          if(cancelRequested)throw new Error('video_upload_cancelled');
          activeRequest=new AbortController();
          const res=await fetch(target.href,{
            method:'PATCH',mode:'cors',credentials:'omit',signal:activeRequest.signal,
            headers:{...common,'Upload-Offset':String(offset),'Content-Type':'application/offset+octet-stream'},
            body:file.slice(offset,end)
          });
          activeRequest=null;
          if(!res.ok)throw new Error('HTTP '+res.status);
          const next=Number(res.headers.get('Upload-Offset'));
          if(!Number.isSafeInteger(next)||next<=offset||next>end){
            throw new Error('アップロード位置を確認できませんでした。');
          }
          offset=next;
          success=true;
        }catch(error){
          activeRequest=null;
          if(cancelRequested)throw new Error('video_upload_cancelled');
          // On a dropped mobile connection the chunk might already have
          // reached Stream. Recover offset by HEAD before ever retrying bytes.
          try{
            const head=await fetch(target.href,{
              method:'HEAD',mode:'cors',credentials:'omit',headers:common
            });
            if(head.ok){
              const serverOffset=Number(head.headers.get('Upload-Offset'));
              if(Number.isSafeInteger(serverOffset)&&serverOffset>=offset&&serverOffset<=file.size){
                if(serverOffset>=end){offset=serverOffset;success=true;break;}
                offset=serverOffset;
                if(offset>0&&offset<end)break;
              }
            }
          }catch(ignore){}
          if(retry===5)throw new Error(
            'Cloudflareへの送信が完了しませんでした。回線を確認してください。（'+
            String(error.message||'通信エラー').slice(0,80)+'）'
          );
        }
      }
      setStatus('動画をCloudflareへ送信中… '+Math.min(100,Math.floor(offset*100/file.size))+'%');
    }
    setStatus('送信完了。Cloudflareで動画の登録を確認しています…');
    // A mobile Safari "Load failed" can mean that the *response* to an
    // already-committed attachment was lost (Railway logs HTTP 499). Verify
    // the exact just-uploaded UID from the database before reporting failure
    // or retrying. A playable older video is NOT proof that this UID saved.
    async function readBack(attempts){
      for(let i=0;i<attempts;i++){
        if(cancelRequested)throw new Error('video_upload_cancelled');
        if(i)await pause(1200);
        try{
          const puppies=await BigPawAPI.breederPuppies();
          const matching=Array.isArray(puppies)?
            puppies.find(p=>String(p.id)===currentPuppyId):null;
          if(matching&&String(matching.videoUid||'')===String(ticket.uid))return matching;
        }catch(e){
          // A temporary GET failure must not erase an already saved video.
        }
      }
      return null;
    }
    let confirmedPuppy=null;
    let networkRetries=0;
    for(let attempt=0;attempt<50;attempt++){
      if(cancelRequested)throw new Error('video_upload_cancelled');
      if(attempt)await pause(2000);
      if(cancelRequested)throw new Error('video_upload_cancelled');
      try{
        await BigPawAPI.attachPuppyVideo(currentPuppyId,ticket.uid);
        break;
      }catch(e){
        if(e.data?.error==='video_upload_not_received'){
          if(attempt===49)
            throw new Error('Cloudflareへの送信完了後、動画の登録確認ができませんでした。');
          continue;
        }
        // Only an indeterminate network error is eligible for an idempotent
        // retry. Explicit HTTP 400/403/422 must retain their original error.
        if(e.status)throw e;
        setStatus('通信が途切れました。動画が保存済みか確認しています…');
        confirmedPuppy=await readBack(4);
        if(confirmedPuppy)break;
        networkRetries+=1;
        if(networkRetries>=3){
          throw new Error('通信が途切れたため、保存結果を確認できませんでした。再登録する前に編集画面を開き直して確認してください。');
        }
        setStatus('保存状況を確認できませんでした。同じ動画の登録を再確認しています…');
      }
    }
    // A successful POST response alone is not sufficient; confirm the exact
    // UID is persisted. Keep the previously attached video if an old one plays.
    const puppy=confirmedPuppy||await readBack(4);
    if(!puppy){
      throw new Error('動画の保存結果を確認できませんでした。編集画面を開き直して確認してください。');
    }
    selected=null;
    cleanupObjectUrls();
    const input=$('puppyVideo');
    if(input)input.value='';
    setPreview('');
    renderExisting(puppy);
    setStatus('動画を登録しました。');
    return puppy;
  }
  function init(){
    const input=$('puppyVideo');
    if(input&&!input.dataset.bigpawVideoBound){
      input.dataset.bigpawVideoBound='1';
      input.addEventListener('change',()=>{
        const file=input.files&&input.files[0];
        selectionError=false;
        uploadError=null;
        cancelRequested=false;
        // This promise MUST be assigned synchronously with the change event.
        // Previously the async listener awaited metadata before assigning
        // pendingUpload, letting a fast Save button bypass the upload entirely.
        pendingChoose=choose(file);
        const savingExisting=!!(file&&currentPuppyId);
        const form=input.closest('form');
        const saveButton=form&&form.querySelector('button[type="submit"], .btn-main.btn-wide');
        const priorDisabled=saveButton?saveButton.disabled:false;
        if(savingExisting){
          uploadInProgress=true;
          if(saveButton)saveButton.disabled=true;
          showCancelButton(true);
        }
        pendingUpload=pendingChoose.then(async ok=>{
          if(!ok){
            selectionError=!!file;
            input.value='';
            return null;
          }
          if(!savingExisting)return null;
          input.disabled=true;
          try{
            return await uploadIfSelected(currentPuppyId);
          }catch(e){
            if(cancelRequested){
              selected=null;
              input.value='';
              cleanupObjectUrls();
              setPreview('');
              uploadError=null;
              setStatus('動画の送信を中止しました。通常の内容は保存できます。');
              return null;
            }
            uploadError=e;
            setStatus('動画を保存できませんでした：'+String(e.message||'通信エラー'),true);
            return null;
          }finally{
            input.disabled=false;
          }
        }).catch(e=>{
          uploadError=e;
          setStatus('動画を保存できませんでした：'+String(e.message||'通信エラー'),true);
          return null;
        }).finally(()=>{
          uploadInProgress=false;
          activeRequest=null;
          showCancelButton(false);
          if(saveButton)saveButton.disabled=priorDisabled;
        });
      });
    }
  }
  window.addEventListener('beforeunload',event=>{
    if(!uploadInProgress)return;
    event.preventDefault();
    event.returnValue='';
  });
  window.BigPawPuppyVideo={
    maxSeconds:MAX_SECONDS,
    durationAllowed,
    renderExisting,
    uploadIfSelected,
    hasSelected:()=>!!selected,
    waitForSelection:async()=>{const valid=await pendingChoose;await pendingUpload;if(uploadError)throw uploadError;const input=$('puppyVideo');if(selectionError||(input&&input.files&&input.files.length&&!valid))throw new Error('動画を確認できませんでした。動画を選び直してください。');},
    clear:()=>{selectionError=false;uploadError=null;selected=null;cleanupObjectUrls();setPreview('');setStatus('')},
    init
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
  window.addEventListener('pagehide',cleanupObjectUrls);
})();