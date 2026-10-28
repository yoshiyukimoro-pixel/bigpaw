#!/usr/bin/env node
// Isolated frontend regression: no production writes, no real login, no emails.
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const BASE='http://127.0.0.1:18087';
const cases=[
 {name:'with_two_visit_choices',kind:'現地で見学を希望',preferred_date:'2026-11-01',message:'現地で見学を希望\n第1希望 2026-11-01 16:30\n第2希望 2026-11-02 09:15\n子犬に会いたいです'},
 {name:'without_visit_date',kind:'現地で見学を希望',preferred_date:'',message:'現地で見学を希望\n子犬に会いたいです'},
];
function routeApi(page,fixture,role='breeder'){
 const item={...fixture,id:'q_test',puppy_id:'p_test',name:'見学希望者',status:'未返信',puppy_name:'テストの子犬',breeder_name:'テスト犬舎'};
 const notifications=[{id:'n1',kind:'inquiry',title:'新しい問い合わせ',body:'テストの子犬に問い合わせが届きました',created_at:1793180000}];
 return page.route('**/api/**', async route=>{
  const url=new URL(route.request().url());
  const path=url.pathname;let obj=null,code=200;
  if(path==='/api/me')obj={id:'b_test',role,email:'breeder@example.test'};
  else if(path==='/api/inquiries')obj=[item];
  else if(path==='/api/puppies/p_test')obj={id:'p_test',name:'テストの子犬',breeder:'テスト犬舎'};
  else if(path==='/api/inquiries/q_test/visit')obj=null;
  else if(path==='/api/breeder/invoices')obj=[];
  else if(path==='/api/notifications')obj=notifications;
  else if(path==='/api/health')obj={ok:true};
  else {code=404;obj={error:'fixture_missing',path}}
  await route.fulfill({status:code,contentType:'application/json',body:JSON.stringify(obj)});
 });
}

async function enhance(page,alerts=false){
 // The production start command injects the shared mobile menu into HTML.
 // Mirror that injection on this disposable static HTTP test server.
 await page.addScriptTag({url:BASE+'/mobile-global-nav.js'});
 if(alerts)await page.addScriptTag({url:BASE+'/attention-alerts.js'});
}

