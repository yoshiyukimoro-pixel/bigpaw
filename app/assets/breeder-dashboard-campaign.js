/* BIG PAW breeder dashboard: read-only first-100 campaign banner.
 * Never infer free eligibility from local state. Hide for operator/buyer/not logged in.
 * Fee waiver eligibility and remaining slots are provided solely by the server API. */
(function(){
  'use strict';
  const banner=document.getElementById('bpBreederDashboardCampaign');
  const count=document.getElementById('bpBreederDashboardCampaignCount');
  if(!banner||!count)return;
  let currentRole=null,revision=0;
  async function updateForRole(role){
    currentRole=role||null;
    const request=++revision;
    banner.hidden=true;
    count.textContent='';
    if(role!=='breeder')return;
    try{
      const response=await fetch('/api/campaign/first100',{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw new Error('HTTP '+response.status);
      const data=await response.json();
      if(revision!==request||currentRole!=='breeder')return;
      if(!data||data.status!=='active'||data.eligible!==true||!Number.isInteger(data.remaining)||data.remaining<1)return;
      count.textContent=data.remaining>20?'残り'+data.remaining+'頭・受付中！':'残りわずか・受付中！';
      banner.hidden=false;
    }catch(err){
      // Fail closed instead of advertising an unverified waiver or stale counter.
      if(revision===request){banner.hidden=true;count.textContent='';}
      console.warn('BIG PAW 管理画面の成約キャンペーン情報を確認できませんでした',err);
    }
  }
  document.addEventListener('bigpaw:campaign-refresh',()=>updateForRole(currentRole));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&currentRole==='breeder')updateForRole('breeder');});
  window.addEventListener('focus',()=>{if(currentRole==='breeder')updateForRole('breeder');});
  // A campaign may finish while the dashboard is open, without navigation.
  setInterval(()=>{if(currentRole==='breeder'&&!document.hidden)updateForRole('breeder');},60000);
  window.BigPawBreederDashboardCampaign=Object.freeze({updateForRole});
})();