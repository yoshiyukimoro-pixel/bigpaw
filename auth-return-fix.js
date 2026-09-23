(()=>{
  const p=location.pathname;
  const LAST='bigpaw_last_role_page';
  const login='/login.html';
  if(p.endsWith(login)) return;

  async function currentRole(){
    try{
      const r=await fetch('/api/me',{credentials:'include',cache:'no-store'});
      if(!r.ok) return '';
      const u=await r.json();
      return String(u.role||'');
    }catch(e){ return ''; }
  }
  function goLogin(){ sessionStorage.setItem(LAST,location.pathname+location.search); location.replace(login); }

  // Application page: any authenticated account may view it; backend controls submission eligibility.
  const authOnly=['/breeder-register.html','/account.html','/messages.html','/notifications.html'];
  // Approved breeder workspace. Operator is intentionally NOT treated as breeder here.
  const breederOnly=['/admin.html','/breeder-puppy-new.html','/breeder-inquiries.html','/breeder-billing.html','/breeder-deal-report.html'];
  const operatorOnly=['/operator-admin.html','/operator-breeders.html','/operator-breeder-applications.html','/operator-listings.html','/operator-deals.html','/operator-support.html','/operator-deal-reports.html','/operator-revenue.html','/operator-reports.html','/operator-invoices.html','/operator-automations.html'];
  const buyerOnly=['/mypage.html','/my-page.html'];

  let need='';
  if(operatorOnly.some(x=>p.endsWith(x))) need='operator';
  else if(breederOnly.some(x=>p.endsWith(x))) need='breeder';
  else if(buyerOnly.some(x=>p.endsWith(x))) need='buyer';
  else if(authOnly.some(x=>p.endsWith(x))) need='auth';
  else return;

  currentRole().then(role=>{
    if(!role){ goLogin(); return; }
    if(need==='auth') return;
    if(role===need) return;
    const dest=role==='operator'?'/operator-admin.html':role==='breeder'?'/admin.html':'/mypage.html';
    location.replace(dest);
  });
})();
