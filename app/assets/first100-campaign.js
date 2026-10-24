/* BIG PAW: live first-100 breeder campaign. API is source of truth, no client-side counting. */
(function(){
  'use strict';
  const elements=Array.from(document.querySelectorAll('[data-bp-first100]'));
  if(!elements.length)return;
  const safe = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
  const style=document.createElement('style');
  style.textContent='.bp-first100{margin:18px 0;padding:17px 20px;border:1px solid #b8d9ee;border-radius:16px;background:#edf7ff;color:#25557b;font-size:14px;line-height:1.65}.bp-first100 strong{font-size:19px}.bp-first100 .bp-first100-status{display:block;font-weight:900;color:#1b608c;font-size:18px;margin-top:6px}.bp-first100 small{display:block;color:#4f6475;margin-top:8px}.bp-first100 a{color:#195f91;text-decoration:underline;font-weight:700}.bp-first100[data-state=ended],.bp-first100[data-state=sold_out]{background:#f0f2f5;color:#626b76;border-color:#d5d9dd}.bp-first100[data-state=ended] .bp-first100-status,.bp-first100[data-state=sold_out] .bp-first100-status{color:#626b76}';
  document.head.appendChild(style);
  async function refresh(){
    try{
      const res=await fetch('/api/campaign/first100',{cache:'no-store',credentials:'same-origin'});
      if(!res.ok)throw new Error('campaign unavailable');
      const data=await res.json();
      for(const el of elements){
        if(data.status==='inactive'){el.hidden=true;continue;}
        el.hidden=false;
        el.classList.add('bp-first100');
        el.dataset.state=data.status;
        const endDate=new Date(data.endsAt*1000).toLocaleDateString('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'long',day:'numeric'});
        const badge=data.status==='active'?data.remainingLabel:data.status==='sold_out'?'先着100頭に達したため終了しました':data.status==='ended'?'キャンペーン期間は終了しました':'まもなく開始';
        const title=data.status==='active'?'🎉 先着100頭・通常成約手数料5％無料！':'🎉 BIG PAW オープン記念キャンペーン';
        el.innerHTML='<strong>'+safe(title)+'</strong><span class="bp-first100-status">'+safe(badge)+'</span>'+
          '<small>サイト全体の先着100頭・1犬舎の上限なし。成約申請を受け付けた時点で1頭カウントし、キャンセルされても枠は戻りません。'+
          '期間は開始から6か月（'+safe(endDate)+'まで）。100頭到達で早期終了します。推しワン追加3％は無料対象外です。'+
          '掲載料・月額費用は無料。 <a href="breeder-fees.html">詳細を見る</a></small>';
      }
    }catch(err){
      // Avoid showing unverified free offers or misleading counts on an API failure.
      elements.forEach(el=>{el.hidden=true;});
      console.warn('キャンペーン残枠が取得できませんでした',err);
    }
  }
  document.addEventListener('bigpaw:campaign-refresh',refresh);
  refresh();
})();