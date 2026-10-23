#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {prioritize}=require('../app/assets/oshiwan-search-priority.js');

const dogs=Array.from({length:10},(_,i)=>({
 id:'p'+i,breed:'スタンダードプードル',breedKey:'standard-poodle',
 status:'募集中',price:100000+i*5000
}));
const groups=[{breed:'スタンダードプードル',puppies:dogs.slice(5).map(x=>({id:x.id}))}];
const snapshot=JSON.stringify(dogs);
const test1=prioritize(dogs,groups);
assert.equal(test1.ordered.length,10,'total result count stays ten');
assert.deepEqual(test1.ordered.slice(0,5).map(x=>x.id),['p5','p6','p7','p8','p9'],'featured occupy first five search positions');
assert.deepEqual(test1.ordered.slice(5).map(x=>x.id),['p0','p1','p2','p3','p4'],'regular listings follow');
assert.equal(new Set(test1.ordered.map(x=>x.id)).size,10,'no puppy is duplicated');
assert.equal(JSON.stringify(dogs),snapshot,'regular sort source stays unchanged');
assert.deepEqual(test1.featuredIds,['p5','p6','p7','p8','p9']);

const two=prioritize(dogs,[{puppies:[{id:'p9'},{id:'p8'}]}]);
assert.deepEqual(two.ordered.slice(0,2).map(x=>x.id),['p9','p8']);
assert.equal(two.ordered.length,10,'two promoted puppies still leave ten total');
assert.deepEqual(prioritize(dogs,[]).ordered, dogs,'no advertisements yields regular order');
assert.deepEqual(prioritize(dogs,[{puppies:[{id:'unknown'}]}]).ordered,dogs,'unmatched promo does not create cards');

const filtered=dogs.filter(x=>x.id==='p1'||x.id==='p8');
const filterResult=prioritize(filtered,groups);
assert.deepEqual(filterResult.ordered.map(x=>x.id),['p8','p1'],'filters happen before promotion and other dogs stay excluded');
assert.deepEqual(filterResult.featuredIds,['p8']);

const bad=dogs.slice();bad[5]={...bad[5],status:'成約済み'};
const cancelled=prioritize(bad,groups);
assert(!cancelled.featuredIds.includes('p5'),'sold puppies never promoted');
assert.equal(cancelled.ordered.length,10,'promotion cannot remove regular status data');

const duplicate=prioritize(dogs,[{puppies:[{id:'p5'},{id:'p5'},{id:'p6'}]}]);
assert.deepEqual(duplicate.featuredIds,['p5','p6'],'duplicate promotion IDs appear only once');
assert.equal(duplicate.ordered.length,10);

const mixed=[
 {breed:'スタンダードプードル',puppies:dogs.slice(0,5).map(x=>({id:x.id}))},
 {breed:'ゴールデンレトリバー',puppies:dogs.slice(5).map(x=>({id:x.id}))}
];
const mix=prioritize(dogs,mixed);
assert.deepEqual(mix.featuredIds,['p0','p5','p1','p6','p2'],'multiple breeds share five positions fairly');
assert.equal(mix.ordered.length,10);
assert.equal(prioritize(dogs,groups,2).featuredIds.length,2,'promotion limit can be reduced but not exceed five');
assert.equal(prioritize(dogs,groups,100).featuredIds.length,5,'promotion cap is five');

const search=fs.readFileSync(path.resolve(__dirname,'../app/search-list-rebuild.html'),'utf8');
const homepage=fs.readFileSync(path.resolve(__dirname,'../app/index.html'),'utf8');
assert(search.includes('oshiwan-search-priority.js'),'live search source loads the sorter');
assert(search.includes('window.BigPawOshiwanSearch.prioritize(list,oshiwanGroups,5)'),'search results are promoted after filtering and regular sorting');
assert(search.includes('bp-oshi-promoted') && search.includes('bp-oshi-search-pr'),'promoted cards visually show sponsored marker');
assert(!homepage.includes('<script src="assets/oshiwan.js'),'separate homepage featured section removed');
console.log('OSHIWAN_SEARCH_PRIORITY_OK|ten_results|five_sponsored_first|all_regular_follow|no_duplicates|filters|sold|multi_breed|homepage_removed');
