#!/usr/bin/env node
'use strict';
/** Simulates the operator form's AI assistant without browser/network dependencies. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync('app/assets/operator-ai-listing.js','utf8');
const buildElement=(tagName='INPUT')=>({
 tagName,value:'',style:{},files:[],options:[],listeners:{},textContent:'',
 addEventListener(type,fn){this.listeners[type]=fn},
 dispatchEvent(ev){if(this.listeners[ev.type])this.listeners[ev.type](ev)},
 add(option){this.options.push(option)},
});
async function run({role='operator',scope='b_miyamoto',apiResponse,apiError}={}){
 const ids={};
 for(const key of ['puppyName','breed','gender','color','birth','price','weight','adultMin','adultMax',
 'father','mother','desc','healthStatus','vaccineStatus','microchipStatus','geneticTestStatus']){
  ids[key]=buildElement(['breed','gender','father','mother','healthStatus','vaccineStatus',
   'microchipStatus','geneticTestStatus'].includes(key)?'SELECT':'INPUT');
 }
 const option=(value)=>({value,textContent:value});
 ids.breed.options=[option('スタンダードプードル'),option('サモエド')];
 ids.gender.options=[option('男の子'),option('女の子')];
 for(const k of ['father','mother'])ids[k].options=[option('未登録')];
 for(const k of ['healthStatus'])ids[k].options=[option('未登録'),option('実施済み')];
 for(const k of ['vaccineStatus'])ids[k].options=[option('未登録'),option('接種済み')];
 for(const k of ['microchipStatus'])ids[k].options=[option('未登録'),option('装着済み')];
 for(const k of ['geneticTestStatus'])ids[k].options=[option('未登録'),option('実施済み')];
 ids.photo=buildElement('INPUT');ids.photo.files=[{name:'dog.jpg'}];
 const controls={};
 for(const name of ['bpAiSource','bpAiConsent','bpAiFeedback','bpAiGenerate','bpAiPhotoCount','bpAiImport','bpAiJson']){
  controls[name]=buildElement();
 }
 const panel={id:'',style:{},innerHTML:'',querySelector(s){return controls[s.slice(1)]}};
 const form={firstChild:{},querySelector(){return {className:'stepbar'}},insertBefore(node){this.child=node}};
 const document={
  createElement(){return panel},
  querySelector(s){return s==='form'?form:null},
  getElementById(s){return ids[s]||null},
 };
 let called=0;
 const ctx={
  document,location:{search:scope?'?breederId='+scope:''},URLSearchParams,
  Event:class{constructor(type){this.type=type}},
  Option:class{constructor(label,value){this.value=value;this.textContent=label}},
  queueMicrotask(fn){fn()},
  window:{},
  BigPawAPI:{
   me:async()=>({role}),
   request:async()=>{called++;if(apiError)throw apiError;return apiResponse||{fields:{name:'ヤンヤン'}}}
  }
 };
 await vm.runInNewContext(script,ctx,{filename:'operator-ai-listing.js'});
 return {ctx,controls,ids,form,get called(){return called}};
}
(async()=>{
 const a=await run({apiResponse:{fields:{
  name:'ヤンヤン',breed:'サモエド',gender:'男の子',birth:'2024-09-04',
  price:130000,weight:23,healthStatus:'実施済み',desc:'引退犬として家族を募集'
 },missing:['父犬情報'],warnings:['金額内訳を再確認']}});
 assert(a.form.child&&a.form.child.id==='bpAiListingPanel','AI panel attached to operator form');
 assert(a.controls.bpAiPhotoCount.textContent.includes('1枚'),'photo count reads uploaded input');
 a.controls.bpAiSource.value='サモエドのヤンヤンくん。2024年9月4日生まれ、2歳。';
 await a.controls.bpAiGenerate.listeners.click();
 assert.strictEqual(a.called,0,'no model submission without consent');
 assert(a.controls.bpAiFeedback.textContent.includes('同意'),'explicit consent explained');
 a.controls.bpAiConsent.checked=true;
 await a.controls.bpAiGenerate.listeners.click();
 assert.strictEqual(a.called,1,'consented model request is sent once');
 assert.strictEqual(a.ids.puppyName.value,'ヤンヤン');
 assert.strictEqual(a.ids.breed.value,'サモエド');
 assert.strictEqual(a.ids.price.value,'130000');
 assert(a.controls.bpAiFeedback.textContent.includes('父犬情報'),'missing information visible');
 assert(a.controls.bpAiFeedback.textContent.includes('金額内訳'),'model warning visible');
 const b=await run();
 b.controls.bpAiJson.value=JSON.stringify({fields:{name:'ヤンヤン',breed:'サモエド',price:130000}});
 b.controls.bpAiImport.listeners.click();
 assert.strictEqual(b.ids.puppyName.value,'ヤンヤン');
 assert.strictEqual(b.called,0,'JSON paste import never calls OpenAI');
 const c=await run({scope:''});
 c.controls.bpAiConsent.checked=true;
 c.controls.bpAiSource.value='サモエドのヤンヤンくん。2024年9月4日生まれ、2歳。';
 await c.controls.bpAiGenerate.listeners.click();
 assert.strictEqual(c.called,0,'no AI request without kennel scope');
 const d=await run({role:'breeder'});
 assert(!d.form.child,'AI panel hidden for ordinary breeder');
 const e=await run({apiError:{data:{error:'ai_not_configured'}}});
 e.controls.bpAiConsent.checked=true;
 e.controls.bpAiSource.value='サモエドのヤンヤンくん。2024年9月4日生まれ、2歳。';
 await e.controls.bpAiGenerate.listeners.click();
 assert(e.controls.bpAiFeedback.textContent.includes('APIキーが未設定'),'missing key safely reported');
 console.log('OPERATOR_AI_UI_BEHAVIOR_OK|consent|source|import|unknown|scoped|breeder_hidden|no_key');
})().catch(e=>{console.error(e);process.exit(1)});
