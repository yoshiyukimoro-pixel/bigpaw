/* Opt-in control on the existing breeder/agent puppy editor; save separately. */
(function(){
  const safe = value => String(value||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const init = async () => {
    const main = document.querySelector('form.card');
    if(!main) return;
    const id = new URLSearchParams(location.search).get('id') || (typeof editId!=='undefined' ? editId : '');
    const panel = document.createElement('div');
    panel.id='bpOshiEditor';
    panel.style.cssText='margin-top:24px;padding:18px;border:2px solid #bdd8fb;border-radius:18px;background:#f0f7ff;color:#12304c';
    panel.innerHTML = '<h2 style="margin:0 0 8px;font-size:19px">🐾 推しワンに登録</h2>' +
      '<p style="font-size:13px;line-height:1.7;margin:0 0 12px">BIG PAWトップページの「今の推しワン！」に、犬種ごと最大5頭を掲載。6頭以上はページ更新ごとに入れ替わります。同じ犬舎・同じ犬種は2頭まで登録できます。</p>' +
      '<div id="bpOshiState" style="font-size:13px;margin-bottom:10px" aria-live="polite">登録状態を確認しています…</div>' +
      '<label id="bpOshiAgree" style="display:none;font-size:13px;line-height:1.7"><input id="bpOshiConsent" type="checkbox"> 推しワン掲載中に受けた問い合わせを起点とする成約は、初回成約無料特典が適用される場合を除き、成約手数料3％（税込）が発生することに同意します。</label>' +
      '<button type="button" id="bpOshiButton" class="btn btn-sub" style="margin-top:12px;background:#2367a8;color:white;border:0" disabled>読み込み中…</button>' +
      '<p id="bpOshiMessage" role="status" style="font-size:12px;margin:10px 0 0"></p>';
    const target = document.getElementById('editOnly');
    if(target) target.insertAdjacentElement('afterend',panel);
    else main.appendChild(panel);
    const state = panel.querySelector('#bpOshiState');
    const btn = panel.querySelector('#bpOshiButton');
    const agree = panel.querySelector('#bpOshiAgree');
    const consent = panel.querySelector('#bpOshiConsent');
    const msg = panel.querySelector('#bpOshiMessage');
    if(!id){
      state.textContent='子犬を掲載した後、編集画面から登録できます。';
      btn.textContent='掲載後に設定可能';
      return;
    }
    let enabled=false, eligible=false, count=0, limit=2;
    async function reload(){
      try{
        const res=await fetch('/api/oshiwan/'+encodeURIComponent(id)+'/state',{credentials:'same-origin',cache:'no-store'});
        const x=await res.json();
        if(!res.ok)throw Error(x.message||x.error||'取得失敗');
        enabled=!!x.enabled;eligible=!!x.eligible;count=x.kennelBreedCount||0;limit=x.kennelBreedLimit||2;
        state.textContent=(enabled?'推しワン登録中':'未登録')+' ｜ この犬舎の同じ犬種：'+count+'/'+limit+'頭';
        agree.style.display=enabled?'none':'block';
        btn.disabled=(!enabled&&!eligible) || (!enabled&&count>=limit);
        btn.textContent=enabled?'推しワンの登録を解除する':'推しワンに登録する';
        if(!enabled && !eligible) msg.textContent='公開中・募集中の子犬だけが対象です。';
        else if(!enabled && count>=limit) msg.textContent='同じ犬舎の同じ犬種は2頭までです。他の子犬の登録を解除してください。';
        else msg.textContent='';
      }catch(e){state.textContent='登録状態を確認できませんでした。';btn.disabled=true;msg.textContent=safe(e.message);}
    }
    btn.addEventListener('click',async ()=>{
      if(!enabled && !consent.checked){msg.textContent='3％の成約手数料について同意にチェックしてください。';return}
      btn.disabled=true;
      try{
        const res=await fetch('/api/oshiwan/'+encodeURIComponent(id)+'/selection',{
          method:'POST',credentials:'same-origin',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({enabled:!enabled,agreeOshiwanTerms:!enabled ? consent.checked:false})
        });
        const x=await res.json();
        if(!res.ok)throw Error(x.message||x.error||'更新失敗');
        consent.checked=false;
        await reload();
        msg.textContent=enabled?'推しワンに登録しました。':'推しワンの登録を解除しました。';
      }catch(e){msg.textContent=e.message||'登録できませんでした。';btn.disabled=false}
    });
    await reload();
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
  else init();
})();
