#!/usr/bin/env node
'use strict';
// Browser-level regression for the handover theme. Strictly isolated targets only.
// Never change or test real customer/breeder data.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const mode = process.argv[2];
const BASE = mode === 'local' ? 'http://127.0.0.1:18086'
           : mode === 'staging' ? 'https://bigpaw-test-production.up.railway.app' : '';
if (!BASE) throw Error('SAFE_TARGET_REQUIRED');
function log(s) { console.log('PASS|' + s, {flush:true}); }
function rgb(s) { return s.replace(/\s+/g,''); }
async function health() {
  const response = await fetch(BASE + '/api/health', { signal: AbortSignal.timeout(25000) });
  if (!response.ok) throw Error('TEST_SERVER_HEALTH_' + response.status);
  const h = await response.json();
  // Fails closed if the endpoint becomes production, accepts payments, or sends real SMTP.
  assert.equal(h.environment, 'development', 'must never operate against production');
  assert.equal(h.mailConfigured, false, 'test must not have SMTP');
  assert.equal(h.paymentMode, 'demo', 'test must not process real payments');
  log(mode + '|isolated_environment_guard');
}
async function login(page, role) {
  await page.goto(BASE + (role === 'operator' ? '/operator-login.html' : '/login.html'));
  await page.locator('#email').fill(role === 'operator' ? 'admin@bigpaw.jp' : 'dog44@bigpaw.jp');
  await page.locator('#password').fill(role === 'operator' ? 'admin1234' : 'demo1234');
  await page.locator('form button').first().click();
  await page.waitForURL(role === 'operator' ? '**/operator-admin.html*' : '**/admin.html*', {timeout:20000});
  const actualRole=await page.evaluate(async()=>{
    const r=await fetch('/api/me',{credentials:'include',cache:'no-store'});
    return r.ok?(await r.json()).role:'UNAUTHENTICATED';
  });
  assert.equal(actualRole,role,'real authenticated role');
  log(mode+'|'+role+'_browser_login');
}
async function assertTheme(page, theme) {
  await page.waitForFunction(theme=>document.body.classList.contains('bigpaw-'+theme+'-theme'),theme);
  const actual=await page.evaluate(()=>getComputedStyle(document.body).backgroundColor);
  const expected=theme==='breeder'?'rgb(243, 248, 255)':'rgb(255, 251, 234)';
  assert.equal(rgb(actual), rgb(expected), 'actual background CSS for '+theme);
  log(mode+'|'+theme+'_background_computed');
}
async function operatorTests(browser) {
  const ctx=await browser.newContext({viewport:{width:1350,height:900}});
  const page=await ctx.newPage();
  await login(page,'operator');
  await page.goto(BASE+'/breeder-sales-handover.html');
  await assertTheme(page,'operator');
  assert.equal(await page.locator('#settingsOperator').isVisible(),true,'operator target chooser visible');
  assert.equal(await page.locator('#saveBtn').isVisible(),false,'operator cannot save');
  assert.equal(await page.locator('#reservationAmount').isDisabled(),true,'operator fields read-only');
  const options=await page.locator('#settingsBreeder option').count();
  assert(options>=2,'registered breeder can be selected');
  await page.locator('#settingsBreeder').selectOption({index:1});
  await page.waitForFunction(()=>{const x=document.getElementById('settingsStatus');return x&&!x.textContent.includes('読み込み中')});
  const status=await page.locator('#settingsStatus').textContent();
  assert(!String(status).includes('読み込めません'),'operator readback success');
  const denied=await page.evaluate(async()=> {
    const response=await fetch('/api/breeder/sales-handover-settings',{method:'POST',
      credentials:'include',headers:{'Content-Type':'application/json'},body:'{}'});
    return response.status;
  });
  assert.equal(denied,403,'server-side role authorization remains enforced');
  log(mode+'|operator_yellow_read_only_and_post_forbidden');
  await page.goto(BASE+'/breeder-sales-handover.html?view=breeder');
  await assertTheme(page,'breeder');
  assert.equal(await page.locator('#settingsOperator').isVisible(),true,'operator identity still enforced under blue theme');
  assert.equal(await page.locator('#saveBtn').isVisible(),false,'operator does not become breeder');
  assert.equal(await page.locator('#reservationAmount').isDisabled(),true,'read only in blue view');
  assert.equal(await page.locator('.side').isVisible(),true,'breeder navigation retained');
  log(mode+'|operator_breeder_blue_view_read_only');
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  await assertTheme(page,'breeder');
  const bodyWidth=await page.evaluate(()=>document.documentElement.scrollWidth);
  assert(bodyWidth <= 430,'mobile layout has no gross horizontal overflow');
  log(mode+'|operator_blue_mobile_390');
  await ctx.close();
}
async function breederTests(browser) {
  const ctx=await browser.newContext({viewport:{width:1350,height:900}});
  const page=await ctx.newPage();
  await login(page,'breeder');
  await page.goto(BASE+'/breeder-sales-handover.html');
  await assertTheme(page,'breeder');
  await page.waitForFunction(()=>!document.getElementById('handoverForm').disabled);
  assert.equal(await page.locator('#settingsOperator').isVisible(),false,'breeder has no operator scope chooser');
  assert.equal(await page.locator('#saveBtn').isVisible(),true,'breeder save available');
  // Changes only in disposable database, never in real BIG PAW data.
  const marker='browser-e2e-'+Date.now();
  await page.locator('#reservationAmount').fill('100000');
  await page.locator('#reservationNote').fill(marker);
  await page.locator('#saveBtn').click();
  await page.waitForFunction(()=>document.getElementById('saved').style.display==='block');
  await page.reload();
  await page.waitForFunction(()=>!document.getElementById('handoverForm').disabled);
  assert.equal(await page.locator('#reservationAmount').inputValue(),'100000');
  assert.equal(await page.locator('#reservationNote').inputValue(),marker);
  log(mode+'|breeder_save_reload_exact_values');
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  await assertTheme(page,'breeder');
  const width=await page.evaluate(()=>document.documentElement.scrollWidth);
  assert(width<=430,'breeder mobile layout no gross overflow');
  log(mode+'|breeder_blue_mobile_390');
  await ctx.close();
}
(async()=>{
 await health();
 const browser=await chromium.launch({headless:true});
 try {await operatorTests(browser);await breederTests(browser);}
 finally{await browser.close();}
 console.log('HANDOVER_REAL_BROWSER_TESTS_OK|'+mode);
})().catch(e=>{console.error('HANDOVER_REAL_BROWSER_TEST_FAILED|'+mode+'|'+(e.stack||e));process.exit(1);});
