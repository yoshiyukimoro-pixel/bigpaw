const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium, webkit} = require('playwright');

(async () => {
  for (const [name,browserType] of [['Chromium',chromium],['iPhone Safari (WebKit)',webkit]]) {
    const browser=await browserType.launch({headless:true});
    const page=await browser.newPage({viewport:name==='Chromium'?{width:1280,height:900}:{width:390,height:844}});
    const errs=[];page.on('pageerror',e=>errs.push(e.message));
    const url='file://'+path.resolve('app/shop.html');
    await page.goto(url);
    assert.equal(await page.locator('a.prod').count(),35,name+' full catalog');
    assert.match(await page.locator('#count').innerText(),/35/);
    await page.locator('button[data-brand="ACANA"]').click();
    assert.equal(await page.locator('a.prod').count(),14);
    await page.locator('button[data-brand="ORIJEN"]').click();
    assert.equal(await page.locator('a.prod').count(),8);
    await page.locator('button[data-brand="ZIWI"]').click();
    assert.equal(await page.locator('a.prod').count(),9);
    await page.locator('button[data-brand="CHARM"]').click();
    assert.equal(await page.locator('a.prod').count(),4);
    await page.locator('button[data-brand=""]').click();
    await page.locator('#keyword').fill('パピー');
    assert(await page.locator('a.prod').count()>0,'keyword search');
    await page.locator('#keyword').fill('');
    await page.locator('#life').selectOption({label:'子犬'});
    assert.equal(await page.locator('a.prod').count(),4,'4 puppy recipes');
    await page.locator('#life').selectOption('');
    await page.locator('#focus').selectOption({label:'大型犬'});
    assert.equal(await page.locator('a.prod').count(),4,'4 large breed products');
    await page.locator('#focus').selectOption('');
    await page.locator('a.prod[href="shop.html?item=A02"]').click();
    assert.match(await page.locator('.detail h1').innerText(),/パピーラージ/);
    assert(await page.locator('.disabled').isDisabled(),'checkout intentionally disabled');
    assert.equal(await page.locator('#listing').isVisible(),false,'list hidden on detail page');
    assert.deepEqual(errs,[],'no uncaught JS exceptions');
    console.log('SHOP_BROWSER_OK|'+name+'|catalog=35|filters=4|details=ok|purchase=disabled');
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exit(1)});
