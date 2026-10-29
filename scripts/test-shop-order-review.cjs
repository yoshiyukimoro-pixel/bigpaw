/* Browser regression: staging-only order review does not create orders or charge cards. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium,webkit} = require('playwright');

const root = path.resolve('app');
let unsafeRequests = 0;
const server = http.createServer((req,res) => {
  if(req.method!=='GET' && req.method!=='HEAD'){
    unsafeRequests++;
    res.writeHead(405).end(); return;
  }
  let url;
  try{url=new URL(req.url,'http://127.0.0.1');}catch(_){res.writeHead(400).end();return;}
  const location=path.resolve(root,'.'+decodeURIComponent(url.pathname));
  if(!location.startsWith(root+path.sep)){
    res.writeHead(403).end();return;
  }
  let bytes;
  try{bytes=fs.readFileSync(location);}catch(_){res.writeHead(404).end();return;}
  const mime=location.endsWith('.css')?'text/css':
    location.endsWith('.js')?'text/javascript':
    location.endsWith('.webp')?'image/webp':'text/html';
  res.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'});
  res.end(bytes);
});
(async()=>{
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  const base='http://127.0.0.1:'+server.address().port;
  try{
    for(const [name,browserType] of [['Chromium',chromium],['iPhone Safari WebKit',webkit]]){
      const browser=await browserType.launch({headless:true});
      try{
        const page=await browser.newPage({viewport:name==='Chromium'?
          {width:1280,height:900}:{width:390,height:844}});
        const errors=[];
        page.on('pageerror',e=>errors.push(e.message));
        await page.goto(base+'/shop.html?item=A02');
        await page.locator('#previewAddToCart').click();
        assert.equal(await page.locator('#previewCartCount').innerText(),'1');
        await page.locator('#previewReviewOrder').click();
        await page.waitForURL('**/shop.html?order=review');
        assert.equal(await page.locator('#orderReview').isVisible(),true);
        assert.equal(await page.locator('#listing').isVisible(),false);
        assert.equal(await page.locator('#single').isVisible(),false);
        assert.match(await page.locator('#orderReviewItems').innerText(),/パピーラージ/);
        assert.match(await page.locator('#orderReviewTotal').innerText(),/21,450円/);
        assert.match(await page.locator('.order-summary-row .free').innerText(),/0円/);
        assert.match(await page.locator('#orderAddressTitle').innerText(),/お届け先/);
        assert.match(await page.locator('.order-status').first().innerText(),/Square/);
        assert.equal(await page.locator('#previewCheckout').isDisabled(),true);
        assert.equal(await page.locator('#orderConfirmPreview').isDisabled(),true);
        await page.locator('#orderConfirmChecked').check();
        assert.equal(await page.locator('#orderConfirmPreview').isEnabled(),true);
        await page.locator('#orderConfirmPreview').click();
        assert.match(await page.locator('#orderPreviewConfirmation').innerText(),/注文・決済はまだ行われていません/);
        assert.equal(await page.locator('#previewCheckout').isDisabled(),true);
        await page.locator('#orderEditCart').click();
        assert.equal(await page.locator('#previewCartDialog').isVisible(),true);
        await page.locator('button[data-action="plus"]').click();
        assert.match(await page.locator('#orderReviewTotal').innerText(),/42,900円/);
        assert.equal(await page.locator('#orderConfirmPreview').isDisabled(),true,
          'a cart mutation requires amount reconfirmation');
        await page.locator('#previewCartContinue').click();
        await page.locator('#orderConfirmChecked').check();
        assert.equal(await page.locator('#orderConfirmPreview').isEnabled(),true);
        const horizontal=await page.evaluate(()=>
          document.documentElement.scrollWidth - document.documentElement.clientWidth);
        assert(horizontal<=2,name+' has unwanted horizontal scrolling: '+horizontal);
        await page.evaluate(()=>sessionStorage.setItem('bigpaw_shop_preview_cart_v1',
          JSON.stringify({A02:10,Z01:10,C03:10,O07:10,Z06:10,O06:10,O03:10})));
        await page.reload();
        assert.equal(await page.locator('#orderReviewLimit').isVisible(),true,
          'order limit must be enforced in review UI');
        assert.equal(await page.locator('#orderConfirmPreview').isDisabled(),true);
        await page.evaluate(()=>sessionStorage.removeItem('bigpaw_shop_preview_cart_v1'));
        await page.reload();
        assert.equal(await page.locator('#orderReviewEmpty').isVisible(),true);
        assert.equal(await page.locator('#orderReviewContent').isVisible(),false);
        assert.equal(await page.locator('#previewCheckout').isDisabled(),true);
        assert.deepEqual(errors,[],name+' unexpected JavaScript exceptions');
        console.log('SHOP_ORDER_REVIEW_OK|'+name+'|zero_shipping|price_integrity|no_checkout');
      }finally{await browser.close();}
    }
    assert.equal(unsafeRequests,0,'review UI must not POST or create orders');
  } finally {await new Promise(ok=>server.close(ok));}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
