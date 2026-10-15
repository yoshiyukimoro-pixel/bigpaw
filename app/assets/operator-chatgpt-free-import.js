/* BIG PAW: free ChatGPT JSON-to-form assistant.
   Operator only. No external API, no auto-upload and no auto-publish. */
(async function(){
  let account;
  try{account=await BigPawAPI.me()}catch(_){return}
  if(!account||account.role!=='operator'||(typeof editId!=='undefined'&&editId))return;
  const scope=new URLSearchParams(location.search).get('breederId')||'';
  const form=document.querySelector('form');if(!form)return;
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
      const d=new Date(s+'T00:00:00');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==s){
        warnings.push('生年月日を確認してください');return
      }
      el.value=s;
    }else if(dropdowns.has(k)){
      const s=String(value).trim();
      let option=[...el.options].find(o=>o.value===s||o.textContent===s);
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
  form.addEventListener('submit',function(event){
    if(!imported)return; // Existing non-AI operator publishing remains unchanged.
    const required=[
      ['breed','犬種'],['gender','性別'],['birth','生年月日'],['price','税込価格'],
      ['desc','紹介文']
    ];
    const absent=required.filter(([k])=>{
      const val=String(target(k)?.value||'').trim();
      return !val||(k==='price'&&!(Number(val)>0));
    }).map(([,name])=>name);
    if(absent.length||!reviewed.checked){
      event.preventDefault();event.stopImmediatePropagation();
      message((absent.length?'必須項目を確認してください：'+absent.join('、')+'\n':'')
        +'掲載先の犬舎・価格・写真・紹介文を確認し、チェックを入れてから掲載してください。',true);
      panel.scrollIntoView({behavior:'smooth',block:'start'});
    }
  },true);
})();