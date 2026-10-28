#!/usr/bin/env node
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const BASE='http://127.0.0.1:18087';
const oldRequest='オンライン見学を希望\n第1希望 2026-11-01 14:00';
const fixture=(message,kind)=>({id:'q_test',puppy_id:'p_test',name:'テスト購入者',puppy_name:'テスト子犬',breeder_name:'犬舎',status:'未返信',preferred_date:kind==='inperson'?'2026-11-01':'',message});
async function stub(page,inquiry){
 const posts=[];
 await page.route('**/api/**',async route=>{
   const url=new URL(route.request().url()),path=url.pathname,method=route.request().method();
   if(method!=='GET')posts.push({path,body:route.request().postDataJSON()});
   let value,code=200;
   if(path==='/api/puppies/p_test')value={id:'p_test',name:'テスト子犬',breed:'スタンダードプードル',color:'ブラック',gender:'男の子',breeder:'犬舎'};
   else if(path==='/api/me')value={id:'u_test',role:'buyer',email:'buyer@example.test'};
   else if(path==='/api/inquiries'&&method==='GET')value=[inquiry||fixture('オンラインでの相談を希望（LINE・FaceTimeなど）','online')];
   else if(path==='/api/inquiries'&&method==='POST')value={id:'q_test'};
   else if(path==='/api/inquiries/q_test/messages')value=[];
   else if(path==='/api/health')value={ok:true,videoConfigured:false};
   else if(path==='/api/notifications')value=[];
   else if(path==='/api/breeder/invoices')value=[];
   else if(path==='/api/inquiries/q_test/visit')value=null;
   else {value={error:'missing_test_fixture',path};code=404}
   await route.fulfill({status:code,contentType:'application/json',body:JSON.stringify(value)});
 });
 return posts;
}
async function buyer(browser,name){
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const posts=await stub(page);
 await page.goto(BASE+'/inquiry.html?id=p_test');
 await page.waitForFunction(()=>document.querySelector('#puppyLabel')?.textContent.includes('犬舎'));
 const online=page.locator('#kind');
 await online.selectOption({label:'オンラインでの相談を希望（LINE・FaceTimeなど）'});
 assert.equal(await page.locator('#visitDateField1').isVisible(),false);
 assert.equal(await page.locator('#visitDateField2').isVisible(),false);
 assert.equal(await page.locator('#externalVideoHelp').isVisible(),true);
 assert.match(await page.locator('#externalVideoHelp').innerText(),/LINEやFaceTime/);
 await page.locator('#name').fill('テスト購入者');
 await page.locator('#phone').fill('09000000000');
 await page.locator('#email').fill('buyer@example.test');
 await page.locator('#message').fill('LINEで相談したいです');
 await page.locator('input[type=checkbox]').check();
 page.on('dialog',d=>d.accept());
 await page.locator('#submitInquiryBtn').click();
 await page.waitForFunction(()=>location.pathname.endsWith('messages.html')&&location.search.includes('q_test'));
 const inquiryPosts=posts.filter(p=>p.path==='/api/inquiries');
 assert.equal(inquiryPosts.length,1,name+' online should send exactly one ordinary inquiry');
 assert.equal(inquiryPosts[0].body.preferredDate,'');
 assert.match(inquiryPosts[0].body.message,/LINEで相談したいです/);
 assert.doesNotMatch(inquiryPosts[0].body.message,/第1希望/);
 assert.equal(posts.filter(p=>/\/visit$|\/video-room$/.test(p.path)).length,0);
 await page.close();
 
 const local=await browser.newPage({viewport:{width:390,height:844}});
 const localPosts=await stub(local);
 await local.goto(BASE+'/inquiry.html?id=p_test');
 await local.waitForFunction(()=>document.querySelector('#puppyLabel')?.textContent.includes('犬舎'));
 assert.equal(await local.locator('#visitDateField1').isVisible(),true);
 await local.locator('#date1').fill('2026-11-01');
 await local.locator('#preferredTime1').fill('14:00');
 await local.locator('#name').fill('テスト購入者');
 await local.locator('#phone').fill('09000000000');
 await local.locator('#email').fill('buyer@example.test');
 await local.locator('input[type=checkbox]').check();
 local.on('dialog',d=>d.accept());
 await local.locator('#submitInquiryBtn').click();
 await local.waitForFunction(()=>location.pathname.endsWith('messages.html')&&location.search.includes('q_test'));
 assert.equal(localPosts.filter(p=>p.path==='/api/inquiries').length,1);
 assert.equal(localPosts.find(p=>p.path==='/api/inquiries').body.preferredDate,'2026-11-01');
 assert.match(localPosts.find(p=>p.path==='/api/inquiries').body.message,/第1希望 2026-11-01 14:00/);
 await local.close();
 console.log('EXTERNAL_VIDEO_BUYER_OK|'+name);
}
async function breeder(browser,name){
 const page=await browser.newPage({viewport:{width:390,height:844}});
 await stub(page,fixture(oldRequest,'online'));
 await page.goto(BASE+'/breeder-inquiries.html');
 await page.waitForFunction(()=>document.querySelector('#inquiryList')?.textContent.includes('テスト購入者'));
 assert.match(await page.locator('#inquiryList').innerText(),/LINE・FaceTime/);
 assert.equal(await page.locator('.bp-visit-action').count(),0,'online consult cannot be confirmed as BIG PAW visit');
 assert.equal(await page.locator('a[href*="online-visit.html"]').count(),0);
 assert.equal(await page.locator('#visits').innerText(),'0件');
 assert.equal(await page.locator('a[href="messages.html?inquiry=q_test"]').count(),1);
 await page.close();
 const inperson=await browser.newPage({viewport:{width:390,height:844}});
 await stub(inperson,fixture('現地で見学を希望\n第1希望 2026-11-01 14:00','inperson'));
 await inperson.goto(BASE+'/breeder-inquiries.html');
 await inperson.waitForFunction(()=>document.querySelector('#inquiryList')?.textContent.includes('テスト購入者'));
 assert.equal(await inperson.locator('.bp-visit-action').count(),1,'in-person visit must retain schedule control');
 assert.equal(await inperson.locator('#visits').innerText(),'1件');
 await inperson.close();
 const direct=await browser.newPage({viewport:{width:390,height:844}});
 const posts=await stub(direct);
 await direct.goto(BASE+'/online-visit.html?inquiry=q_test');
 assert.match(await direct.locator('#onlineGuide').innerText(),/予約・日時確定・ビデオ通話ルームの提供は行っていません/);
 assert.equal(await direct.locator('input[type=date],input[type=time],button#requestVideoBtn,button#joinBtn').count(),0);
 assert.match(await direct.locator('#onlineGuide').innerText(),/LINE・FaceTime/);
 assert.equal(await direct.locator('#conversationLink').getAttribute('href'),'messages.html?inquiry=q_test');
 assert.equal(posts.length,0);
 await direct.close();
 console.log('EXTERNAL_VIDEO_BREEDER_OK|'+name);
}
(async()=>{
 const fs=require('node:fs'),path=require('node:path');
 const dir=path.join(__dirname,'..','app');
 const msg=fs.readFileSync(path.join(dir,'messages.html'),'utf8');
 assert.ok(!msg.includes('id="onlineVisit"'),'remove old booking CTA from shared message page');
 assert.ok(!msg.includes('onlineVisitRequestNotice'),'remove old booking alert script');
 assert.ok(!msg.includes("onlineVisit.href='online-visit.html"),'do not navigate to managed booking');
 assert.ok(msg.includes('LINE・FaceTimeなどでのオンライン相談'),'keep direct-call guidance');
 const all=[
  ['chromium',chromium],
  ['iphone_webkit',webkit]
 ];
 for(const [name,type] of all){
   const browser=await type.launch({headless:true});
   try{await buyer(browser,name);await breeder(browser,name)}finally{await browser.close()}
 }
})().catch(e=>{console.error(e);process.exit(1)});
