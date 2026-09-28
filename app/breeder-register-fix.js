(()=>{
  function fix(){
    const c=document.getElementById('agreeCommissionTerms');
    const b=document.getElementById('submitBtn');
    if(c&&b){
      const sync=()=>{b.disabled=!c.checked;b.setAttribute('aria-disabled',String(!c.checked));};
      c.addEventListener('change',sync);
      sync();
    }
    if(!document.getElementById('bpMailGuide')){
      const form=document.getElementById('breederApplicationForm');
      if(form){
        const n=document.createElement('div');
        n.id='bpMailGuide';
        n.className='notice';
        n.style.cssText='margin-top:14px;font-size:13px;line-height:1.7';
        n.innerHTML='<b>審査結果メールについて</b><br>BIG PAWからのメールは <b>noreply@bigpaw.site</b> より送信します。審査結果の連絡後、5分ほど待っても届かない場合は迷惑メールフォルダをご確認いただき、<b>noreply@bigpaw.site</b> からのメールを受信できるよう受信許可設定をご確認ください。';
        form.appendChild(n);
      }
    }
  }
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',fix):fix();
})();
