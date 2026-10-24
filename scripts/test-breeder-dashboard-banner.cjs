#!/usr/bin/env node
'use strict';
/* Read-only, rendered breeder dashboard banner tests for Chromium and Safari WebKit.
 * All campaign variants are synthetic and exercised only on a disposable sandbox.
 * Live production checks use real GET /api/campaign/first100, no credentials/writes. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const {execSync}=require('child_process');
const fs=require('fs');
const origin=process.argv[2]||'http://127.0.0.1:18096';
const live=process.env.BIGPAW_DASHBOARD_LIVE_READONLY==='1';
function chromePath(){
 for(const name of ['google-chrome','google-chrome-stable','chromium','chromium-browser']){
  try{const v=execSync('command -v '+name,{encoding:'utf8'}).trim();if(v&&fs.existsSync(v))return v;}catch(_e){}
 }
 throw Error('CHROME_MISSING');
}
async function test(engine,label){
 const browser=await engine.launch({headless:true,...(label==='chromium'?{executablePath:chromePath(),args:['--no-sandbox']}:{})});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:3});
  const page=await context.newPage();
  let role='breeder';
  let scenario={status:'active',eligible:true,remaining:100,limit:100};
  let errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  if(live){
   await page.route('**/*',route=>{
    if(!['GET','HEAD','OPTIONS'].includes(route.request().method())){
     errors.push('production write blocked: '+route.request().url());
     return route.abort();
    }
    return route.continue();
   });
  }
  await page.route('**/api/me',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({role})}));
  if(!live)await page.route('**/api/campaign/first100',r=>scenario==='unavailable'?r.abort():r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(scenario)}));
  const response=await page.goto(origin+'/admin.html?banner-e2e='+label,{waitUntil:'domcontentloaded'});
  assert.equal(response.status(),200,'dashboard HTTP 200');
  const banner=page.locator('#bpBreederDashboardCampaign');
  await banner.waitFor({state:'visible',timeout:25000});
  await page.locator('#bpParentQuick').waitFor({state:'visible',timeout:25000});
  const layout=await page.evaluate(()=>{
    const heading=document.querySelector('.main h1');
    const promo=document.getElementById('bpBreederDashboardCampaign');
    const action=document.getElementById('bpParentQuick');
    const firstAction=action?.querySelector('a[href="breeder-puppy-new.html"]');
    const parentAction=action?.querySelector('a[href="parent-dogs.html"]');
    return {
      headingBeforePromo:!!(heading.compareDocumentPosition(promo)&Node.DOCUMENT_POSITION_FOLLOWING),
      promoImmediatelyBeforeActions:promo.nextElementSibling===action,
      bannerTop:promo.getBoundingClientRect().top,
      actionTop:action.getBoundingClientRect().top,
      firstActionVisible:!!firstAction&&getComputedStyle(firstAction).display!=='none',
      parentActionVisible:!!parentAction&&getComputedStyle(parentAction).display!=='none',
      actionLinks:[...action.querySelectorAll('a')].map(a=>a.getAttribute('href')),
      viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth
    };
  });
  assert.equal(layout.headingBeforePromo,true,'campaign must follow page heading');
  assert.equal(layout.promoImmediatelyBeforeActions,true,'campaign must immediately precede BOTH quick action buttons');
  assert(layout.actionTop>layout.bannerTop,'campaign must be visually above puppy and parent controls');
  assert(layout.firstActionVisible&&layout.parentActionVisible,'both puppy and parent actions must remain visible');
  assert.deepEqual(layout.actionLinks,['breeder-puppy-new.html','parent-dogs.html'],'quick action targets preserved');
  assert(layout.scrollWidth<=layout.viewport+15,'no horizontal overflow on mobile');
  console.log('BREEDER_DASHBOARD_PROMO_FIRST_LAYOUT_OK|'+label+'|'+JSON.stringify(layout));
  if(!live){
    const fiveDayInfo=await page.evaluate(()=>{
      const ts=Math.floor(Date.now()/1000);
      const shared={breed:'スタンダードプードル',color:'ブラック',gender:'男の子',status:'募集中',reviewStatus:'approved',price:300000,createdAt:ts-10*86400};
      dogs=[
        {...shared,id:'old-rank',name:'6日前に上位表示',rankAt:ts-6*86400,imageUrl:''},
        {...shared,id:'new-rank',name:'3日前に上位表示',rankAt:ts-3*86400,imageUrl:''}
      ];
      engagementReady=false;render();
      return {
        ready:document.querySelectorAll('.bp-rank-status[data-ready="yes"]').length,
        waiting:document.querySelectorAll('.bp-rank-status[data-ready="no"]').length,
        allText:document.getElementById('dogList').innerText,
        width:document.documentElement.scrollWidth,
        viewport:innerWidth
      };
    });
    assert.equal(fiveDayInfo.ready,1,'only the aged puppy is eligible to return to the top');
    assert.equal(fiveDayInfo.waiting,1,'recent puppy shows a remaining-day countdown');
    assert(fiveDayInfo.allText.includes('上位表示できます！')&&fiveDayInfo.allText.includes('あと2日で上位表示できます'),'both visible breeder update notices must render');
    assert(fiveDayInfo.allText.includes('現在1頭が更新可能です')&&fiveDayInfo.allText.includes('前回の上位表示'),'top eligible-count summary and last date render');
    assert.equal(await page.locator('button').filter({hasText:'掲載順位を更新'}).count(),0,'no extra ranking button');
    assert(fiveDayInfo.width<=fiveDayInfo.viewport+15,'rank messages must not overflow mobile layout');
    console.log('BREEDER_FIVE_DAY_RANK_NOTICE_RENDERED_OK|'+label+'|1_ready|1_countdown|last_rank_date|no_rank_button');
  }
  assert.equal(await page.locator('.bp-first-sale-benefit').count(),0,'legacy notice cannot duplicate banner');
  const initial=await page.evaluate(()=>{
   const e=document.querySelector('#bpBreederDashboardCampaign'),s=getComputedStyle(e);
   return {bg:s.backgroundImage,display:s.display,count:document.querySelector('#bpBreederDashboardCampaignCount').textContent,
     url:e.getAttribute('href'),width:document.documentElement.scrollWidth,viewport:innerWidth,
     visible:!e.hidden};
  });
  assert(initial.visible&&initial.display!=='none','dashboard orange must be rendered');
  assert(/255, 244, 189|255, 223, 140/.test(initial.bg),'gold CSS expected '+initial.bg);
  assert(initial.url.includes('breeder-fees.html?v=20261024-fresh-e2e4'),'fresh fee target expected');
  assert(initial.width<=initial.viewport+15,'dashboard must fit iPhone');
  assert(/残り(100|\d+)頭・受付中|残りわずか・受付中/.test(initial.count),'counter must show approved campaign count');
  console.log('DASHBOARD_GOLD_VISIBLE_OK|'+label+'|'+JSON.stringify(initial));
  if(!live){
   async function next(data,expectedText){
    scenario=data;
    const reply=data==='unavailable' ? page.waitForRequest(x=>x.url().includes('/api/campaign/first100')) : page.waitForResponse(x=>x.url().includes('/api/campaign/first100'));
    await page.evaluate(()=>document.dispatchEvent(new Event('bigpaw:campaign-refresh')));
    await reply;
    if(expectedText){
      await page.waitForFunction(s=>document.querySelector('#bpBreederDashboardCampaignCount')?.textContent===s,expectedText);
      assert.equal(await banner.isVisible(),true,'active campaign must remain visible');
    }else{
      await banner.waitFor({state:'hidden'});
      assert.equal(await page.locator('#bpParentQuick').isVisible(),true,'quick actions remain visible after campaign closes');
      assert.equal(await page.locator('#bpBreederDashboardCampaignCount').textContent(),'','never display stale slots');
    }
   }
   await next({status:'active',eligible:true,remaining:21,limit:100},'残り21頭・受付中！');
   await next({status:'active',eligible:true,remaining:20,limit:100},'残りわずか・受付中！');
   await next({status:'active',eligible:true,remaining:1,limit:100},'残りわずか・受付中！');
   for(const state of ['sold_out','ended','inactive']){
     await next({status:state,eligible:false,remaining:0,limit:100},null);
   }
   await next('unavailable',null);
   await next({status:'active',eligible:true,remaining:99,limit:100},'残り99頭・受付中！');
   await page.evaluate(()=>window.BigPawBreederDashboardCampaign.updateForRole('operator'));
   await banner.waitFor({state:'hidden'});
   await page.evaluate(()=>window.BigPawBreederDashboardCampaign.updateForRole('buyer'));
   await banner.waitFor({state:'hidden'});
   await page.evaluate(()=>window.BigPawBreederDashboardCampaign.updateForRole(null));
   await banner.waitFor({state:'hidden'});
   console.log('DASHBOARD_QUOTA_STATES_AND_ROLE_GATES_OK|'+label+'|21|20|1|sold_out|ended|inactive|network_fail|operator|buyer|anonymous');
   await page.evaluate(()=>window.BigPawBreederDashboardCampaign.updateForRole('breeder'));
   await banner.waitFor({state:'visible'});
  }
  await Promise.all([page.waitForURL('**/breeder-fees.html*'),banner.click()]);
  await page.locator('#bpBreederCampaign').waitFor({state:'visible',timeout:25000});
  assert.equal(await page.locator('#bpBreederStandardHero').isVisible(),false,'regular 5% hero hidden');
  assert.equal(errors.length,0,'unexpected JS errors '+errors.join(';'));
  console.log('DASHBOARD_CAMPAIGN_TAP_THROUGH_OK|'+label+'|'+page.url());
  await context.close();
 }finally{await browser.close();}
}
(async()=>{
 const health=await fetch(origin+'/api/health').then(r=>r.json());
 if(live){
  assert.equal(new URL(origin).origin,'https://bigpaw.site','production smoke is pinned to BIG PAW');
  assert.notEqual(health.environment,'development','production must be live');
 }else{
  assert.equal(health.environment,'development','dashboard tests must use disposable development only');
  assert.equal(health.mailConfigured,false,'no live mail from test');
  assert.equal(health.paymentMode,'demo','no live payments from test');
 }
 await test(chromium,'chromium');
 if(process.env.BIGPAW_TEST_WEBKIT==='1')await test(webkit,'webkit');
 console.log('BREEDER_DASHBOARD_CAMPAIGN_E2E_OK|mobile|roles|quota|expires|click|chrome'+(process.env.BIGPAW_TEST_WEBKIT==='1'?'_and_webkit':''));
})().catch(e=>{console.error(e);process.exitCode=1});
