/* Offline-only Chromium/WebKit test of the dormant browser-to-server quote
 * checker. Every provider/API response is synthetic; no Square/payment call.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {chromium,webkit}=require('playwright');

const baseDir=path.resolve('app');
let unexpectedWrites=0;
let apiHits=0;
const server=http.createServer((req,res)=>{
  if(req.method!=='GET'&&req.method!=='HEAD'){
    unexpectedWrites++;
    res.writeHead(405).end();return;
  }
  const url=new URL(req.url,'http://127.0.0.1');
  if(url.pathname.startsWith('/api/')){
    apiHits++;
    res.writeHead(404).end();return;
  }
  let full;
  try {full=path.resolve(baseDir,'.'+decodeURIComponent(url.pathname));}
  catch (_) {res.writeHead(400).end();return;}
  if(!full.startsWith(baseDir+path.sep)){
    res.writeHead(403).end();return;
  }
  let body;
  try{body=fs.readFileSync(full);}
  catch(_){res.writeHead(404).end();return;}
  const mime=full.endsWith('.js')?'text/javascript':
    full.endsWith('.css')?'text/css':
    full.endsWith('.webp')?'image/webp':'text/html';
  res.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'});
  res.end(body);
});

const TERMS='a'.repeat(64), CSRF='b'.repeat(64);
const rows=[{sku:'A02',quantity:1,unitYen:21450,lineYen:21450}];
const quote=()=>({
  server_verified:true,payment_link_created:false,
  currency:'JPY',terms_sha256:TERMS,
  line_items:[{sku:'A02',name:'パピーラージブリードレシピ',
              size:'11.4kg',quantity:1,unit_yen:21450,line_yen:21450}],
  subtotal_yen:21450,shipping_yen:0,amount_yen:21450
});
const config=()=>({
  ready:true,shipping_included:true,approved_terms_sha256:TERMS,
  csrf_token:CSRF
});
async function attempt(page,overrides={}){
  return page.evaluate(async args=>{
    try{
      const value=await window.BigPawShopQuote.verify({
        rows:args.rows,displayedAmountYen:args.amount,
        approvedTermsSha256:args.terms
      });
      return {ok:true,value};
    }catch(e){return {ok:false,reason:e.message};}
  },{rows:overrides.rows||rows,
     amount:overrides.amount===undefined?21450:overrides.amount,
     terms:overrides.terms===undefined?TERMS:overrides.terms});
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  try{
    for (const [label,engine] of [['Chromium',chromium],['iPhone Safari WebKit',webkit]]){
      const browser=await engine.launch({headless:true});
      try{
        const page=await browser.newPage({viewport:label==='Chromium'?
          {width:1280,height:900}:{width:390,height:844}});
        const jsErrors=[];
        page.on('pageerror',e=>jsErrors.push(e.message));
        await page.goto(origin+'/shop.html?order=review');
        assert.equal(await page.locator('#previewCheckout').isDisabled(),true);
        assert.equal(await page.evaluate(()=>typeof window.BigPawShopQuote.verify),'function');
        assert.equal(apiHits,0,'loading the storefront must not fetch checkout');
        let mockConfig=config(),mockQuote=quote(),posts=0,gets=0;
        await page.route('**/api/shop/checkout/config',route=>{
          gets++;
          const request=route.request();
          assert.equal(request.method(),'GET');
          return route.fulfill({status:200,contentType:'application/json',
                               body:JSON.stringify(mockConfig)});
        });
        await page.route('**/api/shop/checkout/quote',route=>{
          posts++;
          const request=route.request();
          assert.equal(request.method(),'POST');
          assert.equal(request.headers()['x-shop-csrf'],CSRF);
          assert.equal(request.headers()['content-type'],'application/json');
          assert.deepEqual(request.postDataJSON(),{
            cart:{A02:1},terms_sha256:TERMS
          });
          return route.fulfill({status:200,contentType:'application/json',
                               body:JSON.stringify(mockQuote)});
        });

        let result=await attempt(page);
        assert.equal(result.ok,true,JSON.stringify(result));
        assert.equal(result.value.amountYen,21450);
        assert.equal(result.value.shippingYen,0);
        assert.equal(posts,1);
        assert.equal(gets,1);

        // A local cart spoof is rejected before contacting any endpoint.
        let before=posts;
        result=await attempt(page,{amount:1});
        assert.equal(result.reason,'display_amount_mismatch');
        assert.equal(posts,before);
        for(const invalid of [
          [{sku:'X99',quantity:0,unitYen:21450,lineYen:0}],
          [{sku:'A02',quantity:1,unitYen:21450,lineYen:1}],
          [...rows,...rows]
        ]){
          result=await attempt(page,{rows:invalid});
          assert.equal(result.reason,'invalid_cart');
          assert.equal(posts,before);
        }
        // Terms must be supplied by the owner's displayed, signed-off text;
        // a server-returned hash is not an authorization substitute.
        result=await attempt(page,{terms:'0'.repeat(64)});
        assert.equal(result.reason,'seller_terms_not_approved');
        assert.equal(posts,before);
        mockConfig={...config(),approved_terms_sha256:'0'.repeat(64)};
        result=await attempt(page);
        assert.equal(result.reason,'seller_terms_not_approved');
        assert.equal(posts,before);
        mockConfig=config();

        for(const badQuote of [
          {...quote(),amount_yen:1},
          {...quote(),shipping_yen:999},
          {...quote(),payment_link_created:true},
          {...quote(),terms_sha256:'0'.repeat(64)},
          {...quote(),line_items:[{...quote().line_items[0],unit_yen:1,line_yen:1}]},
          {...quote(),line_items:[...quote().line_items,...quote().line_items]}
        ]){
          mockQuote=badQuote;
          result=await attempt(page);
          assert.equal(result.reason,'server_quote_mismatch');
        }
        mockQuote=quote();
        assert.equal(await page.locator('#previewCheckout').isDisabled(),true);
        assert.deepEqual(jsErrors,[]);
        console.log('SHOP_QUOTE_BROWSER_OK|'+label+
                    '|mocked_server_only|terms_cart_tax_shipping_match|no_checkout');
      }finally{await browser.close();}
    }
    assert.equal(unexpectedWrites,0,'no local HTTP POST may reach server');
    assert.equal(apiHits,0,'all API requests must be test mocks');
  }finally{await new Promise(done=>server.close(done));}
})().catch(error=>{console.error(error);server.close();process.exit(1);});
