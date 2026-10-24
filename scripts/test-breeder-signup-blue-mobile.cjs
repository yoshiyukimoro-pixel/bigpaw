#!/usr/bin/env node
'use strict';
/* Public home -> breeder application: ensure menu is blue before signup.
 * Keeps guest/buyer permission based on session, never forces breeder auth.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const {execSync}=require('node:child_process');
const fs=require('node:fs');
const origin=process.argv[2]||'http://127.0.0.1:18096';
const live=process.env.BIGPAW_DASHBOARD_LIVE_READONLY==='1';
function installedChrome(){
  for(const cmd of ['google-chrome','google-chrome-stable','chromium','chromium-browser']){
    try{const v=execSync('command -v '+cmd,{encoding:'utf8'}).trim();if(v&&fs.existsSync(v))return v;}catch(_e){}
  }
  throw new Error('CHROME_NOT_FOUND');
}
async function run(engine,name,role){
 const browser=await engine.launch({headless:true,...(name==='chromium'?{executablePath:installedChrome(),args:['--no-sandbox']}:{})});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:3});
  const page=await context.newPage();
  if(live)await page.route('**/*',route=>(['GET','HEAD','OPTIONS'].includes(route.request().method())?route.continue():route.abort()));
  await page.route('**/api/me',route=>route.fulfill({status:role?200:401,contentType:'application/json',body:JSON.stringify(role?{role,emailVerified:true}:{error:'not logged in'})}));
  if(role==='buyer')await page.route('**/api/breeder-applications',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
  if(role==='breeder'||role==='operator')await page.route('**/'+(role==='breeder'?'admin':'operator-admin')+'.html',route=>route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><title>Dashboard destination</title>'}));
  const response=await page.goto(origin+'/index.html?signup-blue-check='+name+'-'+(role||'guest'),{waitUntil:'domcontentloaded'});
  assert.equal(response.status(),200,'public home status');
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible',timeout:25000});
  assert.notEqual(await page.locator('html').getAttribute('data-bp-mobile-tone'),'breeder','public home must keep buyer/public pink');
  const apply=page.locator('a[href^="breeder-register.html"]').filter({hasText:'ブリーダー掲載申請'}).first();
  assert.equal(await apply.count(),1,'public CTA visible in DOM');
  if(role==='breeder'||role==='operator'){
    const dest=role==='breeder'?'admin.html':'operator-admin.html';
    await Promise.all([page.waitForURL('**/'+dest,{waitUntil:'domcontentloaded',timeout:25000}),apply.click()]);
    assert.equal(new URL(page.url()).pathname,'/'+dest,role+' must go to own dashboard and not a duplicate application');
    console.log('REGISTERED_ROLE_BREEDER_CTA_REDIRECT_OK|'+name+'|'+role+'|'+dest);
    await context.close();return;
  }
  await Promise.all([page.waitForURL('**/breeder-register.html*',{waitUntil:'load',timeout:25000}),apply.click()]);
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible',timeout:25000});
  const debug=await page.evaluate(()=>({path:location.pathname,href:location.href,tone:document.documentElement.getAttribute('data-bp-mobile-tone'),navScripts:Array.from(document.scripts).map(s=>s.src).filter(s=>s.includes('mobile-global-nav')),globalFlag:window.__BIGPAW_GLOBAL_MOBILE_NAV__}));
  console.log('BREEDER_SIGNUP_MENU_DEBUG|'+name+'|'+(role||'guest')+'|'+JSON.stringify(debug));
  assert.equal(debug.path,'/breeder-register.html','must have navigated to the registration document');
  const header=page.locator('#bpRegistrationHeaderLink');
  await header.waitFor({state:'visible',timeout:25000});
  assert.equal((await header.innerText()).trim(),role==='buyer'?'マイページ':'ログイン','header must reflect actual session');
  assert.equal(await header.getAttribute('href'),role==='buyer'?'mypage.html':'login.html?next=%2Fbreeder-register.html');
  assert.equal((await page.locator('#bpRegistrationHeading').innerText()).trim(),role==='buyer'?'ブリーダー掲載申請':'大型犬ブリーダー新規登録');
  assert.equal(await page.locator('.breeder-signup-promo [data-bp-first100]').count(),1,'exactly one campaign banner placeholder');
  assert.equal(await page.locator('section.card.pad.breeder-info-card').count(),0,'old duplicate promo section removed');
  const apiStatus=await page.evaluate(async()=>{const r=await fetch('/api/campaign/first100',{cache:'no-store'});return r.ok?(await r.json()).status:'unknown'});
  if(apiStatus==='active'){
    const banner=page.locator('.breeder-signup-promo [data-bp-first100]');
    await banner.waitFor({state:'visible',timeout:25000});
    const style=await banner.evaluate(el=>({background:getComputedStyle(el).backgroundImage,border:getComputedStyle(el).borderTopColor,links:[...el.querySelectorAll('a')].map(a=>a.getAttribute('href'))}));
    assert(style.background.includes('linear-gradient')&&style.background.includes('255, 243, 211'),'campaign must be orange/gold, not blue');
    assert.equal(style.border,'rgb(232, 166, 62)','campaign orange border');
    assert(style.links.some(h=>h?.startsWith('breeder-fees.html?v=20261024-fresh-e2e4')),'campaign details link to fresh fee details');
    console.log('BREEDER_SIGNUP_SINGLE_ORANGE_CAMPAIGN_OK|'+name+'|'+(role||'guest')+'|'+JSON.stringify(style));
  }
  assert.equal(await page.locator('html').getAttribute('data-bp-mobile-tone'),'breeder','breeder registration menu must be blue');
  const menu=page.locator('#bp-global-mobile-menu-button');
  await menu.click();
  const drawer=page.locator('#bp-global-mobile-menu-drawer');
  const actual=await drawer.evaluate(e=>({bg:getComputedStyle(e).backgroundColor,title:e.getAttribute('aria-label'),links:Array.from(e.querySelectorAll('a')).map(a=>a.textContent.trim())}));
  assert.equal(actual.bg,'rgb(243, 248, 255)','blue menu drawer');
  if(!role)assert.equal(await drawer.locator('.bp-logout').count(),0,'guest has no logout');
  if(role==='buyer')assert.equal(await drawer.locator('.bp-logout').count(),1,'buyer remains buyer and may logout');
  assert.equal(await drawer.locator('a[href="/breeder-puppy-new.html?new=1"]').count(),0,'nonbreeder must not be granted breeder menu');
  assert.equal(await drawer.locator('a[href="/operator-admin.html"]').count(),0,'signup route must not grant operator menu');
  assert.equal(await page.locator('#bp-global-mobile-menu-button').getAttribute('aria-expanded'),'true','drawer actually opened');
  console.log('BREEDER_SIGNUP_BLUE_AFTER_PUBLIC_CTA_OK|'+name+'|'+(role||'guest')+'|'+JSON.stringify(actual));
  await context.close();
 }finally{await browser.close();}
}
(async()=>{
 const health=await fetch(origin+'/api/health').then(r=>r.json());
 if(live){assert.equal(new URL(origin).origin,'https://bigpaw.site');assert.notEqual(health.environment,'development');}
 else{assert.equal(health.environment,'development');assert.equal(health.paymentMode,'demo');assert.equal(health.mailConfigured,false);}
 for(const role of ['', 'buyer','breeder','operator']){await run(chromium,'chromium',role);if(process.env.BIGPAW_TEST_WEBKIT==='1')await run(webkit,'webkit',role);}
 console.log('PUBLIC_TO_BREEDER_REGISTRATION_BLUE_E2E_OK|guest|buyer|breeder|operator|orange_single_campaign|role_routing|chromium'+(process.env.BIGPAW_TEST_WEBKIT==='1'?'_webkit':''));
})().catch(e=>{console.error(e);process.exitCode=1});
