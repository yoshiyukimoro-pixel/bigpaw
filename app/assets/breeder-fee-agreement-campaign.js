/* BIG PAW breeder terms: live display status only, no pricing or quota mutations. */
(function(){
  'use strict';
  const status=document.getElementById('bpFeeTermsCampaignStatus');
  const period=document.getElementById('bpFeeTermsCampaignPeriod');
  if(!status||!period)return;
  function show(state,message,details){
    status.dataset.state=state;
    status.textContent=message;
    period.textContent=details||'';
  }
  function dateText(seconds){
    if(!Number.isFinite(seconds))return '';
    const d=new Date(seconds*1000);
    return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'long',day:'numeric'}).format(d);
  }
  async function refresh(){
    try{
      const response=await fetch('/api/campaign/first100',{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw Error('HTTP '+response.status);
      const data=await response.json();
      const end=dateText(data.endsAt);
      const detail=end?'期間終了予定：'+end+'（100頭到達で早期終了）':'先着100頭到達または開始から6か月で新規受付終了';
      if(data.status==='active'&&data.eligible===true){
        // API deliberately hides the exact remainder at 20 or fewer.
        const count=Number.isInteger(data.remaining)&&data.remaining>20?'残り'+data.remaining+'頭・受付中！':'残りわずか・受付中！';
        show('active',count,detail);
      }else if(data.status==='sold_out'){
        show('sold_out','先着100頭に達したため新規受付終了',end?'期間：'+end+'まで（100頭到達で早期終了）':'キャンペーンは受付終了しました');
      }else if(data.status==='ended'){
        show('ended','キャンペーン期間が終了しました',end?'終了日：'+end:'');
      }else if(data.status==='upcoming'){
        show('upcoming','キャンペーン開始前です',detail);
      }else{
        show('inactive','現在、キャンペーンの新規受付はありません','過去に無料適用が確定した取引は、その記録に従います。');
      }
    }catch(e){
      show('unavailable','現在の受付状況を確認できません','無料適用の可否は成約申請時のBIG PAWの記録で決まります。');
      console.warn('BIG PAW 成約手数料適用条件：キャンペーン状態の取得失敗',e);
    }
  }
  document.addEventListener('bigpaw:campaign-refresh',refresh);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  refresh();
})();