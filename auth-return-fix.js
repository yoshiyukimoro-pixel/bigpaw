(()=>{
  const K='bigpaw_breeder_return';
  const p=location.pathname;
  const ownerMail='yoshiyukimoro@gmail.com';

  if(p.endsWith('/breeder-register.html')){
    sessionStorage.setItem(K,'1');
    return;
  }

  async function loggedInBreeder(){
    try{
      const r=await fetch('/api/me',{credentials:'include',cache:'no-store'});
      if(!r.ok) return false;
      const u=await r.json();
      const role=String(u.role||'');
      const email=String(u.email||'').trim().toLowerCase();
      return role==='breeder' || role==='operator' || email===ownerMail;
    }catch(e){
      return false;
    }
  }

  if(p.endsWith('/login.html')){
    loggedInBreeder().then(ok=>{
      if(ok){
        const next=sessionStorage.getItem('bigpaw_last_breeder_page') || 'breeder-register.html';
        if(next==='breeder-admin.html') sessionStorage.removeItem('bigpaw_last_breeder_page');
        location.replace(next);
      }
    });
    return;
  }

  if(p.endsWith('/breeder-puppy-new.html')){
    sessionStorage.setItem('bigpaw_last_breeder_page', location.pathname.replace(/^\//,''));
  }
})();