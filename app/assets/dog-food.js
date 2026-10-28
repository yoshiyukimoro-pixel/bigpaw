/* Stand-alone prelaunch catalog. No order, cart, payment, or backend API requests. */
(function(){
  'use strict';
  const products = Array.isArray(window.BIGPAW_FOOD_PRODUCTS) ? window.BIGPAW_FOOD_PRODUCTS : [];
  const grid = document.getElementById('productGrid');
  const count = document.getElementById('resultCount');
  const empty = document.getElementById('emptyState');
  const keyword = document.getElementById('keyword');
  const brand = document.getElementById('brandFilter');
  const purpose = document.getElementById('purposeFilter');
  const dialog = document.getElementById('productDialog');
  const detailBody = document.getElementById('detailBody');
  const panel = dialog.querySelector('[role="dialog"]');
  let lastFocus = null;
  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const imagePath = p => 'assets/dog-food-images/' + encodeURIComponent(p.image);
  function picture(p) {
    const placeholder = '<div class="image-placeholder"><span class="paw" aria-hidden="true">🐾</span><b>' + esc(p.brand) + '</b><small>商品画像は掲載準備中</small></div>';
    // Actual manufacturer images will be installed only after optimization/rights check.
    return '<div class="image-box"><img src="' + imagePath(p) + '" alt="' + esc(p.brand + ' ' + p.name) + '" loading="lazy" hidden><div class="fallback">' + placeholder + '</div></div>';
  }
  function wirePictures(root) {
    root.querySelectorAll('.image-box').forEach(box => {
      const img = box.querySelector('img');
      const fallback = box.querySelector('.fallback');
      img.addEventListener('load', () => { img.hidden = false; fallback.hidden = true; });
      img.addEventListener('error', () => { img.hidden = true; fallback.hidden = false; });
    });
  }
  function card(p) {
    return '<article class="product">' + picture(p) +
      '<div class="product-body"><div class="product-brand">' + esc(p.brand) + ' / ' + esc(p.series) + '</div>' +
      '<h3>' + esc(p.name) + '</h3>' +
      '<div class="tags"><span class="tag">' + esc(p.purpose) + '</span><span class="tag size">' + esc(p.size) + '</span></div>' +
      '<p class="product-desc">' + esc(p.description) + '</p>' +
      '<div class="product-bottom"><div class="unpriced">販売価格：準備中</div>' +
      '<button type="button" class="product-btn" data-product-id="' + esc(p.id) + '" aria-label="' + esc(p.name) + 'の詳細を見る">商品の詳細を見る</button></div></div></article>';
  }
  function matches(p) {
    const q = keyword.value.trim().toLocaleLowerCase('ja-JP');
    const words = [p.brand,p.series,p.name,p.size,p.description,p.purpose].join(' ').toLocaleLowerCase('ja-JP');
    return (!q || words.includes(q)) && (!brand.value || brand.value===p.brand) && (!purpose.value || purpose.value===p.purpose);
  }
  function render() {
    const found = products.filter(matches);
    grid.innerHTML = found.map(card).join('');
    count.textContent = found.length + '商品 / 全' + products.length + '商品';
    empty.hidden = found.length!==0;
    wirePictures(grid);
    document.querySelectorAll('[data-quick]').forEach(b => b.classList.toggle('active', b.dataset.quick===purpose.value));
  }
  function openDetails(id, updateUrl) {
    const p = products.find(item => item.id===id);
    if (!p) return;
    lastFocus = document.activeElement;
    detailBody.innerHTML = '<div class="detail-layout">' + picture(p) +
      '<div><div class="product-brand">' + esc(p.brand) + ' / ' + esc(p.series) + '</div>' +
      '<h2 id="detailName">' + esc(p.name) + '</h2>' +
      '<div class="tags"><span class="tag">' + esc(p.purpose) + '</span><span class="tag size">' + esc(p.size) + '</span></div>' +
      '<p class="detail-copy">' + esc(p.description) + '</p>' +
      '<p class="detail-meta">商品番号：' + esc(p.id) + '</p>' +
      '<div class="detail-warning"><strong>販売準備中・注文できません</strong>商品画像・正式名称・成分表・価格・送料を確認後に公開する予定です。現在は予約・注文・決済を受け付けていません。</div></div></div>';
    wirePictures(detailBody);
    dialog.hidden = false;
    document.body.classList.add('dialog-open');
    panel.focus();
    if (updateUrl) history.pushState({food:id},'', '?id='+encodeURIComponent(id));
  }
  function closeDetails(updateUrl) {
    if (dialog.hidden) return;
    dialog.hidden = true;
    document.body.classList.remove('dialog-open');
    if (updateUrl) history.pushState(null,'',location.pathname);
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  }
  [keyword,brand,purpose].forEach(el => el.addEventListener(el===keyword?'input':'change',render));
  document.getElementById('clearFilters').addEventListener('click',() => {
    keyword.value='';brand.value='';purpose.value='';render();keyword.focus();
  });
  document.querySelectorAll('[data-quick]').forEach(btn => btn.addEventListener('click',() => {
    purpose.value = purpose.value===btn.dataset.quick ? '' : btn.dataset.quick;
    render();document.getElementById('catalog').scrollIntoView({behavior:'smooth'});
  }));
  grid.addEventListener('click',event => {
    const button=event.target.closest('[data-product-id]');
    if(button) openDetails(button.dataset.productId,true);
  });
  document.getElementById('closeDialog').addEventListener('click',()=>closeDetails(true));
  dialog.addEventListener('click',event=>{if(event.target.dataset.close)closeDetails(true);});
  document.addEventListener('keydown',event=>{
    if(dialog.hidden)return;
    if(event.key==='Escape'){event.preventDefault();closeDetails(true);}
    if(event.key==='Tab'){
      // Only the close control is focusable in this prelaunch dialog.
      event.preventDefault();document.getElementById('closeDialog').focus();
    }
  });
  window.addEventListener('popstate',()=>{
    const id = new URLSearchParams(location.search).get('id');
    const valid=products.some(p=>p.id===id);
    if(valid){closeDetails(false);openDetails(id,false);} else closeDetails(false);
  });
  render();
  const initial=new URLSearchParams(location.search).get('id');
  if(initial)openDetails(initial,false);
})();
