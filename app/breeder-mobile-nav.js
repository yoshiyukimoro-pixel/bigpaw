(()=>{
  if(window.__BIGPAW_BREEDER_MOBILE_NAV__) return;
  window.__BIGPAW_BREEDER_MOBILE_NAV__=true;

  const items=[
    ['🏠','管理トップ','/admin.html'],
    ['＋','子犬を掲載','/breeder-puppy-new.html?new=1'],
    ['💬','見学・問い合わせ','/breeder-inquiries.html'],
    ['✅','成約申請','/breeder-deal-report.html'],
    ['💴','請求・お支払い','/breeder-billing.html'],
    ['🐩','親犬管理','/parent-dogs.html'],
    ['🩺','健康情報','/health-records.html'],
    ['🏡','犬舎プロフィール','/breeder-profile-edit.html'],
    ['💳','料金・手数料','/breeder-fees.html'],
    ['🌐','公開サイト','/index.html']
  ];

  async function role(){
    try{
      const r=await fetch('/api/me',{credentials:'include',cache:'no-store'});
      if(!r.ok) return '';
      const j=await r.json();
      return String(j.role||'');
    }catch(e){ return ''; }
  }

  function mount(){
    if(document.getElementById('bp-breeder-mobile-menu-button')) return;

    const style=document.createElement('style');
    style.textContent=`
      #bp-breeder-mobile-menu-button,#bp-breeder-mobile-menu-overlay,#bp-breeder-mobile-menu-drawer{display:none}
      @media(max-width:900px){
        #bp-breeder-mobile-menu-button{display:flex;position:fixed;top:12px;left:12px;z-index:100003;align-items:center;gap:6px;border:1px solid #b7d5ef;border-radius:13px;padding:9px 12px;background:#fff;color:#315f89;font-weight:800;font-size:14px;box-shadow:0 3px 14px rgba(0,0,0,.12);-webkit-tap-highlight-color:transparent}
        #bp-breeder-mobile-menu-overlay{position:fixed;inset:0;z-index:100004;background:rgba(25,37,52,.42)}
        #bp-breeder-mobile-menu-drawer{position:fixed;top:0;left:0;bottom:0;z-index:100005;width:min(86vw,360px);background:#f3f8ff;color:#42546a;box-shadow:8px 0 28px rgba(0,0,0,.18);overflow:auto;padding:18px 14px calc(24px + env(safe-area-inset-bottom));}
        body.bp-breeder-menu-open{overflow:hidden}
        body.bp-breeder-menu-open #bp-breeder-mobile-menu-overlay,body.bp-breeder-menu-open #bp-breeder-mobile-menu-drawer{display:block}
        #bp-breeder-mobile-menu-drawer .bp-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:4px 4px 14px;border-bottom:1px solid #cfe0ef;margin-bottom:10px}
        #bp-breeder-mobile-menu-drawer .bp-title{font-size:18px;font-weight:900;color:#315f89}
        #bp-breeder-mobile-menu-drawer .bp-close{width:42px;height:42px;border:1px solid #c7d9e8;border-radius:12px;background:#fff;font-size:24px;color:#42546a}
        #bp-breeder-mobile-menu-drawer a{display:flex;align-items:center;gap:10px;min-height:50px;padding:10px 12px;margin:5px 0;border:1px solid #d7e5f1;border-radius:13px;background:#fff;color:#42546a;text-decoration:none;font-weight:800;font-size:16px}
        #bp-breeder-mobile-menu-drawer a.bp-current{background:#dceeff;border-color:#a9cae7;color:#24547d}
        #bp-breeder-mobile-menu-drawer .bp-icon{width:28px;text-align:center}
        #bp-breeder-mobile-menu-drawer .bp-logout{width:100%;min-height:48px;margin-top:14px;border:1px solid #d7cdd5;border-radius:13px;background:#fff;color:#6d5572;font-weight:800;font-size:15px}
      }
    `;
    document.head.appendChild(style);

    const btn=document.createElement('button');
    btn.id='bp-breeder-mobile-menu-button';
    btn.type='button';
    btn.setAttribute('aria-label','ブリーダー管理メニューを開く');
    btn.innerHTML='<span style="font-size:18px">☰</span><span>メニュー</span>';

    const overlay=document.createElement('div');
    overlay.id='bp-breeder-mobile-menu-overlay';

    const drawer=document.createElement('nav');
    drawer.id='bp-breeder-mobile-menu-drawer';
    drawer.setAttribute('aria-label','ブリーダー管理メニュー');
    const path=location.pathname;
    drawer.innerHTML=`<div class="bp-head"><div><div class="bp-title">🐾 BIG PAW</div><div style="font-size:13px;color:#71849a;margin-top:2px">ブリーダー管理</div></div><button class="bp-close" type="button" aria-label="メニューを閉じる">×</button></div>`+
      items.map(([icon,label,href])=>{
        const base=href.split('?')[0];
        const current=path===base;
        return `<a href="${href}" class="${current?'bp-current':''}"><span class="bp-icon">${icon}</span><span>${label}</span></a>`;
      }).join('')+
      `<button class="bp-logout" type="button">ログアウト</button>`;

    const close=()=>document.body.classList.remove('bp-breeder-menu-open');
    btn.addEventListener('click',()=>document.body.classList.add('bp-breeder-menu-open'));
    overlay.addEventListener('click',close);
    drawer.querySelector('.bp-close').addEventListener('click',close);
    drawer.querySelector('.bp-logout').addEventListener('click',async()=>{
      try{await fetch('/api/logout',{method:'POST',credentials:'include'});}catch(e){}
      location.replace('/login.html');
    });
    document.addEventListener('keydown',e=>{if(e.key==='Escape') close();});

    document.body.append(btn,overlay,drawer);
  }

  role().then(r=>{
    if(r!=='breeder') return;
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',mount,{once:true});
    else mount();
  });
})();
