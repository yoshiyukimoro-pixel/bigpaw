#!/usr/bin/env node
'use strict';
// Real, isolated browser test. Never point at production (no real customers).
const assert = require('node:assert/strict');
const {chromium, webkit} = require('playwright');
const {execSync} = require('node:child_process');
const url=process.argv[2]||'http://127.0.0.1:18097';
if(!/^http:\/\/(?:127\.0\.0\.1|localhost):\d+$/.test(url))throw Error('LOCAL_DEVELOPMENT_ONLY');
function chromePath(){
 for(const n of ['google-chrome','google-chrome-stable','chromium','chromium-browser']){
   try{const s=execSync('command -v '+n,{encoding:'utf8'}).trim();if(s)return s}catch(_){}
 }
 return null;
}
const item={breed:'スタンダードプードル',breedKey:'standard-poodle',
 title:'2027年春 予約希望受付中',phase:'交配予定',
 plannedMating:'2027-01-10',expectedBirth:'2027-03-10',
 description:'大型犬の出産に向けて事前相談を受け付けています。',
 status:'受付中'};
async function login(context,email,pw){
 const resp=await context.request.post(url+'/api/login',{data:{email,password:pw}});
 assert.equal(resp.status(),200,'login request');
 const body=await resp.json();assert.equal(body.user.email,email);
}
async function api(context,method,path,payload){
 const response=await context.request.fetch(url+'/api'+path,{method,data:payload});
 assert(response.ok(),method+' '+path+' response '+response.status()+' '+(await response.text()).slice(0,200));
 return response.json();
}
async function assertBreederBlue(page,where){
 const state=await page.evaluate(()=>({
   theme:document.documentElement.getAttribute('data-bp-page-theme'),
   bodyBg:getComputedStyle(document.body).backgroundColor,
   topbarBg:getComputedStyle(document.querySelector('.topbar')).backgroundImage,
   saveBg:getComputedStyle(document.querySelector('#saveBtn')).backgroundColor,
   titleBorder:getComputedStyle(document.querySelector('#title')).borderColor
 }));
 assert.equal(state.theme,'breeder',where+' must remain breeder themed');
 assert.equal(state.bodyBg,'rgb(243, 248, 255)',where+' body must be breeder blue');
 assert(state.topbarBg.includes('rgb(95, 143, 195)'),where+' topbar must use breeder blue: '+state.topbarBg);
 assert.equal(state.saveBg,'rgb(36, 91, 148)',where+' save button must be blue');
 assert.equal(state.titleBorder,'rgb(184, 200, 216)',where+' input border must be blue/gray');
}
async function check(engine,label){
 const browser=await engine.launch({headless:true,...(label==='chromium'&&chromePath()?{executablePath:chromePath(),args:['--no-sandbox']}: {})});
 try{
   const manager=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
   const errors=[];
   const mpage=await manager.newPage();
   mpage.on('pageerror',e=>errors.push('manage: '+e.message));
   await login(manager,'dog44@bigpaw.jp','demo1234');
   await mpage.goto(url+'/admin.html',{waitUntil:'domcontentloaded'});
   await mpage.locator('a.dashboard-action[href^="planned-litter-manage.html"]').waitFor({state:'visible',timeout:20000});
   const dashboardPlannedBg=await mpage.locator('a.dashboard-action[href^="planned-litter-manage.html"]').evaluate(el=>getComputedStyle(el).backgroundColor);
   assert.equal(dashboardPlannedBg,'rgb(228, 241, 255)',label+' breeder dashboard planned-litter entry must be blue');
   // The new feature must be reachable even if the mobile sidebar is hidden.
   await mpage.locator('a.dashboard-action[href^="planned-litter-manage.html"]').click();
   await mpage.waitForURL('**/planned-litter-manage.html?v=20261026-blue3');
   await mpage.locator('#listings').waitFor();
   await mpage.waitForFunction(()=>document.querySelector('#listings')&&!document.querySelector('#listings').textContent.includes('読み込み中'),null,{timeout:20000});
   await assertBreederBlue(mpage,label+' breeder mobile manager');
   // Reproduce the reported iPhone symptom: a late theme mutation/pink stylesheet must not win after the initial blue paint.
   await mpage.evaluate(()=>{
     document.documentElement.setAttribute('data-bp-page-theme','buyer');
     const late=document.createElement('style');
     late.id='test-late-pink-theme';
     late.textContent='body{background:#fff7fb!important}.topbar{background:#ef7fa8!important}';
     document.head.appendChild(late);
   });
   await mpage.waitForFunction(()=>document.documentElement.getAttribute('data-bp-page-theme')==='breeder'&&getComputedStyle(document.body).backgroundColor==='rgb(243, 248, 255)'&&getComputedStyle(document.querySelector('.topbar')).backgroundImage.includes('rgb(95, 143, 195)'),null,{timeout:5000});
   await assertBreederBlue(mpage,label+' breeder mobile manager after late pink override');
   await mpage.locator('#breed').selectOption('standard-poodle');
   await mpage.locator('#phase').selectOption('交配予定');
   const title=item.title+' '+label;
   await mpage.locator('#title').fill(title);
   await mpage.locator('#plannedMating').fill(item.plannedMating);
   await mpage.locator('#expectedBirth').fill(item.expectedBirth);
   await mpage.locator('#description').fill(item.description);
   await mpage.locator('#saveBtn').click();
   await mpage.waitForFunction(text=>document.querySelector('#listings')?.textContent.includes(text),title,{timeout:20000});
   const list=await api(manager,'GET','/planned-litters/mine');
   const created=list.filter(x=>x.title===title);
   assert.equal(created.length,1,'created through actual browser form');
   const lid=created[0].id;
   // Anonymous public page and individual detail.
   const publicContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
   const publicPage=await publicContext.newPage();
   publicPage.on('pageerror',e=>errors.push('public: '+e.message));
   await publicPage.goto(url+'/planned-litters.html',{waitUntil:'domcontentloaded'});
   await publicPage.getByText(title).waitFor();
   await publicPage.getByRole('link',{name:'詳しく見る・相談する'}).click();
   await publicPage.waitForURL('**/planned-litters.html?id=*');
   await publicPage.getByText('これは事前相談・仮予約希望').waitFor();
   assert.equal((await publicPage.locator('#send').textContent()).trim(),'予約希望・事前相談を送信');
   // Buyer signs in; sends an interest inquiry that is not a sale or payment.
   const buyer=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
   await login(buyer,'demo@bigpaw.jp','demo1234');
   const bpage=await buyer.newPage();
   bpage.on('pageerror',e=>errors.push('buyer: '+e.message));
   await bpage.goto(url+'/planned-litters.html?id='+encodeURIComponent(lid),{waitUntil:'domcontentloaded'});
   await bpage.locator('#preferredGender').selectOption('女の子');
   await bpage.locator('#message').fill('子犬の予約希望について詳しくご相談させてください。');
   await bpage.locator('#agree').check();
   await bpage.locator('#send').click();
   await bpage.getByText('事前相談を送信しました。').waitFor({timeout:20000});
   await mpage.reload({waitUntil:'domcontentloaded'});
   await mpage.waitForFunction(()=>document.querySelector('#inquiries')?.textContent.includes('山田'),null,{timeout:20000});
   const latest=await api(manager,'GET','/planned-litters/inquiries');
   const ownInquiry=latest.filter(x=>x.planned_litter_id===lid);
   assert.equal(ownInquiry.length,1,'received buyer interest');
   assert.equal(ownInquiry[0].preferred_gender,'女の子');
   // Managing visibility must immediately hide the public listing.
   await mpage.locator('#listings article.item').filter({hasText:title}).getByRole('button',{name:'非公開に変更'}).click();
   await mpage.waitForFunction(text=>[...document.querySelectorAll('#listings article.item')].some(x=>x.textContent.includes(text)&&x.textContent.includes('非公開')),title,{timeout:20000});
   await publicPage.goto(url+'/planned-litters.html',{waitUntil:'domcontentloaded'});
   await publicPage.getByText('現在、受付中の出産予定はありません。').waitFor({timeout:20000});
   for(const [page,where] of [[mpage,'manage'],[bpage,'buyer'],[publicPage,'public']]){
      const width=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
      assert(width.scroll<=width.viewport+20,label+' '+where+' mobile overflow '+JSON.stringify(width));
   }
   // Operator dashboard stays yellow, but operator proxying the breeder manager keeps the breeder page blue.
   const operator=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
   await login(operator,'admin@bigpaw.jp','admin1234');
   const opage=await operator.newPage();
   opage.on('pageerror',e=>errors.push('operator: '+e.message));
   await opage.goto(url+'/operator-admin.html',{waitUntil:'domcontentloaded'});
   const operatorTheme=await opage.evaluate(()=>({
     theme:document.documentElement.getAttribute('data-bp-page-theme'),
     bodyBg:getComputedStyle(document.body).backgroundColor
   }));
   assert.equal(operatorTheme.theme,'operator',label+' operator dashboard theme');
   assert.equal(operatorTheme.bodyBg,'rgb(255, 251, 234)',label+' operator dashboard must remain yellow');
   await opage.goto(url+'/planned-litter-manage.html?breederId=b_dog44',{waitUntil:'domcontentloaded'});
   await opage.locator('#listings').waitFor();
   await opage.waitForFunction(()=>document.querySelector('#listings')&&!document.querySelector('#listings').textContent.includes('読み込み中'),null,{timeout:20000});
   await assertBreederBlue(opage,label+' operator proxy breeder manager');
   await opage.locator('#bigpaw-operator-review-banner').waitFor({state:'visible',timeout:10000});
   assert((await opage.locator('#bigpaw-operator-review-banner').textContent()).includes('運営確認モード'));

   // Desktop-sized browser check covers PC/desktop Safari layout as well as the mobile checks above.
   const desktop=await browser.newContext({viewport:{width:1440,height:900}});
   await login(desktop,'dog44@bigpaw.jp','demo1234');
   const dpage=await desktop.newPage();
   dpage.on('pageerror',e=>errors.push('desktop: '+e.message));
   await dpage.goto(url+'/planned-litter-manage.html',{waitUntil:'domcontentloaded'});
   await dpage.locator('#listings').waitFor();
   await dpage.waitForFunction(()=>document.querySelector('#listings')&&!document.querySelector('#listings').textContent.includes('読み込み中'),null,{timeout:20000});
   await assertBreederBlue(dpage,label+' breeder desktop manager');
   const desktopWidth=await dpage.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
   assert(desktopWidth.scroll<=desktopWidth.viewport+20,label+' desktop overflow '+JSON.stringify(desktopWidth));

   assert(!errors.length,label+' browser errors: '+errors.join('; '));
   console.log('PLANNED_LITTER_BROWSER_OK '+label+' mobile+desktop blue breeder theme, yellow operator dashboard, operator proxy, form, public listing, buyer inquiry, private status');
   await desktop.close();await operator.close();await buyer.close();await publicContext.close();await manager.close();
 }finally{await browser.close()}
}
(async()=>{await check(chromium,'chromium');await check(webkit,'webkit')})().catch(e=>{console.error(e);process.exit(1)});
