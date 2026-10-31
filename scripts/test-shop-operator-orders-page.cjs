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
let auditEvents = [];
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
  if(req.url==='/api/operator/shop-orders/audit'){
    res.writeHead(authorized?200:401,{'content-type':'application/json','cache-control':'no-store'});
    res.end(authorized?JSON.stringify({events:auditEvents}):JSON.stringify({error:'unauthorized'}));return;
  }
  if(req.url==='/api/operator/shop-orders/reconcile-token'){
    res.writeHead(authorized?200:401,{'content-type':'application/json','cache-control':'no-store'});
    res.end(authorized?JSON.stringify({csrf_token:'A'.repeat(43)}):JSON.stringify({error:'unauthorized'}));return;
  }
  if(req.url==='/api/operator/shop-orders/shipping-address'&&req.method==='POST'){
    res.writeHead(authorized?200:401,{'content-type':'application/json','cache-control':'no-store'});
    res.end(authorized?JSON.stringify({temporary_view_only:true,recipient:{
      name:'PRIVATE <Buyer>',phone:'09012345678',postal:'100-0001',
      prefecture:'東京都',city:'千代田区',line1:'丸の内1-1-1',
      line2:'',line3:''}}):JSON.stringify({error:'unauthorized'}));return;
  }
  if(req.url==='/api/operator/shop-orders/reconcile'&&req.method==='POST'){
    auditEvents=[{order_id:sample.orders[0].order_id,actor_id:'operator_test',action:'payment_reconciled',outcome:'newly_paid',created_at:1793390100}];
    res.writeHead(authorized?200:401,{'content-type':'application/json','cache-control':'no-store'});
    res.end(authorized?JSON.stringify({state:'paid_verified',new_transition:true}):JSON.stringify({error:'unauthorized'}));return;
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
      auditEvents=[];
      await page.getByRole('button',{name:'再読み込み'}).click();
      await page.getByText(/表示中 1件/).waitFor();
      assert.match(await page.locator('main').innerText(),/過去にSquare入金確認あり/);
      assert.match(await page.locator('main').innerText(),/現在の決済・返金状況はSquareで個別確認が必要/);
      assert.equal(await page.locator('form.reconcile').count(),1);
      assert.match(await page.locator('form.reconcile').innerText(),/返金・発送・メール送信はしません/);
      assert.match(await page.locator('#audit').innerText(),/手動照合の記録はありません/);
      await page.getByText(/注文商品を表示/).click();
      assert.match(await page.locator('main').innerText(),/ACANA アダルトラージ/);
      assert.equal(await page.locator('main').innerText().then(t=>/東京都|〒[0-9]{3}-[0-9]{4}|090-[0-9-]{8,}|buyer@example\.com|4111[ -]?1111/.test(t)),false);
      page.on('dialog',dialog=>dialog.accept());
      const address=page.getByRole('button',{name:'お届け先を一時表示（運営者のみ）'});
      assert.equal(await address.count(),1);
      await address.click();
      const delivery=page.locator('.delivery-label');
      await delivery.getByText('PRIVATE <Buyer>').waitFor();
      assert.match(await delivery.innerText(),/東京都|千代田区/);
      assert.equal(await delivery.locator('script').count(),0,
        'Untrusted buyer name must be text, not script markup');
      await page.getByRole('button',{name:'配送先を隠す'}).click();
      assert.equal(await delivery.innerText(),'');
      assert.equal(await page.locator('.delivery-label:not([hidden])').count(),0);
      await page.locator('input[name="payment_id"]').fill('SYNTHETICPAYMENT123456');
      await page.getByRole('button',{name:'Squareと照合'}).click();
      await page.getByText('Squareで入金を新規確認し、監査記録を保存しました。').waitFor();
      assert.match(await page.locator('#audit').innerText(),/新規入金確認/);
      console.log(name+': operator order list UI OK');
    } finally { await browser.close(); authorized=false; }
  }
})().catch(err=>{console.error(err);process.exitCode=1;}).finally(()=>server.close());
