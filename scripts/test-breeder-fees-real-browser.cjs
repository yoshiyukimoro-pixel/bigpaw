#!/usr/bin/env node
'use strict';
/* Real browser clicks through the actual mobile breeder menu and evaluates
 * the visible campaign, not mere HTML or href substring checks. Test DB only.
 */
const assert=require('node:assert/strict');
const { chromium, webkit }=require('playwright');
const { execSync }=require('child_process');
const fs=require('fs');
function installedChrome(){
 if(process.env.BIGPAW_CHROME_BIN)return process.env.BIGPAW_CHROME_BIN;
 for(const command of ['google-chrome','google-chrome-stable','chromium','chromium-browser']){
  try{const p=execSync('command -v '+command,{encoding:'utf8'}).trim();if(p&&fs.existsSync(p))return p;}catch(_e){}
 }
 throw Error('GITHUB_RUNNER_CHROME_NOT_FOUND');
}
const origin=process.argv[2]||'http://127.0.0.1:18096';
const liveReadOnly=process.env.BIGPAW_LIVE_READONLY==='1';
const requireFresh=process.env.BIGPAW_EXPECT_LIVE_FRESH==='1' || !liveReadOnly;

async function test(engine,label){
 const browser=await engine.launch({headless:true,...(label.includes('chromium')?{executablePath:installedChrome(),args:['--no-sandbox']}: {})});
 try {
  const ctx=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
  const page=await ctx.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  if(liveReadOnly){
   // Public production smoke: never send writes, no real session or credentials.
   await page.route('**/*',route=>{
    const method=route.request().method();
    if(!['GET','HEAD','OPTIONS'].includes(method)){
     errors.push('Blocked unexpected live write: '+method+' '+route.request().url());
     return route.abort();
    }
    return route.continue();
   });
  }
  // Synthetic breeder role only tests public HTML/menu rendering; not actual login.
  await page.route('**/api/me',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({role:'breeder'})}));
  let status=await page.goto(origin+'/admin.html?pricing-e2e='+label,{waitUntil:'domcontentloaded'});
  assert.equal(status.status(),200,label+' dashboard response');
  const src=await page.locator('script[src*="/mobile-global-nav.js"]').getAttribute('src');
  assert((requireFresh ? /v=20261024-breeder-signup-blue1/ : /v=20261024-(?:breeder-pricing-e2e[34]|breeder-signup-blue1)/).test(src),label+' must load the appropriate cache-busted menu, got '+src);
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible',timeout:25000});
  await page.locator('#bp-global-mobile-menu-button').click();
  const feeLink=page.locator('#bp-global-mobile-menu-drawer a').filter({hasText:'料金・手数料'}).first();
  assert.equal(await feeLink.isVisible(),true,label+' breeder fee menu item visible');
  const href=await feeLink.getAttribute('href');
  assert(requireFresh ? href.includes('/breeder-fees.html?v=20261024-fresh-e2e4') : /\/breeder-fees\.html\?v=20261024-(gold|fresh-e2e4)/.test(href),label+' correct cache-busted target '+href);
  await Promise.all([page.waitForURL('**/breeder-fees.html*',{timeout:25000}),feeLink.click()]);
  await page.waitForFunction(()=>{
   const banner=document.querySelector('#bpBreederCampaign');
   return banner&&!banner.hidden&&!!document.querySelector('#bpBreederCampaignCount')?.textContent;
  },null,{timeout:25000});
  const result=await page.evaluate(()=>{
   const banner=document.getElementById('bpBreederCampaign');
   const hero=document.getElementById('bpBreederStandardHero');
   const card=document.getElementById('bpBreederRegularCalculator');
   const style=getComputedStyle(banner);
   return {
    url:location.href,
    title:document.title,
    bannerHidden:banner.hidden,
    bannerDisplay:style.display,
    bannerBackground:style.backgroundImage,
    bannerBorder:style.borderTopColor,
    heading:banner.querySelector('h1')?.textContent,
    count:document.getElementById('bpBreederCampaignCount')?.textContent,
    heroHidden:hero.hidden,
    heroDisplay:getComputedStyle(hero).display,
    calculatorHidden:card.hidden,
    billingText:document.getElementById('bpBreederStandardFee')?.textContent,
    bodyWidth:document.documentElement.scrollWidth,
    viewport:innerWidth
   };
  });
  assert.equal(result.bannerHidden,false,label+' campaign must be visible');
  assert.notEqual(result.bannerDisplay,'none',label+' banner CSS actually rendered');
  assert(/255, 244, 189|255, 223, 140/.test(result.bannerBackground),label+' golden gradient actually computed: '+result.bannerBackground);
  assert.equal(result.heroHidden,true,label+' old 5% hero hidden');
  assert.equal(result.heroDisplay,'none',label+' 5% hero computed display none');
  assert.equal(result.calculatorHidden,true,label+' outdated calculator hidden');
  assert.equal(result.billingText,'0円（先着100頭対象）',label+' banner matches fee details');
  assert(/残り(100|\d+)頭・受付中|残りわずか・受付中/.test(result.count),label+' remaining visible '+result.count);
  assert(result.bodyWidth<=result.viewport+15,label+' no mobile overflow');
  assert(!errors.length,label+' JS page errors: '+errors.join(';'));
  console.log('REAL_MOBILE_MENU_CLICK_GOLD_OK|'+label+'|'+JSON.stringify(result));
  // A breeder who taps orange「適用条件を見る」must see the CURRENT 100-head
  // agreement, not an outdated normal-5%-only draft.
  if(!liveReadOnly||requireFresh){
  const termsLink=page.locator('#bpBreederCampaign a').filter({hasText:'適用条件を見る'}).first();
  assert((await termsLink.getAttribute('href')).includes('breeder-fee-agreement.html?v=20261024-terms-orange2'),
    label+' campaign conditions must open fresh agreement');
  await Promise.all([page.waitForURL('**/breeder-fee-agreement.html*',{timeout:25000}),termsLink.click()]);
  const termsStatus=page.locator('#bpFeeTermsCampaignStatus');
  await page.waitForFunction(()=>{
    const e=document.getElementById('bpFeeTermsCampaignStatus');
    return e&&e.dataset.state==='active'&&/受付中！/.test(e.textContent);
  },null,{timeout:25000});
  const terms=await page.evaluate(()=>{
    const banner=document.getElementById('bpFeeTermsCampaign');
    const state=document.getElementById('bpFeeTermsCampaignStatus');
    const computed=getComputedStyle(banner);
    const statusStyle=getComputedStyle(state);
    return {
      title:document.title,
      status:state.textContent,
      state:state.dataset.state,
      gold:computed.backgroundImage,
      statusBackground:statusStyle.backgroundColor,
      statusColor:statusStyle.color,
      statusBorder:statusStyle.borderTopColor,
      body:document.body.innerText,
      mobileWidth:document.documentElement.scrollWidth,
      viewport:innerWidth
    };
  });
  assert(terms.title.includes('先着100頭キャンペーン'),label+' agreement page title');
  assert(terms.body.includes('1. 先着100頭キャンペーンの適用条件'),label+' campaign terms first');
  assert(terms.body.includes('対象外の成約は通常5％'),label+' 5% is explicitly for non-eligible sales only');
  assert(terms.body.includes('キャンペーン適用時3％'),label+' featured 3% is disclosed');
  assert(!terms.body.includes('公開前ドラフト'),label+' old launch draft removed');
  assert(!terms.body.includes('初回成約でも合計8％'),label+' obsolete first-sale statement removed');
  assert(/255, 244, 189|255, 223, 140/.test(terms.gold),label+' agreement conditions visible in gold');
  assert.equal(terms.statusBackground,'rgb(255, 250, 241)',label+' remaining heads must have WARM ivory background, not blue');
  assert.equal(terms.statusColor,'rgb(167, 56, 9)',label+' remaining heads must use ORANGE text, not breeder blue');
  assert.equal(terms.statusBorder,'rgb(232, 161, 42)',label+' remaining heads must use orange border');
  assert(/残り(?:100|\d+)頭・受付中！|残りわずか・受付中！/.test(terms.status),label+' live quota status');
  assert(terms.mobileWidth<=terms.viewport+15,label+' agreement no horizontal iPhone overflow');
  console.log('REAL_FEE_CAMPAIGN_TERMS_ORANGE_STATUS_OK|'+label+'|'+JSON.stringify({status:terms.status,title:terms.title}));
  await page.goBack({waitUntil:'domcontentloaded'});
  await page.locator('#bpBreederCampaign').waitFor({state:'visible',timeout:25000});
  }
  await page.goBack({waitUntil:'domcontentloaded'});
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible'});
  await page.locator('#bp-global-mobile-menu-button').click();
  await Promise.all([page.waitForURL('**/breeder-fees.html*'),page.locator('#bp-global-mobile-menu-drawer a').filter({hasText:'料金・手数料'}).first().click()]);
  await page.waitForFunction(()=>document.getElementById('bpBreederCampaign')?.hidden===false);
  console.log('REAL_MOBILE_MENU_BACK_FORWARD_OK|'+label);
  await ctx.close();
 } finally {await browser.close();}
}

