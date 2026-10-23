#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {prioritize,paginate}=require('../app/assets/oshiwan-search-priority.js');

const dogs=Array.from({length:10},(_,i)=>({
 id:'p'+i,breed:'スタンダードプードル',breedKey:'standard-poodle',
 status:'募集中',price:100000+i*5000
}));
const groups=[{breed:'スタンダードプードル',puppies:dogs.slice(5).map(x=>({id:x.id}))}];
const snapshot=JSON.stringify(dogs);
const test1=prioritize(dogs,groups);
assert.equal(test1.ordered.length,15,'10 distinct listings plus 5 separate featured placements = 15 display slots');
assert.deepEqual(test1.ordered.slice(0,5).map(x=>x.id),['p5','p6','p7','p8','p9'],'featured occupy first five search positions');
assert.deepEqual(test1.ordered.slice(5).map(x=>x.id),dogs.map(x=>x.id),'ALL ten puppies, including all promoted puppies, remain in the regular listings');
assert.equal(new Set(test1.ordered.map(x=>x.id)).size,10,'ten distinct puppies remain despite intentional PR repetitions');
assert.equal(test1.ordered.filter(x=>x.id==='p5').length,2,'same puppy appears in PR slot and regular listing');
assert.equal(JSON.stringify(dogs),snapshot,'regular sort source stays unchanged');
assert.deepEqual(test1.featuredIds,['p5','p6','p7','p8','p9']);

const two=prioritize(dogs,[{puppies:[{id:'p9'},{id:'p8'}]}]);
assert.deepEqual(two.ordered.slice(0,2).map(x=>x.id),['p9','p8']);
assert.equal(two.ordered.length,12,'two promoted placements plus ten regular listings');
assert.deepEqual(prioritize(dogs,[]).ordered, dogs,'no advertisements yields regular order');
assert.deepEqual(prioritize(dogs,[{puppies:[{id:'unknown'}]}]).ordered,dogs,'unmatched promo does not create cards');

const filtered=dogs.filter(x=>x.id==='p1'||x.id==='p8');
const filterResult=prioritize(filtered,groups);
assert.deepEqual(filterResult.ordered.map(x=>x.id),['p8','p1','p8'],'filters happen before promotion and filtered sponsored dog remains in organic results');
assert.deepEqual(filterResult.featuredIds,['p8']);

const bad=dogs.slice();bad[5]={...bad[5],status:'成約済み'};
const cancelled=prioritize(bad,groups);
assert(!cancelled.featuredIds.includes('p5'),'sold puppies never promoted');
assert.equal(cancelled.ordered.length,14,'promotion cannot remove regular status data');

const duplicate=prioritize(dogs,[{puppies:[{id:'p5'},{id:'p5'},{id:'p6'}]}]);
assert.deepEqual(duplicate.featuredIds,['p5','p6'],'duplicate promotion IDs appear only once in sponsored positions');
assert.equal(duplicate.ordered.length,12,'sponsored slots deduplicated while preserving all regular puppies');

const mixed=[
 {breed:'スタンダードプードル',puppies:dogs.slice(0,5).map(x=>({id:x.id}))},
 {breed:'ゴールデンレトリバー',puppies:dogs.slice(5).map(x=>({id:x.id}))}
];
const mix=prioritize(dogs,mixed);
assert.deepEqual(mix.featuredIds,['p0','p5','p1','p6','p2'],'multiple breeds share five positions fairly');
assert.equal(mix.ordered.length,15,'all regular dogs preserved with mixed breeds');
assert.equal(prioritize(dogs,groups,2).featuredIds.length,2,'promotion limit can be reduced but not exceed five');
assert.equal(prioritize(dogs,groups,100).featuredIds.length,5,'promotion cap is five');

const fifty=Array.from({length:50},(_,i)=>({id:'dog'+i,status:'募集中',breed:'スタンダードプードル'}));
const promoted=prioritize(fifty,[{puppies:fifty.slice(45).map(x=>({id:x.id}))}]);
assert.equal(promoted.ordered.length,55,'50 distinct puppies and 5 sponsored cards have 55 display slots');
assert.equal(new Set(promoted.ordered.map(x=>x.id)).size,50,'still exactly 50 distinct puppies');
assert.deepEqual([1,2,3].map(n=>paginate(promoted.ordered,n,20).visible.length),[20,20,15],'pagination shows 20, 20, 15 cards');
assert.deepEqual([1,2,3].map(n=>paginate(promoted.ordered,n,20).page),[1,2,3]);
assert.equal(paginate(promoted.ordered,99,20).page,3,'oversized page index clamped safely');
assert.equal(paginate(promoted.ordered,0,20).page,1,'page zero clamped');
const actualSlotIDs=[1,2,3].flatMap(n=>paginate(promoted.ordered,n,20).visible.map(p=>p.id));
assert.deepEqual(actualSlotIDs,promoted.ordered.map(p=>p.id),'pagination never drops or reorders puppies');

const search=fs.readFileSync(path.resolve(__dirname,'../app/search-list-rebuild.html'),'utf8');
const homepage=fs.readFileSync(path.resolve(__dirname,'../app/index.html'),'utf8');
assert(search.includes('oshiwan-search-priority.js'),'live search source loads the sorter');
assert(search.includes('window.BigPawOshiwanSearch.prioritize(list,oshiwanGroups,5)'),'search results are promoted after filtering and regular sorting');
assert(search.includes('window.BigPawOshiwanSearch.paginate(list,pageNum,PAGE_SIZE)'),'search applies pagination to full display list');
assert(search.includes('PAGE_SIZE=20'),'twenty entries per page');
assert(search.includes('bp-oshi-promoted') && search.includes('bp-oshi-search-pr'),'promoted cards visually show sponsored marker');
assert(search.includes('const promoted=position<priority.featuredIds.length'),'only dedicated first five placements receive PR badge');
assert(!homepage.includes('<script src="assets/oshiwan.js'),'separate homepage featured section removed');
console.log('OSHIWAN_SEARCH_PRIORITY_OK|ten_regular_plus_five_PR|intentional_PR_duplicates|fifty_dogs|20_20_15_pagination|filters|sold|multi_breed|homepage_removed');
