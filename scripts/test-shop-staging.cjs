const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const http = require('node:http');
const fs = require('node:fs');
const APP_ROOT = path.resolve('app');
const server = http.createServer((req,res) => {
  let target;
  try { target = new URL(req.url,'http://localhost').pathname; }
  catch(_) { res.writeHead(400).end(); return; }
  const filename=path.resolve(APP_ROOT,'.'+target);
  if(!filename.startsWith(APP_ROOT+path.sep)) {res.writeHead(403).end();return;}
  try {
    const contents=fs.readFileSync(filename);
    const type=filename.endsWith('.html')?'text/html':
      filename.endsWith('.js')?'application/javascript':
      filename.endsWith('.css')?'text/css':
      filename.endsWith('.webp')?'image/webp':'application/octet-stream';
    res.writeHead(200,{'Content-Type':type,'Cache-Control':'no-store'});
    res.end(contents);
  } catch(_) {res.writeHead(404).end();}
});


(async () => {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  for (const [name,browserType] of [['Chromium',chromium],['iPhone Safari (WebKit)',webkit]]) {
    const browser=await browserType.launch({headless:true});
    const page=await browser.newPage({viewport:name==='Chromium'?{width:1280,height:900}:{width:390,height:844}});
    const errs=[];page.on('pageerror',e=>errs.push(e.message));
    const url=base+'/shop.html';
    await page.goto(url);
    assert.equal(await page.locator('a.prod').count(),35,name+' full catalog');
    assert.equal(await page.locator('#previewCartCount').innerText(),'0',name+' initially empty cart');
    assert.equal(await page.locator('#empty').isVisible(),false,name+' no stray empty-results message');
    await page.locator('#previewCartOpen').click();
    assert.equal(await page.locator('#previewCartDialog').isVisible(),true,name+' accessible cart opens');
    assert.match(await page.locator('.cart-empty').innerText(),/まだ商品がありません/);
    assert.equal(await page.locator('#previewCheckout').isDisabled(),true,name+' checkout always disabled');
    await page.locator('#previewCartContinue').click();
    assert.equal(await page.locator('#previewCartDialog').isVisible(),false,name+' cart closes');

    assert.equal(await page.locator('.brand-card').count(),4,name+' four brand choices');
    assert.equal(await page.locator('.brand-section').count(),4,name+' brands separated on initial view');
    assert.equal(await page.locator('#brand-ACANA .series-block').count(),3,name+' ACANA organized by recipe series');
    assert.equal(await page.locator('#brand-ZIWI .series-block').count(),2,name+' ZIWI organized into air- and steam-dried');
    await page.locator('button[data-brand-card="ACANA"]').click();
    assert.equal(await page.locator('a.prod').count(),14,name+' choosing ACANA from large brand card');
    assert.equal(await page.locator('.brand-section').count(),1,name+' selecting brand hides others');
    assert.equal(await page.locator('button[data-brand-card="ACANA"]').getAttribute('aria-pressed'),'true',name+' brand state');
    await page.locator('#clearFilters').click();
    assert.equal(await page.locator('.brand-section').count(),4,name+' reset restores all grouped sections');
    assert.equal(await page.locator('a.prod').count(),35,name+' reset restores all products');

    assert.match(await page.locator('#count').innerText(),/35/);
    assert.equal(await page.locator('.reference-price').count(),35,name+' all retail price labels');
    assert.match(await page.locator('.reference-price').first().innerText(),/販売価格（税込・送料込み）/,name+' all prices include tax and delivery');
    assert.match(await page.locator('.notice').innerText(),/送料込み/,name+' shipping included notice');
    assert.match(await page.locator('a.prod[href="shop.html?item=Z01"] .reference-price').innerText(),/42,900円/,name+' ZIWI venison retail MSRP');
    assert.match(await page.locator('a.prod[href="shop.html?item=Z04"] .reference-price').innerText(),/23,980円/,name+' ZIWI tripe & lamb retail MSRP');
    assert.equal(await page.locator('a.prod[href="shop.html?item=Z01"] .sizerow span').first().innerText(),'2.5kg');

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
    assert.equal(await page.locator('#previewAddToCart').count(),1,name+' demo cart action on detail');
    await page.locator('#previewAddToCart').click();
    assert.equal(await page.locator('#previewCartDialog').isVisible(),true,name+' adding item opens cart');
    assert.equal(await page.locator('#previewCartCount').innerText(),'1',name+' cart has one item');
    assert.match(await page.locator('#previewCartSubtotal').innerText(),/21,450円/,name+' tax-included shipping-included retail total');
    assert.match(await page.locator('.cart-shipping').innerText(),/全商品送料込み/,name+' no additional delivery charge');
    await page.locator('button[data-action="plus"]').click();
    assert.equal(await page.locator('.cart-quantity').innerText(),'2',name+' quantity increment');
    assert.match(await page.locator('#previewCartSubtotal').innerText(),/42,900円/,name+' subtotal updated');
    await page.locator('button[data-action="minus"]').click();
    assert.equal(await page.locator('.cart-quantity').innerText(),'1',name+' quantity decrement');
    assert.equal(await page.locator('#previewCheckout').isDisabled(),true,name+' no real checkout after adding');
    await page.locator('#previewCartContinue').click();
    await page.locator('.back').click();
    assert.equal(await page.locator('a.prod').count(),14,name+' returns to matching ACANA brand');
    assert.match(page.url(),/brand=ACANA/,name+' brand preserved in URL');
    assert.equal(await page.locator('#previewCartCount').innerText(),'1',name+' session cart persists across pages');
    await page.locator('#previewCartOpen').click();
    assert.equal(await page.locator('.cart-quantity').innerText(),'1',name+' preserved cart quantity');
    await page.locator('button[data-action="remove"]').click();
    assert.equal(await page.locator('#previewCartCount').innerText(),'0',name+' remove all');
    assert.match(await page.locator('#previewCartSubtotal').innerText(),/0円/,name+' empty total');
    assert.equal(await page.locator('#previewCheckout').isDisabled(),true,name+' no order even for empty cart');
    await page.locator('#previewCartContinue').click();
    assert.equal(await page.locator('#listing').isVisible(),true,'catalog restored after returning');
    assert.deepEqual(errs,[],'no uncaught JS exceptions');
    console.log('SHOP_BROWSER_OK|'+name+'|catalog=35|filters=4|details=ok|purchase=disabled');
    await browser.close();
  }
  await new Promise(resolve=>server.close(resolve));
})().catch(e=>{console.error(e);server.close();process.exit(1)});
