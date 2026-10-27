/* BIG PAW: free ChatGPT JSON-to-form assistant.
   Operator only. No external API, no auto-upload and no auto-publish. */
(async function(){
  let account;
  try{account=await BigPawAPI.me()}catch(_){return}
  if(!account||account.role!=='operator'||(typeof editId!=='undefined'&&editId))return;
  const scope=new URLSearchParams(location.search).get('breederId')||'';
  const form=document.querySelector('form');if(!form)return;
  // Operator proxy is still a breeder-facing form: keep photo/video areas blue.
  const blueStyle=document.createElement('style');
  blueStyle.id='bpProxyPhotoBlue';
  blueStyle.textContent='.bp-account-page .photo-box{background:#edf5ff!important;border-color:#5f8fc3!important;color:#244d78!important}.bp-account-page .photo-box .muted{color:#426582!important}';
  if(document.head&&document.head.appendChild)document.head.appendChild(blueStyle);
  // Explain required fields before the user attempts to publish.
  const requiredNames={breed:'犬種',gender:'性別',birth:'生年月日',price:'価格（税込）',desc:'紹介文'};
  // Required markers are guidance only; publishing guards still validate actual values.
  const requiredStyle=document.createElement('style');
  requiredStyle.textContent='.bp-required-mark{display:inline-block;margin-left:6px;color:#a82020;font-size:12px;font-weight:800}.bp-optional-mark{display:inline-block;margin-left:6px;color:#64748b;font-size:12px;font-weight:600}';
  if(document.head&&document.head.appendChild)document.head.appendChild(requiredStyle);
  for(const [key,label] of Object.entries(requiredNames)){
    const input=document.getElementById(key);
    const wrapper=input&&input.closest&&input.closest('.field');
    const labelNode=wrapper&&wrapper.querySelector&&wrapper.querySelector('label');
    if(!labelNode||labelNode.querySelector('.bp-required-mark'))continue;
    const mark=document.createElement('span');
    mark.className='bp-required-mark';
    mark.textContent='必須';
    labelNode.appendChild(mark);
  }
  const photoInput=document.getElementById('photo');
  const photoBox=photoInput&&photoInput.closest&&photoInput.closest('.photo-box');
  const photoHeading=photoBox&&photoBox.querySelector&&photoBox.querySelector('b');
  if(photoHeading){
    const mark=document.createElement('span');
    mark.className='bp-required-mark';mark.textContent='必須・1枚以上';
    photoHeading.appendChild(mark);
  }
  const reviewedHint=document.createElement('p');
  reviewedHint.style.cssText='font-size:12px;color:#a82020;font-weight:700;margin:4px 0';
  reviewedHint.textContent='※ 掲載には必須項目・写真1枚以上・内容確認のチェックが必要です。';
  form.insertBefore(reviewedHint,form.querySelector('.stepbar')||form.firstChild);
  const panel=document.createElement('section');
  panel.id='bpFreeListingPanel';
  panel.style.cssText='border:2px solid #b9d5ed;background:#f3f9ff;border-radius:16px;padding:16px;margin:16px 0 20px;line-height:1.7';
  panel.innerHTML=[
    '<h2 style="margin:0 0 8px;font-size:19px">🐾 チャッピー代理掲載（無料）</h2>',
    '<p style="margin:0 0 10px">① ChatGPTにLINE文章・写真を渡して「BIG PAW用の貼り付けデータを作って」と依頼',
    '<br>② チャッピーから届いたデータを下へ貼り付け',
    '<br>③ 「入力欄に反映」を押して写真を最大10枚選び、内容を確認して掲載</p>',
    '<label for="bpFreeJson" style="display:block;font-weight:bold">チャッピーが作った掲載データ</label>',
    '<textarea id="bpFreeJson" rows="6" style="width:100%;font-size:14px" placeholder=\'{"fields":{"name":"ヤンヤン","breed":"サモエド","gender":"男の子","birth":"2024-09-04","price":130000,"desc":"..."},"missing":["毛色"],"warnings":[]}\'></textarea>',
    '<button id="bpFreeImport" class="btn btn-main" type="button" style="margin-top:10px">入力欄に反映する</button>',
    '<div id="bpFreeFeedback" role="status" aria-live="polite" style="white-space:pre-wrap;font-size:13px;margin:12px 0;color:#265f48"></div>',
    '<label style="display:flex;gap:8px;align-items:flex-start;font-size:13px;margin:10px 0">',
    '<input type="checkbox" id="bpFreeReviewed" style="margin-top:5px">',
    '掲載先の犬舎、金額、文章、健康情報、写真を自分で確認しました</label>',
    '<p style="margin:0;font-size:12px">※ この欄は無料です。AIへの有料API送信はありません。貼り付けだけでは登録・公開されません。</p>'
  ].join('');
  form.insertBefore(panel,form.querySelector('.stepbar')||form.firstChild);
  const jsonInput=panel.querySelector('#bpFreeJson');
  const importButton=panel.querySelector('#bpFreeImport');
  const feedback=panel.querySelector('#bpFreeFeedback');
  const reviewed=panel.querySelector('#bpFreeReviewed');
  let imported=false;
  function message(s,bad){
    feedback.textContent=s;
    feedback.style.color=bad?'#a62424':'#265f48';
  }
  const fields=['name','breed','gender','color','birth','price','weight',
    'adultMin','adultMax','father','mother','healthStatus','vaccineStatus',
    'microchipStatus','geneticTestStatus','appealPoint','desc'];
  const dropdowns=new Set(['breed','gender','father','mother',
    'healthStatus','vaccineStatus','microchipStatus','geneticTestStatus']);
  const healthDropdowns=new Set(['healthStatus','vaccineStatus','microchipStatus','geneticTestStatus']);
  function target(k){return document.getElementById(k==='name'?'puppyName':k)}
  function clearFormFields(){
    for(const k of fields){
      const el=target(k);if(!el)continue;
      if(dropdowns.has(k)){
        const reset=healthDropdowns.has(k)||k==='father'||k==='mother'?'未登録':'';
        if(reset){
          const opt=[...el.options].find(o=>o.value===reset||o.textContent===reset);
          if(opt)el.value=opt.value;
        }else{
          if(![...el.options].some(o=>o.value==='')){
            el.insertBefore(new Option(k==='breed'?'犬種を選択':'性別を選択',''),el.firstChild);
          }
          el.value='';
        }
      }else{el.value='';el.dispatchEvent(new Event('input',{bubbles:true}))}
    }
  }
  function set(k,value,warnings){
    if(value===null||value===undefined||String(value).trim()==='')return;
    const el=target(k);if(!el){warnings.push(k+'：入力欄が見つかりません');return}
    if(k==='price'||k==='weight'||k==='adultMin'||k==='adultMax'){
      const n=Number(value);
      if(!Number.isFinite(n)||n<0||(k==='price'&&!Number.isInteger(n))){
        warnings.push(k+'：数値が正しくありません');return;
      }
      if(n===0)return;
      el.value=String(n);
    }else if(k==='appealPoint'){
      const s=String(value);
      if([...s].length>30){warnings.push('アピールポイントは30文字以内にしてください');return}
      el.value=s;
    }else if(k==='birth'){
      const s=String(value);
      const d=new Date(s+'T00:00:00Z');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==s){
        warnings.push('生年月日を確認してください');return
      }
      el.value=s;
    }else if(dropdowns.has(k)){
      const s=String(value).trim();
      // Breeder messages often contain middle dots/spaces absent from breed labels.
      const normalized=s.replace(/[・･\s　]/g,'');
      let option=[...el.options].find(o=>o.value===s||o.textContent===s);
      if(!option&&k==='breed')option=[...el.options].find(o=>String(o.value||o.textContent).replace(/[・･\s　]/g,'')===normalized);
      if(!option&&s!=='未登録'&&(k==='father'||k==='mother')){
        option=new Option(s,s);el.add(option);
      }
      if(!option){warnings.push(k+'：選択肢が一致しません（'+s.slice(0,40)+'）');return}
      el.value=option.value;
    }else{
      el.value=String(value).trim();
    }
    el.dispatchEvent(new Event('input',{bubbles:true}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
  }
  function checkScope(){
    return scope&&window.bigpawProxyId&&String(scope)===String(window.bigpawProxyId);
  }
  importButton.addEventListener('click',function(){
    if(!checkScope()){
      message('掲載先の犬舎を確認できません。運営のブリーダー管理画面から開き直してください。',true);return;
    }
    let raw;
    try{raw=JSON.parse(jsonInput.value)}catch(_){
      message('JSON形式の掲載データをコピーして貼り付けてください。通常のLINE文章はチャッピーに渡して変換してください。',true);return;
    }
    if(!raw||typeof raw!=='object'||Array.isArray(raw)||!raw.fields||
      typeof raw.fields!=='object'||Array.isArray(raw.fields)){
      message('「fields」を含むBIG PAW用の掲載データを貼り付けてください。',true);return;
    }
    const given=raw.fields;
    if(!fields.some(k=>Object.prototype.hasOwnProperty.call(given,k))){
      message('掲載項目がありません。チャッピーにBIG PAW用のデータを作ってもらってください。',true);return;
    }
    const warnings=[];
    clearFormFields();
    for(const k of fields){
      if(Object.prototype.hasOwnProperty.call(given,k))set(k,given[k],warnings);
    }
    const missing=Array.isArray(raw.missing)?raw.missing.filter(x=>typeof x==='string').slice(0,20):[];
    const fromAi=Array.isArray(raw.warnings)?raw.warnings.filter(x=>typeof x==='string').slice(0,20):[];
    const note=['入力欄に反映したよ！ 下の全項目と写真を確認してね。'];
    if(missing.length)note.push('未確認：'+missing.join('、'));
    if(fromAi.length)note.push('注意事項：'+fromAi.join('／'));
    if(warnings.length)note.push('要修正：'+warnings.join('／'));
    const desc=String(target('desc')?.value||'');
    if(/https?:\/\/|[\w.+-]+@[\w.-]+\.\w+/.test(desc)){
      note.push('紹介文にURLまたはメールアドレスがあります。公開前に削除してください。');
    }
    imported=true;
    reviewed.checked=false;
    message(note.join('\n'),warnings.length>0);
  });
  // A browser can skip the form's submit event when a required control is
  // invalid. Validate on the button CLICK too, so a mobile user always learns
  // why nothing was published (even if Safari blocks native submission).
  const publishButton=form.querySelector('button.btn-wide');
  const publishHint=document.createElement('div');
  publishHint.id='bpFreePublishFeedback';
  publishHint.setAttribute('role','alert');
  publishHint.setAttribute('aria-live','assertive');
  publishHint.style.cssText='display:none;border:2px solid #dc8d8d;background:#fff6f6;color:#8d2020;border-radius:12px;padding:12px;margin:12px 0;font-size:14px;white-space:pre-wrap;line-height:1.7';
  if(publishButton)form.insertBefore(publishHint,publishButton);
  function blockers(){
    const problems=[];
    if(!checkScope())problems.push('掲載先の犬舎を確認できません。ブリーダー管理画面から開き直してください。');
    const required=[
      ['breed','犬種'],['gender','性別'],['birth','生年月日'],
      ['price','税込価格'],['desc','紹介文']
    ];
    for(const [key,label] of required){
      const value=String(target(key)?.value||'').trim();
      if(!value||(key==='price'&&!(Number(value)>0)))problems.push(label+'が未入力です。');
    }
    const files=document.getElementById('photo')?.files?.length||0;
    const selected=(typeof selectedPhotos!=='undefined'&&Array.isArray(selectedPhotos))?selectedPhotos.length:files;
    if(selected<1)problems.push('掲載写真を1枚以上選んでください（最大10枚）。');
    if(!reviewed.checked)problems.push('画面上部の「掲載先の犬舎、金額、文章、健康情報、写真を自分で確認しました」にチェックを入れてください。');
    return problems;
  }
  function markRequired(problems){
    const labels={breed:'犬種',gender:'性別',birth:'生年月日',price:'税込価格',desc:'紹介文'};
    let first=null;
    for(const [key,label] of Object.entries(labels)){
      const el=target(key);if(!el)continue;
      const missing=problems.includes(label+'が未入力です。');
      el.style.border=missing?'3px solid #c62828':'';
      el.style.backgroundColor=missing?'#fff0f0':'';
      el.setAttribute('aria-invalid',missing?'true':'false');
      if(missing&&!first)first=el;
    }
    return first;
  }
  function verify(event){
    if(!imported)return false;  // Ordinary manual operator listing not changed.
    const problems=blockers();
    if(!problems.length){
      markRequired([]);
      publishHint.textContent='';
      publishHint.style.display='none';
      return false;
    }
    if(event){
      event.preventDefault();
      event.stopImmediatePropagation();
    }
    const txt='まだ掲載できません。次の内容を確認してね。\n・'+problems.join('\n・');
    publishHint.textContent=txt;
    publishHint.style.display='block';
    const first=markRequired(problems);
    message(txt,true);
    if(first)first.scrollIntoView({block:'center',behavior:'smooth'});
    return true;
  }
  if(publishButton)publishButton.addEventListener('click',verify,true);
  form.addEventListener('submit',verify,true);
  // Native HTML5 validation fires "invalid" on the field and suppresses
  // submit. Keep the explanation visible beside the publish button.
  form.addEventListener('invalid',function(event){
    if(!imported)return;
    const field=event.target;
    const problems=blockers();
    const fieldLabel=field?.closest?.('.field')?.querySelector?.('label')?.textContent?.trim()||field?.getAttribute?.('aria-label')||field?.id||'入力項目';
    const nativeReason=field?.validationMessage||'入力内容を確認してください。';
    const detail=fieldLabel+'：'+nativeReason;
    if(!problems.includes(detail))problems.push(detail);
    publishHint.textContent='掲載できない理由：\\n・'+problems.join('\\n・');
    publishHint.style.display='block';
    markRequired(problems);
    if(field?.style){field.style.border='3px solid #c62828';field.style.backgroundColor='#fff0f0';}
    field?.setAttribute?.('aria-invalid','true');
    field?.scrollIntoView?.({block:'center',behavior:'smooth'});
  },true);
})();