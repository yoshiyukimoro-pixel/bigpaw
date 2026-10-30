/* Independent order review UI. Staging-only: no network, PII, payment or order creation. */
'use strict';
(function () {
  const root = document.getElementById('orderReview');
  if (!root || root.hidden) return;
  const CART_KEY = 'bigpaw_shop_preview_cart_v1';
  const YEN = n => Math.round(n).toLocaleString('ja-JP') + '円';
  const limit = 2_000_000;
  const checkout = document.getElementById('previewCheckout');
  if (!checkout || !checkout.disabled) throw Error('The public checkout must remain disabled');

  root.innerHTML =
    '<div class="order-preview">' +
    '<a class="order-back" href="shop.html">← 商品一覧に戻る</a>' +
    '<div class="order-preview-badge">販売準備中・操作確認用</div>' +
    '<h1>ご注文内容の確認</h1>' +
    '<ol class="order-steps" aria-label="注文の流れ">' +
      '<li>1. 商品を選ぶ</li><li class="active" aria-current="step">2. 注文内容確認</li>' +
      '<li>3. お届け先・カード入力</li><li>4. 注文完了</li>' +
    '</ol>' +
    '<p class="order-preview-warning" role="status">' +
      '<strong>これは注文画面のテスト表示です。</strong> ご注文や決済、在庫の確保は行われません。' +
      '実際の住所やカード情報を入力する必要はありません。</p>' +
    '<div id="orderReviewEmpty" class="order-empty" hidden>カートに商品がありません。' +
      '<a href="shop.html">商品一覧から選んでください。</a></div>' +
    '<div id="orderReviewContent" class="order-columns">' +
      '<div>' +
        '<section class="order-panel" aria-labelledby="orderItemsTitle">' +
          '<h2 id="orderItemsTitle">ご注文商品</h2><div id="orderReviewItems"></div>' +
          '<button type="button" class="order-edit" id="orderEditCart">数量を変更・商品を削除</button>' +
          '<p class="order-edits-notice">数量変更後、合計金額は自動的に更新されます。</p>' +
        '</section>' +
        '<section class="order-panel" aria-labelledby="orderDeliveryTitle">' +
          '<h2 id="orderDeliveryTitle">📦 お届け方法・予定</h2>' +
          '<div class="order-status"><strong>お取り寄せ販売｜通常4〜7日程度でお届け</strong>' +
          '<p>ご注文・決済完了後、九州の仕入先へ発注し、埼玉の当店に入荷・検品後、当店からお客様へ発送します。</p>' +
          '<p>追加送料は0円（全国送料無料）です。お届けまでの日数は注文・決済完了からの目安で、土日祝日・仕入先の休業日・配送地域・交通事情で前後する場合があります。</p>' +
          '<p>仕入先の欠品時は速やかにご連絡し、入荷予定のご案内または全額返金にて対応いたします。</p></div>' +
        '</section>' +
        '<section class="order-panel" aria-labelledby="orderAddressTitle">' +
          '<h2 id="orderAddressTitle">お届け先</h2>' +
          '<div class="order-status"><strong>日本国内への配送</strong>' +
          '<p>お名前・郵便番号・住所・電話番号などは、今後Squareの安全な決済画面で入力する方式です。</p>' +
          '<p>この注文確認画面では個人情報を保存しません。</p></div>' +
        '</section>' +
        '<section class="order-panel" aria-labelledby="orderMethodTitle">' +
          '<h2 id="orderMethodTitle">お支払い方法</h2>' +
          '<div class="order-status">クレジットカード（Square）を予定しています。' +
          '現在はテスト段階のため、支払いはできません。</div>' +
        '</section>' +
        '<section class="order-panel" id="orderCommerceTerms" aria-labelledby="orderCommerceTitle">' +
          '<h2 id="orderCommerceTitle">返品・キャンセル・販売事業者のご案内</h2>' +
          '<p>返品の可否・期限・送料負担、事業者情報などの正式な条件は販売開始前に確定します。' +
          '条件が未確定のため、この画面からお申し込み・決済はできません。</p>' +
          '<p><a href="shop-commerce.html">ドッグフードショップの販売条件（準備中）を確認する</a></p>' +
          '<p><a href="shop-returns.html">返品・キャンセル・不良品・欠品時の対応案（未承認）</a></p>' +
        '</section>' +
      '</div>' +
      '<aside class="order-panel" aria-labelledby="orderTotalTitle">' +
        '<h2 id="orderTotalTitle">お支払い金額</h2>' +
        '<div class="order-summary-row"><span>商品代金（税込）</span><strong id="orderReviewSubtotal"></strong></div>' +
        '<div class="order-summary-row"><span>追加送料</span><strong class="free">0円</strong></div>' +
        '<div class="order-summary-row total"><span>合計（税込・送料込み）</span><strong id="orderReviewTotal"></strong></div>' +
        '<p class="order-data-note">メーカー希望小売価格を税込・送料込みの販売価格として表示しています。</p>' +
        '<p id="orderReviewLimit" class="order-preview-warning" hidden role="alert"></p>' +
        '<label class="order-checked"><input id="orderConfirmChecked" type="checkbox">' +
          '<span>商品・数量・合計金額・追加送料0円と、お取り寄せによる通常4〜7日程度のお届け目安、欠品時のご案内・返金対応を確認しました。正式な返品・キャンセル条件は販売開始前にご案内します。</span></label>' +
        '<button type="button" class="order-submit-test" id="orderConfirmPreview" disabled>' +
          '注文内容を確認する（テスト）</button>' +
        '<p class="order-data-note">このボタンを押しても注文や決済は行われません。' +
          '本番販売開始時にはSquareの決済画面へつながります。</p>' +
        '<p id="orderPreviewConfirmation" class="order-confirmation-message" role="status" hidden>' +
          '注文内容の確認ができました（テスト）。注文・決済はまだ行われていません。</p>' +
      '</aside>' +
    '</div></div>';

  const list = root.querySelector('#orderReviewItems');
  const empty = root.querySelector('#orderReviewEmpty');
  const content = root.querySelector('#orderReviewContent');
  const subtotal = root.querySelector('#orderReviewSubtotal');
  const totalEl = root.querySelector('#orderReviewTotal');
  const warning = root.querySelector('#orderReviewLimit');
  const agreement = root.querySelector('#orderConfirmChecked');
  const button = root.querySelector('#orderConfirmPreview');
  const confirmed = root.querySelector('#orderPreviewConfirmation');
  const byId = new Map(catalog.map(p => [p.id,p]));

  function readCart() {
    try {
      const raw = JSON.parse(sessionStorage.getItem(CART_KEY) || '{}');
      if (!raw || Array.isArray(raw) || typeof raw !== 'object') return [];
      return Object.keys(raw).map(id => {
        const p = byId.get(id);
        const qty = raw[id];
        if (!p || !Number.isInteger(qty) || qty < 1 || qty > 10) return null;
        return {p, qty, unit:Math.round(p.referenceMsrpExTax * 1.1)};
      }).filter(Boolean);
    } catch (_) { return []; }
  }

  function refresh() {
    const rows = readCart();
    const amount = rows.reduce((sum,{qty,unit})=>sum+qty*unit,0);
    const valid = rows.length > 0 && amount <= limit;
    empty.hidden = rows.length !== 0;
    content.hidden = rows.length === 0;
    list.innerHTML = rows.map(({p,qty,unit}) =>
      '<div class="order-line">' +
        '<img src="assets/shop-products/'+encodeURIComponent(p.slug)+'.webp" loading="lazy" alt="" onerror="this.hidden=true">' +
        '<div><strong>'+esc(p.brand+' '+p.name)+'</strong><small>'+esc(p.weight)+' / '+YEN(unit)+' × '+qty+'点</small></div>' +
        '<span class="order-line-price">'+YEN(unit*qty)+'</span></div>'
    ).join('');
    subtotal.textContent = YEN(amount);
    totalEl.textContent = YEN(amount);
    warning.hidden = amount <= limit;
    warning.textContent = amount > limit ? '注文の上限金額を超えています。カートの数量を減らしてください。' : '';
    agreement.checked = false;
    button.disabled = true;
    button.dataset.hasItems = String(valid);
    confirmed.hidden = true;
  }

  root.querySelector('#orderEditCart').addEventListener('click', () => {
    document.getElementById('previewCartOpen').click();
  });
  agreement.addEventListener('change', () => {
    button.disabled = !(agreement.checked && button.dataset.hasItems === 'true');
    confirmed.hidden = true;
  });
  button.addEventListener('click', () => {
    if (button.disabled) return;
    confirmed.hidden = false;
    confirmed.scrollIntoView({block:'nearest',behavior:'smooth'});
  });
  window.addEventListener('bigpaw:shop-cart-updated', refresh);
  window.addEventListener('pageshow', refresh);
  refresh();
})();
