'use strict';
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');

const base=(process.argv[2]||'http://127.0.0.1:18107').replace(/\/$/,'');
const id='p_first_photo_smoke';
const imageA='/assets/bigpaw-logo-header.webp';
const imageB='/assets/bigpaw-logo-full.webp';
const puppy={
  id,name:'子犬写真テスト',breed:'スタンダードプードル',breedKey:'standard',gender:'男の子',
  genderKey:'male',color:'ブラック',area:'埼玉県',price:200000,status:'募集中',
  birth:'2026-09-01',birthDate:'2026-09-01',imageUrl:imageA,photos:[imageA,imageB],
  breeder:'検証用犬舎',breederId:'b_smoke',description:'写真読み込み検証用',desc:'写真読み込み検証用'
};

function installApiDelay(page,delay=1800){
  return Promise.all(['/api/puppies/'+id,'/api/public/puppies/'+id].map(path=>
    page.route('**'+path,async route=>{
      if(route.request().method()!=='GET')return route.continue();
      await new Promise(resolve=>setTimeout(resolve,delay));
      return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(puppy)});
    })
  ));
}

async function run(engine,name){
  const browser=await engine.launch({headless:true});
  const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:2});
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
    await installApiDelay(page);
    await page.goto(base+'/search.html',{waitUntil:'domcontentloaded'});
    await page.evaluate(({id,img})=>{
      const a=document.createElement('a');
      a.id='photo-entry-test-link';
      a.href='puppy-detail.html?id='+encodeURIComponent(id);
      const image=document.createElement('img');
      image.src=img;image.alt='テストの写真';image.width=160;image.height=120;
      a.appendChild(image);a.style.cssText='display:block;position:fixed;top:80px;left:15px;z-index:2147483647;background:white';
      document.body.appendChild(a);
    },{id,img:imageA});
    await page.locator('#photo-entry-test-link').click();
    await page.waitForURL('**/puppy-detail.html?id='+id);
    await page.locator('#mainPhoto').waitFor({state:'attached',timeout:10000});
    const first=await page.locator('#bigpawDetailInitialGallery').evaluate(el=>({
      text:el.textContent.trim(),source:el.querySelector('img')?.getAttribute('src')||''
    }));
    assert.equal(first.text,'','An emoji or decorative loading image appeared');
    assert.ok(first.source.endsWith(imageA),'Clicked listing photo did not appear before API response');
    const session=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('bigpaw_puppy_first_photo_v1')));
    assert.equal(session.id,id,'Click handoff must be scoped to the clicked puppy');
    await page.locator('#bigpawStableGallery .bpsg-stage img').first().waitFor({state:'visible',timeout:18000});
    const gallery=page.locator('#bigpawStableGallery');
    assert.ok((await gallery.innerText()).indexOf('🐩')===-1,'Stable gallery must not display a poodle illustration');
    await page.locator('#bigpawStableGallery .bpsg-thumb').nth(1).click();
    await page.waitForTimeout(200);
    const current=await page.locator('#bigpawStableGallery .bpsg-stage img').first().getAttribute('src');
    assert.ok(current.includes('bigpaw-logo-full.webp'),'Photo selection regression: second photo not shown');

    // A direct link without any list handoff must remain emoji-free as well.
    const direct=await context.newPage();
    await installApiDelay(direct);
    await direct.goto(base+'/puppy-detail.html?id='+id,{waitUntil:'domcontentloaded'});
    const empty=await direct.locator('#bigpawDetailInitialGallery').evaluate(el=>({
      text:el.textContent.trim(),hasImage:!!el.querySelector('img')
    }));
    assert.equal(empty.text,'','Direct-entry detail must not show a poodle illustration');
    assert.equal(empty.hasImage,false,'Direct-entry detail used a photo handoff from a different tab');
    await direct.locator('#bigpawStableGallery .bpsg-stage img').first().waitFor({state:'visible',timeout:18000});
    await direct.close();
    assert.equal(errors.filter(x=>/SyntaxError|ReferenceError/.test(x)).length,0,'Runtime syntax/reference error: '+errors.join('; '));
    console.log('PUPPY_FIRST_PHOTO_BROWSER_OK|'+name+'|list_to_detail=immediate|direct_link=no_emoji|gallery=2photos');
  }finally{
    await browser.close();
  }
}
(async()=>{
  await run(chromium,'Chromium');
  await run(webkit,'WebKit');
})().catch(e=>{console.error(e);process.exitCode=1});
