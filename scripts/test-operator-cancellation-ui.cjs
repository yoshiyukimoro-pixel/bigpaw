const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('app/assets/operator-cancellations.js','utf8');

async function run(action,note=''){
  const message={textContent:''},filter={value:'attention',onchange:null};
  const noteEl={value:note,focusCalled:false,focus(){this.focusCalled=true}};
  const card={dataset:{request:'ic_ui_test'},querySelector:s=>s==='[data-note]'?noteEl:null};
  const button={dataset:{action},disabled:false,onclick:null,closest:()=>card,hasAttribute:()=>false};
  const requests={
    _html:'',
    set innerHTML(v){this._html=v},
    get innerHTML(){return this._html},
    querySelectorAll(sel){
      if(sel==='[data-acknowledge]')return [];
      if(sel==='[data-action],[data-resend]')return [button];
      return [];
    }
  };
  const els={message,filter,requests};
  const calls=[];
  const location={hash:'',search:'',pathname:'/operator-cancellations.html',href:''};
  const windowObj={location,dispatchEvent(){},addEventListener(){},scrollTo(){}};
  const ctx={
    console,URLSearchParams,encodeURIComponent,Event:function Event(){},
    location,window:windowObj,
    document:{getElementById:id=>els[id],querySelectorAll:()=>[]},
    confirm:()=>true,
    BigPawAPI:{request:async(path,opts)=>{
      calls.push({path,opts});
      if(!opts)return {requests:[{
        id:'ic_ui_test',inquiry_id:'q_ui',puppy_name:'青くん',kennel_name:'DOG44',buyer_name:'購入希望者',
        state:'operator_review',operator_seen_at:1,breeder_reason_label:'見学予定だったが見学に至らなかった',
        breeder_note:'',buyer_reason_label:'見学したが契約には至らなかった',buyer_note:'',
        created_at:1,answered_at:2,expires_at:9999999999,mail:{sent_at:3},financial_review:false,history:[]
      }]};
      return {ok:true,state:action==='approve'?'closed':'continued'};
    }}
  };
  vm.createContext(ctx);
  const p=vm.runInContext(code,ctx,{filename:'operator-cancellations.js'});
  await p;
  assert.equal(typeof button.onclick,'function','decision handler installed');
  await button.onclick();
  return {calls,location,message,noteEl};
}

(async()=>{
  const approved=await run('approve','');
  const patch=approved.calls.find(x=>x.opts?.method==='PATCH');
  assert(patch,'approve sends PATCH');
  assert.equal(patch.opts.body.action,'approve');
  assert(patch.opts.body.note.includes('取引中止を承認しました'),'approve auto-fills an audited reason');
  assert.equal(approved.location.href,'operator-cancellations.html?decision=approved','approve navigates to completed notice');

  const continued=await run('continue','');
  assert(!continued.calls.some(x=>x.opts?.method==='PATCH'),'continue still requires a typed reason');
  assert(continued.message.textContent.includes('判断の理由を入力'),'missing reason is shown inline');
  assert(continued.noteEl.focusCalled,'missing reason focuses the textarea');

  console.log('OPERATOR_CANCELLATION_UI_OK|approve_empty_note|patch_sent|redirect|continue_note_required');
})().catch(e=>{console.error(e);process.exit(1)});
