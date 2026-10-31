/* Browsers load catalog plus all 35 galleries, with safe local-only image fixtures. */
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const ROOT=path.resolve('app');
const PAGE=fs.readFileSync(path.join(ROOT,'shop.html'),'utf8');
const ids=[...PAGE.matchAll(/^'([AOZC]\d{2})\|/gm)].map(m=>m[1]);
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==','base64');
let requests=0;
const server=http.createServer((req,res)=>{
  let pathname;
  try{pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);}
  catch(_){res.writeHead(400).end();return;}
  if(pathname.startsWith('/assets/shop-details/')){
    requests++;
    const installed=path.join(ROOT,pathname.slice(1));
    if(fs.existsSync(installed)){
      res.writeHead(200,{'Content-Type':'image/webp','Cache-Control':'max-age=3600'});
      res.end(fs.readFileSync(installed));return;
    }
    res.writeHead(200,{'Content-Type':'image/png','Cache-Control':'max-age=3600'});
    res.end(png);return;
  }
  if(!['/shop.html','/shop-detail-images.js','/shop-detail-gallery.js',
        '/shop-detail-gallery.css','/shop-cart-preview.js'].includes(pathname)){
    res.writeHead(404).end();return;
  }
  const file=path.join(ROOT,pathname.slice(1));
  const type=pathname.endsWith('.css')?'text/css':pathname.endsWith('.js')?'text/javascript':'text/html';
  res.writeHead(200,{'Content-Type':type,'Cache-Control':'no-store'});
  res.end(fs.readFileSync(file));
});
(async()=>{
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  const base='http://127.0.0.1:'+server.address().port;
  for(const [label,browserType] of [['Chromium',chromium],['iPhone Safari WebKit',webkit]]){
    const browser=await browserType.launch({headless:true});
    const context=await browser.newContext({
      viewport:label==='Chromium'?{width:1280,height:900}:{width:390,height:844},
      isMobile:label!=='Chromium',hasTouch:label!=='Chromium'
    });
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/shop.html');
    assert.equal(await page.locator('a.prod').count(),35);
    assert.equal(await page.locator('.shop-image-section').count(),0,'gallery only on product page');
    for(const id of ids){
      await page.goto(base+'/shop.html?item='+id);
      assert.equal(await page.locator('.detail').count(),1,id+' detail loads');
      assert.equal(await page.locator('.shop-image-section').count(),1,id+' gallery exists');
      const count=await page.locator('.shop-image-figure').count();
      assert(count>=4,id+' has manufacturer details');
      const paths=await page.locator('.shop-image-figure img').evaluateAll(
        els=>els.map(el=>new URL(el.src).pathname));
      assert.equal(paths.length,count);
      const own='/assets/shop-details/products/'+id+'/';
      const shared='/assets/shop-details/shared/'+
        ({A:'acana',O:'orijen',Z:'ziwi',C:'charm'})[id[0]]+'/';
      let sharedReached=false;
      for(let i=0;i<count;i++){
        const scope=await page.locator('.shop-image-figure').nth(i).getAttribute('data-scope');
        if(scope==='brand'){sharedReached=true;assert(paths[i].startsWith(shared),id+' wrong brand image');}
        else {assert(!sharedReached,id+' images not product-first');assert(paths[i].startsWith(own),id+' wrong SKU');}
      }
      assert.equal(await page.locator('#previewCheckout').isDisabled(),true,id+' no purchase');
      if(id==='A02'){
        assert.equal(count,5,'ACANA puppy has 2 specific and 3 common images');
        const first=page.locator('.shop-image-figure img').first();
        await first.scrollIntoViewIfNeeded();
        await page.waitForFunction(()=>document.querySelector('.shop-image-figure img')?.naturalWidth>0);
        await page.locator('.shop-image-open').first().click();
        assert.equal(await page.locator('.shop-image-viewer').isVisible(),true,'zoom opens');
        await page.locator('.shop-viewer-close').click();
        assert.equal(await page.locator('.shop-image-viewer').isVisible(),false,'zoom closes');
      }
      if(id==='Z06')assert(paths.some(p=>p.includes('air-chicken-9312.webp')),
        'ZIWI chicken must have chicken-specific shared images');
      if(id==='Z08')assert(paths.every(p=>p.includes('/shared/ziwi/')),
        'ZIWI steam chicken has shared images only');
    }
    assert.deepEqual(errors,[],'uncaught JS errors');
    console.log('SHOP_DETAIL_BROWSER_OK|'+label+'|products=35|galleries=35');
    await browser.close();
  }
  assert(requests>0,'local fixtures must have been requested');
  await new Promise(ok=>server.close(ok));
})().catch(e=>{console.error(e);server.close();process.exit(1);});