async function check(browser,browserName,viewport){
 for(const fixture of cases){
  const page=await browser.newPage({viewport});
  const errors=[];
  page.on('pageerror',e=>errors.push('pageerror: '+e.message));
  page.on('requestfailed',r=>errors.push('request: '+r.url()+' '+(r.failure()?.errorText||'')));
  await routeApi(page,fixture);
  await page.goto(BASE+'/breeder-inquiries.html',{waitUntil:'domcontentloaded'});
  await enhance(page,true);
  try{await page.waitForFunction(()=>document.querySelector('#inquiryList')?.textContent.includes('見学希望者'),{},{timeout:12000})}catch(e){const details=await page.evaluate(()=>({url:location.href,html:document.querySelector('#inquiryList')?.outerHTML,body:document.body?.innerText.slice(0,1500),role:document.documentElement.getAttribute('data-bp-mobile-tone')}));throw new Error('INQUIRY_LIST_NOT_READY|'+JSON.stringify({details,errors}))}
  assert.match(await page.locator('#inquiryList').innerText(),/テストの子犬/);
  assert.match(await page.locator('#inquiryList').innerText(),/現地で見学を希望/);
  assert.equal(await page.locator('#unread').innerText(),'1件');
  assert.equal(await page.locator('#visits').innerText(),'1件');
  if(fixture.preferred_date){
   assert.match(await page.locator('#inquiryList').innerText(),/第1希望 2026-11-01 16:30/);
   assert.match(await page.locator('#inquiryList').innerText(),/第2希望 2026-11-02 09:15/);
  }else assert.match(await page.locator('#inquiryList').innerText(),/希望日時は未入力/);
  assert.equal(await page.locator('html').getAttribute('data-bp-page-theme'),'breeder');
  await page.locator('#bp-global-mobile-menu-button').waitFor({state:'attached'});
  assert.equal(await page.locator('html').getAttribute('data-bp-mobile-tone'),'breeder');
  assert.equal(await page.locator('#bp-global-mobile-menu-drawer .bp-title').innerText(),'🐾 BIG PAW');
  const bg=await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor);
  assert.equal(bg,'rgb(243, 248, 255)',browserName+' breeder page background must be blue');
  await page.locator('#bp-attention-summary').waitFor({state:'attached'});
  await page.waitForFunction(()=>document.querySelector('#bp-attention-summary')?.textContent.includes('見学希望日時'));
  assert.match(await page.locator('#bp-attention-summary').innerText(),/未返信の問い合わせ・メッセージが 1件/);
  assert.equal(new URL(await page.locator('#bp-attention-summary').getAttribute('href'),BASE).pathname,'/breeder-inquiries.html');
  const go=page.locator('a.bp-visit-action');
  assert.match(await go.innerText(),/見学日程を調整|希望日時を確認・調整/);
  await go.click();
  await page.waitForURL('**/visit-confirm.html?inquiry=q_test');
  await page.waitForFunction(()=>document.querySelector('#visitRequestSummary')?.textContent.includes('現地で見学を希望'));
  assert.equal(await page.locator('html').getAttribute('data-bp-page-theme'),'breeder');
  if(fixture.preferred_date){
   assert.match(await page.locator('#visitRequestSummary').innerText(),/第1希望：2026-11-01 16:30/);
   assert.match(await page.locator('#visitRequestSummary').innerText(),/第2希望：2026-11-02 09:15/);
   assert.equal(await page.locator('#visitDate').inputValue(),'2026-11-01');
   assert.equal(await page.locator('#visitTime').inputValue(),'16:30');
  }else{
   assert.match(await page.locator('#visitRequestSummary').innerText(),/希望日時は未入力/);
   assert.equal(await page.locator('#visitDate').inputValue(),'');
  }
  const color=await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor);
  assert.equal(color,'rgb(243, 248, 255)',browserName+' schedule background must be blue');
  await page.close();
  assert.deepEqual(errors,[],browserName+' '+fixture.name+' page script errors');
 }
 const messages=await browser.newPage({viewport});
 await routeApi(messages,cases[0]);
 await messages.goto(BASE+'/messages.html?inquiry=q_test',{waitUntil:'domcontentloaded'});
 await enhance(messages);
 await messages.waitForFunction(()=>document.body.classList.contains('breeder-view'));
 assert.equal(await messages.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(243, 248, 255)');
 await messages.waitForFunction(()=>document.querySelector('#who')?.textContent.includes('見学希望者'));
 assert.match(await messages.locator('#roleNotice').innerText(),/返信または見学日程を調整/);
 assert.match(await messages.locator('#who').innerText(),/見学希望者さん/);
 assert.equal(await messages.locator('html').getAttribute('data-bp-mobile-tone'),'breeder');
 await messages.close();
 const notification=await browser.newPage({viewport});
 await routeApi(notification,cases[0]);
 await notification.goto(BASE+'/notifications.html',{waitUntil:'domcontentloaded'});
 await enhance(notification);
 await notification.locator('.bp-notice-action').waitFor({state:'attached'});
 assert.equal(await notification.locator('html').getAttribute('data-bp-page-theme'),'breeder');
 assert.equal(await notification.locator('html').getAttribute('data-bp-mobile-tone'),'breeder');
 assert.equal(await notification.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(243, 248, 255)');
 assert.equal(new URL(await notification.locator('.bp-notice-action').getAttribute('href'),BASE).pathname,'/breeder-inquiries.html');
 await notification.close();
 console.log('BREEDER_VISIT_NOTICE_BROWSER_OK|'+browserName);
}
(async()=>{
 const setups=[['chromium',chromium,{width:1280,height:800}],['iphone_webkit',webkit,{width:390,height:844}]];
 for(const [name,browserType,viewport] of setups){
  const browser=await browserType.launch({headless:true});
  try{await check(browser,name,viewport)}finally{await browser.close()}
 }
})().catch(e=>{console.error(e);process.exit(1)});
