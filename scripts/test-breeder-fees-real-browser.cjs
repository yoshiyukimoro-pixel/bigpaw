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
  assert(src.includes('v=20261024-breeder-pricing-e2e3'),label+' must load new cache-busted actual menu script, got '+src);
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible',timeout:25000});
  await page.locator('#bp-global-mobile-menu-button').click();
  const feeLink=page.locator('#bp-global-mobile-menu-drawer a').filter({hasText:'料金・手数料'}).first();
  assert.equal(await feeLink.isVisible(),true,label+' breeder fee menu item visible');
  const href=await feeLink.getAttribute('href');
  assert(href.includes('/breeder-fees.html?v=20261024-gold'),label+' correct cache-busted target '+href);
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
