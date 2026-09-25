(()=>{
  if(!/\/parent-dogs\.html$/.test(location.pathname))return;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const COMMON=[
    'DM（変性性脊髄症）',
    'PRA（prcd／進行性網膜萎縮症）',
    'vWD type1（フォンヴィルブランド病Ⅰ）'
  ];
  const RESULTS=['クリア','キャリア','アフェクテッド','判定保留'];

  function parse(value){
    const text=String(value||'').trim();
    if(!text)return [];
    return text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{
      let parts=line.split('｜');
      if(parts.length<2)parts=line.split(/\s*\|\s*/);
      if(parts.length<2)return {name:line,result:''};
      return {name:String(parts.shift()||'').trim(),result:String(parts.join('｜')||'').trim()};
    }).filter(x=>x.name);
  }
  function serialize(rows){
    return rows.filter(x=>String(x.name||'').trim()).map(x=>`${String(x.name).trim()}｜${String(x.result||'クリア').trim()||'クリア'}`).join('\n');
  }
  function render(value,{empty=false}={}){
    const rows=parse(value);
    if(!rows.length)return empty?'<div class="bp-genetics-empty">未登録</div>':'';
    return `<div class="bp-genetics-view">${rows.map(r=>`<div class="bp-genetics-view-row"><span>${esc(r.name)}</span><b>${esc(r.result||'')}</b></div>`).join('')}</div>`;
  }

  function ensureCss(){
    if(document.getElementById('bpParentGeneticsCss'))return;
    const s=document.createElement('style');s.id='bpParentGeneticsCss';
    s.textContent=`
      .bp-genetics-editor{margin-top:8px;border:1px solid #cbdcf4;border-radius:16px;background:#f7fbff;padding:12px}
      .bp-genetics-head,.bp-genetics-edit-row{display:grid;grid-template-columns:minmax(0,1fr) 118px 40px;gap:8px;align-items:center}
      .bp-genetics-head{font-size:12px;font-weight:800;color:#6c809b;margin:0 2px 6px}
      .bp-genetics-edit-row{margin-top:8px}.bp-genetics-edit-row input,.bp-genetics-edit-row select{width:100%;min-width:0;border:1px solid #cbdcf4;border-radius:10px;padding:10px;background:#fff;font:inherit}
      .bp-genetics-remove{width:40px;height:40px;border:1px solid #d9e4f3;border-radius:10px;background:#fff;color:#657b97;font-size:20px;line-height:1}
      .bp-genetics-add{margin-top:10px}.bp-genetics-help{display:block;margin-top:8px;font-size:12px;color:#7d8da2;line-height:1.55}
      .bp-genetics-block{margin-top:14px;padding-top:12px;border-top:1px solid #e4edf8}.bp-genetics-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}.bp-genetics-title b{font-size:14px}.bp-genetics-edit-btn{border:1px solid #cbdcf4;background:#fff;color:#426895;border-radius:10px;padding:7px 9px;font-weight:800;font-size:12px}
      .bp-genetics-view{margin-top:8px;border:1px solid #dce7f7;border-radius:12px;overflow:hidden;background:#fff}
      .bp-genetics-view-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:9px 10px;border-top:1px solid #e7eef8;font-size:13px}.bp-genetics-view-row:first-child{border-top:0}.bp-genetics-view-row span{min-width:0;line-height:1.45}.bp-genetics-view-row b{white-space:nowrap;color:#3f6d9f}
      .bp-genetics-empty{font-size:13px;color:#8c9bae;padding:8px 0}
      @media(max-width:520px){.bp-genetics-head,.bp-genetics-edit-row{grid-template-columns:minmax(0,1fr) 96px 36px;gap:6px}.bp-genetics-edit-row input,.bp-genetics-edit-row select{padding:9px 8px;font-size:14px}.bp-genetics-remove{width:36px;height:38px}.bp-genetics-view-row{font-size:12px;padding:8px}}
    `;
    document.head.appendChild(s);
  }

  function ensureDatalist(){
    if(document.getElementById('bpGeneticsCommon'))return;
    const d=document.createElement('datalist');d.id='bpGeneticsCommon';d.innerHTML=COMMON.map(x=>`<option value="${esc(x)}"></option>`).join('');document.body.appendChild(d);
  }

  function addRow(container,data={}){
    const row=document.createElement('div');row.className='bp-genetics-edit-row';
    const result=String(data.result||'クリア');
    row.innerHTML=`<input class="bp-gen-name" list="bpGeneticsCommon" placeholder="例：DM（変性性脊髄症）" value="${esc(data.name||'')}"><select class="bp-gen-result">${RESULTS.map(x=>`<option${x===result?' selected':''}>${esc(x)}</option>`).join('')}</select><button type="button" class="bp-genetics-remove" aria-label="この検査を削除">×</button>`;
    row.querySelector('.bp-genetics-remove').onclick=()=>{row.remove();if(!container.querySelector('.bp-genetics-edit-row'))addRow(container);syncCreate()};
    row.querySelectorAll('input,select').forEach(el=>{el.addEventListener('input',syncCreate);el.addEventListener('change',syncCreate)});
    container.appendChild(row);
    return row;
  }
  function rowsFrom(container){return [...container.querySelectorAll('.bp-genetics-edit-row')].map(row=>({name:row.querySelector('.bp-gen-name')?.value||'',result:row.querySelector('.bp-gen-result')?.value||'クリア'}))}

  let createRows=null;
  function syncCreate(){
    const ta=document.getElementById('pdGenetics');if(!ta||!createRows)return;
    ta.value=serialize(rowsFrom(createRows));
  }
  function resetCreateRows(){
    if(!createRows)return;createRows.innerHTML='';addRow(createRows);syncCreate();
  }
  function installCreateEditor(){
    const ta=document.getElementById('pdGenetics');if(!ta||document.getElementById('bpCreateGeneticsEditor'))return;
    const field=ta.closest('.field');if(!field)return;
    const label=field.querySelector('label');if(label)label.textContent='遺伝子検査（任意）';
    ta.style.display='none';ta.setAttribute('aria-hidden','true');
    const ed=document.createElement('div');ed.id='bpCreateGeneticsEditor';ed.className='bp-genetics-editor';
    ed.innerHTML='<div class="bp-genetics-head"><span>検査項目</span><span>結果</span><span></span></div><div id="bpCreateGeneticsRows"></div><button type="button" class="btn btn-sub bp-genetics-add" id="bpCreateGeneticsAdd">＋ 検査を追加</button><small class="bp-genetics-help">検査名は自由に入力できます。犬種別候補がある場合は上に表示されます。結果は「クリア」と表示できます。</small>';
    field.appendChild(ed);createRows=ed.querySelector('#bpCreateGeneticsRows');
    const existing=parse(ta.value);(existing.length?existing:[{}]).forEach(x=>addRow(createRows,x));
    ed.querySelector('#bpCreateGeneticsAdd').onclick=()=>{const r=addRow(createRows);r.querySelector('input')?.focus()};syncCreate();
    const form=ta.closest('form');if(form)form.addEventListener('reset',()=>setTimeout(resetCreateRows,0));
  }

  let editDogId='',editRows=null;
  function ensureEditModal(){
    if(document.getElementById('pdGeneticsModal'))return;
    const m=document.createElement('div');m.className='modal';m.id='pdGeneticsModal';
    m.innerHTML='<div class="box"><h2>遺伝子検査を登録・編集</h2><p class="muted" style="margin-top:-4px">左に検査項目、右に結果を登録します。</p><div class="bp-genetics-editor"><div class="bp-genetics-head"><span>検査項目</span><span>結果</span><span></span></div><div id="pdGeneticsEditRows"></div><button type="button" class="btn btn-sub bp-genetics-add" id="pdGeneticsEditAdd">＋ 検査を追加</button></div><div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button type="button" class="btn btn-sub" id="pdGeneticsCancel">キャンセル</button><button type="button" class="btn btn-main" id="pdGeneticsSave">保存する</button></div></div>';
    document.body.appendChild(m);editRows=document.getElementById('pdGeneticsEditRows');
    document.getElementById('pdGeneticsCancel').onclick=()=>m.classList.remove('show');
    document.getElementById('pdGeneticsEditAdd').onclick=()=>{const r=addRow(editRows);r.querySelector('input')?.focus()};
    document.getElementById('pdGeneticsSave').onclick=saveEdit;
  }
  function open(id){
    ensureEditModal();editDogId=String(id||'');const d=(window.__BIGPAW_PARENT_DOGS||[]).find(x=>String(x.id)===editDogId);if(!d)return;
    editRows.innerHTML='';const rows=parse(d.genetics);(rows.length?rows:[{}]).forEach(x=>addRow(editRows,x));
    document.getElementById('pdGeneticsModal').classList.add('show');
  }
  async function saveEdit(){
    if(!editDogId)return;const btn=document.getElementById('pdGeneticsSave');btn.disabled=true;
    try{await BigPawAPI.updateParentDog(editDogId,{genetics:serialize(rowsFrom(editRows))});document.getElementById('pdGeneticsModal').classList.remove('show');if(window.BigPawParentPhoto?.reload)await BigPawParentPhoto.reload()}
    catch(_e){alert('遺伝子検査を保存できませんでした。')}
    finally{btn.disabled=false}
  }

  function decorateManagedCards(){
    const list=window.__BIGPAW_PARENT_DOGS||[],host=document.getElementById('parentList');if(!host||!list.length)return;
    const cards=[...host.children].filter(x=>x.classList.contains('card')&&!x.classList.contains('empty'));
    cards.forEach((card,i)=>{
      const d=list[i];if(!d||card.querySelector('.bp-genetics-block'))return;
      const pad=card.querySelector('.pad');if(!pad)return;
      [...pad.querySelectorAll(':scope > p.muted')].forEach(p=>{if(String(p.textContent||'').trim()===String(d.genetics||'').trim())p.remove()});
      const block=document.createElement('div');block.className='bp-genetics-block';
      block.innerHTML=`<div class="bp-genetics-title"><b>🧬 遺伝子検査</b><button type="button" class="bp-genetics-edit-btn">登録・編集</button></div>${render(d.genetics,{empty:true})}`;
      block.querySelector('button').onclick=()=>window.BigPawParentGenetics.open(d.id);
      const health=[...pad.querySelectorAll('a')].find(a=>String(a.getAttribute('href')||'').includes('health-records.html'));
      if(health)pad.insertBefore(block,health);else pad.appendChild(block);
    });
  }
  function watchCards(){
    const host=document.getElementById('parentList');if(!host)return;
    new MutationObserver(()=>setTimeout(decorateManagedCards,0)).observe(host,{childList:true});
    setTimeout(decorateManagedCards,60);
  }

  window.BigPawParentGenetics={open,render,parse,serialize};
  function start(){ensureCss();ensureDatalist();installCreateEditor();ensureEditModal();watchCards()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
