(()=>{
  if(window.__BIGPAW_GLOBAL_MOBILE_NAV__) return;
  window.__BIGPAW_GLOBAL_MOBILE_NAV__=true;

  const path=location.pathname;
  const query=new URLSearchParams(location.search);
  const operatorPages=['/operator-admin.html','/operator-users.html','/operator-user-detail.html','/operator-breeders.html','/operator-breeder-detail.html','/operator-listings.html','/operator-reports.html','/operator-support.html','/operator-deal-reports.html','/operator-deals.html','/operator-revenue.html','/operator-invoices.html','/operator-audit.html','/operator-backups.html','/operator-automations.html','/project-status.html','/backend-status.html','/launch-checklist.html'];
  const breederPages=['/admin.html','/breeder-puppy-new.html','/breeder-inquiries.html','/breeder-deal-report.html','/breeder-billing.html','/breeder-invoice.html','/breeder-fees.html','/breeder-profile-edit.html','/parent-dogs.html','/breeder-fee-agreement.html'];
  const sharedDealPages=['/messages.html','/online-visit.html','/visit-confirm.html','/deal.html','/reservation.html','/contract.html','/pickup.html','/review.html','/report.html'];

  const menus={
    operator:{
      label:'運営管理',tone:'operator',items:[
        ['🏠','ダッシュボード','/operator-admin.html'],['👤','登録ユーザー','/operator-users.html'],['👥','ブリーダー管理','/operator-breeders.html'],['📦','販売・引渡し設定','/breeder-sales-handover.html'],['🐶','子犬掲載管理','/operator-listings.html'],['✅','成約申請','/operator-deal-reports.html'],['🤝','成約管理','/operator-deals.html'],['💴','売上・手数料','/operator-revenue.html'],['🧾','請求管理','/operator-invoices.html'],['💬','運営お問い合わせ','/operator-support.html'],['⚠️','通報・違反対応','/operator-reports.html'],['📋','監査ログ','/operator-audit.html'],['💾','バックアップ','/operator-backups.html'],['⚙️','自動処理モニター','/operator-automations.html'],['📊','開発状況','/project-status.html'],['🖥️','システム状態','/backend-status.html'],['🌐','公開サイト','/index.html']
      ]
    },
    breeder:{
      label:'ブリーダー管理',tone:'breeder',items:[
        ['🏠','管理トップ','/admin.html'],['＋','子犬を掲載','/breeder-puppy-new.html?new=1'],['💬','見学・問い合わせ','/breeder-inquiries.html'],['✅','成約申請','/breeder-deal-report.html'],['💴','請求・お支払い','/breeder-billing.html'],['🐩','親犬管理','/parent-dogs.html'],['🏡','犬舎プロフィール','/breeder-profile-edit.html'],['💳','料金・手数料','/breeder-fees.html'],['🌐','公開サイト','/index.html']
      ]
    },
    buyer:{
      label:'マイメニュー',tone:'buyer',items:[
        ['🏠','トップ','/index.html'],['🔎','子犬を探す','/search.html'],['❤️','お気に入り','/favorites.html'],['⚖️','比較','/compare.html'],['👤','マイページ','/mypage.html'],['💬','メッセージ','/messages.html'],['🔔','お知らせ','/notifications.html'],['✉️','お問い合わせ','/contact.html']
      ]
    },
    public:{
      label:'メニュー',tone:'public',items:[
        ['🏠','トップ','/index.html'],['🔎','子犬を探す','/search.html'],['🐾','ブリーダー一覧','/breeders.html'],['📖','大型犬ガイド','/breed-guide.html'],['❓','よくある質問','/faq.html'],['✉️','お問い合わせ','/contact.html'],['📝','新規登録','/register.html'],['🔐','ログイン','/login.html']
      ]
    }
  };

  async function currentRole(){
    try{
      const r=await fetch('/api/me',{credentials:'include',cache:'no-store'});
      if(!r.ok) return '';
      const j=await r.json();
      return String(j.role||'');
    }catch(e){return '';}
  }

  function choose(role){
    if(path.endsWith('/breeder-sales-handover.html')&&role==='operator') return 'operator';
    if(((path.startsWith('/operator-')||path.includes('/operator-'))&&!path.endsWith('/operator-login.html')) || operatorPages.some(p=>path.endsWith(p)) || (path.endsWith('/messages.html')&&query.get('mode')==='operator')) return 'operator';
    if(path.endsWith('/notifications.html')&&(role==='breeder'||role==='operator')) return role;
    if(breederPages.some(p=>path.endsWith(p))) return 'breeder';
    if(sharedDealPages.some(p=>path.endsWith(p)) && (role==='breeder'||role==='operator')) return role==='operator'?'operator':'breeder';
    if(role==='buyer') return 'buyer';
    return 'public';
  }

  function mount(kind,role){
    if(document.getElementById('bp-global-mobile-menu-button')) return;
    const cfg=menus[kind]||menus.public;
    const style=document.createElement('style');
    style.textContent=`
      #bp-global-mobile-menu-button,#bp-global-mobile-menu-overlay,#bp-global-mobile-menu-drawer{display:none}
      @media(max-width:900px){
        #bp-global-mobile-menu-button{display:flex;position:fixed;top:calc(10px + env(safe-area-inset-top));left:12px;z-index:100003;align-items:center;gap:6px;border:1px solid var(--bp-menu-border);border-radius:13px;padding:9px 12px;background:#fff;color:var(--bp-menu-text);font-weight:800;font-size:14px;box-shadow:0 3px 14px rgba(0,0,0,.12);-webkit-tap-highlight-color:transparent}
        #bp-global-mobile-menu-overlay{position:fixed;inset:0;z-index:100004;background:rgba(25,37,52,.42)}
        #bp-global-mobile-menu-drawer{position:fixed;top:0;left:0;bottom:0;z-index:100005;width:min(88vw,370px);background:var(--bp-menu-bg);color:#42546a;box-shadow:8px 0 28px rgba(0,0,0,.18);overflow:auto;padding:calc(18px + env(safe-area-inset-top)) 14px calc(24px + env(safe-area-inset-bottom));}
        body.bp-global-menu-open{overflow:hidden}
        body.bp-global-menu-open #bp-global-mobile-menu-overlay,body.bp-global-menu-open #bp-global-mobile-menu-drawer{display:block}
        #bp-global-mobile-menu-drawer .bp-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:4px 4px 14px;border-bottom:1px solid var(--bp-menu-border);margin-bottom:10px}
        #bp-global-mobile-menu-drawer .bp-title{font-size:18px;font-weight:900;color:var(--bp-menu-text)}
        #bp-global-mobile-menu-drawer .bp-close{width:42px;height:42px;border:1px solid var(--bp-menu-border);border-radius:12px;background:#fff;font-size:24px;color:#42546a}
        #bp-global-mobile-menu-drawer a{display:flex;align-items:center;gap:10px;min-height:50px;padding:10px 12px;margin:5px 0;border:1px solid var(--bp-menu-border);border-radius:13px;background:#fff;color:#42546a;text-decoration:none;font-weight:800;font-size:16px}
        #bp-global-mobile-menu-drawer a.bp-current{background:var(--bp-menu-current);color:var(--bp-menu-text)}
        #bp-global-mobile-menu-drawer .bp-icon{width:28px;text-align:center}
        #bp-global-mobile-menu-drawer .bp-shortcut{margin:2px 0 12px;padding:9px 12px;border-radius:12px;background:#fff;border:1px solid var(--bp-menu-border);font-size:13px;font-weight:700;color:#596b7f}
        #bp-global-mobile-menu-drawer .bp-logout{width:100%;min-height:48px;margin-top:14px;border:1px solid #d7cdd5;border-radius:13px;background:#fff;color:#6d5572;font-weight:800;font-size:15px}
      }
      html[data-bp-mobile-tone="operator"]{--bp-menu-bg:#fffbea;--bp-menu-border:#e9dc91;--bp-menu-text:#705d00;--bp-menu-current:#fff2a8}
      html[data-bp-mobile-tone="breeder"]{--bp-menu-bg:#f3f8ff;--bp-menu-border:#c5dced;--bp-menu-text:#315f89;--bp-menu-current:#dceeff}
      html[data-bp-mobile-tone="buyer"],html[data-bp-mobile-tone="public"]{--bp-menu-bg:#fff7fb;--bp-menu-border:#efd0df;--bp-menu-text:#a84f76;--bp-menu-current:#ffe3ef}
    `;
    document.head.appendChild(style);
    document.documentElement.setAttribute('data-bp-mobile-tone',cfg.tone);
    if(document.body.classList.contains('bp-account-page')) document.documentElement.setAttribute('data-bp-page-theme',cfg.tone);

    const btn=document.createElement('button');
    btn.id='bp-global-mobile-menu-button';btn.type='button';btn.setAttribute('aria-label',cfg.label+'を開く');btn.innerHTML='<span style="font-size:18px">☰</span><span>メニュー</span>';
    const overlay=document.createElement('div');overlay.id='bp-global-mobile-menu-overlay';
    const drawer=document.createElement('nav');drawer.id='bp-global-mobile-menu-drawer';drawer.setAttribute('aria-label',cfg.label);

    let items=[...cfg.items];
    let shortcut='';
    if(kind==='public'&&role==='breeder') shortcut='<a class="bp-shortcut" href="/admin.html">ブリーダー管理へ戻る →</a>';
    else if(kind==='public'&&role==='operator') shortcut='<a class="bp-shortcut" href="/operator-admin.html">運営管理へ戻る →</a>';
    else if(kind==='public'&&role==='buyer') shortcut='<a class="bp-shortcut" href="/mypage.html">マイページへ →</a>';

    drawer.innerHTML=`<div class="bp-head"><div><div class="bp-title">🐾 BIG PAW</div><div style="font-size:13px;color:#71849a;margin-top:2px">${cfg.label}</div></div><button class="bp-close" type="button" aria-label="メニューを閉じる">×</button></div>${shortcut}`+
      items.map(([icon,label,href])=>{const base=href.split('?')[0];const current=path===base;return `<a href="${href}" class="${current?'bp-current':''}"><span class="bp-icon">${icon}</span><span>${label}</span></a>`;}).join('')+
      (role?'<button class="bp-logout" type="button">ログアウト</button>':'');

    const close=()=>document.body.classList.remove('bp-global-menu-open');
    btn.addEventListener('click',()=>document.body.classList.add('bp-global-menu-open'));
    overlay.addEventListener('click',close);drawer.querySelector('.bp-close').addEventListener('click',close);
    const logout=drawer.querySelector('.bp-logout');
    if(logout) logout.addEventListener('click',async()=>{try{await fetch('/api/logout',{method:'POST',credentials:'include'});}catch(e){} location.replace('/login.html');});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
    document.body.append(btn,overlay,drawer);
  }

  currentRole().then(role=>{const kind=choose(role);const go=()=>mount(kind,role);if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go,{once:true});else go();});
})();
