/* Injected ONLY by localhost Square Sandbox preview on ?order=review.
   Production app/shop.html NEVER loads this script. No customer PII stored. */
'use strict';
(async () => {
  const root = document.getElementById('orderReview');
  const checkbox = document.getElementById('orderConfirmChecked');
  const reviewed = document.getElementById('orderPreviewConfirmation');
  const confirmButton = document.getElementById('orderConfirmPreview');
  const amountText = document.getElementById('orderReviewTotal');
  const oldCheckout = document.getElementById('previewCheckout');
  if (!root || root.hidden || !checkbox || !reviewed || !confirmButton ||
      !oldCheckout || !oldCheckout.disabled || !amountText) return;

  const cartKey = 'bigpaw_shop_preview_cart_v1';
  const attemptKey = 'bigpaw_shop_sandbox_attempt_v1';
  const orderKey = 'bigpaw_shop_sandbox_last_order_v1';
  const orderIdPattern = /^FOOD[0-9a-f]{32}$/;
  const attemptPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  const moneyLimit = 2000000;
  const byId = new Map(catalog.map(p => [p.id,p]));
  let config = null;
  let pending = false;

  // Only this injected sandbox button can create a *test* order. Public
  // confirmation button remains inert, even if server-side credentials exist.
  const button = document.createElement('button');
  button.id = 'squareReviewSandboxCheckout';
  button.type = 'button';
  button.className = 'order-submit-test';
  button.style.marginTop = '10px';
  button.disabled = true;
  button.textContent = 'Squareテスト決済（接続確認中）';
  const notice = document.createElement('p');
  notice.id = 'squareReviewSandboxNotice';
  notice.setAttribute('role','status');
  notice.className = 'order-data-note';
  button.insertAdjacentElement('afterend', notice);
  confirmButton.insertAdjacentElement('afterend', button);

  const status = document.createElement('div');
  status.className = 'order-status';
  status.id = 'squareReviewSandboxStatus';
  status.style.marginTop = '13px';
  const statusButton = document.createElement('button');
  statusButton.id = 'squareReviewSandboxStatusCheck';
  statusButton.type = 'button';
  statusButton.className = 'order-edit';
  statusButton.textContent = '直近のSquareテスト注文の入金状況を確認する';
  const statusText = document.createElement('p');
  statusText.id = 'squareReviewSandboxStatusResult';
  statusText.setAttribute('role','status');
  statusText.textContent = 'Squareの画面から戻っただけでは入金済みとは判定しません。';
  status.append(statusButton,statusText);
  notice.insertAdjacentElement('afterend',status);

  function readCart() {
    try {
      const raw = JSON.parse(sessionStorage.getItem(cartKey) || '{}');
      if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
      const cart = {};
      for (const [id,qty] of Object.entries(raw)) {
        if (!byId.has(id) || !Number.isInteger(qty) || qty < 1 || qty > 10) return null;
        cart[id]=qty;
      }
      return Object.keys(cart).length ? cart : null;
    } catch (_) { return null; }
  }
  function totalFor(cart) {
    if (!cart) return 0;
    return Object.entries(cart).reduce((sum,[id,qty]) =>
      sum + Math.round(byId.get(id).referenceMsrpExTax * 1.1) * qty,0);
  }
  function fingerprint(cart) {
    return Object.entries(cart).sort((a,b)=>a[0].localeCompare(b[0]))
      .map(([id,qty])=>id+':'+qty).join('|');
  }
  function checkoutAttempt(cart) {
    if (!globalThis.crypto || typeof crypto.randomUUID !== 'function')
      throw new Error('Secure random checkout attempt unavailable');
    const key = fingerprint(cart);
    try {
      const stored = JSON.parse(sessionStorage.getItem(attemptKey) || '{}');
      if (stored.fingerprint === key && attemptPattern.test(stored.id)) return stored.id;
    } catch (_) { /* browser storage unavailable; fail closed below */ }
    const id = crypto.randomUUID();
    sessionStorage.setItem(attemptKey,JSON.stringify({fingerprint:key,id}));
    return id;
  }
  function lastOrder() {
    try {
      const id=sessionStorage.getItem(orderKey);
      return id && orderIdPattern.test(id) ? id : null;
    } catch (_) { return null; }
  }
  function isReviewed() {
    return checkbox.checked && !confirmButton.disabled && !reviewed.hidden;
  }
  let agreedFingerprint = null;
  function canSubmit() {
    const cart=readCart();
    return Boolean(config?.sandbox && config?.ready && !pending &&
      isReviewed() && cart && totalFor(cart) > 0 && totalFor(cart) <= moneyLimit &&
      agreedFingerprint === fingerprint(cart) &&
      amountText.textContent.replace(/[^\d]/g,'') === String(totalFor(cart)));
  }
  function refresh() {
    button.disabled = !canSubmit();
    button.textContent = pending ? 'Squareテスト決済を準備中…' :
      !config?.ready ? 'Squareテスト決済（接続設定待ち）' :
      !isReviewed() ? '注文内容を確認するとSquareテストへ進めます' :
      'Squareのテスト決済へ進む';
    status.hidden = !lastOrder();
  }
  // The verification button is controlled by order-review.js. It must be
  // clicked *after* the checkmark; edits clear this review.
  confirmButton.addEventListener('click', () => {
    const cart=readCart();
    agreedFingerprint = cart && isReviewed() ? fingerprint(cart) : null;
    refresh();
  });
  checkbox.addEventListener('change',() => {
    if (!checkbox.checked) agreedFingerprint=null;
    refresh();
  });
  window.addEventListener('bigpaw:shop-cart-updated',() => {
    agreedFingerprint=null;
    refresh();
  });
  window.addEventListener('pageshow',() => {
    agreedFingerprint=null; // Explicit confirmation required again on return.
    refresh();
  });

  statusButton.addEventListener('click',async()=>{
    const id=lastOrder();
    if(!id) return;
    statusButton.disabled=true;
    statusText.textContent='Square Sandboxで確認した注文状態を取得しています…';
    try{
      const r=await fetch('/api/shop/sandbox/order/'+encodeURIComponent(id),
        {credentials:'same-origin',cache:'no-store'});
      if(!r.ok) throw new Error('unavailable');
      const result=await r.json();
      const labels={
        created:'テスト注文の準備中です。決済は完了していません。',
        payment_pending:'決済確認待ちです。Squareの画面から戻っても入金済みとは判定しません。',
        paid:'Square Sandboxの決済完了をサーバーで確認済みです。実際の入金ではありません。',
      };
      statusText.textContent=labels[result.order_status] || 'テスト注文状態を確認できません。';
    }catch(_){
      statusText.textContent='テスト注文状態を取得できませんでした。再度確認してください。';
    }finally{statusButton.disabled=false;}
  });

  try{
    const r=await fetch('/api/shop/sandbox/config',{credentials:'same-origin',cache:'no-store'});
    if(!r.ok) throw new Error('config unavailable');
    config=await r.json();
    if(config.sandbox !== true || config.real_payments !== false ||
       config.shipping_included !== true || typeof config.csrf_token !== 'string')
      throw new Error('unsafe payment config');
    notice.textContent=config.ready ?
      'Square Sandbox専用。テストカードのみ使用できます。実際の請求はありません。' :
      'Square Sandboxの設定が未完了です。テスト決済は無効です。';
  }catch(_){
    config=null;notice.textContent='Squareテスト接続を確認できません。注文や課金は実行されません。';
  }
  refresh();

  button.addEventListener('click',async()=>{
    if(!canSubmit())return;
    const cart=readCart();
    const amount=totalFor(cart);
    pending=true;refresh();
    notice.textContent='35商品の販売価格表をサーバーで再確認し、Square Sandboxへ接続しています。';
    try{
      const attempt_id=checkoutAttempt(cart);
      const r=await fetch('/api/shop/sandbox/checkout',{
        method:'POST',credentials:'same-origin',cache:'no-store',
        headers:{'Content-Type':'application/json','X-Shop-CSRF':config.csrf_token},
        body:JSON.stringify({cart,attempt_id}),
      });
      if(!r.ok) throw new Error('Square Sandbox checkout unavailable');
      const result=await r.json();
      if(result.sandbox !== true || result.shipping_yen !== 0 ||
         result.amount_yen !== amount || typeof result.order_id!=='string' ||
         !orderIdPattern.test(result.order_id))
        throw new Error('server amount or sandbox order mismatch');
      const dest=new URL(result.checkout_url);
      if(dest.protocol!=='https:'||dest.hostname!=='sandbox.square.link' ||
         dest.username || dest.password)
        throw new Error('unsafe Square sandbox destination');
      sessionStorage.setItem(orderKey,result.order_id);
      notice.textContent='Square Sandboxのテスト決済画面へ移動します。';
      window.location.assign(dest.href);
    }catch(_){
      notice.textContent='テスト決済の準備に失敗したか、表示金額が一致しません。請求済みとは判定しません。注文状態をご確認ください。';
      agreedFingerprint=null;
    }finally{
      pending=false;refresh();
    }
  });
})();
