(()=>{
  const id=new URLSearchParams(location.search).get('id');
  if(!id) return;

  if(!window.__BIGPAW_GALLERY_FIX_LOADING__){
    window.__BIGPAW_GALLERY_FIX_LOADING__=true;
    const s=document.createElement('script');
    s.src='/puppy-gallery-carousel-fix.js?v=20260925-2';
    s.async=true;
    document.head.appendChild(s);
  }

  if(!window.__BIGPAW_DESCRIPTION_FIX_LOADING__){
    window.__BIGPAW_DESCRIPTION_FIX_LOADING__=true;
    const s=document.createElement('script');
    s.src='/puppy-description-format-fix.js?v=20260925-1';
    s.async=true;
    document.head.appendChild(s);
  }

  async function patch(btn){
    if(!btn||btn.dataset.serverFavorite==='1') return;
    btn.dataset.serverFavorite='1';

    // Stop the legacy localStorage-only click handler immediately. Until the
    // server state is known the button cannot be pressed, so favorites and
    // My Page always use the same database state.
    btn.disabled=true;
    btn.onclick=null;
    btn.textContent='♡ お気に入り確認中…';

    let loggedIn=true;
    let saved=false;
    const paint=()=>{
      btn.textContent=saved?'♥ お気に入り保存済み':'♡ お気に入りに保存';
      btn.style.background=saved?'#fff1f7':'#fff';
    };
    try{
      const favs=await BigPawAPI.favorites();
      saved=Array.isArray(favs)&&favs.some(x=>String(x.id)===String(id));
    }catch(e){
      loggedIn=e.status!==401;
      saved=false;
    }
    paint();
    btn.disabled=false;

    btn.onclick=async()=>{
      if(!loggedIn){location.href='/login.html';return;}
      btn.disabled=true;
      try{
        const r=await BigPawAPI.toggleFavorite(id);
        saved=!!r.favorite;
        paint();
        const original=document.getElementById('favBtn');
        if(original) original.textContent=saved?'♥ お気に入り済み':'♡ お気に入りに保存';
      }catch(e){
        if(e.status===401) location.href='/login.html';
        else alert('お気に入りを更新できませんでした');
      }finally{btn.disabled=false;}
    };
  }

  const scan=()=>patch(document.getElementById('bigpawFavButton'));
  scan();
  const mo=new MutationObserver(scan);
  mo.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(scan,300); setTimeout(scan,1000);
})();
