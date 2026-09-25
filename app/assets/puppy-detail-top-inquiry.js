(()=>{
  if(!/\/puppy-detail\.html$/.test(location.pathname))return;

  function install(){
    const fav=document.getElementById('bigpawFavButton');
    if(!fav||document.getElementById('bigpawTopInquiry'))return false;
    const id=new URLSearchParams(location.search).get('id')||'';
    const a=document.createElement('a');
    a.id='bigpawTopInquiry';
    a.href='inquiry.html?id='+encodeURIComponent(id);
    a.textContent='見学・問い合わせ';
    a.setAttribute('aria-label','この子犬の見学・問い合わせ');
    a.style.cssText='display:flex;width:100%;box-sizing:border-box;min-height:54px;margin:0 0 10px;align-items:center;justify-content:center;text-decoration:none;border:0;border-radius:14px;background:linear-gradient(135deg,#ef7fa8,#f28db4);color:#fff;font-weight:900;font-size:17px;box-shadow:0 6px 16px rgba(239,127,168,.18)';
    fav.insertAdjacentElement('beforebegin',a);
    return true;
  }

  if(install())return;
  const mo=new MutationObserver(()=>{if(install())mo.disconnect()});
  mo.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(()=>{install();mo.disconnect()},8000);
})();
