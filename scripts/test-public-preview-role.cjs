#!/usr/bin/env node
'use strict';
/* Isolated browser verification of public puppy preview identity and palette.
 * Runs against the disposable BIG PAW development server, never production. */
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
async function scenario(engine,label,bearerRole,cookieRole,expectedRole){
  const browser=await engine.launch({headless:true,...(label==='chrome'?{executablePath:chromePath(),args:['--no-sandbox']}:{})});
  try{
    const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
    const page=await context.newPage();
    if(bearerRole)await page.addInitScript(()=>localStorage.setItem('bigpaw_api_token_v1','qa-session'));
    else await page.addInitScript(()=>localStorage.removeItem('bigpaw_api_token_v1'));
    let bearer=bearerRole;
    let cookie=cookieRole;
    let requests=0;
    await page.route('**/api/me',route=>{
      requests++;
      const headers=route.request().headers();
      const role=headers.authorization?.startsWith('Bearer ')?bearer:cookie;
      if(!role)return route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({error:'auth_required'})});
      return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'qa-'+role,role})});
    });
    const res=await page.goto(origin+'/puppy-detail.html?id=p1',{waitUntil:'domcontentloaded',timeout:30000});
    assert.equal(res.status(),200);
    const notice=page.locator('#bigpawPublicPreviewNotice');
    if(expectedRole){
      await notice.waitFor({state:'visible',timeout:15000});
      const expectedLabel=expectedRole==='operator'?'運営として一般公開ページを表示中':'ブリーダーとして一般公開ページを表示中';
      const expectedHref=expectedRole==='operator'?'/operator-admin.html':'/admin.html';
      const debug=await page.evaluate(async()=>{
        const api=window.BigPawAPI;
        const sessionRole=api?await api.me().then(x=>x.role).catch(e=>'error:'+e.status):'no-api';
        const cookieRole=await fetch('/api/me',{credentials:'include',cache:'no-store'}).then(r=>r.ok?r.json().then(x=>x.role):'unauthorized').catch(()=>'error');
        return {apiPresent:!!api,tokenPresent:!!api?.token?.(),sessionRole,cookieRole,attr:document.documentElement.getAttribute('data-bigpaw-public-preview-role')};
      });
      console.log('PREVIEW_ROLE_DIAGNOSTIC|'+label+'|expected='+expectedRole+'|'+JSON.stringify(debug));
      assert.equal((await notice.locator('span').textContent()).trim(),expectedLabel);
      assert.equal(await notice.locator('a').getAttribute('href'),expectedHref);
      const computed=await notice.evaluate(x=>({background:getComputedStyle(x).backgroundColor,color:getComputedStyle(x).color}));
      assert.equal(computed.background,expectedRole==='operator'?'rgb(255, 247, 212)':'rgb(243, 248, 255)','role-specific yellow/blue color');
      console.log('PASS_PREVIEW_ROLE|'+label+'|'+expectedRole+'|'+JSON.stringify(computed));
    }else{
      await page.waitForTimeout(800);
      assert.equal(await notice.count(),0,'buyer or guest must have no management notice');
      console.log('PASS_NO_ADMIN_PREVIEW|'+label);
    }
    assert(requests>0,'identity must be checked using authenticated /api/me');
    if(bearerRole==='breeder'&&cookieRole==='operator'){
      // The user changes accounts while Safari has an already-open detail tab.
      bearer='operator';
      await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
      await page.waitForFunction(()=>document.querySelector('#bigpawPublicPreviewNotice span')?.textContent==='運営として一般公開ページを表示中',null,{timeout:15000});
      const updated=page.locator('#bigpawPublicPreviewNotice');
      assert.equal(await updated.locator('a').getAttribute('href'),'/operator-admin.html','role refresh keeps correct management destination');
      assert.equal(await updated.evaluate(x=>getComputedStyle(x).backgroundColor),'rgb(255, 247, 212)','role refresh changes blue to yellow');
      console.log('PASS_PREVIEW_ROLE_REFRESH|'+label+'|breeder_to_operator');
    }
    await context.close();
  }finally{await browser.close()}
}
(async()=>{
  const health=await fetch(origin+'/api/health').then(r=>r.json());
  assert.equal(health.environment,'development','never run preview identity test on production');
  assert.equal(health.mailConfigured,false,'disposable test must not send live mail');
  for(const [engine,label] of [[chromium,'chrome'],[webkit,'webkit']]){
    await scenario(engine,label,'breeder','operator','breeder');
    await scenario(engine,label,'operator','breeder','operator');
    await scenario(engine,label,null,'breeder','breeder');
    await scenario(engine,label,'buyer','operator',null);
    await scenario(engine,label,null,null,null);
  }
  console.log('BIGPAW_PUBLIC_PREVIEW_ROLE_E2E_OK|same_identity_as_API|breeder_blue|operator_yellow|stale_cookie_ignored|role_change_refresh|buyer_guest_hidden|chrome_and_webkit');
})().catch(e=>{console.error(e);process.exitCode=1});
