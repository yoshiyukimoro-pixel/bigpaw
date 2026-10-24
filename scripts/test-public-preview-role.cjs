#!/usr/bin/env node
'use strict';
/* Read-only simulated /api/me session for actual public preview rendering.
 * Does not synthesize conflicting bearer/cookie identities.
 * Runs only against the disposable development server, never production. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const {execSync}=require('child_process');
const fs=require('node:fs');
const origin=process.argv[2]||'http://127.0.0.1:18096';
function chromePath(){
  for(const bin of ['google-chrome','google-chrome-stable','chromium']){
    try{const x=execSync('command -v '+bin,{encoding:'utf8'}).trim();if(x&&fs.existsSync(x))return x}catch(_e){}
  }
  throw Error('CHROME_MISSING');
}
async function test(engine,label){
  const browser=await engine.launch({headless:true,...(label==='chrome'?{executablePath:chromePath(),args:['--no-sandbox']}:{})});
  try{
    const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
    const page=await context.newPage();
    let currentRole='breeder';
    let requests=0;
    await page.route('**/api/me',route=>{
      requests++;
      if(!currentRole)return route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({error:'auth_required'})});
      return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'sandbox-session',role:currentRole})});
    });
    const cases=[
      {role:'breeder',label:'ブリーダーとして一般公開ページを表示中',href:'/admin.html',background:'rgb(243, 248, 255)',text:'rgb(49, 95, 137)'},
      {role:'operator',label:'運営として一般公開ページを表示中',href:'/operator-admin.html',background:'rgb(255, 247, 212)',text:'rgb(112, 93, 0)'},
      {role:'buyer',hidden:true},
      {role:'',hidden:true},
      {role:'breeder',label:'ブリーダーとして一般公開ページを表示中',href:'/admin.html',background:'rgb(243, 248, 255)',text:'rgb(49, 95, 137)'}
    ];
    for(const c of cases){
      currentRole=c.role;
      const response=await page.goto(origin+'/puppy-detail.html?id=p1&scenario='+encodeURIComponent(c.role||'guest'),{waitUntil:'domcontentloaded',timeout:30000});
      assert.equal(response.status(),200);
      const notice=page.locator('#bigpawPublicPreviewNotice');
      if(c.hidden){
        await page.waitForTimeout(500);
        assert.equal(await notice.count(),0,'buyer or guest has no management notice: '+c.role);
      }else{
        await notice.waitFor({state:'visible',timeout:15000});
        assert.equal((await notice.locator('span').textContent()).trim(),c.label);
        assert.equal(await notice.locator('a').getAttribute('href'),c.href);
        const computed=await notice.evaluate(x=>({background:getComputedStyle(x).backgroundColor,text:getComputedStyle(x).color}));
        assert.equal(computed.background,c.background,'background color for '+c.role);
        assert.equal(computed.text,c.text,'text color for '+c.role);
      }
      console.log('PASS_PUBLIC_PREVIEW|'+label+'|'+(c.role||'guest')+'|'+(c.hidden?'no-banner':c.href));
    }
    assert(requests>=cases.length,'must look up session role on each navigation');
    await context.close();
  }finally{await browser.close()}
}
(async()=>{
  const health=await fetch(origin+'/api/health').then(r=>r.json());
  assert.equal(health.environment,'development','never test against production');
  assert.equal(health.mailConfigured,false,'no production mail');
  assert.equal(health.paymentMode,'demo','no production payments');
  await test(chromium,'chrome');
  await test(webkit,'webkit');
  console.log('BIGPAW_PUBLIC_PREVIEW_PALETTE_OK|operator_yellow|breeder_blue|buyer_guest_hidden|no_auth_changes|chrome_webkit');
})().catch(e=>{console.error(e);process.exitCode=1});
