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
  const statusButton = document.createElement('button');
  statusButton.id = 'squareSandboxStatusButton';
  statusButton.type = 'button';
  statusButton.className = 'cart-continue';
  statusButton.textContent = '直近のSquareテスト注文の状態を確認';
  statusButton.hidden = true;
  const statusResult = document.createElement('p');
  statusResult.id = 'squareSandboxStatusResult';
  statusResult.setAttribute('role', 'status');
  statusResult.style.cssText = 'font-size:12px;color:#5b4a62;margin:8px 0;';
  notice.insertAdjacentElement('afterend', statusButton);
  statusButton.insertAdjacentElement('afterend', statusResult);
  const lastOrderKey = 'bigpaw_shop_sandbox_last_order_v1';
  const validOrderId = /^FOOD[0-9a-f]{32}$/;
  function getLastOrderId() {
    try {
      const value = sessionStorage.getItem(lastOrderKey);
      return value && validOrderId.test(value) ? value : null;
    } catch (_) { return null; }
  }
  function storeLastOrderId(value) {
    if (!validOrderId.test(value)) return;
    try { sessionStorage.setItem(lastOrderKey, value); } catch (_) {}
    statusButton.hidden = false;
  }
  statusButton.hidden = !getLastOrderId();
  statusButton.addEventListener('click', async () => {
    const id = getLastOrderId();
    if (!id) return;
    statusButton.disabled = true;
    statusResult.textContent = 'Squareのテスト注文状態を確認しています…';
    try {
      const res = await fetch('/api/shop/sandbox/order/' + encodeURIComponent(id), {
        cache: 'no-store', credentials: 'same-origin',
      });
      if (!res.ok) throw new Error('status unavailable');
      const data = await res.json();
      const labels = {
        created: 'テスト注文は作成されていますが、決済ページの準備中です。',
        payment_pending: 'Squareテスト決済は確認待ちです。完了済みとは判定していません。',
        paid: 'Square Sandboxでテスト決済完了を確認済みです。実際の入金ではありません。',
      };
      statusResult.textContent = labels[data.order_status] ||
        '注文状態を確認できません。';
    } catch (_) {
      statusResult.textContent = 'テスト注文状態を取得できませんでした。後で再確認してください。';
    } finally {
      statusButton.disabled = false;
    }
  });


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
  function checkoutAttemptFor(cart) {
    // Stable attempt for this cart, even if the Square response is lost.
    // New cart/quantities generate a new checkout attempt, not a new charge
    // after a transient network error on the same cart.
    if (!crypto?.randomUUID) throw new Error('Secure checkout ID unavailable');
    const fingerprint = Object.entries(cart).sort((a,b) => a[0].localeCompare(b[0]))
      .map(([id,qty]) => id + ':' + qty).join('|');
    const key = 'bigpaw_shop_sandbox_attempt_v1';
    try {
      const stored = JSON.parse(sessionStorage.getItem(key) || '{}');
      if (stored.fingerprint === fingerprint &&
          /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(stored.id)) {
        return stored.id;
      }
    } catch (_) { /* use a new random attempt */ }
    const attempt = crypto.randomUUID();
    sessionStorage.setItem(key, JSON.stringify({fingerprint, id: attempt}));
    return attempt;
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
        body: JSON.stringify({cart, attempt_id: checkoutAttemptFor(cart)}),
      });
      const result = await res.json();
      if (!res.ok || !result.sandbox || !result.checkout_url) throw new Error('no checkout URL');
      const destination = new URL(result.checkout_url);
      if (destination.protocol !== 'https:' || destination.hostname !== 'sandbox.square.link') {
        throw new Error('unsafe Square URL');
      }
      if (typeof result.order_id !== 'string' || !validOrderId.test(result.order_id)) {
        throw new Error('invalid sandbox order id');
      }
      storeLastOrderId(result.order_id);
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
