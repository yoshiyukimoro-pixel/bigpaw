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
  let currentPuppyId='';
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
  function renderExisting(p){
    currentPuppyId=String((p&&p.id)||currentPuppyId||'');
    const box=$('puppyVideoExisting');
    if(!box)return;
    const embed=String((p&&p.videoEmbedUrl)||'');
    const uid=String((p&&p.videoUid)||'');
    if(embed){
      box.innerHTML='<div style="margin-bottom:10px;font-weight:800">現在の動画</div><div style="aspect-ratio:16/9"><iframe src="'+escapeHtml(embed)+'" title="子犬の動画" style="width:100%;height:100%;border:0;border-radius:14px" allow="accelerometer; gyroscope; encrypted-media; picture-in-picture" allowfullscreen></iframe></div><button type="button" id="deletePuppyVideoBtn" class="btn btn-sub" style="margin-top:10px">この動画を削除</button>';
      const b=$('deletePuppyVideoBtn');if(b)b.onclick=deleteExisting;
    }else if(uid){
      box.innerHTML='<div class="notice">動画を処理しています。しばらくすると公開ページで再生できるようになります。</div><button type="button" id="deletePuppyVideoBtn" class="btn btn-sub" style="margin-top:10px">この動画を削除</button>';
      const b=$('deletePuppyVideoBtn');if(b)b.onclick=deleteExisting;
    }else{
      box.innerHTML='';
    }
  }
  async function deleteExisting(){
    if(!currentPuppyId||!confirm('登録中の動画を削除しますか？'))return;
    const btn=$('deletePuppyVideoBtn');
    if(btn){btn.disabled=true;btn.textContent='削除中…'}
    try{
      await BigPawAPI.deletePuppyVideo(currentPuppyId);
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
    const ticket=await BigPawAPI.createPuppyVideoUpload(currentPuppyId,{fileName:file.name||'puppy-video',fileSize:file.size});
    if(!ticket||!ticket.uid||!ticket.uploadURL)throw new Error('video_upload_ticket_missing');
    setStatus('動画をアップロードしています…');
    // Stream's one-time upload endpoint can omit CORS response headers on iPhone.
    // A no-cors POST still sends the video directly to Cloudflare (never Railway);
    // its opaque response is NOT proof of success. Verify receipt through our API.
    const target=new URL(ticket.uploadURL);
    // Cloudflare Stream currently issues upload.cloudflarestream.com URLs;
    // older tickets use upload.videodelivery.net. Accept ONLY these official
    // Cloudflare Stream upload hosts, never arbitrary third-party domains.
    if(target.protocol!=='https:' ||
       !['upload.cloudflarestream.com','upload.videodelivery.net'].includes(target.hostname) ||
       target.username || target.password){
      throw new Error('動画の送信先を確認できませんでした。');
    }
    // Safari sometimes fails to deliver the File from a cross-origin fetch.
    // Use the browser's native multipart/form-data HTML upload to the genuine
    // one-time Cloudflare Stream endpoint. No video bytes pass through Railway.
    // The hidden frame is NOT evidence of success; only the authenticated
    // Cloudflare status check on the server can confirm delivery.
    const input=$('puppyVideo');
    if(!input||!input.files||!input.files.length||
       input.files[0].size!==file.size||input.files[0].name!==file.name){
      throw new Error('送信する動画ファイルを確認できません。もう一度選択してください。');
    }
    const frame=document.createElement('iframe');
    const frameName='bigpaw-stream-upload-'+Date.now()+'-'+Math.floor(Math.random()*100000);
    frame.name=frameName;
    frame.setAttribute('aria-hidden','true');
    frame.style.display='none';
    const form=document.createElement('form');
    form.method='POST';
    form.enctype='multipart/form-data';
    form.action=target.href;
    form.target=frameName;
    form.style.display='none';
    const marker=document.createComment('bigpaw-video-input-slot');
    const originalName=input.name;
    const originalDisabled=input.disabled;
    input.parentNode.insertBefore(marker,input);
    document.body.appendChild(frame);
    document.body.appendChild(form);
    form.appendChild(input);
    input.name='file';
    // Disabled form fields are omitted from multipart submissions. The file
    // picker is temporarily inside the hidden form and cannot be reselected.
    input.disabled=false;
    try{
      form.submit();
      setStatus('Cloudflareへ動画を送信中です。完了するまで画面を閉じずにお待ちください…');
      // An upload on 4G can take more than a minute. The server returns 409
      // until Stream has actually received the bytes. Never present success
      // based solely on the temporary local video preview.
      for(let attempt=0;attempt<90;attempt++){
        if(attempt>0)await new Promise(resolve=>setTimeout(resolve,2000));
        try{
          await BigPawAPI.attachPuppyVideo(currentPuppyId,ticket.uid);
          break;
        }catch(e){
          if(!e.data||e.data.error!=='video_upload_not_received')throw e;
          if(attempt===89){
            throw new Error('Cloudflareで動画の受信を確認できませんでした。保存されていないため、通信状況を確認して再度お試しください。');
          }
        }
      }
    }finally{
      input.name=originalName;
      input.disabled=originalDisabled;
      if(marker.parentNode)marker.parentNode.replaceChild(input,marker);
      form.remove();
      frame.remove();
    }
    // Do not claim success until the video UID is read back from the database.
    const puppies=await BigPawAPI.breederPuppies();
    const puppy=Array.isArray(puppies)?puppies.find(p=>String(p.id)===currentPuppyId):null;
    if(!puppy||String(puppy.videoUid||'')!==String(ticket.uid)){
      throw new Error('動画の保存を確認できませんでした。再度お試しください。');
    }
    selected=null;
    cleanupObjectUrls();
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
      input.addEventListener('change',async()=>{
        const file=input.files&&input.files[0];
        selectionError=false;
        pendingChoose=choose(file);
        const ok=await pendingChoose;
        if(!ok){selectionError=!!file;input.value='';return;}
        // Existing listing: save video immediately on selection, avoiding form-save races.
        // Keep the file and a visible error if Cloudflare or the database rejects it.
        if(currentPuppyId && file){
          uploadError=null;
          input.disabled=true;
          try{
            pendingUpload=uploadIfSelected(currentPuppyId).catch(e=>{
              uploadError=e;
              setStatus('動画を保存できませんでした：'+String(e.message||'通信エラー'),true);
              return null;
            });
            await pendingUpload;
          }finally{input.disabled=false;}
        }
      });
    }
  }
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