const fs=require('fs');
const vm=require('vm');

function assert(cond,msg){if(!cond)throw new Error(msg)}

const elements={
  color:{value:'ブラック'},gender:{value:'女の子'},status:{value:'募集中'},breed:{value:'スタンダードプードル'},birth:{value:'2026-07-01'},
  price:{value:'235000'},weight:{value:'10'},adultMin:{value:'25'},adultMax:{value:'30'},father:{value:'クラージュ'},mother:{value:'ミルク'},
  health:{checked:true},appealPoint:{value:'🐾保存確認テスト✨'},desc:{value:'紹介文'},photo:{files:[]}
};

global.window=global;
global.document={getElementById:id=>elements[id]||null};
global.location={search:'?id=p_test',href:'breeder-puppy-new.html?id=p_test'};
global.sessionStorage={removeItem(){}};
global.BIGPAW_BREEDS=[];
let alerts=[];
global.alert=msg=>alerts.push(String(msg));
let lastPayload=null;
let readbacks=0;

global.BigPawAPI={request:async()=>[]};
global.BigPawBridge={
  updatePuppy:async(id,payload)=>{lastPayload=payload;return {id}},
  addPuppy:async payload=>{lastPayload=payload;return {id:'p_test'}},
  breederPuppies:async()=>{readbacks++;return [{id:'p_test',appealPoint:lastPayload?.appealPoint||''}]},
  upload:async()=>({id:'x',url:'/x.jpg'})
};

const src=fs.readFileSync('app/breeder-editor-safety-fix.js','utf8');
vm.runInThisContext(src,{filename:'breeder-editor-safety-fix.js'});

(async()=>{
  const submitter={disabled:false,textContent:'変更内容を保存する'};
  await window.savePuppy({preventDefault(){},submitter});
  assert(lastPayload&&lastPayload.appealPoint==='🐾保存確認テスト✨','appealPoint was not sent by override payload');
  assert(readbacks>=1,'saved value was not read back after PATCH');
  assert(alerts.includes('変更を保存しました。'),'success alert missing after verified save');
  assert(location.href==='admin.html','navigation did not happen after verified save');

  alerts=[]; readbacks=0; location.href='breeder-puppy-new.html?id=p_test';
  BigPawBridge.breederPuppies=async()=>{readbacks++;return [{id:'p_test',appealPoint:'古い値'}]};
  await window.savePuppy({preventDefault(){},submitter:{disabled:false,textContent:'変更内容を保存する'}});
  assert(readbacks>=1,'negative case did not perform readback');
  assert(!alerts.includes('変更を保存しました。'),'false success was shown despite readback mismatch');
  assert(location.href!=='admin.html','navigated away despite readback mismatch');
  assert(alerts.some(x=>x.includes('保存確認ができませんでした')),'mismatch warning missing');

  console.log('APPEAL_RUNTIME_BEHAVIOR_OK|payload=appealPoint|readback=performed|success=verified_only|mismatch=false_success_blocked');
})().catch(e=>{console.error('APPEAL_RUNTIME_BEHAVIOR_FAIL|'+e.message);process.exit(1)});
