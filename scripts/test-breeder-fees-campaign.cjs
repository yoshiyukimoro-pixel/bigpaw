#!/usr/bin/env node
'use strict';
const fs=require('fs');
const assert=require('assert').strict;
const path=require('path');
const vm=require('vm');
const root=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(root,'app/breeder-fees.html'),'utf8');
const code=fs.readFileSync(path.join(root,'app/assets/breeder-fees-campaign.js'),'utf8');

for(const id of ['bpBreederStandardHero','bpBreederCampaign','bpBreederCampaignCount','bpBreederCampaignEnd','bpBreederRegularCalculator','bpBreederStandardFee','bpBreederFeeDescription','bpBreederFinalStepTitle','bpBreederFinalStepDescription']){
  assert(html.includes('id="'+id+'"'),'missing UI element '+id);
}
assert(html.includes('id="bpBreederStandardHero" hidden'),'normal headline is initially hidden to prevent flash');
assert(html.includes('id="bpBreederRegularCalculator" hidden'),'regular 5% calculator starts hidden to prevent flash');
assert(html.includes('id="bpBreederCampaign" hidden'),'campaign starts hidden until API verifies eligibility');
assert(html.includes('assets/breeder-fees-campaign.js')&&!html.includes('src="assets/first100-campaign.js"'),'dedicated breeder-only controller');
assert(html.includes('background:linear-gradient(125deg,#fff4bd')&&!html.includes('#bpBreederCampaign{background:#edf7ff'),'gold orange scope, not faint blue');
assert(html.includes('キャンペーン')&&html.includes('5％が無料！'),'strong offer headline');

const ids=['bpBreederStandardHero','bpBreederCampaign','bpBreederCampaignCount','bpBreederCampaignEnd','bpBreederRegularCalculator','bpBreederStandardFee','bpBreederFeeDescription','bpBreederFinalStepTitle','bpBreederFinalStepDescription'];
const elements=()=>Object.fromEntries(ids.map(x=>[x,{hidden:x==='bpBreederStandardHero'||x==='bpBreederRegularCalculator'||x==='bpBreederCampaign',textContent:''}]));
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function verify(name,result,expects,error=false){
  const e=elements();const handlers={};const warnings=[];
  const fetch=async url=>{
    assert.equal(url,'/api/campaign/first100');
    if(error)throw Error('network-failure');
    return {ok:true,json:async()=>result};
  };
  const sandbox={
    document:{getElementById:id=>e[id]||null,addEventListener:(name,cb)=>{handlers[name]=cb;}},
    fetch,Intl,Date,Number,Error,
    console:{warn:(...args)=>warnings.push(args)},
  };
  vm.runInNewContext(code,sandbox,{filename:'breeder-fees-campaign.js'});
  await flush();await flush();
  assert.equal(e.bpBreederStandardHero.hidden,expects.heroHidden,name+' hero state');
  assert.equal(e.bpBreederCampaign.hidden,expects.bannerHidden,name+' banner state');
  assert.equal(e.bpBreederRegularCalculator.hidden,expects.calcHidden,name+' calc state');
  assert.equal(e.bpBreederStandardFee.textContent,expects.fee,name+' fee text');
  assert.equal(e.bpBreederFinalStepTitle.textContent,expects.stepTitle,name+' workflow fee title');
  if(expects.count)assert.equal(e.bpBreederCampaignCount.textContent,expects.count,name+' quota text');
  if(error)assert.equal(warnings.length,1,name+' fails closed');
  assert.equal(typeof handlers['bigpaw:campaign-refresh'],'function',name+' supports refresh');
  console.log('PASS',name);
}
const active={status:'active',eligible:true,remaining:100,limit:100,endsAt:1808525678};
const camp={heroHidden:true,bannerHidden:false,calcHidden:true,fee:'0円（先着100頭対象）',stepTitle:'無料対象なら通常手数料0円'};
const regular={heroHidden:false,bannerHidden:true,calcHidden:false,fee:'5%（税込）',stepTitle:'確認後5%を請求'};
(async()=>{
 await verify('100 remaining displays remaining 100',active,{...camp,count:'残り100頭・受付中！'});
 await verify('21 remaining shows exact number',{...active,remaining:21},{...camp,count:'残り21頭・受付中！'});
 await verify('20 remaining hides precise number',{...active,remaining:20},{...camp,count:'残りわずか・受付中！'});
 await verify('1 remaining hides precise number',{...active,remaining:1},{...camp,count:'残りわずか・受付中！'});
 await verify('0 sold out restores standard header and fee',{status:'sold_out',eligible:false,remaining:null},regular);
 await verify('six months ended restores standard header and fee',{status:'ended',eligible:false},regular);
 await verify('disabled campaign restores standard pricing',{status:'inactive',eligible:false},regular);
 await verify('invalid eligibility is never advertised as free',{status:'active',eligible:false,remaining:1},regular);
 await verify('network failure fails closed',null,regular,true);
 console.log('BREEDER_FEES_CAMPAIGN_PRESENTATION_GATE_OK|gold_orange|active_header_hidden|quota_20_hidden|soldout_restores_5_percent|error_safe|breeder_only');
})().catch(e=>{console.error(e);process.exitCode=1});
