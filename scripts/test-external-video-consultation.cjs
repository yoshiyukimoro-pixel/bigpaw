#!/usr/bin/env node
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const BASE='http://127.0.0.1:18087';
const oldRequest='オンライン見学を希望（LINE・FaceTimeなど）\n第1希望 2026-11-01 14:00\n第2希望 2026-11-02 11:30';
const fixture=(message,kind)=>({id:'q_test',puppy_id:'p_test',name:'テスト購入者',puppy_name:'テスト子犬',breeder_name:'犬舎',status:'未返信',preferred_date:kind==='inperson'?'2026-11-01':'',message});
async function stub(page,inquiry,role='buyer'){
 const posts=[];
 await page.route('**/api/**',async route=>{
   const url=new URL(route.request().url()),path=url.pathname,method=route.request().method();
   if(method!=='GET')posts.push({path,body:route.request().postDataJSON()});
   let value,code=200;
   if(path==='/api/puppies/p_test')value={id:'p_test',name:'テスト子犬',breed:'スタンダードプードル',color:'ブラック',gender:'男の子',breeder:'犬舎'};
   else if(path==='/api/me')value={id:'u_test',role,email:'buyer@example.test'};
   else if(path==='/api/inquiries'&&method==='GET')value=[inquiry||fixture(oldRequest,'online')];
   else if(path==='/api/inquiries'&&method==='POST')value={id:'q_test'};
   else if(path==='/api/inquiries/q_test/messages')value=[];
   else if(path==='/api/health')value={ok:true,videoConfigured:false};
   else if(path==='/api/notifications')value=[];
   else if(path==='/api/breeder/invoices')value=[];
   else if(path==='/api/inquiries/q_test/visit'&&method==='GET')value=null;
   else if(path==='/api/inquiries/q_test/visit'&&method==='POST')value={id:'v_test',status:'confirmed'};
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
 await online.selectOption({label:'オンライン見学を希望（LINE・FaceTimeなど）'});
 assert.equal(await page.locator('#visitDateField1').isVisible(),true);
 assert.equal(await page.locator('#visitDateField2').isVisible(),true);
 await page.locator('#date1').fill('2026-11-01');
 await page.locator('#preferredTime1').fill('14:00');
 await page.locator('#date2').fill('2026-11-02');
 await page.locator('#preferredTime2').fill('11:30');
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
 assert.equal(inquiryPosts[0].body.preferredDate,'2026-11-01');
 assert.match(inquiryPosts[0].body.message,/LINEで相談したいです/);
 assert.match(inquiryPosts[0].body.message,/第1希望 2026-11-01 14:00/);
 assert.match(inquiryPosts[0].body.message,/第2希望 2026-11-02 11:30/);
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
 const onlinePosts=await stub(page,fixture(oldRequest,'online'),'breeder');
 await page.goto(BASE+'/breeder-inquiries.html');
 await page.waitForFunction(()=>document.querySelector('#inquiryList')?.textContent.includes('テスト購入者'));
 assert.match(await page.locator('#inquiryList').innerText(),/LINE・FaceTime/);
 assert.equal(await page.locator('.bp-visit-action').count(),1,'online visit also requires breeder date confirmation');
 assert.equal(await page.locator('a[href*="online-visit.html"]').count(),0);
 assert.equal(await page.locator('#visits').innerText(),'1件');
 assert.match(await page.locator('#inquiryList').innerText(),/第1希望 2026-11-01 14:00/);
 assert.match(await page.locator('#inquiryList').innerText(),/第2希望 2026-11-02 11:30/);
 assert.equal(await page.locator('a[href="messages.html?inquiry=q_test"]').count(),1);
 const msgPage=await browser.newPage({viewport:{width:390,height:844}});
 await stub(msgPage,fixture(oldRequest,'online'),'breeder');
 await msgPage.goto(BASE+'/messages.html?inquiry=q_test');
 await msgPage.waitForFunction(()=>document.querySelector('#who')?.textContent.includes('テスト購入者'));
 assert.equal(await msgPage.locator('#visitLink').isVisible(),true,'online visit must retain its date confirmation action');
 assert.match(await msgPage.locator('#stepHint').innerText(),/第1・第2希望日時/);
 await msgPage.close();
 await page.locator('.bp-visit-action').click();
 await page.waitForURL('**/visit-confirm.html?inquiry=q_test');
 await page.waitForFunction(()=>document.querySelector('#visitRequestSummary')?.textContent.includes('第2希望'));
 assert.match(await page.locator('#visitRequestSummary').innerText(),/第2希望：2026-11-02 11:30/);
 assert.equal(await page.locator('#visitDate').inputValue(),'2026-11-01');
 assert.equal(await page.locator('#visitTime').inputValue(),'14:00');
 assert.equal(await page.locator('#remoteVisitNotice').isVisible(),true);
 assert.equal(await page.locator('#transportField').isVisible(),false);
 page.on('dialog',d=>d.accept());
 await page.locator('#saveVisitBtn').click();
 await page.waitForURL('**/messages.html?inquiry=q_test');
 const confirmed=onlinePosts.find(p=>p.path==='/api/inquiries/q_test/visit');
 assert.ok(confirmed,'online date confirmed by breeder');
 assert.equal(confirmed.body.date,'2026-11-01');
 assert.equal(confirmed.body.time,'14:00');
 assert.equal(confirmed.body.transport,'オンライン見学');
 assert.equal(confirmed.body.status,'confirmed');
 await page.close();
 const inperson=await browser.newPage({viewport:{width:390,height:844}});
 await stub(inperson,fixture('現地で見学を希望\n第1希望 2026-11-01 14:00','inperson'),'breeder');
 await inperson.goto(BASE+'/breeder-inquiries.html');
 await inperson.waitForFunction(()=>document.querySelector('#inquiryList')?.textContent.includes('テスト購入者'));
 assert.equal(await inperson.locator('.bp-visit-action').count(),1,'in-person visit must retain schedule control');
 assert.equal(await inperson.locator('#visits').innerText(),'1件');
 await inperson.close();
 const direct=await browser.newPage({viewport:{width:390,height:844}});
 const posts=await stub(direct);
 await direct.goto(BASE+'/online-visit.html?inquiry=q_test');
 assert.match(await direct.locator('#onlineGuide').innerText(),/第1・第2希望日時をBIG PAWで送信/);
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
 const finalPatch=require('node:fs').readFileSync(require('node:path').resolve(__dirname,'../app/backend/final_patch.py'),'utf8');
 assert.ok(finalPatch.includes('LINE・FaceTimeなどのビデオ通話は当事者同士で行います'),'confirm old Jitsi text is replaced in final production patch');
 const all=[
  ['chromium',chromium],
  ['iphone_webkit',webkit]
 ];
 for(const [name,type] of all){
   const browser=await type.launch({headless:true});
   try{await buyer(browser,name);await breeder(browser,name)}finally{await browser.close()}
 }
})().catch(e=>{console.error(e);process.exit(1)});
