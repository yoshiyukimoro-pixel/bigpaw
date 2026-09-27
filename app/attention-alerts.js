(()=>{
  if(window.__BIGPAW_ATTENTION_ALERTS__) return;
  window.__BIGPAW_ATTENTION_ALERTS__=true;

  const here=location.pathname;
  const q=new URLSearchParams(location.search);
  let role='';
  let lastMap={};

  const style=document.createElement('style');
  style.textContent=`
    .bp-attention-badge{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:#d92d20;color:#fff;font-size:12px;font-weight:900;line-height:1;box-shadow:0 0 0 2px #fff;white-space:nowrap}
    a.bp-attention-link{position:relative!important;outline:2px solid rgba(217,45,32,.32);outline-offset:2px}
    a.bp-attention-link>.bp-attention-badge{position:absolute;top:5px;right:5px;z-index:3}
    #bp-global-mobile-menu-drawer a.bp-attention-link{padding-right:48px!important}
    #bp-global-mobile-menu-button{position:fixed!important}
    #bp-global-mobile-menu-button .bp-attention-dot{position:absolute;top:-6px;right:-7px;width:16px;height:16px;border-radius:50%;background:#d92d20;box-shadow:0 0 0 3px #fff}
    #bp-attention-summary{display:none;margin:6px 0 10px;padding:10px 12px;border-radius:12px;background:#fff1f1;border:1px solid #efb3b3;color:#a51d1d;font-size:14px;font-weight:900}
    #bp-attention-summary.bp-show{display:block}
  `;
  document.head.appendChild(style);

  async function api(path){
    const r=await fetch('/api'+path,{credentials:'include',cache:'no-store'});
    if(!r.ok) throw new Error(String(r.status));
    return r.json();
  }

  async function getRole(){
    try{const me=await api('/me');return String(me.role||'')}catch(e){return ''}
  }

  const n=v=>Math.max(0,Number(v||0)||0);
  const sum=o=>Object.values(o).reduce((a,b)=>a+n(b),0);
  const storageNum=k=>{try{return Number(localStorage.getItem(k)||0)||0}catch(e){return 0}};
  const storageSet=(k,v)=>{try{localStorage.setItem(k,String(v||0))}catch(e){}};
  const newest=rows=>Math.max(0,...(rows||[]).map(x=>Number(x.created_at||0)||0));
  const newer=(rows,kindSet,seen)=> (rows||[]).filter(x=>(!kindSet||kindSet.has(String(x.kind||'')))&&Number(x.created_at||0)>seen).length;

  function keyForHref(href){
    try{
      const u=new URL(href,location.origin);
      if(u.pathname==='/messages.html'&&u.searchParams.get('mode')==='operator') return '/messages.html?mode=operator';
      return u.pathname;
    }catch(e){return ''}
  }

  function clearBadges(){
    document.querySelectorAll('.bp-attention-badge').forEach(x=>x.remove());
    document.querySelectorAll('.bp-attention-link').forEach(x=>x.classList.remove('bp-attention-link'));
    document.querySelectorAll('.bp-attention-dot').forEach(x=>x.remove());
  }

  function applyOne(href,count){
    count=n(count); if(!count) return;
    const wanted=keyForHref(href);
    document.querySelectorAll('a[href]').forEach(a=>{
      if(keyForHref(a.getAttribute('href'))!==wanted) return;
      a.classList.add('bp-attention-link');
      if(a.querySelector(':scope > .bp-attention-badge')) return;
      const b=document.createElement('span');
      b.className='bp-attention-badge';
      b.textContent=count>99?'99+':String(count);
      b.setAttribute('aria-label',count+'件の要確認');
      a.appendChild(b);
    });
  }

  function ensureBreederNoticeLink(){
    const drawer=document.getElementById('bp-global-mobile-menu-drawer');
    if(role!=='breeder'||!drawer||drawer.querySelector('a[href="/notifications.html"]')) return;
    const pub=drawer.querySelector('a[href="/index.html"]');
    const a=document.createElement('a');
    a.href='/notifications.html';
    a.innerHTML='<span class="bp-icon">🔔</span><span>お知らせ</span>';
    if(pub) drawer.insertBefore(a,pub); else drawer.appendChild(a);
  }

  function showSummary(hasAny){
    const drawer=document.getElementById('bp-global-mobile-menu-drawer');
    const btn=document.getElementById('bp-global-mobile-menu-button');
    if(drawer){
      let s=document.getElementById('bp-attention-summary');
      if(!s){s=document.createElement('div');s.id='bp-attention-summary';s.textContent='🔴 要確認があります';const head=drawer.querySelector('.bp-head');if(head) head.insertAdjacentElement('afterend',s)}
      s.classList.toggle('bp-show',!!hasAny);
    }
    if(btn&&hasAny&&!btn.querySelector('.bp-attention-dot')){const d=document.createElement('span');d.className='bp-attention-dot';d.setAttribute('aria-label','要確認あり');btn.appendChild(d)}
  }

  async function operatorMap(){
    const [statsR,invR,repR]=await Promise.allSettled([api('/operator/stats'),api('/operator/invoices'),api('/operator/reports')]);
    const stats=statsR.status==='fulfilled'?statsR.value:{};
    const inv=invR.status==='fulfilled'&&Array.isArray(invR.value)?invR.value:[];
    const reports=repR.status==='fulfilled'&&Array.isArray(repR.value)?repR.value:[];
    const m={
      '/operator-breeders.html':n(stats.pendingBreederApplications),
      '/messages.html?mode=operator':n(stats.unanswered),
      '/operator-deal-reports.html':n(stats.pendingDealReports),
      '/operator-invoices.html':inv.filter(x=>x.status==='issued').length,
      '/operator-support.html':n(stats.openSupport),
      '/operator-reports.html':reports.filter(x=>!['resolved','dismissed'].includes(String(x.status||''))).length
    };
    m['/operator-admin.html']=sum(m);
    return m;
  }

  async function breederMap(){
    const [inqR,invR,notR]=await Promise.allSettled([api('/inquiries'),api('/breeder/invoices'),api('/notifications')]);
    const inq=inqR.status==='fulfilled'&&Array.isArray(inqR.value)?inqR.value:[];
    const inv=invR.status==='fulfilled'&&Array.isArray(invR.value)?invR.value:[];
    const notes=notR.status==='fulfilled'&&Array.isArray(notR.value)?notR.value:[];
    const commKinds=new Set(['message']);
    const otherKinds=new Set(['deal_report','visit','contract','pickup','review','support']);
    const commKey='bp_seen_comm_breeder';
    const noticeKey='bp_seen_notice_breeder';
    let commSeen=storageNum(commKey), noticeSeen=storageNum(noticeKey);
    const latestComm=newest(notes.filter(x=>commKinds.has(String(x.kind||''))));
    const latestNotice=newest(notes.filter(x=>otherKinds.has(String(x.kind||''))));
    if(here.endsWith('/breeder-inquiries.html')||here.endsWith('/messages.html')){storageSet(commKey,latestComm);commSeen=latestComm}
    if(here.endsWith('/notifications.html')){storageSet(commKey,latestComm);storageSet(noticeKey,latestNotice);commSeen=latestComm;noticeSeen=latestNotice}
    const m={
      '/breeder-inquiries.html':inq.filter(x=>x.status==='未返信').length+newer(notes,commKinds,commSeen),
      '/breeder-billing.html':inv.filter(x=>x.status==='issued').length,
      '/notifications.html':newer(notes,otherKinds,noticeSeen)
    };
    m['/admin.html']=sum(m);
    return m;
  }

  async function buyerMap(){
    const notes=await api('/notifications').catch(()=>[]);
    const rows=Array.isArray(notes)?notes:[];
    const commKinds=new Set(['message']);
    const noticeKinds=new Set(rows.map(x=>String(x.kind||'')).filter(k=>k!=='message'));
    const commKey='bp_seen_comm_buyer';
    const noticeKey='bp_seen_notice_buyer';
    let commSeen=storageNum(commKey), noticeSeen=storageNum(noticeKey);
    const latestComm=newest(rows.filter(x=>commKinds.has(String(x.kind||''))));
    const latestNotice=newest(rows.filter(x=>String(x.kind||'')!=='message'));
    if(here.endsWith('/messages.html')){storageSet(commKey,latestComm);commSeen=latestComm}
    if(here.endsWith('/notifications.html')){storageSet(commKey,latestComm);storageSet(noticeKey,latestNotice);commSeen=latestComm;noticeSeen=latestNotice}
    const m={
      '/messages.html':newer(rows,commKinds,commSeen),
      '/notifications.html':newer(rows,noticeKinds,noticeSeen)
    };
    m['/mypage.html']=sum(m);
    return m;
  }

  async function buildMap(){
    if(role==='operator') return operatorMap();
    if(role==='breeder') return breederMap();
    if(role==='buyer') return buyerMap();
    return {};
  }

  async function refresh(){
    if(!role) return;
    try{
      ensureBreederNoticeLink();
      const m=await buildMap();
      lastMap=m;
      clearBadges();
      Object.entries(m).forEach(([href,count])=>applyOne(href,count));
      showSummary(Object.values(m).some(v=>n(v)>0));
    }catch(e){}
  }

  function waitForMenu(){
    refresh();
    let tries=0;
    const timer=setInterval(()=>{
      tries++;
      if(document.getElementById('bp-global-mobile-menu-drawer')){
        ensureBreederNoticeLink();
        refresh();
        clearInterval(timer);
      }else if(tries>=40){
        clearInterval(timer);
      }
    },250);
  }

  getRole().then(r=>{
    role=r;
    if(!role) return;
    const go=()=>{waitForMenu();setInterval(refresh,30000);window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});document.addEventListener('click',e=>{if(e.target.closest('button')&&!e.target.closest('#bp-global-mobile-menu-button,#bp-global-mobile-menu-drawer'))setTimeout(refresh,1500)})};
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go,{once:true});else go();
  });
})();
