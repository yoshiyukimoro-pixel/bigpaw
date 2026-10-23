#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const origin=process.argv[2]||'http://127.0.0.1:18089';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(origin+'/search.html?breed=standard-poodle',{waitUntil:'domcontentloaded'});
  const items=page.locator('#bpResults .bp-puppy-row');
  await items.nth(19).waitFor({timeout:35000});
  assert.equal(await items.count(),20,'page 1 displays exactly 20 cards, including five PR slots');
  assert.equal(await page.locator('#bpCount').innerText(),'50頭','headline counts distinct actual puppies');
  const seen=[];
  async function capturePage(pageNumber, expectedCount, expectedPR){
    assert.equal(await items.count(),expectedCount,'page '+pageNumber+' displays expected slots');
    assert.equal(await page.locator('#bpResults .bp-oshi-promoted').count(),expectedPR,'only dedicated PR cards on page '+pageNumber+' have badge');
    const ids=[];
    for(let i=0;i<expectedCount;i++){
      const item=items.nth(i), url=await item.getAttribute('href');
      ids.push(new URL(url,origin).searchParams.get('id'));
      assert.equal(await item.locator('.bp-oshi-search-badge').count(),i<expectedPR?1:0,'PR badge visible only for sponsored slots on page '+pageNumber);
    }
    seen.push(...ids);
    return ids;
  }
  const first=await capturePage(1,20,5);
  assert.deepEqual(first.slice(0,5).sort(),[45,46,47,48,49].map(i=>'oshi-search-'+i),'first five are sponsored');
  assert.equal(await page.locator('#bpPagination button[aria-current="page"]').innerText(),'1');
  await page.locator('#bpPagination button[data-page="2"]').last().click();
  await page.locator('#bpPagination button[aria-current="page"]').waitFor();
  assert.equal(await page.locator('#bpPagination button[aria-current="page"]').innerText(),'2');
  await capturePage(2,20,0);
  await page.locator('#bpPagination button[data-page="3"]').last().click();
  assert.equal(await page.locator('#bpPagination button[aria-current="page"]').innerText(),'3');
  await capturePage(3,15,0);
  assert.equal(seen.length,55,'50 organic listings plus 5 independent advertised cards');
  assert.equal(new Set(seen).size,50,'all 50 distinct puppies appear in results');
  for(let i=45;i<50;i++)assert.equal(seen.filter(x=>x==='oshi-search-'+i).length,2,'advertised dog also appears in ordinary listing');
  assert.equal(await page.locator('#bpCount').innerText(),'50頭');
  await page.locator('#bpGender').selectOption('female');
  await page.locator('#bpPagination button[aria-current="page"]').waitFor();
  assert.equal(await page.locator('#bpPagination button[aria-current="page"]').innerText(),'1','filter resets pagination');
  assert.equal(await page.locator('#bpCount').innerText(),'25頭','gender-filtered distinct dogs');
  const female=await capturePage(1,20,3);
  assert.deepEqual(female.slice(0,3).sort(),[45,47,49].map(i=>'oshi-search-'+i),'three matching sponsored females appear first');
  await page.locator('#bpPagination button[data-page="2"]').last().click();
  const femaleLast=await capturePage(2,8,0);
  assert.equal(new Set(female.concat(femaleLast)).size,25,'filtered PR dogs also appear in organic list and all 25 females are available');
  assert.equal(female.length+femaleLast.length,28,'25 females plus three PR placements');
  const width=await page.evaluate(()=>({inner:innerWidth,scroll:document.documentElement.scrollWidth}));
  assert(width.scroll<=width.inner+2,'mobile viewport does not overflow');
  assert.deepEqual(errors,[],'no JS page errors');
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});
  assert.equal(await page.locator('#bpOshiwan').count(),0,'separate homepage PR shelf absent');
  console.log('OSHIWAN_SEARCH_MOBILE_BROWSER_OK|fifty_dogs|20_20_15|five_PR_duplicates|50_distinct|gender_25_plus_3|pagination|responsive|homepage_clean');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
