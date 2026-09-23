(()=>{
  const p=location.pathname;
  const LAST='bigpaw_last_role_page';
  const login='/login.html';

  async function currentRole(){
    try{
      const r=await fetch('/api/me',{credentials:'include',cache:'no-store'});
      if(!r.ok) return '';
      const u=await r.json();
      return String(u.role||'');
    }catch(e){ return ''; }
  }
  function homeFor(role){
    return role==='operator'?'/operator-admin.html':role==='breeder'?'/admin.html':'/mypage.html';
  }
  function goLogin(){
    sessionStorage.setItem(LAST,location.pathname+location.search);
    location.replace(login);
  }

  // Login is a shared authentication endpoint, but an already authenticated
  // account always returns to its own workspace.
  if(p.endsWith(login)){
    currentRole().then(role=>{ if(role) location.replace(homeFor(role)); });
    return;
  }

  const authOnly=['/breeder-register.html','/account.html','/messages.html','/notifications.html'];
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

    // Operator review mode: operators may inspect breeder workspace pages.
    // Breeders and buyers never gain operator access.
    if(need==='breeder' && (role==='breeder' || role==='operator')){
      if(role==='operator'){
        document.documentElement.setAttribute('data-bigpaw-operator-review','1');
        const show=()=>{
          if(document.getElementById('bigpaw-operator-review-banner')) return;
          const b=document.createElement('div');
          b.id='bigpaw-operator-review-banner';
          b.textContent='運営確認モード';
          b.style.cssText='position:sticky;top:0;z-index:99999;padding:7px 12px;text-align:center;background:#fff3a8;color:#5b4a00;font-weight:700;border-bottom:1px solid #e2cd62';
          document.body&&document.body.prepend(b);
        };
        document.readyState==='loading'?document.addEventListener('DOMContentLoaded',show):show();
      }
      return;
    }
    if(role===need) return;
    location.replace(homeFor(role));
  });
})();