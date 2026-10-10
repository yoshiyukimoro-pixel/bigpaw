(()=>{
  const id=new URLSearchParams(location.search).get('id');
  if(!id) return;

  // The built-in puppy gallery is the stable implementation. Do not load the
  // experimental replacement carousel; it could race with the normal gallery
  // on iPhone Safari and make the detail page appear to freeze.
  window.__BIGPAW_PUPPY_GALLERY_CAROUSEL_FIX__=true;

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
    let preference={enabled:false,choiceMade:true};
    const help=document.createElement('p');
    help.id='bigpawFavoriteEmailHelp';
    help.style.cssText='font-size:13px;line-height:1.6;color:#785a69;margin:0 0 16px';
    btn.insertAdjacentElement('afterend',help);
    const paint=()=>{
      btn.textContent=saved?'♥ お気に入り保存済み'
        :(!preference.choiceMade
          ?'♡ お気に入り登録＆変更メールを受け取る'
          :'♡ お気に入りに保存');
      btn.style.background=saved?'#fff1f7':'#fff';
      if(!loggedIn){
        help.textContent='お気に入りの登録にはログインが必要です。';
      }else if(!preference.choiceMade){
        help.textContent='お気に入り登録すると、この子を含むお気に入りの子犬の写真・価格・紹介文・募集状況の変更をメールでお知らせします。登録で受信に同意したことになります。後から設定で停止できます。';
      }else{
        help.innerHTML=preference.enabled
          ?'変更メール通知：ON　<a href="/account.html">通知設定</a>'
          :'変更メール通知：OFF（以前の設定を尊重します）　<a href="/account.html">通知をONにする</a>';
      }
    };
    try{
      const [favs,prefs]=await Promise.all([
        BigPawAPI.favorites(),
        BigPawAPI.request('/favorite-notifications/settings')
      ]);
      saved=Array.isArray(favs)&&favs.some(x=>String(x.id)===String(id));
      preference={enabled:!!prefs.enabled,choiceMade:!!prefs.choiceMade};
    }catch(e){
      loggedIn=e.status!==401;
      // Unavailable settings must not be construed as consent.
      preference={enabled:false,choiceMade:true};
      saved=false;
    }
    paint();
    btn.disabled=false;

    btn.onclick=async()=>{
      if(!loggedIn){location.href='/login.html';return;}
      btn.disabled=true;
      try{
        const consent=!saved&&!preference.choiceMade;
        const r=await BigPawAPI.toggleFavorite(id,consent?{subscribeToFavoriteUpdates:true}:{});
        saved=!!r.favorite;
        if(consent&&saved){
          // Consent is recorded atomically with the new favorite on the server.
          preference={enabled:true,choiceMade:true};
        }
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
