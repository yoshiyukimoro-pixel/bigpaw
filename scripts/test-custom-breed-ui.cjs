'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const data = fs.readFileSync('app/assets/breed-data.js','utf8');
const editor = fs.readFileSync('app/breeder-puppy-new.html','utf8');
const search = fs.readFileSync('app/search-list-rebuild.html','utf8');
const detail = fs.readFileSync('app/puppy-detail.html','utf8');

new vm.Script(data, {filename:'breed-data.js'});
for (const [i,s] of [...search.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].entries()){
  new vm.Script(s[1],{filename:'search:inline:'+i});
}
assert.match(editor, /<select id="breed">/, 'breeder edit form remains present');
assert.match(editor, /BigPawBridge\.addPuppy/, 'registration intact');
assert.match(editor, /BigPawBridge\.updatePuppy/, 'editing intact');
assert.match(editor, /photoPreview/, 'photo UI intact');
assert.match(detail,/BigPawBridge\.puppy/, 'puppy detail intact');
assert.match(data,/other\.textContent=OTHER_LABEL/, 'other choice exists');
assert.match(data,/input\.required=true/, 'required field on other choice');
assert.match(data,/input\.required=false/, 'normal breeds remain optional');
assert.match(data,/input\.maxLength=80/, 'custom breed maximum length');
assert.match(data,/o\.value=name;\s*o\.textContent=name;\s*o\.selected=true/, 'name is selected as breed');
assert.match(data,/return OTHER_KEY/, 'custom breeds remain in other category');
assert.match(data,/if\(d\.breedKey===OTHER_KEY\|\|\(!known&&d\.breed\)\)/, 'editing custom names loads them');
assert.match(data,/if\(isOther&&\(!input\.value\.trim\(\)/, 'blank custom breed blocked');
assert.match(search,/id="bpOtherBreedSearchWrap"/, 'name search rendered');
assert.match(search,/customBreedQuery\.addEventListener\('input'/, 'live filtering wired');
assert.match(search,/selected\.includes\('other'\)/, 'multi-select other supported');

// Test the ACTUAL filtering code extracted from search.html, not a reimplementation.
const start=search.indexOf("        const isOtherSelected=selected.includes('other')");
const end=search.indexOf("        if(g!=='all')",start);
assert(start>0&&end>start,'custom name filter exists in search render');
const body=search.slice(start,end);
const filter = new Function('selected','b','customBreedWrap','customBreedQuery','list',
  body+'\nreturn list;');
const puppies=[
 {breedKey:'other',breed:'ゴールデンドゥードル'},
 {breedKey:'other',breed:'ラブラドゥードル'},
 {breedKey:'other',breed:'バーニードゥードル'},
 {breedKey:'standard-poodle',breed:'スタンダードプードル'}
];
function run(keys,key,text){
 const box={style:{}},input={value:text};
 const result=filter(keys,key,box,input,puppies.slice());
 return {names:result.map(x=>x.breed),visible:box.style.display,value:input.value};
}
assert.deepEqual(run(['other'],'other','ゴールデン').names,['ゴールデンドゥードル']);
assert.deepEqual(run(['other'],'other','ドゥードル').names,puppies.slice(0,3).map(x=>x.breed));
assert.deepEqual(run(['other','standard-poodle'],'all','ラブラ').names,['ラブラドゥードル','スタンダードプードル']);
assert.deepEqual(run(['standard-poodle'],'standard-poodle','何か').names,puppies.map(x=>x.breed));
assert.equal(run(['standard-poodle'],'standard-poodle','何か').value,'');
assert.equal(run(['other'],'other','').visible,'block');
assert.equal(run([],'all','').visible,'none');
assert.deepEqual(run(['other'],'other','ラブラ<script>').names,[],'HTML cannot match by injection');
console.log('CUSTOM_BREED_UI_OK|registration=present|edit=present|other_required=true|free_text=preserved|search=matching|multi_select=safe|standard_search=unchanged');
