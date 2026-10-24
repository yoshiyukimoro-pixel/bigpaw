#!/usr/bin/env node
'use strict';
/* Test-only browser rendering of 3% promotional invoices.
 * All invoice records are synthetic API responses, never written to any database.
 * Covers current first-100 campaigns, historical frozen 3% waivers, and ordinary 8%.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {execSync}=require('node:child_process');
const {chromium,webkit}=require('playwright');
const origin=process.argv[2]||'http://127.0.0.1:18096';
function chromePath(){
 for(const name of ['google-chrome','google-chrome-stable','chromium','chromium-browser']){
  try{const p=execSync('command -v '+name,{encoding:'utf8'}).trim();if(p&&fs.existsSync(p))return p}catch(_e){}
 }
 throw Error('CHROME_MISSING');
}
const issued=1790000000,due=issued+7*86400;
const invoices=[
 {id:'test-campaign',invoice_no:'BP-TEST-CAMP',deal_id:'fixture-camp',status:'issued',
  puppy_name:'推しワン試験犬',breed:'スタンダードプードル',kennel_name:'試験犬舎',
  sale_amount:300000,rate_bps:300,fee_amount:9000,issued_at:issued,due_at:due,
  note:'BIG PAW 先着100頭成約キャンペーン・推しワン利用料3％（税込）'},
 {id:'test-legacy',invoice_no:'BP-TEST-LEGACY',deal_id:'fixture-legacy',status:'issued',
  puppy_name:'過去の試験犬',breed:'スタンダードプードル',kennel_name:'試験犬舎',
  sale_amount:300000,rate_bps:300,fee_amount:9000,issued_at:issued,due_at:due,
  note:'BIG PAW 初回成約無料・推しワン利用料3％（税込）'},
 {id:'test-regular',invoice_no:'BP-TEST-REGULAR',deal_id:'fixture-regular',status:'issued',
  puppy_name:'通常の試験犬',breed:'スタンダードプードル',kennel_name:'試験犬舎',
  sale_amount:300000,rate_bps:800,fee_amount:24000,issued_at:issued,due_at:due,
  note:'BIG PAW 成約手数料5％＋推しワン利用料3％（税込）'}
];
const cfg={commissionRateBps:500,commissionDueDays:7,issuerName:'BIG PAW試験',postal:'',
 address:'',bankName:'試験銀行',bankBranch:'試験支店',bankAccountType:'普通',
 bankAccountNo:'12345',bankAccountHolder:'テスト'};
async function test(engine,label){
 const browser=await engine.launch({headless:true,...(label==='chromium'?{executablePath:chromePath(),args:['--no-sandbox']}:{})});
 try{
  const ctx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:3});
  const page=await ctx.newPage(),errors=[];
  let currentRole='breeder',billingConfigRequests=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',route=>{
   const u=new URL(route.request().url());
   if(route.request().method()!=='GET')return route.abort();
   const table={
    '/api/me':{role:currentRole,emailVerified:true},
    '/api/breeder/invoices':invoices,
    '/api/operator/invoices':[],
    '/api/breeder-profile':{billing_suspended:false},
    '/api/breeder/billing-config':cfg,
    '/api/campaign/first100':{status:'active',remaining:99,remainingLabel:'99頭'},
    '/api/breeder/first-sale-benefit':{used:false},
    '/api/breeder/deal-policy-consent':{accepted:true}
   };
   if(u.pathname==='/api/breeder/billing-config')billingConfigRequests++;
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(table[u.pathname]??{})});
  });
  const status=await page.goto(origin+'/breeder-billing.html?invoice-label-e2e='+label,{waitUntil:'domcontentloaded'});
  assert.equal(status.status(),200);
  await page.waitForFunction(()=>document.querySelector('#rows')?.innerText.includes('BP-TEST-CAMP'));
  const listText=await page.locator('#rows').innerText();
  assert(listText.includes('通常成約手数料0円（先着100頭キャンペーン適用）'),'live promo invoice breakdown must state campaign');
  assert(listText.includes('通常成約手数料0円（初回無料特典適用）'),'genuine legacy invoice keeps historical label');
  assert(listText.includes('推しワン利用料3％：9,000円'),'campaign 3% invoiced, not free');
  assert(listText.includes('請求合計 24,000円'),'regular 8% invoice retained');
  assert(!(await page.locator('#billingLead').innerText()).includes('初回無料特典対象'),'billing header must not advertise obsolete first-sale waiver');
  await page.goto(origin+'/breeder-invoice.html?id=test-campaign',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#doc')?.innerText.includes('BP-TEST-CAMP'));
  let rendered=await page.locator('#doc').innerText();
  assert(rendered.includes('先着100頭キャンペーン適用'),'printed invoice labels current waiver correctly');
  assert(rendered.includes('推しワン利用料 3%'),'printed invoice separately bills promotion');
  assert(rendered.includes('9,000'),'printed invoice shows actual 9000 yen');
  assert(rendered.includes('請求日から7日以内'),'printed invoice shows seven-day due');
  assert(!(rendered.includes('初回無料特典')),'current first-100 invoice must not claim obsolete first-sale waiver');
  await page.goto(origin+'/breeder-invoice.html?id=test-legacy',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#doc')?.innerText.includes('BP-TEST-LEGACY'));
  rendered=await page.locator('#doc').innerText();
  assert(rendered.includes('初回無料特典適用'),'historical invoice preserves its original waiver');
  await page.goto(origin+'/breeder-invoice.html?id=test-regular',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#doc')?.innerText.includes('BP-TEST-REGULAR'));
  rendered=await page.locator('#doc').innerText();
  assert(rendered.includes('24,000')&&rendered.includes('請求日から7日以内'),'regular 8% and seven days unchanged');
  // Operator-only sample is safe before any real contract or invoice exists.
  currentRole='operator';
  await page.goto(origin+'/operator-invoices.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#rows')?.innerText.includes('請求はありません'));
  assert.equal(await page.locator('a[href="operator-invoice-preview.html"]').count(),1,'operator billing has sample preview link');
  await page.locator('a[href="operator-invoice-preview.html"]').click();
  await page.waitForFunction(()=>!document.querySelector('#previewInvoice')?.hidden);
  const preview=await page.locator('#previewInvoice').innerText();
  assert(preview.includes('見本・テスト表示')&&preview.includes('実際の請求書ではありません'),'preview clearly marked sample');
  assert(preview.includes('試験銀行')&&preview.includes('試験支店')&&preview.includes('12345')&&preview.includes('テスト'),'preview shows the configured bank data');
  assert(preview.includes('請求元')&&preview.includes('BIG PAW試験'),'preview shows configured issuer');
  assert(preview.includes('9,000円')&&preview.includes('発行日から7日以内'),'preview includes 3% amount and seven-day due');
  assert.equal(await page.locator('#previewPrint').isDisabled(),false,'authorized operator can print sample');
  console.log('OPERATOR_INVOICE_PREVIEW_OK|'+label+'|bank_present|operator_only|seven_day|no_real_invoice');
  currentRole='buyer';
  billingConfigRequests=0;
  await page.goto(origin+'/operator-invoice-preview.html?deny-buyer=1',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#previewError')?.innerText.includes('運営アカウント'));
  assert.equal(await page.locator('#previewInvoice').isHidden(),true,'buyer must never see bank details in operator preview');
  assert.equal(billingConfigRequests,0,'buyer must not request account config through operator preview');
  console.log('OPERATOR_INVOICE_PREVIEW_BUYER_DENIED_OK|'+label);
  assert.deepEqual(errors,[],'no JavaScript errors');
  console.log('OSHIWAN_INVOICE_RENDERED_LABELS_OK|'+label+'|first100=9000_and_7days|legacy_preserved|after_quota=24000_and_7days');
  await ctx.close();
 }finally{await browser.close()}
}
(async()=>{
 const health=await fetch(origin+'/api/health').then(r=>r.json());
 assert.equal(health.environment,'development','only disposable development server may run synthetic invoice tests');
 await test(chromium,'chromium');
 if(process.env.BIGPAW_TEST_WEBKIT==='1')await test(webkit,'webkit');
})().catch(e=>{console.error(e);process.exitCode=1});
