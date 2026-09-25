(()=>{
  const BREEDING_REASONS=[
    '一般家庭で家族として暮らしてほしいため',
    '繁殖目的での販売を行っていないため',
    '体格・サイズ等を考慮し繁殖に向かないため',
    '健康面・遺伝的リスクを考慮しているため',
    '血統・繁殖計画上、繁殖を認めていないため',
    '犬舎の繁殖方針によるため'
  ];
  const BREEDER_SALE_REASONS=[
    '一般家庭にお迎えいただきたいため',
    '繁殖目的での販売を行っていないため',
    '同業ブリーダーへの販売を行っていないため',
    '転売・再販売防止のため',
    '血統・繁殖計画上、同業者への販売を行っていないため',
    '犬舎の販売方針によるため'
  ];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const opts=a=>a.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');

  function installBreederEditor(){
    const form=document.querySelector('form[onsubmit*="savePuppy"]');
    if(!form||document.getElementById('bigpawSalesPolicy'))return;
    const photoHeading=[...form.querySelectorAll('h2')].find(x=>(x.textContent||'').trim()==='写真');
    if(!photoHeading)return;
    const wrap=document.createElement('section');
    wrap.id='bigpawSalesPolicy';
    wrap.style.marginTop='22px';
    wrap.innerHTML=`
      <h2>販売・繁殖条件</h2>
      <div class="notice" style="margin-bottom:14px">購入希望者がお問い合わせ前に確認できる情報です。可否を選択し、不可の場合は理由を選んでください。</div>
      <div class="form-grid">
        <div class="field">
          <label>この子犬での繁殖</label>
          <select id="breedingAllowed" required><option value="">選択してください</option><option value="1">繁殖可</option><option value="0">繁殖不可</option></select>
        </div>
        <div class="field" id="breedingReasonField" style="display:none">
          <label>繁殖不可の理由</label>
          <select id="breedingNgReason">${opts(BREEDING_REASONS)}</select>
        </div>
        <div class="field">
          <label>ブリーダーへの販売</label>
          <select id="breederSaleAllowed" required><option value="">選択してください</option><option value="1">販売可</option><option value="0">販売不可</option></select>
        </div>
        <div class="field" id="breederSaleReasonField" style="display:none">
          <label>ブリーダーへの販売不可の理由</label>
          <select id="breederSaleNgReason">${opts(BREEDER_SALE_REASONS)}</select>
        </div>
      </div>`;
    photoHeading.parentNode.insertBefore(wrap,photoHeading);
    const breedingAllowed=document.getElementById('breedingAllowed');
    const breederSaleAllowed=document.getElementById('breederSaleAllowed');
    const breedingReasonField=document.getElementById('breedingReasonField');
    const breederSaleReasonField=document.getElementById('breederSaleReasonField');
    const sync=()=>{
      breedingReasonField.style.display=breedingAllowed.value==='0'?'block':'none';
      breederSaleReasonField.style.display=breederSaleAllowed.value==='0'?'block':'none';
    };
    breedingAllowed.addEventListener('change',sync);breederSaleAllowed.addEventListener('change',sync);sync();

    const augment=payload=>{
      if(!['0','1'].includes(breedingAllowed.value)||!['0','1'].includes(breederSaleAllowed.value))return Object.assign({},payload);
      return Object.assign({},payload,{
        breedingAllowed:breedingAllowed.value==='1',
        breedingNgReason:breedingAllowed.value==='0'?document.getElementById('breedingNgReason').value:'',
        breederSaleAllowed:breederSaleAllowed.value==='1',
        breederSaleNgReason:breederSaleAllowed.value==='0'?document.getElementById('breederSaleNgReason').value:''
      });
    };
    if(window.BigPawBridge&&!BigPawBridge.__salesPolicyWrapped){
      const add=BigPawBridge.addPuppy.bind(BigPawBridge),update=BigPawBridge.updatePuppy.bind(BigPawBridge);
      BigPawBridge.addPuppy=(payload)=>add(augment(payload));
      BigPawBridge.updatePuppy=(id,payload)=>update(id,augment(payload));
      BigPawBridge.__salesPolicyWrapped=true;
    }
    const editId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId')||'';
    if(editId&&window.BigPawBridge){
      BigPawBridge.breederPuppies().then(ds=>{
        const d=(ds||[]).find(x=>String(x.id)===String(editId));if(!d)return;
        if(d.salesPolicySet){
          breedingAllowed.value=d.breedingAllowed===false?'0':'1';
          breederSaleAllowed.value=d.breederSaleAllowed===false?'0':'1';
          if(d.breedingNgReason&&BREEDING_REASONS.includes(d.breedingNgReason))document.getElementById('breedingNgReason').value=d.breedingNgReason;
          if(d.breederSaleNgReason&&BREEDER_SALE_NG_REASONS.includes(d.breederSaleNgReason))document.getElementById('breederSaleNgReason').value=d.breederSaleNgReason;
        }
        sync();
      }).catch(()=>{});
    }
  }

  function installStepNavigation(){
    const form=document.querySelector('form[onsubmit*="savePuppy"]');
    if(!form)return;
    const steps=[...form.querySelectorAll('.stepbar .step')];
    if(steps.length<4)return;
    const photoHeading=[...form.querySelectorAll('h2')].find(x=>(x.textContent||'').trim()==='写真');
    const targets=[
      document.getElementById('breed')?.closest('.field')||form.querySelector('h1'),
      document.getElementById('father')?.closest('.field')||[...form.querySelectorAll('h2')].find(x=>(x.textContent||'').includes('健康')),
      photoHeading,
      document.getElementById('bigpawSalesPolicy')||form.querySelector('button.btn-main.btn-wide')
    ];
    steps.forEach((step,i)=>{
      step.style.cursor='pointer';
      step.style.userSelect='none';
      step.setAttribute('role','button');
      step.setAttribute('tabindex','0');
      step.setAttribute('aria-label',(step.textContent||'').trim()+'へ移動');
      const go=()=>{
        const target=targets[i];if(!target)return;
        steps.forEach(s=>s.classList.remove('active'));
        step.classList.add('active');
        target.scrollIntoView({behavior:'smooth',block:'start'});
      };
      step.addEventListener('click',go);
      step.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}});
    });
    steps.forEach((s,i)=>s.classList.toggle('active',i===0));
  }

  async function installPublicDetail(){
    if(!/puppy-detail\.html$/.test(location.pathname)||document.getElementById('bigpawSalesPolicyPublic'))return;
    const id=new URLSearchParams(location.search).get('id');if(!id||!window.BigPawBridge)return;
    try{
      const p=await BigPawBridge.puppy(id);if(!p||!p.salesPolicySet)return;
      const cards=[...document.querySelectorAll('.card.pad')];
      const about=cards.find(x=>x.querySelector('h2')&&x.querySelector('h2').textContent.includes('この子について'));
      if(!about)return;
      const box=document.createElement('div');
      box.id='bigpawSalesPolicyPublic';box.className='card pad';box.style.marginTop='18px';
      const breedingOk=p.breedingAllowed!==false,saleOk=p.breederSaleAllowed!==false;
      box.innerHTML=`<h2>販売・繁殖条件</h2><div class="tablelike">
        <div class="table-row"><div>この子犬での繁殖</div><div><b>${breedingOk?'繁殖可':'繁殖不可'}</b>${!breedingOk&&p.breedingNgReason?`<br><span class="muted">※ ${esc(p.breedingNgReason)}</span>`:''}</div></div>
        <div class="table-row"><div>ブリーダーへの販売</div><div><b>${saleOk?'販売可':'販売不可'}</b>${!saleOk&&p.breederSaleNgReason?`<br><span class="muted">※ ${esc(p.breederSaleNgReason)}</span>`:''}</div></div>
      </div><p class="muted" style="margin-top:12px">「繁殖可」は繁殖能力を保証するものではありません。販売・繁殖条件はブリーダーの譲渡方針です。</p>`;
      about.insertAdjacentElement('afterend',box);
    }catch(_e){}
  }

  function boot(){installBreederEditor();installStepNavigation();installPublicDetail()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
