/* Only injected by shop_payments.local_preview on 127.0.0.1. NEVER loaded on BIG PAW production. */
'use strict';
(async () => {
  const cartDialog = document.getElementById('previewCartDialog');
  const checkoutDisabled = document.getElementById('previewCheckout');
  const count = document.getElementById('previewCartCount');
  const messageArea = document.querySelector('.cart-shipping');
  if (!cartDialog || !checkoutDisabled || !count || !messageArea) return;

  const notice = document.createElement('p');
  notice.id = 'squareSandboxNotice';
  notice.setAttribute('role','status');
  notice.style.cssText = 'font-size:12px;color:#8a4972;margin:8px 0;line-height:1.6';
  const button = document.createElement('button');
  button.id = 'squareSandboxCheckout';
  button.type = 'button';
  button.className = 'checkout-disabled';
  button.style.cssText = 'background:#e8dce6;color:#604454;margin-top:8px;';
  button.disabled = true;
  button.textContent = 'Squareテスト決済（設定確認中）';
  checkoutDisabled.insertAdjacentElement('afterend', button);
  button.insertAdjacentElement('afterend', notice);

  let config = null;
  let pending = false;
  function currentCart() {
    const key = 'bigpaw_shop_preview_cart_v1';
    try {
      const stored = JSON.parse(sessionStorage.getItem(key) || '{}');
      if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return {};
      const valid = Object.fromEntries(Object.entries(stored)
        .filter(([id,qty]) => /^[AOZC]\d{2}$/.test(id) &&
          Number.isInteger(qty) && qty >= 1 && qty <= 10));
      return valid;
    } catch (_) { return {}; }
  }
  function refresh() {
    const hasItems = Object.keys(currentCart()).length > 0;
    button.disabled = !config?.ready || pending || !hasItems;
    button.textContent = pending ? 'Square Sandboxと通信中…' :
      !config?.ready ? 'Squareテスト決済（テスト用接続設定待ち）' :
      !hasItems ? '商品をカートに入れてください' : 'Squareのテスト決済画面へ進む';
    if (!pending) button.style.background = button.disabled ? '#e8dce6' : '#ad4678';
    if (!pending) button.style.color = button.disabled ? '#604454' : '#ffffff';
  }
  const observer = new MutationObserver(refresh);
  observer.observe(count, {childList: true, characterData: true, subtree: true});
  try {
    const response = await fetch('/api/shop/sandbox/config', {cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw new Error('config');
    config = await response.json();
    if (!config.sandbox) throw new Error('not sandbox');
    notice.textContent = config.ready ?
      'Sandbox専用。実際の料金は請求されません。送料は販売価格に含まれます。' :
      'Sandboxのアクセストークン・店舗ID・Webhook設定を非公開の環境変数に登録すると使えます。';
  } catch (_) {
    notice.textContent = 'テスト用サーバーの設定を読み込めませんでした。';
  }
  refresh();

  button.addEventListener('click', async () => {
    if (!config?.ready || pending) return;
    const cart = currentCart();
    if (!Object.keys(cart).length) return;
    pending = true;
    refresh();
    notice.textContent = '注文金額をBIG PAWで再計算してSquare Sandboxに接続しています。';
    try {
      const res = await fetch('/api/shop/sandbox/checkout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-Shop-CSRF': config.csrf_token},
        body: JSON.stringify({cart}),
      });
      const result = await res.json();
      if (!res.ok || !result.sandbox || !result.checkout_url) throw new Error('no checkout URL');
      const destination = new URL(result.checkout_url);
      if (destination.protocol !== 'https:' || destination.hostname !== 'sandbox.square.link') {
        throw new Error('unsafe Square URL');
      }
      notice.textContent = 'Square Sandboxのテストページを開きます。';
      window.location.assign(destination.href);
    } catch (_) {
      notice.textContent = 'テスト決済ページを作れませんでした。請求は発生していません。再試行前に注文状態を確認してください。';
    } finally {
      pending = false;
      refresh();
    }
  });
})();
