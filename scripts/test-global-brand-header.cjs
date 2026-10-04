const assert=require('assert'),path=require('path');
module.exports=async({page,cfg})=>{
 const guests=await page(),buyer=await page('u_demo'),breeder=await page('u_dog44'),operator=await page('u_admin');
 const breederPages=new Set(['admin.html','health-records.html','parent-dogs.html']);
 const buyerPages=new Set(['account.html','mypage.html','notifications.html','favorites.html','compare.html','messages.html','inquiry.html','deal.html','reservation.html','contract.html','pickup.html','review.html','report.html','visit-confirm.html','online-visit.html','buyer-sale-confirmation.html']);
 const operatorPages=new Set(['project-status.html','backend-status.html','launch-checklist.html']);
 function owner(name){if(name.startsWith('operator-')&&name!=='operator-login.html'||operatorPages.has(name))return operator;if(name.startsWith('breeder-')&&!['breeder-register.html','breeder-detail.html','breeder-fees.html'].includes(name)||breederPages.has(name))return breeder;return buyerPages.has(name)?buyer:guests}
 function route(name){
  const detail={'puppy-detail.html':'id='+cfg.regressionPuppy,'breeder-puppy-new.html':'id='+cfg.regressionPuppy,'breeder-detail.html':'id=b_dog44','operator-breeder-detail.html':'id=b_dog44','operator-user-detail.html':'id=u_demo','breeder-cancellation.html':'inquiry='+cfg.browserInquiry,'messages.html':'inquiry='+cfg.browserInquiry,'breed-guide-detail.html':'breed=standard-poodle'};
  return 'https://bigpaw.site/'+name+(detail[name]?'?'+detail[name]:'');
 }
 async function geometry(p,label,width){
  await p.locator('.bp-brand-header .bigpaw-header-logo').waitFor();
  await p.waitForFunction(()=>{const i=document.querySelector('.bp-brand-header .bigpaw-header-logo');return i?.complete&&i.naturalWidth>0});
  assert.equal(await p.locator('.bp-brand-header').count(),1,label+' single header');
  const img=await p.locator('.bp-brand-header .bigpaw-header-logo').boundingBox(),nav=await p.locator('.bp-brand-nav').boundingBox();assert(img.x>=0&&img.x-nav.x<32&&img.width>100,label+' logo at upper left of header');
  const button=p.locator('#bp-global-mobile-menu-button');await button.waitFor({state:'attached'});
  if(width<=900){
   const b=await button.boundingBox();assert(b&&b.x>=img.x+img.width&&b.x+b.width<=width,label+' menu separate from logo and inside viewport');
   assert(Math.abs(b.y-img.y)<=16,label+' menu in logo row');
   for(const cta of await p.locator('.bp-brand-header .nav-cta').all()){const c=await cta.boundingBox();if(c)assert(c.y>=b.y+b.height||c.x+c.width<=b.x,label+' CTA not covered')}
   await button.click();assert.equal(await button.getAttribute('aria-expanded'),'true');assert(await p.locator('#bp-global-mobile-menu-drawer').isVisible());
   await p.keyboard.press('Escape');assert.equal(await button.getAttribute('aria-expanded'),'false');assert(await p.locator('#bp-global-mobile-menu-drawer').isHidden());
   await p.evaluate(()=>scrollTo(0,400));await p.waitForFunction(()=>{const h=document.querySelector('.bp-brand-header').getBoundingClientRect(),b=document.getElementById('bp-global-mobile-menu-button').getBoundingClientRect();return Math.abs(b.top-(Math.max(0,h.top)+12))<2});
   const scrolled=await p.locator('.bp-brand-header .bigpaw-header-logo').boundingBox(),menu=await button.boundingBox();assert(menu.x>=scrolled.x+scrolled.width,label+' no overlap after scroll');await p.evaluate(()=>scrollTo(0,0));
  }else assert(await button.isHidden(),label+' desktop navigation unchanged');
 }
 let checks=0;
 for(const name of cfg.pages){
  const p=owner(name);await p.setViewportSize({width:390,height:844});const response=await p.goto(route(name));assert(response?.ok(),name+' HTTP success');await geometry(p,name+' mobile',390);checks++;
  await p.setViewportSize({width:1280,height:900});await geometry(p,name+' desktop',1280);checks++;
 }
 for(const [p,name] of [[guests,'breed-guide.html'],[buyer,'mypage.html'],[breeder,'admin.html'],[operator,'operator-admin.html']]){
  await p.setViewportSize({width:320,height:740});await p.goto(route(name));await geometry(p,name+' narrow',320);checks++;
  await p.screenshot({path:path.join(cfg.work,'global-header-'+name+'.png'),fullPage:false});
 }
 for(const p of [buyer,breeder,operator]){await p.setViewportSize({width:390,height:844});await p.goto(route('notifications.html'));await geometry(p,'notifications role',390);checks++}
 // Brand loads even when session discovery fails; the public menu remains usable.
 await guests.route('**/api/me',r=>r.fulfill({status:503,contentType:'application/json',body:'{}'}));await guests.goto(route('breed-guide.html'));await geometry(guests,'session failure',320);await guests.unroute('**/api/me');checks++;
 console.log('GLOBAL_BRAND_HEADER_BROWSER_OK|pages='+cfg.pages.length+'|checks='+checks+'|mobile_desktop_narrow|menu_escape_scroll|logo_loaded|session_failure');
 for(const p of [guests,buyer,breeder,operator])await p.context().close();
};
