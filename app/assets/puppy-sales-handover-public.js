(()=>{
  if(window.__BIGPAW_PUPPY_SALES_HANDOVER_PUBLIC__) return;
  window.__BIGPAW_PUPPY_SALES_HANDOVER_PUBLIC__=true;
  if(!/puppy-detail\.html$/.test(location.pathname)) return;

  const puppyId=new URLSearchParams(location.search).get('id')||'';
  if(!puppyId) return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const yen=n=>Number(n||0).toLocaleString('ja-JP')+'円';
  const included=v=>v===true?'生体価格に含まれます':v===false?'生体価格とは別途必要です':'';
  const visit=v=>v===true?'受け付けます':v===false?'受け付けません':'';

  function hasContent(s){
    if(!s||!s.configured) return false;
    return (s.pedigreeOrganizations||[]).length||s.pedigreeOther1||s.pedigreeOther2||s.pedigreeNote||
      s.vaccineIncluded!==null||s.vaccineNote||Number(s.reservationAmount||0)>0||s.balanceTiming||s.reservationNote||
      s.sameDayVisit!==null||s.visitNote||s.handoverText||Number(s.minHandoverDays||0)>0||
      s.healthExamIncluded!==null||s.microchipIncluded!==null||s.healthNote||s.cancellationPolicy;
  }

  function row(label,value,detail=''){
    if(!value&&!detail) return '';
    return `<div class="bigpaw-handover-row"><div class="bigpaw-handover-label">${esc(label)}</div><div class="bigpaw-handover-value">${value?`<b>${esc(value)}</b>`:''}${detail?`<div class="bigpaw-handover-note">${esc(detail)}</div>`:''}</div></div>`;
  }

  function ensureStyle(){
    if(document.getElementById('bigpawPuppyHandoverStyle')) return;
    const st=document.createElement('style');
    st.id='bigpawPuppyHandoverStyle';
    st.textContent=`#bigpawPuppySalesHandover{margin:20px 0;padding:20px;border:1px solid #f0dbe5;border-radius:22px;background:#fff;color:#5b4b62}#bigpawPuppySalesHandover h2{margin:0 0 8px;font-size:22px}#bigpawPuppySalesHandover .intro{margin:0 0 14px;color:#8f8195;font-size:14px;line-height:1.7}.bigpaw-handover-row{display:grid;grid-template-columns:minmax(112px,.9fr) minmax(0,1.6fr);gap:14px;padding:13px 0;border-top:1px solid #f3e4eb}.bigpaw-handover-row:first-child{border-top:0}.bigpaw-handover-label{font-weight:800}.bigpaw-handover-value b{font-size:15px}.bigpaw-handover-note{margin-top:5px;color:#8f8195;white-space:pre-wrap;line-height:1.6;font-size:13px}@media(max-width:640px){#bigpawPuppySalesHandover{padding:18px 16px}.bigpaw-handover-row{grid-template-columns:1fr;gap:5px}}`;
    document.head.appendChild(st);
  }

  async function puppy(){
    if(window.__BIGPAW_DETAIL_PUPPY&&window.__BIGPAW_DETAIL_PUPPY.breederId) return window.__BIGPAW_DETAIL_PUPPY;
    if(window.BigPawBridge&&typeof BigPawBridge.puppy==='function'){
      try{return await BigPawBridge.puppy(puppyId)}catch(_e){}
    }
    try{
      const r=await fetch('/api/puppies/'+encodeURIComponent(puppyId),{credentials:'same-origin',cache:'no-store'});
      return r.ok?await r.json():null;
    }catch(_e){return null}
  }

  async function load(){
    if(document.getElementById('bigpawPuppySalesHandover')) return;
    const p=await puppy();
    const breederId=p&&p.breederId?String(p.breederId):'';
    if(!breederId) return;
    try{
      const r=await fetch('/api/breeders/'+encodeURIComponent(breederId)+'/sales-handover-settings',{credentials:'same-origin',cache:'no-store'});
      if(!r.ok) return;
      const s=await r.json();
      if(!hasContent(s)) return;

      const pedigree=[...(s.pedigreeOrganizations||[]),s.pedigreeOther1,s.pedigreeOther2].filter(Boolean).join('・');
      const vaccine=included(s.vaccineIncluded);
      const reservation=Number(s.reservationAmount||0)>0?yen(s.reservationAmount):'';
      const reservationDetail=[s.balanceTiming,s.reservationNote].filter(Boolean).join('／');
      const sameDay=visit(s.sameDayVisit);
      const handover=Number(s.minHandoverDays||0)>0?'生後'+Number(s.minHandoverDays)+'日目以降':'';
      const healthParts=[];
      if(s.healthExamIncluded!==null) healthParts.push('健康診断：'+included(s.healthExamIncluded));
      if(s.microchipIncluded!==null) healthParts.push('マイクロチップ：'+included(s.microchipIncluded));

      const rows=[
        row('血統証明書',pedigree,s.pedigreeNote||''),
        row('ワクチン代',vaccine,s.vaccineNote||''),
        row('予約金',reservation,reservationDetail),
        row('当日の見学',sameDay,s.visitNote||''),
        row('お引き渡し時期',handover,s.handoverText||''),
        row('健康診断・マイクロチップ',healthParts.join(' ／ '),s.healthNote||''),
        row('キャンセル規定',s.cancellationPolicy?'登録あり':'',s.cancellationPolicy||'')
      ].filter(Boolean).join('');
      if(!rows) return;

      ensureStyle();
      const box=document.createElement('section');
      box.id='bigpawPuppySalesHandover';
      box.setAttribute('aria-label','お迎えについて');
      box.innerHTML=`<h2>お迎えについて</h2><p class="intro">このブリーダーが登録している販売・引渡し条件です。表示価格に含まれる費用や予約金などをご確認いただけます。</p><div>${rows}</div><p class="intro" style="margin:14px 0 0">正式な金額・条件は、お申し込み前にブリーダーからの案内をご確認ください。</p>`;

      const more=document.getElementById('bigpawDetailMore');
      if(more) more.insertAdjacentElement('afterend',box);
      else {
        const wrap=document.querySelector('main .wrap');
        if(wrap) wrap.appendChild(box);
      }
    }catch(_e){}
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(load,0),{once:true});
  else setTimeout(load,0);
})();
