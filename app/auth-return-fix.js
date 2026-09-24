(()=>{
  if(window.__BIGPAW_AUTH_GUARD__) return;
  window.__BIGPAW_AUTH_GUARD__=true;
  const p=location.pathname;
  const LAST='bigpaw_last_role_page';
  const login='/login.html';
  const operatorLogin='/operator-login.html';

  if(p.endsWith('/puppy-detail.html')){
    const s=document.createElement('script');
    s.src='/puppy-detail-favorites-fix.js';
    s.async=true;
    document.head.appendChild(s);
  }
  if(p.endsWith('/breeder-puppy-new.html')){
    const q=new URLSearchParams(location.search);
    const urlEditId=q.get('id')||'';
    const stale=sessionStorage.getItem('bigpawEditPuppyId')||'';
    if(!urlEditId&&stale){
      sessionStorage.removeItem('bigpawEditPuppyId');
      if(!q.has('new')){
        location.replace('/breeder-puppy-new.html?new=1');
        return;
      }
    }
    const safety=document.createElement('script');
    safety.src='/breeder-editor-safety-fix.js';
    safety.async=false;
    document.head.appendChild(safety);
    if(urlEditId){
      const order=document.createElement('script');
      order.src='/breeder-photo-order-fix.js';
      order.async=false;
      document.head.appendChild(order);
    }
  }

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
  function goLogin(target=login){
    sessionStorage.setItem(LAST,location.pathname+location.search);
    location.replace(target);
  }
  async function loadOwnParentDogs(){
    if(!p.endsWith('/breeder-puppy-new.html')) return;
    try{
      const r=await fetch('/api/parent-dogs',{credentials:'include',cache:'no-store'});
      if(!r.ok) return;
      const dogs=await r.json();
      const fill=(id,sex)=>{
        const el=document.getElementById(id); if(!el) return;
        const current=el.value;
        const names=[...new Set((Array.isArray(dogs)?dogs:[]).filter(d=>String(d.sex||'')===sex).map(d=>String(d.name||'').trim()).filter(Boolean))];
        if(current&&current!=='未登録'&&!names.includes(current)) names.unshift(current);
        el.innerHTML=names.map(n=>'<option>'+n.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</option>').join('')+'<option>未登録</option>';
        if(current&&(names.includes(current)||current==='未登録')) el.value=current;
        else el.value=names[0]||'未登録';
      };
      fill('father','父犬'); fill('mother','母犬');
    }catch(e){}
  }

  if(p.endsWith('/admin.html')){
    const label=document.querySelector('.side p');
    if(label&&label.textContent.includes('DOG44')) label.textContent='ブリーダー管理';
  }
  if(p.endsWith('/breeder-puppy-new.html')){
    const editing=!!new URLSearchParams(location.search).get('id');
    if(!editing){
      const notice=[...document.querySelectorAll('.notice')].find(x=>(x.textContent||'').includes('掲載審査へ進み'));
      if(notice) notice.textContent='承認済みブリーダーの子犬は、保存後すぐにBIG PAWへ公開されます。';
    }
  }

  if(p.endsWith(login)){
    const q=new URLSearchParams(location.search);
    if(q.get('switch')==='1'){
      fetch('/api/logout',{method:'POST',credentials:'include'})
        .catch(()=>{})
        .finally(()=>history.replaceState(null,'',login));
      return;
    }
    currentRole().then(role=>{ if(role) location.replace(homeFor(role)); });
    return;
  }
  if(p.endsWith(operatorLogin)){
    currentRole().then(role=>{
      if(role==='operator') location.replace('/operator-admin.html');
      else if(role) location.replace(homeFor(role));
    });
    return;
  }

  const authOnly=['/breeder-register.html','/account.html','/messages.html','/notifications.html','/breeder-fee-agreement.html','/visit-confirm.html','/deal.html','/online-visit.html','/reservation.html','/contract.html','/pickup.html','/review.html','/report.html'];
  const breederOnly=['/admin.html','/breeder-puppy-new.html','/breeder-inquiries.html','/breeder-billing.html','/breeder-deal-report.html','/breeder-profile-edit.html','/breeder-invoice.html','/parent-dogs.html','/health-records.html'];
  const operatorOnly=['/operator-admin.html','/operator-breeders.html','/operator-breeder-applications.html','/operator-listings.html','/operator-deals.html','/operator-support.html','/operator-deal-reports.html','/operator-revenue.html','/operator-reports.html','/operator-invoices.html','/operator-automations.html','/operator-audit.html','/operator-backups.html','/project-status.html','/backend-status.html'];
  const buyerOnly=['/mypage.html','/my-page.html'];

  let need='';
  if(operatorOnly.some(x=>p.endsWith(x))) need='operator';
  else if(breederOnly.some(x=>p.endsWith(x))) need='breeder';
  else if(buyerOnly.some(x=>p.endsWith(x))) need='buyer';
  else if(authOnly.some(x=>p.endsWith(x))) need='auth';
  else return;

  currentRole().then(role=>{
    if(!role){ goLogin(need==='operator'?operatorLogin:login); return; }
    if(need==='auth') return;

    if(need==='breeder' && (role==='breeder' || role==='operator')){
      if(role==='breeder') loadOwnParentDogs();
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
