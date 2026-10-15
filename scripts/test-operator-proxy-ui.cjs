#!/usr/bin/env node
'use strict';
const assert=require('assert');
const fs=require('fs');
const vm=require('vm');
const script=fs.readFileSync('app/assets/operator-proxy-listing.js','utf8');
const patch=fs.readFileSync('app/backend/operator_proxy_listing_ui_patch.py','utf8');
assert(patch.includes("breederId:window.bigpawProxyId||''"),
  'form must submit the verified breeder ID');
async function scenario({role='operator',scope='b_miyamoto',status='approved'}={}){
  const submit={disabled:false};
  const notice={style:{},textContent:''};
  const form={firstChild:{},insertBefore(node){this.notice=node;},querySelector(){return submit}};
  const heading={textContent:'子犬を掲載'};
  const controls=new Map();
  for(const id of ['breed','father','mother','color','birth','price','weight','adultMin','adultMax','desc','puppyName']){
    controls.set(id,{value:'DOG44',checked:true,
      replaceChildren(...args){this.children=args;},
      insertBefore(o){this.option=o;}});
  }
  const document={
    createElement(){return notice;},
    querySelector(selector){return selector==='form'?form:selector==='h1'?heading:null;},
    getElementById(id){return controls.get(id)||null;},
    querySelectorAll(){return [{checked:true}]}
  };
  const ctx={
    window:{},document,editId:'',
    URLSearchParams,Option:function(label,value){return {label,value}},
    location:{search:scope?'?breederId='+encodeURIComponent(scope):''},
    BigPawAPI:{
      me:async()=>({role}),
      request:async()=>({id:scope,kennel_name:'宮本犬舎',prefecture:'千葉県',review_status:status})
    }
  };
  await vm.runInNewContext(script,ctx,{filename:'operator-proxy-listing.js'});
  return {ctx,submit,heading,form,controls};
}
(async()=>{
  let r=await scenario();
  assert.equal(r.ctx.window.bigpawProxyId,'b_miyamoto','approved operator selection saved for POST');
  assert.equal(r.submit.disabled,false,'approved operator can submit');
  assert(r.form.notice.textContent.includes('宮本犬舎'),'selected kennel shown');
  assert.equal(r.controls.get('price').value,'','DOG44 default removed');
  assert.equal(r.controls.get('father').children[0].label,'未登録','DOG44 parents removed');
  r=await scenario({scope:''});
  assert.equal(r.submit.disabled,true,'missing operator selection blocks form');
  assert(!r.ctx.window.bigpawProxyId,'missing selection never sets breeder ID');
  r=await scenario({status:'pending'});
  assert.equal(r.submit.disabled,true,'unapproved selection blocks form');
  assert(!r.ctx.window.bigpawProxyId,'unapproved breeder ID never set');
  r=await scenario({role:'breeder'});
  assert.equal(r.submit.disabled,false,'regular breeder flow unaffected');
  assert(!r.ctx.window.bigpawProxyId,'normal breeder does not impersonate operator');
  console.log('OPERATOR_PROXY_BROWSER_SCOPE_OK|selected|missing|unapproved|regular_breeder');
})().catch(err=>{console.error(err);process.exit(1)});
