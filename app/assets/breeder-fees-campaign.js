/* BIG PAW breeder fees only: presentation from the live campaign API.
   No mutations, no local quota bookkeeping, no changes to buyer/operator UI. */
(function(){
  'use strict';
  const byId=id=>document.getElementById(id);
  const banner=byId('bpBreederCampaign');
  const hero=byId('bpBreederStandardHero');
  const calculator=byId('bpBreederRegularCalculator');
  const fee=byId('bpBreederStandardFee');
  const desc=byId('bpBreederFeeDescription');
  const stepTitle=byId('bpBreederFinalStepTitle');
  const stepDescription=byId('bpBreederFinalStepDescription');
  if(!banner||!hero||!calculator||!fee||!desc||!stepTitle||!stepDescription)return;
  function showNormal(){
    banner.hidden=true;
    hero.hidden=false;
    calculator.hidden=false;
    fee.textContent='5%（税込）';
    desc.textContent='成約手数料は、BIG PAW経由で成約した子犬の最終生体販売価格に対して計算します。';
    stepTitle.textContent='確認後5%を請求';
    stepDescription.textContent='BIG PAW運営の確認後に成約確定し、請求書を自動発行。請求日から7日以内にお支払いください。';
  }
  function showCampaign(data){
    hero.hidden=true;
    banner.hidden=false;
    calculator.hidden=true;
    fee.textContent='0円（先着100頭対象）';
    desc.textContent='先着100頭の成約申請に限り、通常成約手数料5％を免除します。対象外は通常5％。推しワン経由の成約は追加利用料3％（税込）がかかります。';
    stepTitle.textContent='無料対象なら通常手数料0円';
    stepDescription.textContent='成約申請時に先着100頭の無料枠を確保し、お迎え完了時に通常成約手数料5％を免除します。推しワン利用料3％は別途発生し、請求書はお迎え完了時に発行します。';
    const remaining=Number.isInteger(data.remaining)&&data.remaining>20
      ? '残り'+data.remaining+'頭・受付中！'
      : '残りわずか・受付中！';
    byId('bpBreederCampaignCount').textContent=remaining;
    let deadline='';
    if(Number.isFinite(data.endsAt)){
      const end=new Date(data.endsAt*1000);
      if(!isNaN(end.getTime())){
        const day=new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'long',day:'numeric'}).format(end);
        deadline='期間：'+day+'まで（100頭到達で早期終了）。';
      }
    }
    byId('bpBreederCampaignEnd').textContent=deadline;
  }
  async function update(){
    try{
      const result=await fetch('/api/campaign/first100',{credentials:'same-origin',cache:'no-store'});
      if(!result.ok)throw new Error('HTTP '+result.status);
      const data=await result.json();
      if(data&&data.status==='active'&&data.eligible===true){
        showCampaign(data);
      }else{
        // sold_out, ended, inactive: ordinary 5% headline reappears automatically.
        showNormal();
      }
    }catch(err){
      // Don't claim the 5% fee is waived when live eligibility cannot be verified.
      showNormal();
      console.warn('BIG PAW 成約キャンペーンの状態を確認できませんでした',err);
    }
  }
  document.addEventListener('bigpaw:campaign-refresh',update);
  update();
})();
