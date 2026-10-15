#!/usr/bin/env node
'use strict';
// Test the REAL runtime save override against a disposable local development API.
// Must not be pointed at the public BIG PAW site. No production records are used.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {URLSearchParams}=require('node:url');
const BASE=process.argv[2]||'';
let TOKEN='',KENNEL_A='',KENNEL_B='';
if(!/^http:\/\/(?:127\.0\.0\.1|localhost):\d+$/.test(BASE))
  throw Error('ISOLATED_LOCAL_TEST_ONLY');
const proxySource=fs.readFileSync('app/assets/operator-proxy-listing.js','utf8');
const saveSource=fs.readFileSync('app/breeder-editor-safety-fix.js','utf8');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==','base64');
async function api(method,path,body){
  const h=TOKEN?{Authorization:'Bearer '+TOKEN}:{};
  let payload;
  if(body!==undefined){h['Content-Type']='application/json';payload=JSON.stringify(body)}
  const response=await fetch(BASE+'/api'+path,{method,headers:h,body:payload});
  const result=await response.json();
  if(!response.ok){
    const err=Error(result.message||result.error||'request_failed');
    err.status=response.status;err.data=result;throw err;
  }
  return result;
}
async function upload(puppyId,file,i){
  const form=new FormData();
  form.append('puppyId',puppyId);
  form.append('file',file,'proxy-'+i+'.png');
  const res=await fetch(BASE+'/api/uploads',{method:'POST',headers:{Authorization:'Bearer '+TOKEN},body:form});
  const data=await res.json();
  if(!res.ok){const err=Error(data.error||'upload_failed');err.status=res.status;throw err;}
  return data;
}
function element(value='',options=[]){
  return {value,checked:false,disabled:false,textContent:'',style:{},options:options.map(x=>({value:x,textContent:x})),
    children:[],files:[],firstChild:{},
    insertBefore(x){this.options.unshift(x)},replaceChildren(...xs){this.options=xs.map(x=>({value:x.value,textContent:x.textContent}))}};
}
async function createScenario({scope=KENNEL_A,verified=true,photos=1}={}){
  const values={
    puppyName:'ヤンヤン',breed:'サモエド',gender:'男の子',color:'ホワイト',
    birth:'2024-09-04',price:'130000',weight:'23',
    adultMin:'',adultMax:'',father:'未登録',mother:'未登録',
    status:'募集中',health:'',healthStatus:'未登録',
    vaccineStatus:'接種済み',microchipStatus:'未登録',geneticTestStatus:'未登録',
    appealPoint:'新しい家族を募集中',desc:'サモエドのヤンヤン。価格13万円（税込）。血統証明書の発行はできません。'
  };
  const ids={};
  for(const [k,v] of Object.entries(values))ids[k]=element(v);
  ids.breed.options=[{value:'サモエド',textContent:'サモエド'}];
  ids.father.options=[{value:'未登録',textContent:'未登録'}];
  ids.mother.options=[{value:'未登録',textContent:'未登録'}];
  ids.photo=element();ids.photo.files=Array.from({length:photos},()=>new Blob([png],{type:'image/png'}));
  const submit=element();submit.textContent='この内容で掲載する';
  const form={firstChild:{},notice:null,querySelector(){return submit},insertBefore(v){this.notice=v}};
  const title=element();
  const document={
    querySelector(selector){return selector==='form'?form:selector==='h1'?title:null},
    getElementById(id){return ids[id]||null},
    querySelectorAll(){return []},
    createElement(){return element()},
  };
  const alerts=[];const created=[];const seen=[];
  const location={search:'?breederId='+scope,href:'breeder-puppy-new.html?breederId='+scope};
  const window={renderPersistedPhotos(){},__BIGPAW_BREEDER_EDITOR_SAFETY__:false};
  const BigPawAPI={
    me:async()=>({role:'operator'}),
    request:async(path,options={})=>{
      if(path.startsWith('/breeder-profile?id='))return api('GET',path);
      return api(options.method||'GET',path,options.body);
    },
    breederPuppies:async({breederId})=>api('GET','/breeder/puppies?breederId='+encodeURIComponent(breederId))
  };
  const BigPawBridge={
    breederPuppies:async()=>api('GET','/breeder/puppies'),
    addPuppy:async(data)=>{seen.push(data);const p=await api('POST','/puppies',data);created.push(p);return p;},
    updatePuppy:async(pid,data)=>api('PATCH','/puppies/'+pid,data),
    upload:(file,pid)=>upload(pid,file,Math.floor(Math.random()*999)),
  };
  const context={window,document,location,URLSearchParams,BigPawAPI,BigPawBridge,
    alert:(s)=>alerts.push(String(s)),sessionStorage:{removeItem(){}},editId:'',
    Option:function(label,value){this.textContent=label;this.value=value},
    console};
  await vm.runInNewContext(proxySource,context,{filename:'operator-proxy-listing.js'});
  assert.equal(window.bigpawProxyId,scope,'real proxy selection resolves verified breeder');
  // Simulate the actual ChatGPT form importer filling verified facts after proxy clears defaults.
  for(const [k,v] of Object.entries(values))if(ids[k])ids[k].value=v;
  if(!verified)window.bigpawProxyId=KENNEL_B;
  vm.runInNewContext(saveSource,context,{filename:'breeder-editor-safety-fix.js'});
  return {context,window,location,alerts,created,seen,ids,submit};
}
async function run(){
  // Authenticate only to the disposable development instance; the preceding
  // proxy test already created these synthetic A and B kennel fixtures.
  const login=await api('POST','/login',{email:'admin@bigpaw.jp',password:'admin1234'});
  TOKEN=login.token;
  assert(TOKEN,'isolated operator credentials verified');
  const listings=await api('GET','/operator/listings');
  const a=listings.find(x=>String(x.breeder||'').includes('代理掲載A犬舎'));
  const b=listings.find(x=>String(x.breeder||'').includes('代理掲載B犬舎'));
  assert(a?.breederId&&b?.breederId&&a.breederId!==b.breederId,'synthetic test breeders must exist');
  KENNEL_A=a.breederId;KENNEL_B=b.breederId;
  // A mismatched account MUST fail before the first POST.
  let s=await createScenario({verified:false});
  await s.window.savePuppy({preventDefault(){},submitter:s.submit});
  assert.equal(s.seen.length,0,'mismatched selection blocked before POST');
  assert.equal(s.created.length,0,'no unassigned puppy created');
  assert(s.alerts.some(x=>x.includes('掲載先の犬舎')),'actionable selection error');
  console.log('PASS|operator_runtime_rejects_unverified_scope');
  for(const count of [1,5,10]){
    s=await createScenario({photos:count});
    await s.window.savePuppy({preventDefault(){},submitter:s.submit});
    assert.equal(s.seen.length,1,'actual save handler submitted exactly once');
    assert.equal(s.seen[0].breederId,KENNEL_A,'actual submitted JSON includes verified target breeder');
    assert.equal(s.seen[0].name,'ヤンヤン','actual submitted JSON keeps supplied dog name');
    assert.equal(s.created[0].breederId,KENNEL_A,'created server puppy belongs to selected breeder');
    assert.equal(s.created[0].name,'ヤンヤン','server persisted real dog name');
    assert(s.alerts.includes('子犬情報を掲載しました。'),'success only after saved and confirmed');
    assert.equal(s.location.href,'admin.html?breederId='+encodeURIComponent(KENNEL_A),'return to selected kennel');
    const pid=s.created[0].id;
    const a=await api('GET','/breeder/puppies?breederId='+encodeURIComponent(KENNEL_A));
    const b=await api('GET','/breeder/puppies?breederId='+encodeURIComponent(KENNEL_B));
    assert(a.some(x=>x.id===pid&&x.breederId===KENNEL_A&&x.name==='ヤンヤン'),'selected kennel readback exact name');
    assert(b.every(x=>x.id!==pid),'other kennel never receives this puppy');
    const saved=await api('GET','/puppies/'+pid+'/photos');
    assert.equal(saved.length,count,count+' photos persisted');
    assert.equal(saved.filter(x=>x.isMain).length,1,'exactly one main photo');
    console.log('PASS|operator_real_runtime_save|breeder=selected|name=correct|photos='+count+'|scoped_readback');
  }
  console.log('OPERATOR_RUNTIME_SAVE_E2E_OK|real_override|api_post|images_1_5_10|verified_scope|readback|no_public_test');
}
run().catch(err=>{console.error('OPERATOR_RUNTIME_SAVE_E2E_FAILED|'+err.stack);process.exit(1)});