(async()=>{
 const health=await fetch(origin+'/api/health').then(r=>r.json());
 if(liveReadOnly){
  assert.equal(new URL(origin).origin,'https://bigpaw.site','live smoke is limited to known production host');
  assert.notEqual(health.environment,'development','production smoke must not target development');
  console.log('PRODUCTION_READ_ONLY_SMOKE|no credentials|synthetic menu role|HTTP writes blocked');
 }else{
  assert.equal(health.environment,'development','must run only against disposable development SQLite and no production data');
  assert.equal(health.mailConfigured,false,'must not send mail');
  assert.equal(health.paymentMode,'demo','must not process payments');
 }
 const data=await fetch(origin+'/api/campaign/first100').then(r=>r.json());
 assert.equal(data.status,'active','campaign must be active to verify banner on this run');
 assert.equal(data.eligible,true,'campaign must be eligible to verify banner');
 await test(chromium,'chromium-ios-viewport');
 if(process.env.BIGPAW_TEST_WEBKIT==='1')await test(webkit,'webkit-ios-engine');
 console.log('BREEDER_CAMPAIGN_REAL_BROWSER_E2E_OK|actual_menu_tap|actual_computed_orange|5_percent_hidden|browser_back_and_forth|chrome'+(process.env.BIGPAW_TEST_WEBKIT==='1'?'_plus_webkit':''));
})().catch(e=>{console.error(e);process.exitCode=1});
