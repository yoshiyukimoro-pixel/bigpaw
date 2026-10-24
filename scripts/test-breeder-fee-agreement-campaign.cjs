#!/usr/bin/env node
'use strict';
/* A terms/marketing consistency gate using a simulated public read-only campaign API.
   No database writes, no fake quotas on production. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const dir=path.join(__dirname,'../app');
const html=fs.readFileSync(path.join(dir,'breeder-fee-agreement.html'),'utf8');
const terms=fs.readFileSync(path.join(dir,'terms.html'),'utf8');
const fees=fs.readFileSync(path.join(dir,'breeder-fees.html'),'utf8');
const register=fs.readFileSync(path.join(dir,'breeder-register.html'),'utf8');
const js=fs.readFileSync(path.join(dir,'assets/breeder-fee-agreement-campaign.js'),'utf8');
const expect=(text,fragment,label)=>assert(text.includes(fragment),label+' '+fragment);
expect(html,'body.bp-account-page #bpFeeTermsCampaign .status{','campaign quota status must beat global blue breeder theme');
expect(html,'background:#fffaf1','campaign quota warm ivory background');
expect(html,'color:#a73809','campaign quota orange foreground');
expect(html,'border:2px solid #e8a12a','campaign quota orange border');
for(const id of ['bpFeeTermsCampaign','bpFeeTermsCampaignTitle','bpFeeTermsCampaignStatus','bpFeeTermsCampaignPeriod']){
  expect(html,'id="'+id+'"','terms banner');
}
for(const phrase of [
  '成約手数料5％ → 0％','1. 先着100頭キャンペーンの適用条件',
  '犬舎ごとの頭数制限はありません','成約申請が受け付けられた時点で1頭分の枠を消費',
  'キャンセル・成約中止になっても枠は戻りません','開始から<b>6か月間</b>',
  '対象外の成約は通常5％','キャンペーン対象外の場合',
  '「推しワン」は追加3％','キャンペーン適用時3％','合計8％',
  '7日以内','ブリーダーの犬舎ページと子犬掲載'
])expect(html,phrase,'applicability');
assert(!html.includes('公開前ドラフト')&&!html.includes('正式公開時'), 'remove old unfinished draft');
assert(!html.includes('初回成約でも合計8％'),'no misleading obsolete per-kennel first case');
assert(!terms.includes('初回成約手数料無料の特典')&&!terms.includes('ブリーダーごとに、特典開始後の最初'),'obsolete free first-sale terms must be removed');
expect(terms,'BIG PAW先着100頭・成約手数料無料キャンペーン','site terms');
expect(terms,'犬舎ごとの上限はありません','global scope');
expect(register,'data-bp-first100 hidden','registration live promo placeholder');
expect(register,'body .breeder-signup-promo .bp-first100[data-state="active"]','signup promo orange css');
assert.equal((register.match(/data-bp-first100 hidden/g)||[]).length,1,'registration must show only one campaign banner');
assert(!register.includes('先着100頭は成約手数料5％ → 0％！</h2>'),'remove duplicate static signup offer');
expect(register,'通常5％の成約手数料（キャンペーン対象取引は免除）','registration checkbox');
expect(fees,'href="breeder-fee-agreement.html?v=20261024-terms-orange2"','fee page click');
expect(register,'href="breeder-fee-agreement.html?v=20261024-terms-orange2"','registration agreement link');
assert(!fs.readFileSync(path.join(dir,'index.html'),'utf8').includes('20261024-terms-orange2'),'buyer homepage not touched');

const flush=()=>new Promise(r=>setImmediate(r));
async function test(name,response,expectedState,expectedText,isError=false){
 const els={
  bpFeeTermsCampaignStatus:{textContent:'',dataset:{}},
  bpFeeTermsCampaignPeriod:{textContent:''}
 };
 const handlers={};
 const fakeFetch=async url=>{
  assert.equal(url,'/api/campaign/first100');
  if(isError)throw Error('network blocked');
  return {ok:true,json:async()=>response};
 };
 const sandbox={document:{getElementById:id=>els[id]||null,addEventListener:(name,cb)=>{handlers[name]=cb},hidden:false},fetch:fakeFetch,Date,Intl,Number,Error,console:{warn:()=>{}}};
 vm.runInNewContext(js,sandbox,{filename:'breeder-fee-agreement-campaign.js'});
 await flush();await flush();
 const stat=els.bpFeeTermsCampaignStatus;
 assert.equal(stat.dataset.state,expectedState,name+' state');
 assert.equal(stat.textContent,expectedText,name+' text');
 assert.equal(typeof handlers['bigpaw:campaign-refresh'],'function','refresh handler available');
 console.log('PASS terms banner',name,stat.textContent);
}
(async()=>{
 const active={status:'active',eligible:true,remaining:100,endsAt:1808500000};
 await test('100 available',active,'active','残り100頭・受付中！');
 await test('21 exact',{...active,remaining:21},'active','残り21頭・受付中！');
 await test('20 private',{...active,remaining:null},'active','残りわずか・受付中！');
 await test('1 private',{...active,remaining:null},'active','残りわずか・受付中！');
 await test('sold out',{status:'sold_out',eligible:false,endsAt:1808500000},'sold_out','先着100頭に達したため新規受付終了');
 await test('ended',{status:'ended',eligible:false,endsAt:1808500000},'ended','キャンペーン期間が終了しました');
 await test('inactive',{status:'inactive',eligible:false},'inactive','現在、キャンペーンの新規受付はありません');
 await test('upcoming',{status:'upcoming',eligible:false,endsAt:1808500000},'upcoming','キャンペーン開始前です');
 await test('network failure',null,'unavailable','現在の受付状況を確認できません',true);
 console.log('BREEDER_FEE_AGREEMENT_CAMPAIGN_GATE_OK|terms_current|site_terms_current|registration_consistency|live_quota|expiry|no_draft|buyer_untouched');
})().catch(e=>{console.error(e);process.exitCode=1});