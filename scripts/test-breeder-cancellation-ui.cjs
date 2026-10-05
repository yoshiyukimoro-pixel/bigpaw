const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('app/assets/breeder-cancellation.js','utf8');

async function runCase(postResult, expectedSuffix, loadRequest=null){
  const els={};
  for(const id of ['message','puppy','current','form','reason','note','accurate','listingAction','submit']){
    els[id]={id,textContent:'',innerHTML:'',hidden:false,value:'',checked:false,disabled:false};
  }
  els.form.onsubmit=null;
  els.reason.value='visit_not_held';
  els.note.value='';
  els.accurate.checked=true;
  const location={search:'?inquiry=q_test',pathname:'/breeder-cancellation.html',href:''};
  let calls=[];
  const request=async (path,opts)=>{
    calls.push({path,opts});
    if(!opts) return loadRequest||{puppy_name:'青くん',request:null,breederReasons:{visit_not_held:'見学予定だったが見学に至らなかった'}};
    if(postResult instanceof Error) throw postResult;
    return postResult;
  };
  const ctx={
    console,URLSearchParams,encodeURIComponent,
    location,window:{location},
    document:{getElementById:id=>els[id]},
    BigPawAPI:{request},
    confirm:()=>true,
    setTimeout,clearTimeout
  };
  vm.createContext(ctx);
  vm.runInContext(code,ctx,{filename:'breeder-cancellation.js'});
  await new Promise(r=>setTimeout(r,0));
  assert.equal(typeof els.form.onsubmit,'function','submit handler installed');
  await els.form.onsubmit({preventDefault(){}});
  await new Promise(r=>setTimeout(r,0));
  assert(location.href.endsWith(expectedSuffix),`expected redirect ${expectedSuffix}, got ${location.href}`);
  assert.equal(calls.filter(x=>x.opts?.method==='POST').length,1,'one POST only');
  return {els,calls};
}

(async()=>{
  await runCase({ok:true,state:'buyer_pending',id:'ic_new'},'breeder-inquiries.html?cancellation=submitted');
  await runCase({ok:true,state:'buyer_pending',id:'ic_old',alreadySubmitted:true},'breeder-inquiries.html?cancellation=already');
  const e=new Error('この問い合わせは中止申請済みです。');e.status=409;
  await runCase(e,'breeder-inquiries.html?cancellation=already');

  const load={
    puppy_name:'青くん',
    request:{state:'buyer_pending',breeder_reason_label:'見学予定だったが見学に至らなかった',breeder_note:'',review_note:'',mail:{sent_at:123,attempts:1}},
    breederReasons:{visit_not_held:'見学予定だったが見学に至らなかった'}
  };
  const result=await runCase({ok:true,alreadySubmitted:true},'breeder-inquiries.html?cancellation=already',load);
  assert(result.els.current.innerHTML.includes('購入希望者への確認メール：送信処理完了'),'mail status is visible');
  assert.equal(result.els.form.hidden,true,'existing pending request hides resubmit form');
  console.log('BREEDER_CANCELLATION_UI_OK|new_redirect|repeat_redirect|409_fallback|mail_status|pending_form_hidden');
})().catch(e=>{console.error(e);process.exit(1)});
