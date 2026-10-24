#!/usr/bin/env node
'use strict';
const assert=require('assert').strict;
const fs=require('fs');
const path=require('path');
const root=path.join(__dirname,'..','app');
const stamp='?v=20261024-fresh-e2e4';
const links=[
  ['admin.html','href="breeder-fees.html'+stamp+'"'],
  ['breeder-billing.html','href="breeder-fees.html'+stamp+'"'],
  ['breeder-sales-handover.html','href="breeder-fees.html'+stamp+'"'],
  ['breeder-fee-agreement.html','href="breeder-fees.html'+stamp+'"'],
  ['mobile-global-nav.js',"'料金・手数料','/breeder-fees.html"+stamp+"'"],
  ['breeder-mobile-nav.js',"'料金・手数料','/breeder-fees.html"+stamp+"'"],
];
for(const [file,link] of links){
  const text=fs.readFileSync(path.join(root,file),'utf8');
  assert(text.includes(link),'stale breeder fees URL remains in entry '+file);
  assert(!text.includes('href="breeder-fees.html"'),'unversioned HTML URL '+file);
  console.log('PASS revised breeder link',file);
}
const register=fs.readFileSync(path.join(root,'breeder-register.html'),'utf8');
const dynamic=fs.readFileSync(path.join(root,'assets','first100-campaign.js'),'utf8');
assert(register.includes('data-bp-first100 hidden'),'registration uses live campaign element');
assert(/src="assets\/first100-campaign\.js\?v=20261024-signup-[a-z0-9-]+"/.test(register),'registration uses dated versioned live campaign');
assert(!register.includes('src="assets/first100-campaign.js"'),'registration must not use an unversioned campaign script');
assert(dynamic.includes('href="breeder-fees.html'+stamp+'"'),'dynamic registration promo has versioned fees link');
assert(!register.includes('href="breeder-fees.html"'),'registration has no unversioned static link');
const globalNav=fs.readFileSync(path.join(root,'mobile-global-nav.js'),'utf8');
assert(globalNav.includes("'/breeder-fees.html','/breeder-profile-edit.html'"),'breeder page route recognition changed');
const fees=fs.readFileSync(path.join(root,'breeder-fees.html'),'utf8');
assert(fees.includes('id="bpBreederCampaign"')&&fees.includes('id="bpBreederStandardHero" hidden'),'new page is gold promo');
assert(fees.includes('breeder-fees-campaign.js'),'actual fee page has correct campaign controller');
assert(!fees.includes('src="assets/first100-campaign.js"'),'old blue promo not used');
const controller=fs.readFileSync(path.join(root,'assets','breeder-fees-campaign.js'),'utf8');
assert(controller.includes("data.status==='active'")&&controller.includes("hero.hidden=false"),'automatic restoration on end preserved');
for (const file of ['index.html','search.html','puppy-detail.html']) {
  const buyer=fs.readFileSync(path.join(root,file),'utf8');
  assert(!buyer.includes('v=20261024-fresh-e2e4'),'buyer pages left alone');
}
console.log('BREEDER_ACCOUNT_FEE_LINKS_CACHEBUST_GATE_OK|six_static_entries_and_dynamic_registration|normal_menu_recognition|buyer_untouched|gold_promo_existing|end_restores_5_percent');
