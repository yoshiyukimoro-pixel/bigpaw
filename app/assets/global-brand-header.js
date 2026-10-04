/* Shared presentation only. Account, form and photo logic stays on each page. */
(()=>{
  if(window.__BIGPAW_GLOBAL_BRAND_HEADER__)return;
  window.__BIGPAW_GLOBAL_BRAND_HEADER__=true;
  const logo='/assets/bigpaw-logo-header.webp?v=20260926b';
  function mount(){
    const style=document.createElement('style');
    style.textContent=`
      .bp-brand-header{position:sticky!important;top:0!important;z-index:100!important;background:#fff!important;border-bottom:1px solid var(--line,#efd0df)}
      .bp-brand-header>.bp-brand-nav{display:flex!important;align-items:center!important;gap:18px;min-height:68px;height:auto!important;box-sizing:border-box;margin:0 auto;max-width:1120px;padding:5px 20px}
      .bp-brand-header .logo{display:flex!important;align-items:center!important;flex:0 0 auto!important;font-size:0!important;line-height:0!important;margin:0!important}
      .bp-brand-header .bigpaw-header-logo{display:block!important;width:150px!important;height:58px!important;object-fit:contain!important}
      .bp-brand-header.bp-brand-added .bp-brand-nav{max-width:none;padding-right:150px}
      @media(max-width:900px){
        .bp-brand-header>.bp-brand-nav{position:relative;flex-wrap:wrap!important;gap:0;min-height:62px;padding:8px 14px!important}
        .bp-brand-header .logo{margin-right:118px!important}
        .bp-brand-header .bigpaw-header-logo{width:118px!important;height:46px!important}
        .bp-brand-header .navlinks{flex:0 0 100%;margin:0!important;justify-content:flex-end;gap:10px;padding-top:6px;padding-bottom:2px;flex-wrap:wrap}
        .bp-brand-header .navlinks a:not(.nav-cta){display:none}
        .bp-brand-header .navlinks:not(:has(.nav-cta)){display:none}
        body.bp-brand-menu-ready #bigpaw-admin-logout{display:none!important}
      }
      @media print{.bp-brand-header{position:static!important}#bp-global-mobile-menu-button,#bp-global-mobile-menu-drawer,#bp-global-mobile-menu-overlay{display:none!important}}
    `;
    document.head.appendChild(style);
    let header=document.querySelector('header.site-header')||document.querySelector('body>header');
    if(!header){
      header=document.createElement('header');header.className='site-header bp-brand-added';
      header.innerHTML='<div class="wrap nav"><a class="logo" href="/index.html"></a></div>';
      document.body.prepend(header);
    }
    header.classList.add('bp-brand-header');
    let nav=header.querySelector('.nav');
    if(!nav){nav=document.createElement('div');nav.className='wrap nav';header.prepend(nav)}
    nav.classList.add('bp-brand-nav');
    let brand=nav.querySelector('.logo');
    if(!brand){brand=document.createElement('a');brand.className='logo';brand.href='/index.html';nav.prepend(brand)}
    brand.innerHTML='<img class="bigpaw-header-logo" src="'+logo+'" alt="BIG PAW" width="150" height="58">';
    if(brand.tagName==='A')brand.setAttribute('aria-label','BIG PAW ホーム');
    function placeMenu(){
      const button=document.getElementById('bp-global-mobile-menu-button');
      if(!button)return;
      const box=header.getBoundingClientRect();
      // Keep the fixed alert-bearing menu inside the sticky header's first row.
      button.style.top=Math.max(0,box.top)+12+'px';
      button.style.left='auto';button.style.right='14px';
    }
    window.bigpawPlaceBrandMenu=placeMenu;
    let queued=false;
    function schedule(){if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;placeMenu()})}
    addEventListener('scroll',schedule,{passive:true});addEventListener('resize',schedule);
    if(window.ResizeObserver)new ResizeObserver(schedule).observe(header);
    placeMenu();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
