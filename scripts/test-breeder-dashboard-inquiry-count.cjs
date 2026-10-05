const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('app/admin.html','utf8');
const match=html.match(/<script>\s*(let dogs=\[\];[\s\S]*?load\(\);)\s*<\/script>/);
assert(match,'admin dashboard inline script found');
const code=match[1];

async function run(inquiries){
  const el=()=>({textContent:'',innerHTML:'',style:{display:''}});
  const ctx={
    console,
    sOpen:el(),sTalk:el(),sDone:el(),sInquiry:el(),dogList:el(),loginNotice:el(),billingSuspend:el(),
    alert(){},prompt(){return null},encodeURIComponent,
    BigPawBridge:{
      breederPuppies:async()=>[],
      me:async()=>({role:'breeder'}),
      isServerMode:()=>true,
      inquiries:async()=>inquiries,
      updatePuppy:async()=>{}
    },
    BigPawAPI:{breederProfile:async()=>({billing_suspended:false})},
    BigPaw:{esc:s=>String(s??''),currency:n=>String(n)}
  };
  vm.createContext(ctx);
  vm.runInContext(code,ctx,{filename:'admin-inline.js'});
  for(let i=0;i<20;i++){await new Promise(r=>setTimeout(r,0));if(ctx.sInquiry.textContent!=='')break}
  return ctx.sInquiry.textContent;
}

(async()=>{
  assert.equal(await run([
    {status:'取引終了'},{status:'成約済み'},{status:'取引終了'}
  ]),'0','three historical inquiries must display zero');
  assert.equal(await run([
    {status:'取引終了'},{status:'成約済み'},{status:'未返信'},{status:'見学調整中'}
  ]),'2','only active inquiry statuses are counted');
  console.log('BREEDER_DASHBOARD_INQUIRY_COUNT_UI_OK|historical_3_to_0|active_only');
})().catch(e=>{console.error(e);process.exit(1)});
