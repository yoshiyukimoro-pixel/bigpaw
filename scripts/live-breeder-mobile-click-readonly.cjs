#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const {execSync}=require('child_process');
const {chromium}=require('playwright');
const origin='https://bigpaw.site';
(async()=>{
  const health=await fetch(origin+'/api/health',{headers:{'Cache-Control':'no-cache'}}).then(r=>r.json());
  assert.equal(health.environment,'production');
  const info=await fetch(origin+'/api/campaign/first100',{headers:{'Cache-Control':'no-cache'}}).then(r=>r.json());
  assert.equal(info.status,'active');
  assert.equal(info.eligible,true);
  const chrome=execSync('command -v google-chrome',{encoding:'utf8'}).trim();
  const browser=await chromium.launch({headless:true,executablePath:chrome,args:['--no-sandbox']});
  try{
    const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
    const page=await context.newPage();
    // READ ONLY. The user's actual login is never used. /api/me is intercepted locally
    // to show the same breeder mobile drawer without real login credentials.
    await page.route('**/api/me',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({role:'breeder'})}));
    const response=await page.goto(origin+'/admin.html?mobile-live-smoke=20261024',{waitUntil:'domcontentloaded',timeout:45000});
    assert.equal(response.status(),200);
    const src=await page.locator('script[src*="/mobile-global-nav.js"]').getAttribute('src');
    assert(src.includes('v=20261024-breeder-pricing-e2e3'),'live dashboard must load freshly versioned mobile menu '+src);
    await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible',timeout:30000});
    await page.locator('#bp-global-mobile-menu-button').click();
    const link=page.locator('#bp-global-mobile-menu-drawer a').filter({hasText:'料金・手数料'}).first();
    assert(await link.isVisible(),'the breeder fee menu link is clickable');
    await Promise.all([page.waitForURL('**/breeder-fees.html*',{timeout:30000}),link.click()]);
    await page.waitForFunction(()=>{const el=document.getElementById('bpBreederCampaign');return el&&!el.hidden&&document.getElementById('bpBreederCampaignCount')?.textContent;},null,{timeout:30000});
    const view=await page.evaluate(()=>{
      const gold=document.getElementById('bpBreederCampaign');
      const five=document.getElementById('bpBreederStandardHero');
      return {
        location:location.href,
        background:getComputedStyle(gold).backgroundImage,
        border:getComputedStyle(gold).borderTopColor,
        visible:getComputedStyle(gold).display!=='none'&&!gold.hidden,
        oldHeroHidden:five.hidden&&getComputedStyle(five).display==='none',
        normalFeeText:document.getElementById('bpBreederStandardFee').textContent,
        remaining:document.getElementById('bpBreederCampaignCount').textContent,
        width:document.documentElement.scrollWidth,
        viewport:innerWidth,
        title:document.title
      };
    });
    assert(view.visible,'orange campaign must be visible');
    assert(/255, 244, 189/.test(view.background),'computed golden gradient '+view.background);
    assert(view.oldHeroHidden,'old headline with regular 5% must be hidden');
    assert.equal(view.normalFeeText,'0円（先着100頭対象）');
    assert(/残り(?:\d+頭|わずか)・受付中/.test(view.remaining),'must show remaining eligibility: '+view.remaining);
    assert(view.width<=view.viewport+15,'no horizontal phone overflow');
    console.log('LIVE_PRODUCTION_REAL_MOBILE_TAP_GOLD_OK|'+JSON.stringify(view));
    await page.goBack({waitUntil:'domcontentloaded'});
    await page.locator('#bp-global-mobile-menu-button').waitFor({state:'visible'});
    await page.locator('#bp-global-mobile-menu-button').click();
    await Promise.all([page.waitForURL('**/breeder-fees.html*'),page.locator('#bp-global-mobile-menu-drawer a').filter({hasText:'料金・手数料'}).first().click()]);
    await page.waitForFunction(()=>document.getElementById('bpBreederCampaign')?.hidden===false);
    console.log('LIVE_PRODUCTION_REAL_MOBILE_BACK_FORWARD_OK');
    console.log('NO_USER_LOGIN_NO_PRODUCTION_WRITE_BREEDER_VIEW_SIMULATED');
    await context.close();
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
