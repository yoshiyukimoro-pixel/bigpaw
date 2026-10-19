(()=>{
  if(!location.pathname.endsWith('/admin.html')&&!location.pathname.endsWith('/breeder-inquiries.html'))return;
  const main=document.querySelector('main');
  if(!main||!window.BigPawAPI)return;
  const box=document.createElement('section');
  box.className='card pad';
  box.style.cssText='margin:18px 0;border:1px solid #b9d7f5;background:#f8fbff';
  box.innerHTML='<h2 style="margin-top:0">成約対象範囲の規約</h2><p data-policy-text></p><p>同意後に新たに始まった問い合わせに限り、問い合わせ開始から90日以内の最初の成約報告に適用します。期間内に報告した取引のお迎え完了報告は、90日経過後も行えます。過去の問い合わせには遡及しません。</p><p data-policy-status role="status">同意状況を確認しています…</p><label style="display:flex;gap:8px;align-items:flex-start"><input type="checkbox" data-policy-check><span>対象範囲、成約手数料5%（税込・1円未満切り捨て）、請求日から7日以内の支払条件を確認し、同意後の問い合わせに限ること、最初の成約報告は問い合わせ開始から90日以内であること、およびお迎え完了報告は期間後も可能であることを確認し、適用に同意します。</span></label><button class="btn btn-sub" type="button" data-policy-accept>規約に同意する</button>';
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
          const review=document.createElement('p');
          review.style.cssText='margin:8px 0;color:#52708b;font-size:14px';
          review.innerHTML='<a href="terms.html#deal-scope">同意済み・成約対象範囲の規約を見返す</a>';
          box.replaceWith(review);
        }catch(error){status.textContent=error?.data?.message||'同意を記録できませんでした。再度お試しください。';button.disabled=false}
      };
    }catch(_error){box.remove()}
  }
  load();
})();
