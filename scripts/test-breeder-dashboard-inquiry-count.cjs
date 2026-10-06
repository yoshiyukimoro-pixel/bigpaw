const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('app/admin.html','utf8');
const match=html.match(/<script>\s*(let dogs=\[\],operatorScopeId=''[\s\S]*?load\(\);)\s*<\/script>/);
assert(match,'admin dashboard inline script found');
const code=match[1];

async function run({role='breeder',inquiries=[],breeders=[],breederId='',puppyRows=[]}={}){
  const el=()=>({textContent:'',innerHTML:'',value:'',style:{display:''},onchange:null});
  const els={
    sOpen:el(),sTalk:el(),sDone:el(),sInquiry:el(),dogList:el(),loginNotice:el(),billingSuspend:el(),
    operatorScope:el(),operatorBreeder:el(),kennelModeLabel:el()
  };
  const calls=[];
  const location={search:breederId?'?breederId='+encodeURIComponent(breederId):'',href:'',pathname:'/admin.html'};
  const ctx={
    console,location,
    ...els,
    alert(){},prompt(){return null},encodeURIComponent,URLSearchParams,
    BigPawBridge:{
      breederPuppies:async()=>puppyRows,
      me:async()=>({role}),
      isServerMode:()=>true,
      inquiries:async()=>inquiries,
      updatePuppy:async()=>{}
    },
    BigPawAPI:{
      breederProfile:async()=>({billing_suspended:false}),
      breederPuppies:async params=>{calls.push({kind:'breederPuppies',params});return puppyRows},
      request:async p=>{
        calls.push({kind:'request',path:p});
        if(p==='/operator/breeders')return breeders;
        if(p.startsWith('/breeder-profile?id='))return {billing_suspended:false,id:decodeURIComponent(p.split('=')[1])};
        throw new Error('unexpected '+p);
      }
    },
    BigPaw:{esc:s=>String(s??''),currency:n=>String(n)}
  };
  vm.createContext(ctx);
  vm.runInContext(code,ctx,{filename:'admin-inline.js'});
  for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,0));if(ctx.sInquiry.textContent!==''||ctx.dogList.innerHTML)break}
  return {ctx,calls};
}

(async()=>{
  let r=await run({inquiries:[{status:'取引終了'},{status:'成約済み'},{status:'取引終了'}]});
  assert.equal(r.ctx.sInquiry.textContent,'0','three historical inquiries must display zero');

  r=await run({inquiries:[{status:'取引終了'},{status:'成約済み'},{status:'未返信'},{status:'見学調整中'}]});
  assert.equal(r.ctx.sInquiry.textContent,'2','only active inquiry statuses are counted');

  const breeders=[{id:'b_dog44',kennel_name:'DOG44'},{id:'b_other',kennel_name:'別犬舎'}];
  const mixedPuppies=[
    {id:'p_dog44',breederId:'b_dog44',name:'DOG44の子犬',breed:'スタンダードプードル',gender:'男の子',color:'ブラック',status:'募集中',price:300000},
    {id:'p_other',breederId:'b_other',name:'他人の子犬',breed:'スタンダードプードル',gender:'女の子',color:'ホワイト',status:'募集中',price:320000}
  ];
  r=await run({
    role:'operator',breeders,puppyRows:mixedPuppies,
    inquiries:[
      {breeder_id:'b_dog44',status:'未返信'},
      {breeder_id:'b_other',status:'未返信'}
    ]
  });
  let autoCall=r.calls.find(x=>x.kind==='breederPuppies');
  assert(autoCall&&autoCall.params.breederId==='b_dog44','operator opening breeder management directly defaults to DOG44');
  assert(r.ctx.dogList.innerHTML.includes('DOG44の子犬'),'direct operator breeder management shows DOG44 puppy');
  assert(!r.ctx.dogList.innerHTML.includes('他人の子犬'),'direct operator breeder management never shows another breeder puppy');
  assert.equal(r.ctx.sOpen.textContent,'1','direct operator view counts only DOG44 puppies');
  assert.equal(r.ctx.sInquiry.textContent,'1','direct operator view counts only DOG44 inquiries');
  assert(r.ctx.kennelModeLabel.textContent.includes('DOG44'),'direct operator view is visibly scoped to DOG44');

  r=await run({
    role:'operator',breeders,breederId:'b_dog44',puppyRows:mixedPuppies,
    inquiries:[
      {breeder_id:'b_dog44',status:'未返信'},
      {breeder_id:'b_other',status:'未返信'},
      {breeder_id:'b_dog44',status:'取引終了'}
    ]
  });
  const call=r.calls.find(x=>x.kind==='breederPuppies');
  assert(call&&call.params.breederId==='b_dog44','operator puppy request carries selected breederId');
  assert(r.ctx.dogList.innerHTML.includes('DOG44の子犬'),'selected breeder puppy is shown');
  assert(!r.ctx.dogList.innerHTML.includes('他人の子犬'),'other breeder puppy is never mixed into selected breeder dashboard');
  assert.equal(r.ctx.sOpen.textContent,'1','only selected breeder open puppy is counted');
  assert.equal(r.ctx.sInquiry.textContent,'1','only selected breeder active inquiries are counted');
  assert(r.ctx.kennelModeLabel.textContent.includes('DOG44'),'operator scope is visibly labeled with selected kennel');

  console.log('BREEDER_DASHBOARD_SCOPE_UI_OK|historical_count|operator_defaults_dog44|selected_only|other_breeder_hidden|inquiries_scoped');
})().catch(e=>{console.error(e);process.exit(1)});
