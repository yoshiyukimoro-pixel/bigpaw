(()=>{
  if(!location.pathname.endsWith('/admin.html')&&!location.pathname.endsWith('/breeder-inquiries.html'))return;
  const main=document.querySelector('main');
  if(!main||!window.BigPawAPI)return;
  const box=document.createElement('section');
  box.className='card pad';
  box.style.cssText='margin:18px 0;border:1px solid #b9d7f5;background:#f8fbff';
  box.innerHTML='<h2 style="margin-top:0">成約対象範囲の規約</h2><p data-policy-text></p><p>同意後に新たに生じた問い合わせにのみ適用します。過去の問い合わせには遡及しません。</p><p data-policy-status role="status">同意状況を確認しています…</p><label style="display:flex;gap:8px;align-items:flex-start"><input type="checkbox" data-policy-check><span>対象範囲、成約手数料5%（税込・1円未満切り捨て）、請求日から7日以内の支払条件を確認し、今後の新しい接点への適用に同意します。</span></label><button class="btn btn-sub" type="button" data-policy-accept>規約に同意する</button>';
  main.insertBefore(box,main.firstChild);
  const status=box.querySelector('[data-policy-status]'),check=box.querySelector('[data-policy-check]'),button=box.querySelector('[data-policy-accept]');
  async function load(){
    try{
      const state=await BigPawAPI.request('/breeder/deal-policy-consent');
      box.querySelector('[data-policy-text]').textContent=state.policyText;
      status.textContent=state.accepted?'同意済み（'+state.acceptance.version+'）':'未同意です。新しい対象範囲は、同意後に新たに生じた問い合わせから適用されます。';
      check.disabled=state.accepted;button.disabled=state.accepted;
      button.onclick=async()=>{
        if(!check.checked){status.textContent='規約を確認し、同意チェックを入れてください。';return}
        button.disabled=true;
        try{
          await BigPawAPI.request('/breeder/deal-policy-consent',{method:'POST',body:{accepted:true,version:state.currentVersion}});
          status.textContent='同意を記録しました。適用はこれから新たに生じる問い合わせからです。';
          check.disabled=true;
        }catch(error){status.textContent=error?.data?.message||'同意を記録できませんでした。再度お試しください。';button.disabled=false}
      };
    }catch(_error){box.remove()}
  }
  load();
})();
