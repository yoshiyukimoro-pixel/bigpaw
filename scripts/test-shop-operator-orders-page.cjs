'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium, webkit} = require('playwright');

const html = fs.readFileSync(path.join(__dirname, '../app/operator-shop-orders.html'), 'utf8');
const sample = {read_only:true,count:1,orders:[{
  order_id:'FOOD0123456789abcdef0123456789abcdef',amount_yen:21450,
  created_at:1793390000,paid_at:1793390050,payment_recorded_historically:true,
  current_payment_status:'not_checked',manual_square_check_required:true,
  verified_signed_event_count:1,
  items:[{sku:'A02',name:'ACANA アダルトラージ',size:'11.4kg',qty:1,unit_yen:21450}],
}]};
let authorized = false;
const server = http.createServer((req,res)=>{
  if(req.url==='/operator-shop-orders.html'){
    res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store'});res.end(html);return;
  }
  if(req.url==='/assets/style.css'||req.url==='/assets/account-page-theme.css'){
    res.writeHead(200,{'content-type':'text/css'});res.end('');return;
  }
  if(req.url==='/api/operator/shop-orders'){
    res.writeHead(authorized?200:401,{'content-type':'application/json','cache-control':'no-store'});
    res.end(authorized?JSON.stringify(sample):JSON.stringify({error:'unauthorized'}));return;
  }
  res.writeHead(404).end();
});

(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  for(const [name,type,viewport] of [
    ['Chromium',chromium,{width:1280,height:900}],
    ['iPhone Safari WebKit',webkit,{width:390,height:844}],
  ]){
    const browser=await type.launch({headless:true});
    try{
      const page=await browser.newPage({viewport});
      await page.goto(base+'/operator-shop-orders.html');
      await page.getByText('運営アカウントでログインしてください。').waitFor();
      authorized=true;
      await page.getByRole('button',{name:'再読み込み'}).click();
      await page.getByText(/表示中 1件/).waitFor();
      assert.match(await page.locator('main').innerText(),/過去にSquare入金確認あり/);
      assert.match(await page.locator('main').innerText(),/現在の決済・返金状況はSquareで個別確認が必要/);
      await page.getByText(/注文商品を表示/).click();
      assert.match(await page.locator('main').innerText(),/ACANA アダルトラージ/);
      assert.equal(await page.locator('main').innerText().then(t=>/東京都|〒[0-9]{3}-[0-9]{4}|090-[0-9-]{8,}|buyer@example\.com|4111[ -]?1111/.test(t)),false);
      console.log(name+': operator order list UI OK');
    } finally { await browser.close(); authorized=false; }
  }
})().catch(err=>{console.error(err);process.exitCode=1;}).finally(()=>server.close());
