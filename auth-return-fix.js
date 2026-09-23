(()=>{
  const p=location.pathname;
  const LAST='bigpaw_last_breeder_page';

  // Login page must remain visible until the user explicitly submits the form.
  // The page's own doLogin() handles authentication and role-based navigation.
  if(p.endsWith('/login.html')) return;

  async function currentRole(){
    try{
      const r=await fetch('/api/me',{credentials:'include',cache:'no-store'});
      if(!r.ok) return '';
      const u=await r.json();
      return String(u.role||'');
    }catch(e){ return ''; }
  }

  const protectedBreederPages = [
    '/breeder-puppy-new.html',
    '/breeder-register.html',
    '/breeder-inquiries.html',
    '/breeder-billing.html',
    '/breeder-deal-report.html'
  ];

  if(protectedBreederPages.some(x=>p.endsWith(x))){
    const target=location.pathname+location.search;
    currentRole().then(role=>{
      if(role==='breeder' || role==='operator'){
        sessionStorage.setItem(LAST,target);
        return;
      }
      sessionStorage.setItem(LAST,target);
      location.replace('/login.html');
    });
  }
})();