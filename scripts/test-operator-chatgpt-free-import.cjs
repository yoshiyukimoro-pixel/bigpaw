#!/usr/bin/env node
'use strict';
/** No browser/network used; exercises the DOM import feature with fake form. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('app/assets/operator-chatgpt-free-import.js','utf8');
const parentPatch=fs.readFileSync('app/backend/operator_proxy_listing_ui_patch.py','utf8');
const freePatch=fs.readFileSync('app/backend/operator_chatgpt_free_import_patch.py','utf8');
assert(parentPatch.includes("breederId:window.bigpawProxyId||''"),'existing scoped save must be retained');
assert(freePatch.includes('operator-chatgpt-free-import.js'),'free UI injected after existing UI');
assert(!source.includes('/api/operator/ai-listing-draft'),'free mode must not invoke paid OpenAI');
assert(!source.includes('OPENAI_API_KEY'),'free mode must not request API key');

function el(tagName='INPUT'){
 return {tagName,style:{},value:'',textContent:'',checked:false,options:[],firstChild:{},
 listeners:{},setAttribute(name,value){this[name]=value},addEventListener(event,fn){this.listeners[event]=fn;},
 dispatchEvent(event){this.changeEvent=event;},insertBefore(opt){this.options.unshift(opt)},
 add(opt){this.options.push(opt)},scrollIntoView(){this.didScroll=true}};
}
async function simulate({role='operator',scope='b_miyamoto',verified='b_miyamoto',editId=''}={}){
 const elements={};
 const selectors={
  breed:['','スタンダードプードル','サモエド','グレートピレニーズ'],
  gender:['男の子','女の子'],
  father:['クラージュ','未登録'],mother:['ミルク','未登録'],
  healthStatus:['未登録','未実施','実施済み','実施済み（異常なし）'],
  vaccineStatus:['未登録','未接種','接種済み'],
  microchipStatus:['未登録','未装着','装着済み'],
  geneticTestStatus:['未登録','未実施','実施済み'],
 };
 const keys=['puppyName','breed','gender','color','birth','price','weight','adultMin','adultMax',
    'father','mother','healthStatus','vaccineStatus','microchipStatus','geneticTestStatus','appealPoint','desc'];
 for(const key of keys){
  const node=el(selectors[key]?'SELECT':'INPUT');
  if(selectors[key])node.options=selectors[key].map(s=>({value:s,textContent:s}));
  node.value=key==='price'?'258000':key==='color'?'ブラック':key==='birth'?'2026-07-01':'';
  elements[key]=node;
 }
 const parts={};for(const key of ['bpFreeJson','bpFreeImport','bpFreeFeedback','bpFreeReviewed'])parts[key]=el();
 const panel=el('SECTION');panel.querySelector=(query)=>parts[query.slice(1)];
 const form=el('FORM'),publishButton=el('BUTTON');
 form.querySelector=(q)=>q==='button.btn-wide'?publishButton:null;
 form.insertBefore=(node)=>{if(node.id==='bpFreeListingPanel')form.child=node;else form.publishHint=node;};
 let created=0;const document={createElement:()=>created++===0?panel:el('DIV'),querySelector:q=>q==='form'?form:null,getElementById:id=>elements[id]||null};
 const calls=[];
 elements.photo=el('INPUT');elements.photo.files=[{name:'dog-1.jpg'}];
 const ctx={document,window:{bigpawProxyId:verified},URLSearchParams,Option:function(t,v){this.textContent=t;this.value=v},
   Date,Event:class{constructor(type){this.type=type}},location:{search:scope?'?breederId='+scope:''},
   BigPawAPI:{me:async()=>{calls.push('me');return {role}}},
   editId};
 await vm.runInNewContext(source,ctx,{filename:'operator-chatgpt-free-import.js'});
 return {ctx,form,panel,parts,elements,calls,publishButton};
}
function importData(sim,data){
 sim.parts.bpFreeJson.value=JSON.stringify(data);
 sim.parts.bpFreeImport.listeners.click();
}
function submit(sim){
 const e={preventDefault(){this.prevented=true},stopImmediatePropagation(){this.stopped=true}};
 sim.form.listeners.submit(e);
 return e;
}
(async()=>{
 const data={fields:{name:'ヤンヤン',breed:'サモエド',gender:'男の子',
   color:'ホワイト',birth:'2024-09-04',price:130000,weight:23,
   desc:'元繁殖犬のサモエド。温かい家庭を探しています。',
   appealPoint:'新しい家族を募集中',vaccineStatus:'接種済み'},
   missing:['マイクロチップの有無'],warnings:['価格内訳：12万円＋1万円']};
 let s=await simulate();
 assert.strictEqual(s.panel.id,'bpFreeListingPanel');
 assert.strictEqual(s.calls.length,1,'only sign-in lookup, no AI network');
 importData(s,data);
 assert.strictEqual(s.elements.puppyName.value,'ヤンヤン');
 assert.strictEqual(s.elements.breed.value,'サモエド');
 importData(s,{fields:{breed:'グレート・ピレニーズ',gender:'男の子',birth:'2026-09-07',price:280000,desc:'11月3日からお迎え可能'}});
 assert.strictEqual(s.elements.breed.value,'グレートピレニーズ','middle dot in Great Pyrenees normalized');
 importData(s,data);
 assert.strictEqual(s.elements.gender.value,'男の子');
 assert.strictEqual(s.elements.birth.value,'2024-09-04');
 assert.strictEqual(s.elements.price.value,'130000');
 assert.strictEqual(s.elements.color.value,'ホワイト');
 assert.strictEqual(s.elements.desc.value,data.fields.desc);
 assert.strictEqual(s.elements.appealPoint.value,'新しい家族を募集中');
 assert.strictEqual(s.elements.vaccineStatus.value,'接種済み');
 assert(s.parts.bpFreeFeedback.textContent.includes('マイクロチップ'),'missing info shown');
 assert(s.parts.bpFreeFeedback.textContent.includes('価格内訳'),'warnings shown');
 let e=submit(s);
 assert(e.prevented&&e.stopped,'publish blocked until review');
 // Clicking bottom button must tell mobile Safari users why submission stops.
 let clickEvent={preventDefault(){this.prevented=true},stopImmediatePropagation(){this.stopped=true}};
 s.publishButton.listeners.click(clickEvent);
 assert(clickEvent.prevented&&clickEvent.stopped,'click is blocked before form submission');
 assert(s.form.publishHint.textContent.includes('チェック'),'check explanation shown beside publish button');
 s.parts.bpFreeReviewed.checked=true;
 e=submit(s);
 assert(!e.prevented,'publish allowed after completing review with photo');
 // Missing photos must be stated clearly and block accidental publication.
 s.elements.photo.files=[];
 clickEvent={preventDefault(){this.prevented=true},stopImmediatePropagation(){this.stopped=true}};
 s.publishButton.listeners.click(clickEvent);
 assert(clickEvent.prevented,'photo-less attempted publish is stopped');
 assert(s.form.publishHint.textContent.includes('写真を1枚以上'),'photo explanation shown beside button');
 s.elements.photo.files=[{name:'dog-1.jpg'}];
 e=submit(s);
 assert(!e.prevented,'valid photo and reviewed checkbox allow publishing');
 // Import again with incomplete information: old dog data must not remain.
 importData(s,{fields:{name:'別の子',breed:'サモエド'},missing:['性別','税込価格']});
 assert.strictEqual(s.elements.puppyName.value,'別の子');
 assert.strictEqual(s.elements.price.value,'','previous dog price cleared on reimport');
 assert.strictEqual(s.elements.birth.value,'','previous dog birth cleared on reimport');
 assert.strictEqual(s.elements.gender.value,'','previous dog gender cleared on reimport');
 assert.strictEqual(s.parts.bpFreeReviewed.checked,false,'new import resets review');
 s.parts.bpFreeReviewed.checked=true;
 e=submit(s);
 assert(e.prevented,'incomplete core fields cannot be published');
 // malformed JSON must never mutate prior state
 s.parts.bpFreeJson.value='LINEの文章そのまま';
 s.parts.bpFreeImport.listeners.click();
 assert.strictEqual(s.elements.puppyName.value,'別の子');
 assert(s.parts.bpFreeFeedback.textContent.includes('JSON形式'),'clearly report need for structured data');
 // unknown breed should not be silently set to another breed
 importData(s,{fields:{name:'新しい子',breed:'不明の犬種',gender:'女の子',birth:'2024-09-04',price:100000,
   desc:'テスト'}});
 assert.strictEqual(s.elements.breed.value,'','unknown breed rejected');
 assert(s.parts.bpFreeFeedback.textContent.includes('選択肢'),'unknown choice flagged');
 // ordinary breeder never sees operator-only panel
 s=await simulate({role:'breeder'});
 assert(!s.form.child,'free panel hidden for regular breeder');
 // wrong kennel selection fails closed
 s=await simulate({scope:'b_wrong'});
 importData(s,data);
 assert.strictEqual(s.elements.puppyName.value,'','wrong kennel cannot import');
 assert(s.parts.bpFreeFeedback.textContent.includes('掲載先'),'wrong kennel explicitly warned');
 // no scope fails closed, too
 s=await simulate({scope:''});
 importData(s,data);
 assert.strictEqual(s.elements.puppyName.value,'','no kennel scope cannot import');
 // existing edit operation unaffected
 s=await simulate({editId:'p_existing'});
 assert(!s.form.child,'existing edit page unaffected');
 console.log('CHATGPT_FREE_IMPORT_UI_PASS|consent_free|autofill|scope|review_guard|reimport_clean|invalid_json|unknown_breed|breeder_hidden|edit_unchanged');
})().catch(err=>{console.error(err);process.exit(1)});
