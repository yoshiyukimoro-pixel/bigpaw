(function(){
 'use strict';
 const path=location.pathname;
 const make=(href,label)=>{const a=document.createElement('a');a.className='btn btn-sub';a.href=href;a.textContent=label;return a};
 const add=()=>{
  if(path.endsWith('/breeder-inquiries.html')){
   document.querySelectorAll('#inquiryList .table-row').forEach(row=>{
    if(row.querySelector('[data-cancel-link]'))return;
    const ref=row.querySelector('a[href*="messages.html?inquiry="]');if(!ref)return;
    const id=new URL(ref.href).searchParams.get('inquiry');const a=make('breeder-cancellation.html?inquiry='+encodeURIComponent(id),'取引中止を申請・確認');a.dataset.cancelLink='1';ref.parentNode.append(' ',a);
   });
  }
  if(path.endsWith('/messages.html')&&typeof me!=='undefined'&&me?.role==='breeder'&&typeof selected!=='undefined'&&selected){
   const ref=document.getElementById('onlineVisit');if(!ref)return;
   let a=document.getElementById('cancellationThreadLink');if(!a){a=make('','取引中止を申請・確認');a.id='cancellationThreadLink';ref.parentNode.append(' ',a)}
   a.href='breeder-cancellation.html?inquiry='+encodeURIComponent(selected);
  }
 };
 if(path.endsWith('/operator-admin.html')||path.endsWith('/operator-sale-confirmations.html')){
  const box=document.createElement('section');box.className='card pad';box.style.margin='16px 0';
  const link=make('operator-cancellations.html','取引中止申請の確認');box.append(link);document.querySelector('main')?.prepend(box);
  BigPawAPI.request('/operator/inquiry-cancellations').then(r=>{const n=r.requests.filter(x=>['operator_review','unanswered'].includes(x.state)).length;link.textContent='取引中止申請の確認'+(n?'（要確認 '+n+'件）':'')}).catch(()=>{});
 }
 if(path.endsWith('/mypage.html')){const p=document.createElement('p');p.style.padding='12px 20px';p.append(make('buyer-cancellation-confirmation.html','取引中止申請の確認'));document.querySelector('main')?.append(p)}
 const watched=document.getElementById('inquiryList')||document.getElementById('who');
 if(watched)new MutationObserver(add).observe(watched,{childList:true,subtree:true});
 add();
})();
