const fs=require('fs');const assert=require('assert');const path=require('path');const {chromium}=require('playwright');
(async()=>{
 const cfg=JSON.parse(fs.readFileSync(process.argv[2]));
 const packaged=(await import(process.env.BIGPAW_TEST_CHROMIUM_MODULE)).default;
 const browser=await chromium.launch({executablePath:process.env.BIGPAW_TEST_CHROMIUM_PATH,args:packaged.args,headless:true});
 const errors=[];const contexts=[];
 async function role(uid,viewport={width:390,height:844}){
  const c=await browser.newContext({viewport});contexts.push(c);
  await c.addCookies([{name:'bigpaw_session',value:'test-'+uid,domain:'bigpaw.site',path:'/',secure:true,httpOnly:true}]);
  const page=await c.newPage();page.on('pageerror',e=>errors.push({url:page.url(),error:e.message,stack:e.stack}));
  await page.route('https://bigpaw.site/**',async route=>{
   const req=route.request(),u=new URL(req.url());
   const headers={...(await req.allHeaders()),host:'bigpaw.site',cookie:'bigpaw_session=test-'+uid};
   const res=await c.request.fetch(cfg.base+u.pathname+u.search,{method:req.method(),headers,data:req.postDataBuffer()||undefined});
   await route.fulfill({response:res});
  });
  page.on('dialog',async d=>d.accept(d.type()==='prompt'?(d.message().includes('YYYY-MM-DD')?cfg.today:d.defaultValue()||'試験で購入者と履歴を確認'):undefined));return page;
 }
 const seller=await role('u_dog44');await seller.goto('https://bigpaw.site/breeder-deal-report.html');
 await seller.locator('#benefit').filter({hasText:'使用済み'}).waitFor();
 await seller.locator('#inquiry').selectOption(cfg.browserInquiry);await seller.locator('#amount').fill('310000');await seller.locator('#date').fill(cfg.today);await seller.locator('#agree').check();await seller.locator('#accurate').check();await seller.locator('#submit').click();
 await seller.locator('#message').filter({hasText:'申請しました'}).waitFor();
 await seller.screenshot({path:path.join(cfg.work,'seller-mobile.png'),fullPage:true});
 const buyer=await role('u_demo');await buyer.goto('https://bigpaw.site/buyer-sale-confirmation.html');
 await buyer.waitForLoadState('networkidle');await buyer.screenshot({path:path.join(cfg.work,'buyer-before-answer.png'),fullPage:true});let card=buyer.locator('section').filter({hasText:'ブラウザー試験犬'}).filter({hasText:'お迎えが決まりましたか'});await card.getByRole('button',{name:'はい',exact:true}).click();await buyer.locator('#message').filter({hasText:'回答を保存しました'}).waitFor();
 await seller.reload();await seller.locator('#accurate').check();let sale=seller.locator('#workflow .item').filter({hasText:'ブラウザー試験犬'});await sale.getByRole('button',{name:'お迎え完了を報告'}).click();await seller.locator('#message').filter({hasText:'お迎え完了を報告しました'}).waitFor();
 await buyer.reload();card=buyer.locator('section').filter({hasText:'ブラウザー試験犬'}).filter({hasText:'お迎えは完了しましたか'});await card.getByRole('button',{name:'はい',exact:true}).click();await buyer.locator('#message').filter({hasText:'回答を保存しました'}).waitFor();
 await buyer.screenshot({path:path.join(cfg.work,'buyer-mobile.png'),fullPage:true});await seller.reload();await seller.locator('#workflow .item').filter({hasText:'ブラウザー試験犬'}).filter({hasText:'お迎え完了'}).waitFor();
 const op=await role('u_admin',{width:1280,height:900});await op.goto('https://bigpaw.site/operator-sale-confirmations.html');await op.locator('#disputes').filter({hasText:'虚偽を確認'}).waitFor();await op.getByRole('button',{name:'警告メールを確認・送信',exact:true}).first().click();await op.locator('#message').filter({hasText:'警告メールを送信待ちに登録しました'}).waitFor();await op.locator('#warningHistory').filter({hasText:'今後、虚偽申告や手数料回避'}).waitFor();await op.screenshot({path:path.join(cfg.work,'operator-desktop.png'),fullPage:true});
 for(const p of [seller,buyer,op])assert(await p.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal clipping');
 // Existing browser routes, photos, search, favorites and admin pages still render.
 for(const url of ['search.html','puppy-detail.html?id='+cfg.regressionPuppy,'mypage.html']){await buyer.goto('https://bigpaw.site/'+url);await buyer.waitForLoadState('networkidle');assert((await buyer.locator('body').innerText()).length>100,url+' has meaningful content');}
 await buyer.goto('https://bigpaw.site/puppy-detail.html?id='+cfg.regressionPuppy);await buyer.waitForLoadState('networkidle');assert(await buyer.locator('img').count()>0,'existing puppy photos render');
 await seller.goto('https://bigpaw.site/breeder-puppy-new.html?id='+cfg.regressionPuppy);await seller.waitForLoadState('networkidle');assert((await seller.locator('body').innerText()).includes('子犬'),'existing puppy editor renders');
 await op.goto('https://bigpaw.site/operator-breeders.html');await op.waitForLoadState('networkidle');assert((await op.locator('body').innerText()).includes('ブリーダー'),'existing breeder management renders');
 console.log('BROWSER_ERRORS',JSON.stringify(errors));assert.deepEqual(errors,[],'no browser JavaScript exceptions');
 await browser.close();console.log('FIRST_SALE_BROWSER_OK|mobile_seller_buyer_end_to_end|desktop_operator|existing_routes|no_js_errors');
})().catch(e=>{console.error(e);process.exit(1)});
