/* BIG PAW preview-only cart: retail prices include tax and shipping; does NOT create orders, contact any backend, or process payments. */
'use strict';
(function () {
  const STORAGE_KEY = 'bigpaw_shop_preview_cart_v1';
  const MAX_PER_ITEM = 10;
  const ids = new Set(catalog.map(p => p.id));
  const dialog = document.getElementById('previewCartDialog');
  const openBtn = document.getElementById('previewCartOpen');
  const closeBtn = document.getElementById('previewCartContinue');
  const items = document.getElementById('previewCartItems');
  const countEl = document.getElementById('previewCartCount');
  const totalEl = document.getElementById('previewCartSubtotal');
  if (!dialog || !openBtn || !items || !countEl || !totalEl) return;

  function storageRead() {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
      const clean = {};
      Object.keys(parsed).forEach(id => {
        const qty = parsed[id];
        if (ids.has(id) && Number.isInteger(qty) && qty > 0 && qty <= MAX_PER_ITEM) clean[id] = qty;
      });
      return clean;
    } catch (_) { return {}; }
  }

  let cart = storageRead();
  function save() {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(cart)); }
    catch (_) { /* A file:// preview may disable sessionStorage; stay in memory. */ }
    window.dispatchEvent(new Event('bigpaw:shop-cart-updated'));
  }
  function yen(value) { return Math.round(value).toLocaleString('ja-JP') + '円'; }
  function price(p) { return Math.round(p.referenceMsrpExTax * 1.1); }
  function badgeCount() { return Object.values(cart).reduce((sum, qty) => sum + qty, 0); }
  function updateQty(id, delta) {
    if (!ids.has(id) || !Number.isInteger(delta)) return;
    const next = Math.min(MAX_PER_ITEM, Math.max(0, (cart[id] || 0) + delta));
    if (next) cart[id] = next; else delete cart[id];
    save(); render();
  }
  function render() {
    const products = Object.keys(cart).map(id => catalog.find(p => p.id === id)).filter(Boolean);
    countEl.textContent = String(badgeCount());
    let total = 0;
    items.innerHTML = products.length ? products.map(p => {
      const qty = cart[p.id];
      const subtotal = price(p) * qty;
      total += subtotal;
      return '<div class="cart-row" data-cart-id="' + esc(p.id) + '">' +
        '<img src="assets/shop-products/' + encodeURIComponent(p.slug) + '.webp" alt="" onerror="this.hidden=true">' +
        '<div><div class="cart-row-title">' + esc(p.brand + ' ' + p.name) + '</div>' +
        '<div class="cart-row-info">' + esc(p.weight) + ' / 販売価格（税込・送料込み）' + yen(price(p)) + '</div>' +
        '<div class="cart-row-tools"><button type="button" data-action="minus" aria-label="' + esc(p.name) + 'を1点減らす">−</button>' +
        '<span class="cart-quantity">' + qty + '</span>' +
        '<button type="button" data-action="plus" aria-label="' + esc(p.name) + 'を1点増やす" ' + (qty >= MAX_PER_ITEM ? 'disabled' : '') + '>＋</button>' +
        '<button type="button" class="remove" data-action="remove" aria-label="' + esc(p.name) + 'を削除">削除</button>' +
        '<strong>' + yen(subtotal) + '</strong></div></div></div>';
    }).join('') : '<p class="cart-empty">カートにはまだ商品がありません。</p>';
    totalEl.textContent = yen(total);
  }
  function showCart() {
    render();
    if (typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal();
  }
  function closeCart() { if (dialog.open) dialog.close(); }
  openBtn.addEventListener('click', showCart);
  closeBtn.addEventListener('click', closeCart);
  dialog.addEventListener('click', event => {
    const btn = event.target.closest('button[data-action]');
    if (!btn) return;
    const row = btn.closest('[data-cart-id]');
    if (!row) return;
    const id = row.dataset.cartId;
    if (btn.dataset.action === 'minus') updateQty(id, -1);
    if (btn.dataset.action === 'plus') updateQty(id, 1);
    if (btn.dataset.action === 'remove') updateQty(id, -MAX_PER_ITEM);
  });
  // The button is an explicit preview action. The existing order button remains disabled.
  const detailPurchase = document.querySelector('.detail .disabled');
  const id = new URLSearchParams(location.search).get('item');
  if (detailPurchase && ids.has(id)) {
    const add = document.createElement('button');
    add.type = 'button'; add.id = 'previewAddToCart';
    add.className = 'cart-try';
    add.textContent = 'お試しカートに入れる';
    add.setAttribute('aria-label', catalog.find(p => p.id === id).name + 'をお試しカートに入れる');
    detailPurchase.parentElement.insertBefore(add, detailPurchase);
    add.addEventListener('click', () => { updateQty(id, 1); showCart(); });
  }
  render();
})();