'use strict';
/* Offline-only browser test of review -> Square Sandbox: no real charges. */
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');

const root=path.resolve('app');
const checkoutJs=fs.readFileSync('shop_payments/review_sandbox_checkout.js','utf8');
const previewHtml=fs.readFileSync('app/shop.html','utf8')
  .replace('</body>','<script src="shop-sandbox-review.js" defer></script></body>');
const checkoutPath='/api/shop/sandbox/checkout';
const fakeSquare='https://sandbox.square.link/u/BIGPAW_REVIEW_TEST_ONLY';
const testOrder='FOOD12345678901234567890123456789012';
const posted=[];
let ready=true,chargeState='payment_pending',wrongAmount=false;
let unsafeCalls=0;
const srv=http.createServer(async(req,res)=>{
  const u=new URL(req.url,'http://127.0.0.1');
  const route=u.pathname;
  const json=(value,code=200)=>{
    res.writeHead(code,{'Content-Type':'application/json','Cache-Control':'no-store'});
    res.end(JSON.stringify(value));
  };
  if(req.method==='GET' && route==='/api/shop/sandbox/config'){
    json({sandbox:true,ready,csrf_token:'mock-review-csrf',real_payments:false,shipping_included:true});
    return;
  }
  if(req.method==='GET' && route==='/api/shop/sandbox/order/'+testOrder){
    json({order_status:chargeState});return;
  }
  if(req.method==='POST' && route===checkoutPath){
    const parts=[];for await(const b of req)parts.push(b);
    const obj=JSON.parse(Buffer.concat(parts).toString());
    posted.push(obj);
    json({sandbox:true,checkout_url:fakeSquare,order_id:testOrder,
      amount_yen:wrongAmount?1:21450,shipping_yen:0});
    return;
  }
  if(req.method!=='GET'){unsafeCalls++;res.writeHead(404).end();return;}
  if(route==='/shop.html'){
    res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});
    res.end(previewHtml);return;
  }
  if(route==='/shop-sandbox-review.js'){
    res.writeHead(200,{'Content-Type':'text/javascript'});
    res.end(checkoutJs);return;
  }
  const filename=path.resolve(root,'.'+decodeURIComponent(route));
  if(!filename.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  try{
    const data=fs.readFileSync(filename);
    const type=filename.endsWith('.webp')?'image/webp':
      filename.endsWith('.css')?'text/css':
      filename.endsWith('.js')?'text/javascript':'text/html';
    res.writeHead(200,{'Content-Type':type});res.end(data);
  }catch(_){res.writeHead(404).end();}
});
(async()=>{
  await new Promise(ok=>srv.listen(0,'127.0.0.1',ok));
  const base='http://127.0.0.1:'+srv.address().port;
  try{
    for(const [name,type] of [['Chromium',chromium],['iPhone WebKit',webkit]]){
      const browser=await type.launch({headless:true});
      try{
        const page=await browser.newPage({viewport:name==='Chromium'?
          {width:1250,height:850}:{width:390,height:844}});
        const errors=[];page.on('pageerror',e=>errors.push(e.message));
        await page.route(fakeSquare,route=>route.fulfill({status:200,
          contentType:'text/html',body:'<h1>Sandbox Square test only</h1>'}));
        ready=false;wrongAmount=false;chargeState='payment_pending';
        await page.goto(base+'/shop.html?item=A02');
        await page.locator('#previewAddToCart').click();
        await page.locator('#previewReviewOrder').click();
        await page.waitForURL('**/shop.html?order=review');
        await page.waitForSelector('#squareReviewSandboxCheckout');
        assert.match(await page.locator('#orderCommerceTerms').innerText(),
          /返品・キャンセル・販売事業者/);
        assert.equal(await page.locator('a[href="shop-commerce.html"]').count(), 2,
          'shop footer and final review must both link to retail disclosures');
        assert.equal(await page.locator('#previewCheckout').isDisabled(),true,
          'public live checkout must stay disabled');
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isDisabled(),true);
        assert.match(await page.locator('#squareReviewSandboxNotice').innerText(),/未完了/);
        const before=posted.length;
        await page.locator('#orderConfirmChecked').check();
        await page.locator('#orderConfirmPreview').click();
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isDisabled(),true,
          'unconfigured Sandbox cannot start checkout');
        assert.equal(posted.length,before);
        ready=true;await page.reload();
        await page.waitForSelector('#squareReviewSandboxCheckout');
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isDisabled(),true,
          'must recheck after page refresh');
        await page.locator('#orderConfirmChecked').check();
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isDisabled(),true,
          'checkmark by itself cannot charge');
        await page.locator('#orderConfirmPreview').click();
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isEnabled(),true);
        await page.locator('#orderEditCart').click();
        await page.locator('button[data-action="plus"]').click();
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isDisabled(),true,
          'quantity change resets completed review');
        await page.locator('button[data-action="minus"]').click();
        await page.locator('#previewCartContinue').click();
        await page.locator('#orderConfirmChecked').check();
        await page.locator('#orderConfirmPreview').click();
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isEnabled(),true);

        wrongAmount=true;
        await page.locator('#squareReviewSandboxCheckout').click();
        await page.waitForFunction(()=>document.querySelector('#squareReviewSandboxNotice')?.textContent.includes('一致しません'));
        assert(page.url().startsWith(base),'amount mismatch blocks navigation to Square');
        assert.equal(posted.length,before+1);
        assert.deepEqual(Object.keys(posted.at(-1)).sort(),['attempt_id','cart']);
        assert.equal(posted.at(-1).cart.A02,1);
        // Failed attempt cannot be reused without reconfirmation.
        assert.equal(await page.locator('#squareReviewSandboxCheckout').isDisabled(),true);
        wrongAmount=false;
        await page.locator('#orderConfirmPreview').click();
        await page.locator('#squareReviewSandboxCheckout').click();
        await page.waitForURL(fakeSquare);
        assert.match(await page.locator('h1').innerText(),/Sandbox Square test/);
        assert.equal(posted.length,before+2);
        assert.equal(posted.at(-1).attempt_id,posted.at(-2).attempt_id,
          'same cart retries use same immutable attempt ID');
        await page.goto(base+'/shop.html?order=review');
        assert.equal(await page.locator('#squareReviewSandboxStatusCheck').isVisible(),true);
        assert.match(await page.locator('#squareReviewSandboxStatusResult').innerText(),/戻っただけでは入金済みとは判定しません/);
        await page.locator('#squareReviewSandboxStatusCheck').click();
        await page.waitForFunction(()=>document.querySelector('#squareReviewSandboxStatusResult')?.textContent.includes('決済確認待ち'));
        assert.match(await page.locator('#squareReviewSandboxStatusResult').innerText(),/確認待ち/);
        chargeState='paid';
        await page.locator('#squareReviewSandboxStatusCheck').click();
        await page.waitForFunction(()=>document.querySelector('#squareReviewSandboxStatusResult')?.textContent.includes('サーバーで確認済み'));
        assert.match(await page.locator('#squareReviewSandboxStatusResult').innerText(),/実際の入金ではありません/);
        assert.equal(await page.locator('#previewCheckout').isDisabled(),true);
        assert.deepEqual(errors,[],'uncaught browser errors');
        console.log('SHOP_REVIEW_SQUARE_SANDBOX_OK|'+name+'|confirm_first|amount_verify|status_safe');
      }finally{await browser.close();}
    }
    assert.equal(unsafeCalls,0,'no unexpected network mutations');
  }finally{await new Promise(ok=>srv.close(ok));}
})().catch(e=>{console.error(e);srv.close();process.exit(1)});
