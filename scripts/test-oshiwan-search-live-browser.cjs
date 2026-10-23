#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const origin=process.argv[2]||'http://127.0.0.1:18089';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
  const failures=[];
  page.on('pageerror',e=>failures.push(String(e)));
  await page.goto(origin+'/search.html?breed=standard-poodle',{waitUntil:'domcontentloaded'});
  await page.locator('#bpResults .bp-puppy-row').first().waitFor({timeout:30000});
  const items=page.locator('#bpResults .bp-puppy-row');
  await items.nth(9).waitFor({timeout:15000});
  assert.equal(await items.count(),10,'exactly ten search rows on breed search');
  const ids=[];
  for(let i=0;i<10;i++){
    const item=items.nth(i);
    const href=await item.getAttribute('href');
    ids.push(new URL(href,origin).searchParams.get('id'));
    assert.equal(await item.evaluate(e=>e.classList.contains('bp-oshi-promoted')),i<5,'only positions 1–5 carry 推しワン border');
    assert.equal(await item.locator('.bp-oshi-search-badge').count(),i<5?1:0,'only promoted positions show 推しワン PR label');
  }
  assert.equal(new Set(ids).size,10,'no duplicated puppy in search results');
  assert(ids.slice(0,5).every(id=>/^oshi-search-([5-9])$/.test(id)),'promoted IDs appear in first five positions');
  assert(ids.slice(5).every(id=>/^oshi-search-([0-4])$/.test(id)),'ordinary IDs appear after sponsored five');
  assert.equal(await page.locator('#bpCount').innerText(),'10頭');
  await page.locator('#bpGender').selectOption('female');
  await page.waitForTimeout(250);
  const visible=page.locator('#bpResults .bp-puppy-row');
  assert.equal(await visible.count(),5,'gender filter retains five puppies');
  assert.equal(await page.locator('#bpResults .bp-oshi-promoted').count(),3,'only three matching sponsored dogs are prioritized after filter');
  const femaleIDs=[];
  for(let i=0;i<5;i++)femaleIDs.push(new URL(await visible.nth(i).getAttribute('href'),origin).searchParams.get('id'));
  assert.deepEqual(femaleIDs.slice(0,3).sort(),['oshi-search-5','oshi-search-7','oshi-search-9'],'filtered featured dogs first');
  const width=await page.evaluate(()=>({inner:innerWidth,scroll:document.documentElement.scrollWidth}));
  assert(width.scroll<=width.inner+2,'mobile layout does not horizontally overflow');
  assert.deepEqual(failures,[],'no browser JavaScript errors');
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});
  assert.equal(await page.locator('#bpOshiwan').count(),0,'separate featured homepage shelf removed');
  console.log('OSHIWAN_SEARCH_MOBILE_BROWSER_OK|ten_results|top5_PR|remaining5_regular|gender_filter|no_duplicates|responsive|home_no_separate_shelf');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
