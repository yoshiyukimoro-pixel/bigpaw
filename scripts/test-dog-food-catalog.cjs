#!/usr/bin/env node
'use strict';
/** Read-only prelaunch guard: catalog works without backend, cart or payment. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.join(__dirname,'..','app');
const html = fs.readFileSync(path.join(root,'dog-food.html'),'utf8');
const css = fs.readFileSync(path.join(root,'assets','dog-food.css'),'utf8');
const dataJs = fs.readFileSync(path.join(root,'assets','dog-food-products.js'),'utf8');
const clientJs = fs.readFileSync(path.join(root,'assets','dog-food.js'),'utf8');
const sandbox = {window:{}};
vm.runInNewContext(dataJs,sandbox,{filename:'dog-food-products.js'});
new vm.Script(clientJs,{filename:'dog-food.js'});
const p = sandbox.window.BIGPAW_FOOD_PRODUCTS;
assert.equal(p.length,35);
const totals={ACANA:14,ORIJEN:8,ZIWI:9,CHARM:4};
for(const [brand,total] of Object.entries(totals)) assert.equal(p.filter(item=>item.brand===brand).length,total,brand);
assert.equal(new Set(p.map(item=>item.id)).size,35,'duplicate ids');
assert.equal(new Set(p.map(item=>item.image)).size,35,'duplicate images');
for(const item of p){
  for(const field of ['id','brand','series','name','size','purpose','description','image'])
    assert.equal(typeof item[field],'string',item.id+': '+field);
  assert.match(item.image,/^[a-z0-9-]+\.webp$/);
  assert.equal(item.price,null,'no unapproved prices');
  assert.equal(item.available,false,'no unsourced stock availability');
}
assert(html.includes('name="robots" content="noindex,nofollow"'),'must stay unindexed before release');
for(const id of ['productGrid','brandFilter','purposeFilter','keyword','productDialog'])
  assert(html.includes('id="'+id+'"'),'missing '+id);
assert(html.includes('assets/dog-food-products.js'));
assert(html.includes('assets/dog-food.js'));
assert(css.includes('@media'),'responsive styles required');
assert(!/fetch\s*\(|XMLHttpRequest|\/api\//.test(clientJs),'catalog must not contact live API');
assert(!/Stripe|Checkout|決済する|購入を確定|注文を確定/.test(html+clientJs),'no payment/checkout before release');
for(const missing of ['ziwi-venison.webp','ziwi-tripe-lamb.webp']) assert(p.some(item=>item.image===missing));
console.log('DOG_FOOD_PRELAUNCH_OK|35 products|4 brands|no price|no checkout|noindex');
