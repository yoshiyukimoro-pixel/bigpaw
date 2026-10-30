'use strict';
/* Browser-only preview of fictional future orders. No real Square calls. */
const assert = require('node:assert/strict');
const http = require('node:http');
const {execFileSync} = require('node:child_process');
const {chromium,webkit} = require('playwright');

// Python's real read-only renderer produces the exact HTML shown in staging.
// The temporary SQLite path does not exist, so the page uses two clearly
// fictitious cards and zero counted actual orders.
const preview = execFileSync('python3', ['-c', [
  'import os, tempfile',
  'from shop_payments.live_order_ledger import LiveOrderLedger',
  'from shop_payments.staging_live_overview_page import render_order_overview_preview',
  'with tempfile.TemporaryDirectory() as d:',
  ' print(render_order_overview_preview(LiveOrderLedger(os.path.join(d,"offline.sqlite"))))',
].join('\n')], {encoding:'utf8', env:{...process.env,PYTHONPATH:'.'}});
assert(preview.includes('DEMO-ORDER-001'));
let mutations=0;
const server=http.createServer((req,res)=>{
  if(req.method!=='GET') {mutations++;res.writeHead(405).end();return;}
  if(req.url!=='/shop-live-orders-preview.html'){
    res.writeHead(404).end();return;
  }
  res.writeHead(200,{
    'Content-Type':'text/html; charset=utf-8',
    'Cache-Control':'no-store',
    'X-Robots-Tag':'noindex,nofollow',
  });res.end(preview);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port+'/shop-live-orders-preview.html';
  try{
    for(const [name,browserType] of [
      ['Chromium',chromium],['iPhone Safari WebKit',webkit]
    ]){
      const browser=await browserType.launch({headless:true});
      try{
        const page=await browser.newPage({
          viewport:name==='Chromium'?{width:1280,height:850}:{width:390,height:844},
        });
        const exceptions=[];
        page.on('pageerror',err=>exceptions.push(err.message));
        await page.goto(url);
        assert.match(await page.title(),/注文管理の表示確認/);
        assert.match(await page.locator('main').innerText(),/これは管理画面の表示テスト/);
        assert.match(await page.locator('.sample').innerText(),/架空の注文/);
        assert.equal(await page.locator('.sample .order').count(),2);
        assert.equal(await page.locator('.stats .stat strong').first().innerText(),'0');
        assert.equal(await page.locator('form').count(),0);
        assert.equal(await page.locator('button').count(),0);
        assert.match(await page.locator('.sample').innerText(),/返金・入金状態は未確認/);
        const overflow=await page.evaluate(()=>
          document.documentElement.scrollWidth-document.documentElement.clientWidth);
        assert(overflow<=2,name+' horizontal scroll overflow: '+overflow);
        assert.deepEqual(exceptions,[]);
        console.log('SHOP_OPERATOR_PREVIEW_OK|'+name+'|fictitious_cards|zero_orders|read_only');
      }finally{await browser.close();}
    }
    assert.equal(mutations,0);
  }finally{await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);server.close();process.exit(1);});
