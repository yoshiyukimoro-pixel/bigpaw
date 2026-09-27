(()=>{
  if(window.__BIGPAW_SALES_HANDOVER_PUBLIC__) return;
  window.__BIGPAW_SALES_HANDOVER_PUBLIC__=true;
  if(!/breeder-detail\.html$/.test(location.pathname)) return;

  const breederId=new URLSearchParams(location.search).get('id')||'';
  if(!breederId) return;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const yn=v=>v===true?'含まれます':v===false?'別途・または含まれません':'未設定';
  const ok=v=>v===true?'受け付けます':v===false?'受け付けません':'未設定';
  const yen=n=>Number(n||0)>0?Number(n).toLocaleString('ja-JP')+'円':'予約金なし';

  function hasContent(s){
    if(!s||!s.configured) return false;
    return (s.pedigreeOrganizations||[]).length||s.pedigreeOther1||s.pedigreeOther2||s.pedigreeNote||
      s.vaccineIncluded!==null||s.vaccineNote||Number(s.reservationAmount||0)>0||s.balanceTiming||s.reservationNote||
      s.sameDayVisit!==null||s.visitNote||s.handoverText||Number(s.minHandoverDays||0)>0||
      s.healthExamIncluded!==null||s.microchipIncluded!==null||s.healthNote||s.cancellationPolicy;
  }

  function row(label,value,detail=''){
    if(!value&&!detail) return '';
    return `<div class="table-row"><div>${esc(label)}</div><div><b>${esc(value||'-')}</b>${detail?`<br><span class="muted">${esc(detail)}</span>`:''}</div></div>`;
  }

  async function load(){
    try{
      const r=await fetch('/api/breeders/'+encodeURIComponent(breederId)+'/sales-handover-settings',{cache:'no-store'});
      if(!r.ok) return;
      const s=await r.json();
      if(!hasContent(s)||document.getElementById('bigpawSalesHandoverPublic')) return;

      const orgs=[...(s.pedigreeOrganizations||[]),s.pedigreeOther1,s.pedigreeOther2].filter(Boolean).join('・');
      const handoverDays=Number(s.minHandoverDays||0)>0?'生後'+Number(s.minHandoverDays)+'日目以降':'';
      const reservation=yen(s.reservationAmount);
      const health=`健康診断：${yn(s.healthExamIncluded)} ／ マイクロチップ：${yn(s.microchipIncluded)}`;

      const box=document.createElement('div');
      box.id='bigpawSalesHandoverPublic';
      box.className='card pad';
      box.style.marginTop='18px';
      box.innerHTML=`<h2>販売・引渡し条件</h2><p class="muted">このブリーダーが登録している基本条件です。子犬ごとの条件がある場合は、問い合わせ時の案内が優先されます。</p><div class="tablelike">
        ${row('血統証明書',orgs||'未設定',s.pedigreeNote||'')}
        ${row('ワクチン代',yn(s.vaccineIncluded),s.vaccineNote||'')}
        ${row('予約金',reservation,[s.balanceTiming,s.reservationNote].filter(Boolean).join('／'))}
        ${row('問い合わせ当日の見学',ok(s.sameDayVisit),s.visitNote||'')}
        ${row('引き渡し時期',handoverDays||'条件を確認してください',s.handoverText||'')}
        ${row('健康診断・マイクロチップ',health,s.healthNote||'')}
        ${row('キャンセル規定',s.cancellationPolicy?'登録あり':'未設定',s.cancellationPolicy||'')}
      </div>`;

      const firstCard=document.querySelector('main .card.pad');
      if(firstCard) firstCard.insertAdjacentElement('afterend',box);
    }catch(_e){}
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',load,{once:true});
  else load();
})();
