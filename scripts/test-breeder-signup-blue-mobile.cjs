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
  await page.route('**/api/me',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(role?{role}:{})}));
  const response=await page.goto(origin+'/index.html?signup-blue-check='+name+'-'+(role||'guest'),{waitUntil:'domcontentloaded'});
  assert.equal(response.status(),200,'public home status');
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible',timeout:25000});
  assert.notEqual(await page.locator('html').getAttribute('data-bp-mobile-tone'),'breeder','public home must keep buyer/public pink');
  const apply=page.locator('a[href="breeder-register.html"]').filter({hasText:'ブリーダー掲載申請'}).first();
  assert.equal(await apply.count(),1,'public CTA visible in DOM');
  await Promise.all([page.waitForURL('**/breeder-register.html',{timeout:25000}),apply.click()]);
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible',timeout:25000});
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
 for(const role of ['', 'buyer']){await run(chromium,'chromium',role);if(process.env.BIGPAW_TEST_WEBKIT==='1')await run(webkit,'webkit',role);}
 console.log('PUBLIC_TO_BREEDER_REGISTRATION_BLUE_E2E_OK|guest|buyer|chromium'+(process.env.BIGPAW_TEST_WEBKIT==='1'?'_webkit':''));
})().catch(e=>{console.error(e);process.exitCode=1});
