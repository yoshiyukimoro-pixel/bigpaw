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
  await page.waitForFunction(()=>document.querySelectorAll('#settingsBreeder option').length>=2,null,{timeout:20000});
  const options=await page.locator('#settingsBreeder option').count();
  assert(options>=2,'registered breeder can be selected');
  await page.locator('#settingsBreeder').selectOption({index:1});
  await page.waitForFunction(()=>{const x=document.getElementById('settingsStatus');return x&&!x.textContent.includes('読み込み中')});
  const status=await page.locator('#settingsStatus').textContent();
  assert(!String(status).includes('読み込めません'),'operator readback success');
  const denied=await page.evaluate(async()=> {
    const breederId=document.getElementById('settingsBreeder').value;
    const response=await fetch('/api/breeder/sales-handover-settings',{method:'POST',
      credentials:'include',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({breederId,reservationAmount:987654})});
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

async function localProxyBrowserTests(browser) {
  // Only the disposable localhost Docker test server, after synthetic A/B fixtures.
  assert.equal(mode,'local');
  const ctx=await browser.newContext({viewport:{width:1350,height:900}});
  const page=await ctx.newPage();
  const dialogs=[];
  page.on('dialog',async d=>{dialogs.push(d.message());await d.accept()});
  await login(page,'operator');
  const get=async path=>page.evaluate(async path=>{
    const r=await fetch('/api'+path,{credentials:'include'});
    if(!r.ok)throw Error(path+':'+r.status);
    return r.json();
  },path);
  const all=await get('/operator/listings');
  const candidates=all.filter(x=>String(x.breeder||'').includes('代理掲載A犬舎')&&x.id&&x.breederId);
  const other=all.find(x=>String(x.breeder||'').includes('代理掲載B犬舎')&&x.breederId);
  assert(candidates.length&&other,'pre-seeded proxy A/B fixtures');
  let selected=null,initialPhotos=[];
  for(const p of candidates){
    const photos=await get('/puppies/'+encodeURIComponent(p.id)+'/photos');
    if(photos.length>0&&photos.length<10){selected=p;initialPhotos=photos;break}
  }
  assert(selected,'selected breeder has editable puppy and space for another image');
  assert.notEqual(selected.breederId,other.breederId);
  await page.goto(BASE+'/admin.html?breederId='+encodeURIComponent(selected.breederId));
  await page.waitForFunction(id=>document.getElementById('operatorBreeder')?.value===id,selected.breederId,{timeout:20000});
  const edit=page.locator('#dogList a[href*="'+selected.id+'"]').first();
  await edit.waitFor({state:'visible',timeout:20000});
  await edit.click();
  await page.waitForURL('**/breeder-puppy-new.html?id=*',{timeout:20000});
  await page.waitForFunction(n=>window.persistedPhotos?.length===n,initialPhotos.length,{timeout:20000});
  assert.equal(new URL(page.url()).searchParams.get('breederId'),selected.breederId);
  const note='PROXY-BROWSER-EDIT-'+Date.now();
  await page.locator('#desc').fill(note);
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==','base64');
  await page.locator('#photo').setInputFiles({name:'proxy-browser-photo.png',mimeType:'image/png',buffer:png});
  await page.locator('form button.btn-main.btn-wide').first().click();
  await page.waitForURL('**/admin.html?breederId=*',{timeout:30000});
  const afterPhotos=await get('/puppies/'+selected.id+'/photos');
  assert.equal(afterPhotos.length,initialPhotos.length+1,'photo appended without deleting old images');
  const selectedList=await get('/breeder/puppies?breederId='+encodeURIComponent(selected.breederId));
  assert(selectedList.some(x=>x.id===selected.id&&x.desc===note),'edited puppy text stored for selected breeder');
  await page.goto(BASE+'/breeder-puppy-new.html?id='+selected.id+'&breederId='+selected.breederId);
  await page.waitForFunction(({note,n})=>document.getElementById('desc')?.value===note&&window.persistedPhotos?.length===n,{note,n:afterPhotos.length},{timeout:20000});
  assert.equal(await page.locator('#photoPreview img').count(),afterPhotos.length);
  console.log('PASS|local|real_operator_browser_proxy_edit_photo_append_reload');

  await page.goto(BASE+'/admin.html?breederId='+encodeURIComponent(other.breederId));
  await page.waitForFunction(id=>document.getElementById('operatorBreeder')?.value===id,other.breederId,{timeout:20000});
  assert.equal(await page.locator('#dogList a[href*="'+selected.id+'"]').count(),0);
  assert((await get('/breeder/puppies?breederId='+encodeURIComponent(other.breederId))).every(x=>x.id!==selected.id));
  console.log('PASS|local|proxy_cross_breeder_browser_scope');

  const breederCtx=await browser.newContext({viewport:{width:1350,height:900}});
  const bp=await breederCtx.newPage();
  await login(bp,'breeder');
  await bp.goto(BASE+'/breeder-profile-edit.html');
  await bp.waitForFunction(()=>document.getElementById('kennel')?.value?.length>0,null,{timeout:20000});
  const reg='LOCAL-LEGAL-REG-'+Date.now();
  await bp.locator('#registration').fill(reg);
  await bp.locator('#saveBtn').click();
  await bp.locator('#msg .notice').first().waitFor({state:'visible',timeout:18000});
  await bp.reload();
  await bp.waitForFunction(v=>document.getElementById('registration')?.value===v,reg,{timeout:18000});
  const own=await bp.evaluate(async()=>await(await fetch('/api/breeder-profile',{credentials:'include'})).json());
  assert.equal(own.registration_no,reg);
  await page.goto(BASE+'/breeder-profile-edit.html?breederId='+encodeURIComponent(own.id));
  await page.waitForFunction(v=>document.getElementById('registration')?.value===v,reg,{timeout:20000});
  console.log('PASS|local|breeder_legal_profile_save_and_operator_readback');
  await breederCtx.close();
  await ctx.close();
}

(async()=>{
 await health();
 const browser=await chromium.launch({headless:true});
 try {await operatorTests(browser);await breederTests(browser);if(mode==='local')await localProxyBrowserTests(browser);}
 finally{await browser.close();}
 console.log('HANDOVER_REAL_BROWSER_TESTS_OK|'+mode);
})().catch(e=>{console.error('HANDOVER_REAL_BROWSER_TEST_FAILED|'+mode+'|'+(e.stack||e));process.exit(1);});
