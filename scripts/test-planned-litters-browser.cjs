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
async function check(engine,label){
 const browser=await engine.launch({headless:true,...(label==='chromium'&&chromePath()?{executablePath:chromePath(),args:['--no-sandbox']}: {})});
 try{
   const manager=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
   const errors=[];
   const mpage=await manager.newPage();
   mpage.on('pageerror',e=>errors.push('manage: '+e.message));
   await login(manager,'dog44@bigpaw.jp','demo1234');
   await mpage.goto(url+'/admin.html',{waitUntil:'domcontentloaded'});
   await mpage.locator('a.dashboard-action[href="planned-litter-manage.html"]').waitFor({state:'visible',timeout:20000});
   // The new feature must be reachable even if the mobile sidebar is hidden.
   await mpage.locator('a.dashboard-action[href="planned-litter-manage.html"]').click();
   await mpage.waitForURL('**/planned-litter-manage.html');
   await mpage.locator('#listings').waitFor();
   await mpage.waitForFunction(()=>document.querySelector('#listings')&&!document.querySelector('#listings').textContent.includes('読み込み中'),null,{timeout:20000});
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
   assert(!errors.length,label+' browser errors: '+errors.join('; '));
   console.log('PLANNED_LITTER_BROWSER_OK '+label+' mobile form, public listing, buyer inquiry, private status');
   await buyer.close();await publicContext.close();await manager.close();
 }finally{await browser.close()}
}
(async()=>{await check(chromium,'chromium');await check(webkit,'webkit')})().catch(e=>{console.error(e);process.exit(1)});
