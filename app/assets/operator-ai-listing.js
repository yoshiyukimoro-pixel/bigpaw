/* Operator-only, preview-only AI listing assistant. No automatic publication. */
(async function(){
 let me;try{me=await BigPawAPI.me()}catch(_){return}
 if(!me||me.role!=='operator'||(typeof editId!=='undefined'&&editId))return;
 const selectedId=new URLSearchParams(location.search).get('breederId')||'';
 const form=document.querySelector('form');if(!form)return;
 const panel=document.createElement('section');
 panel.id='bpAiListingPanel';
 panel.style.cssText='border:1px solid #c2d8e8;background:#f5faff;border-radius:16px;padding:16px;margin-bottom:18px';
 panel.innerHTML=`
 <h2 style="margin:0 0 8px;font-size:20px">✨ チャッピーAI代理掲載（下書き）</h2>
 <p class="muted">届いた文章から登録項目と紹介文の下書きを作れます。内容は必ずご確認ください。AIだけでは公開されません。</p>
 <label for="bpAiSource" style="display:block;font-weight:bold;margin-top:12px">LINE等の文章</label>
 <textarea id="bpAiSource" rows="6" style="width:100%;margin-top:6px" placeholder="サモエドのヤンヤン、2024年9月4日生まれ、男の子。体重23kg、合計13万円..."></textarea>
 <label style="display:flex;gap:8px;align-items:flex-start;margin:12px 0;font-size:13px">
 <input id="bpAiConsent" type="checkbox" style="margin-top:4px">
 AI解析のため上記文章をOpenAI APIへ送信することに同意する（電話番号・住所などは事前に除いてください）
 </label>
 <button id="bpAiGenerate" type="button" class="btn btn-main">✨ AIで入力欄を作成</button>
 <details style="margin-top:14px">
 <summary style="cursor:pointer;font-weight:bold">チャッピーから受け取った掲載データ（JSON）を読み込む</summary>
 <p class="muted">ChatGPTが作ったJSON形式の掲載データを、AI用APIキーなしで入力欄に反映できます。</p>
 <textarea id="bpAiJson" rows="5" style="width:100%" placeholder='{"fields":{"name":"ヤンヤン","breed":"サモエド","gender":"男の子"}}'></textarea>
 <button id="bpAiImport" type="button" class="btn btn-sub" style="margin-top:8px">掲載データを読み込む</button>
 </details>
 <div id="bpAiFeedback" role="status" aria-live="polite" style="white-space:pre-wrap;margin-top:12px;font-size:13px"></div>
 <div style="margin-top:12px;font-size:13px">📷 写真は下の「写真」から1〜10枚選んでください。順番を確認して掲載します。<b id="bpAiPhotoCount">選択中：0枚</b></div>
 `;
 form.insertBefore(panel,form.querySelector('.stepbar')||form.firstChild);
 const source=panel.querySelector('#bpAiSource'),consent=panel.querySelector('#bpAiConsent');
 const feedback=panel.querySelector('#bpAiFeedback'),generate=panel.querySelector('#bpAiGenerate');
 const photoCount=panel.querySelector('#bpAiPhotoCount'),photo=document.getElementById('photo');
 const setMessage=(message,error=false)=>{feedback.textContent=message;feedback.style.color=error?'#a12c2c':'#225c42'};
 const keys=['name','breed','gender','color','birth','price','weight','adultMin','adultMax',
  'father','mother','desc','healthStatus','vaccineStatus','microchipStatus','geneticTestStatus'];
 function fill(k,v){
  if(v===undefined||v===null||v==='')return true;
  if(typeof v==='number'&&v===0)return true;
  const el=document.getElementById(k==='name'?'puppyName':k);
  if(!el)return false;
  const value=String(v);
  if(el.tagName==='SELECT'){
   const option=[...el.options].find(o=>o.value===value||o.textContent===value);
   if(option){el.value=option.value;return true}
   if(k==='father'||k==='mother'){el.add(new Option(value,value));el.value=value;return true}
   return false;
  }
  el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));return true;
 }
 function apply(json){
  if(!json||typeof json!=='object'||Array.isArray(json))throw Error('掲載データがJSON形式ではありません');
  const fields=json.fields&&typeof json.fields==='object'?json.fields:json;
  let n=0;const unknown=[];
  keys.forEach(k=>{if(Object.prototype.hasOwnProperty.call(fields,k)){
    if(fill(k,fields[k]))n++;else unknown.push(k+'：'+String(fields[k]).slice(0,40));
  }});
  const missing=Array.isArray(json.missing)?json.missing:[];
  const warnings=Array.isArray(json.warnings)?json.warnings:[];
  const messages=['入力欄を更新しました（'+n+'項目）。内容を確認してから「この内容で掲載する」を押してください。'];
  if(unknown.length)messages.push('選択できなかった項目：'+unknown.join('、'));
  if(missing.length)messages.push('不足情報：'+missing.join('、'));
  if(warnings.length)messages.push('確認事項：'+warnings.join('／'));
  setMessage(messages.join('\n'),unknown.length>0);
 }
 panel.querySelector('#bpAiImport').addEventListener('click',()=>{
  try{apply(JSON.parse(panel.querySelector('#bpAiJson').value))}
  catch(e){setMessage('読み込みエラー：'+(e.message||'JSONをご確認ください'),true)}
 });
 generate.addEventListener('click',async()=>{
  if(!selectedId){setMessage('掲載先のブリーダーを選択してください。',true);return}
  if(!consent.checked){setMessage('AI解析のための送信同意が必要です。',true);return}
  if(source.value.trim().length<15){setMessage('文章は15文字以上入力してください。',true);return}
  generate.disabled=true;setMessage('AIで解析しています…');
  try{
   const result=await BigPawAPI.request('/operator/ai-listing-draft',{
    method:'POST',body:{breederId:selectedId,notes:source.value.trim(),consent:true}
   });apply(result)
  }catch(e){
   const error=e?.data?.error||'';
   if(error==='ai_not_configured')setMessage('AI連携のAPIキーが未設定です。今は下のJSON貼り付け機能を利用できます。',true);
   else setMessage('解析できませんでした。時間をおいてやり直してください。（'+(error||'network_error')+'）',true)
  }finally{generate.disabled=false}
 });
 function updatePhotos(){
  const chosen=photo?.files?.length||0;
  const saved=Array.isArray(window.persistedPhotos)?window.persistedPhotos.length:0;
  photoCount.textContent='選択中：'+(chosen+saved)+'枚（最大10枚）';
 }
 if(photo)photo.addEventListener('change',()=>queueMicrotask(updatePhotos));
 updatePhotos();
})();