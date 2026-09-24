(()=>{
  if(window.__BIGPAW_DESCRIPTION_FORMAT_FIX__) return;
  window.__BIGPAW_DESCRIPTION_FORMAT_FIX__=true;

  function formatLegacy(raw){
    let t=String(raw||'').replace(/\r\n?/g,'\n').trim();
    if(!t) return t;

    // Preserve breeder-authored line breaks exactly when they already exist.
    const newlineCount=(t.match(/\n/g)||[]).length;
    if(newlineCount>=2) return t;

    // Support old records that may contain literal escaped newlines.
    if(t.includes('\\n')){
      const decoded=t.replace(/\\n/g,'\n');
      if((decoded.match(/\n/g)||[]).length>=2) return decoded;
      t=decoded;
    }

    // Legacy campaign copy was saved as one long paragraph. Add display-only
    // breaks around its natural sections without changing the database text.
    t=t
      .replace(/(🎉✨\s*シルバーウィーク限定キャンペーン\s*✨🎉)\s*/g,'$1\n\n')
      .replace(/(見学予約も値引き対象です‼️?)\s*/g,'$1\n\n')
      .replace(/(9月16日[〜～-]9月23日までの期間限定で、?\s*特別価格にてご案内いたします[^\n]*?✨)\s*/g,'$1\n\n')
      .replace(/\s*(男の子|女の子)\s*(?=通常価格)/g,'\n\n$1\n')
      .replace(/(通常価格\s*[0-9,]+円)\s*/g,'$1\n')
      .replace(/(➡️\s*期間限定特別価格\s*[0-9,]+円)\s*/g,'$1\n\n')
      .replace(/(期間中にご見学・ご成約いただいた方限定の特別価格となります[^\n]*?😊)\s*/g,'$1\n')
      .replace(/(気になっていた子がいましたら、?\s*ぜひこの機会にご見学ください[^\n]*?🐾)\s*/g,'$1\n')
      .replace(/\s*([―ー]{6,})\s*/g,'\n$1\n\n')
      .replace(/\s*(🩷❤️🧡💛💚🩵💙💜)\s*/g,'\n$1\n\n')
      .replace(/(たくさんの子犬の中から、[^\n]*?ありがとうございます😊)\s*/g,'$1\n\n')
      .replace(/(💙✨[^\n]*?✨💙)\s*/g,'$1\n\n');

    // For old single-paragraph descriptions, make emoji-ended sentences easier
    // to scan on phones. This is display-only and leaves saved text untouched.
    t=t.replace(/([。！？]|(?:です|ます|でした|ません)[🥺😊☺️🥰🐶🐾💕💙💜💞✨🏆‼️❣️🩷❤️🧡💛💚🩵🎉🙌🧬🎀🧸]+)\s+(?=[^\n])/g,'$1\n\n');
    return t.replace(/\n{3,}/g,'\n\n').trim();
  }

  function fixInquiryLinks(){
    const pageId=new URLSearchParams(location.search).get('id')||'';
    [...document.querySelectorAll('a[href*="inquiry.html"]')].forEach(a=>{
      try{
        const raw=a.getAttribute('href')||'';
        const u=new URL(raw,location.href);
        const puppyId=u.searchParams.get('id')||u.searchParams.get('puppy')||pageId;
        if(puppyId) a.setAttribute('href','inquiry.html?id='+encodeURIComponent(puppyId));
      }catch(_e){}
    });
  }

  function apply(){
    let changed=false;
    fixInquiryLinks();
    [...document.querySelectorAll('h1,h2,h3,h4')].forEach(h=>{
      if((h.textContent||'').trim()!=='この子について') return;
      const box=h.closest('.detailsection,.card,section,article,div');
      if(!box) return;
      const p=box.querySelector('#desc,p');
      if(!p || p.dataset.bigpawDescriptionFormatted==='1') return;
      const raw=(p.innerText||p.textContent||'').trim();
      if(!raw || raw==='詳しい紹介文を掲載します。' || raw==='詳しくはブリーダーへお問い合わせください。') return;
      p.textContent=formatLegacy(raw);
      p.style.setProperty('white-space','pre-wrap','important');
      p.style.setProperty('line-height','1.9','important');
      p.style.setProperty('overflow-wrap','anywhere','important');
      p.dataset.bigpawDescriptionFormatted='1';
      changed=true;
    });
    return changed;
  }

  const run=()=>apply();
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',run);
  else run();
  const mo=new MutationObserver(run);
  mo.observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  setTimeout(run,250);
  setTimeout(run,800);
  setTimeout(()=>{run();mo.disconnect();},2500);
})();
