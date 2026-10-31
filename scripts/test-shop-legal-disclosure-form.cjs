/* BIG PAW food-shop legal seller-contact request, PC and iPhone browser.
 * Local mock API only. No real mail, seller PII, customers or payment.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const root=path.resolve('app');
let writes=0;
const server=http.createServer((req,res)=>{
  if(!['GET','HEAD'].includes(req.method)){writes++;res.writeHead(405).end();return;}
  let url;
  try{url=new URL(req.url,'http://127.0.0.1');}catch(_){res.writeHead(400).end();return;}
  let requested;
  try{requested=path.resolve(root,'.'+decodeURIComponent(url.pathname));}
  catch(_){res.writeHead(400).end();return;}
  if(!requested.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  let data;
  try{data=fs.readFileSync(requested);}catch(_){res.writeHead(404).end();return;}
  const mime=requested.endsWith('.js')?'text/javascript':
    requested.endsWith('.css')?'text/css':'text/html';
  res.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'});res.end(data);
});
(async()=>{
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  const base='http://127.0.0.1:'+server.address().port;
  try{
    const admin=fs.readFileSync(path.resolve(root,'operator-support.html'),'utf8');
    const backend=fs.readFileSync(path.resolve(root,'backend/server.py'),'utf8');
    assert(admin.includes('【要対応・特商法】フードショップの住所・電話番号の開示請求'));
    assert(admin.includes("'/operator/support/'+encodeURIComponent(id)+'/reply'"));
    assert(backend.includes("if path=='/api/support':"));
    assert(backend.includes("'support_ticket_created'"));
    assert(backend.includes("if category=='ドッグフードショップ販売者情報の開示請求':"));
    assert(backend.includes("notify_targets.add('info@bigpaw.site')"),
      'request must notify the dedicated owner mailbox even without an operator account');
    assert(backend.includes("if rate_limited('support:'+self.client_address[0],5,3600)"),
      'the existing support endpoint must continue to rate-limit public requests');
    for(const [label,browserType] of [['PC Chromium',chromium],['iPhone Safari WebKit',webkit]]){
      const browser=await browserType.launch({headless:true});
      try{
        const page=await browser.newPage({viewport:label.startsWith('PC')?
          {width:1280,height:900}:{width:390,height:844}});
        const errors=[],posted=[];
        page.on('pageerror',error=>errors.push(error.message));
        await page.route('**/api/support',route=>{
          assert.equal(route.request().method(),'POST');
          posted.push(route.request().postDataJSON());
          return route.fulfill({status:201,contentType:'application/json',
            body:JSON.stringify({id:'sup_TEST123456',status:'open'})});
        });
        await page.goto(base+'/shop-commerce.html');
        const link=page.locator('a[href="contact.html?topic=shop-legal-disclosure"]');
        assert.equal(await link.count(),1);
        await link.click();
        await page.waitForURL('**/contact.html?topic=shop-legal-disclosure');
        assert.match(await page.locator('h1').innerText(),/フードショップ/);
        assert.equal(await page.locator('#category').inputValue(),
          'ドッグフードショップ販売者情報の開示請求');
        assert.match(await page.locator('#subject').inputValue(),/販売者住所・電話番号/);
        assert.match(await page.locator('#message').inputValue(),/開示を希望/);
        assert.match(await page.locator('form .notice').last().innerText(),/自動開示ではありません/);
        await page.locator('#name').fill('TEST ONLY');
        await page.locator('#email').fill('customer@example.invalid');
        await page.locator('button[type="submit"]').click();
        await page.locator('#result .notice').waitFor({state:'visible',timeout:10000});
        assert.match(await page.locator('#result').innerText(),/受付番号：sup_TEST123456/);
        assert.equal(posted.length,1);
        const request=posted[0];
        assert.equal(request.category,'ドッグフードショップ販売者情報の開示請求');
        assert.equal(request.email,'customer@example.invalid');
        assert.match(request.message,/開示を希望/);
        assert.deepEqual(Object.keys(request).sort(),['category','email','message','name','subject']);
        assert(!/\b0[789]0[- ]?\d{4}[- ]?\d{4}\b/.test(JSON.stringify(request)));
        assert(!/\b\d{3}-\d{4}\b/.test(JSON.stringify(request)));
        assert.equal(await page.locator('#category').inputValue(),
          'ドッグフードショップ販売者情報の開示請求');
        await page.goto(base+'/contact.html');
        assert.equal(await page.locator('#category').inputValue(),'サイト利用について',
          'regular contact requests must not become disclosure tickets');
        assert.deepEqual(errors,[],label+' JavaScript exceptions');
        console.log('SHOP_LEGAL_DISCLOSURE_FORM_OK|'+label+'|numbered_ticket|operator_review|no_auto_pii_send');
      }finally{await browser.close();}
    }
    assert.equal(writes,0,'No external POST; all submission calls must be mocked');
  }finally{await new Promise(ok=>server.close(ok));}
})().catch(e=>{console.error(e);server.close();process.exit(1)});
