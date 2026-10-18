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

// Validate actual editor override (not only the inline HTML handler).
const editorSafety=fs.readFileSync('app/breeder-editor-safety-fix.js','utf8');
const es=editorSafety.indexOf('  const breedKey=name=>{');
const ee=editorSafety.indexOf('  const editId=',es);
assert(es>=0&&ee>es,'real overridden editor breedKey available');
const getEditorKey=new Function('window',editorSafety.slice(es,ee)+'\nreturn breedKey;')({
  BIGPAW_BREEDS:[
    {ja:'スタンダードプードル',key:'standard-poodle'},
    {ja:'サモエド',key:'samoyed'},
    {ja:'その他の犬種・ミックス犬',key:'other'}
  ]
});
assert.equal(getEditorKey('シーパドゥードル'),'other','custom breed must NOT be sent as breedKey');
assert.equal(getEditorKey('ゴールデンドゥードル'),'other');
assert.equal(getEditorKey('サモエド'),'samoyed','standard breeds still retain original key');
assert.equal(getEditorKey('スタンダードプードル'),'standard-poodle');
assert.match(editorSafety,/breed:value\('breed'\)/,'free-text value is saved as breed');
assert.match(editorSafety,/breedKey:breedKey\(value\('breed'\)\)/,'real editor uses normalized category key');
assert.match(editor,/name\]\|\|'other'/,'inline fallback must also normalize category');

// Test ACTUAL public search filter and legacy normalization extracted from source.
const helperStart=search.indexOf('      function searchableBreedKey(p){');
const helperEnd=search.indexOf('      function render(scroll){',helperStart);
assert(helperStart>0&&helperEnd>helperStart,'legacy custom breed key normalization installed');
const helper=search.slice(helperStart,helperEnd);
const filterStart=search.indexOf('        if(selected.length)list=list.filter',helperEnd);
const filterEnd=search.indexOf("        if(g!=='all')",filterStart);
assert(filterStart>0&&filterEnd>filterStart,'complete public breed filter exists');
const filter=new Function('selected','b','customBreedWrap','customBreedQuery','list','window',
 helper+search.slice(filterStart,filterEnd)+'\nreturn list;');
const puppies=[
 {breedKey:'other',breed:'ゴールデンドゥードル'},
 {breedKey:'other',breed:'ラブラドゥードル'},
 {breedKey:'シーパドゥードル',breed:'シーパドゥードル'}, // legacy bad key, already saved in production
 {breedKey:'その他の犬種・ミックス犬',breed:'バーニードゥードル'},
 {breedKey:'standard-poodle',breed:'スタンダードプードル'},
 {breedKey:'standard',breed:'スタンダードプードル'}, // old known-breed key
 {breedKey:'samoyed',breed:'サモエド'}
];
const breeds=[
 {ja:'その他の犬種・ミックス犬',key:'other'},
 {ja:'スタンダードプードル',key:'standard-poodle'},
 {ja:'サモエド',key:'samoyed'}
];
function run(keys,key,text){
 const box={style:{}},input={value:text};
 const result=filter(keys,key,box,input,puppies.slice(),{BIGPAW_BREEDS:breeds});
 return {names:result.map(x=>x.breed),visible:box.style.display,value:input.value};
}
assert.deepEqual(run(['other'],'other','シーパドゥードル').names,['シーパドゥードル'],
 'legacy saved names must appear in other search');
assert.deepEqual(run(['other'],'other','ゴールデン').names,['ゴールデンドゥードル']);
assert.deepEqual(run(['other'],'other','ドゥードル').names,
 ['ゴールデンドゥードル','ラブラドゥードル','シーパドゥードル','バーニードゥードル']);
assert.deepEqual(run(['other','standard-poodle'],'all','ラブラ').names,
 ['ラブラドゥードル','スタンダードプードル','スタンダードプードル']);
assert.deepEqual(run(['standard-poodle'],'standard-poodle','何か').names,
 ['スタンダードプードル','スタンダードプードル']);
assert.deepEqual(run(['samoyed'],'samoyed','').names,['サモエド']);
assert.equal(run(['standard-poodle'],'standard-poodle','何か').value,'');
assert.equal(run(['other'],'other','').visible,'block');
assert.equal(run([],'all','').visible,'none');
assert.deepEqual(run(['other'],'other','ラブラ<script>').names,[],'safe text-only match');
console.log('CUSTOM_BREED_UI_OK|editor_override=verified|correct_other_key=verified|legacy_data=searchable|custom_name_filter=verified|standard_breeds=preserved|photo_ui=intact');
