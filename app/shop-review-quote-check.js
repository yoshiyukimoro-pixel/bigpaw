/* Future-only client for the read-only Square-free seller price quote.
 * It is deliberately NOT wired to the preview purchase button.  The server
 * route also returns 404 until the proprietor's entire launch gate is met.
 * No credentials, address, payment link or customer data are stored here.
 */
'use strict';
(function (global) {
  const DIGEST = /^[a-f0-9]{64}$/;
  const SKU = /^[A-Z][0-9]{2}$/;
  const MAX_YEN = 2000000;
  const MAX_ITEMS = 35;
  const whole = n => Number.isSafeInteger(n);

  function snapshot(rows, displayedAmountYen) {
    if (!Array.isArray(rows) || rows.length < 1 || rows.length > MAX_ITEMS) {
      throw Error('invalid_cart');
    }
    const cart = {};
    const seen = new Set();
    let amount = 0;
    const clean = [];
    for (const r of rows) {
      if (!r || typeof r !== 'object' || !SKU.test(r.sku) ||
          seen.has(r.sku) || !whole(r.quantity) || r.quantity < 1 ||
          r.quantity > 10 || !whole(r.unitYen) || r.unitYen < 1 ||
          !whole(r.lineYen) || r.lineYen !== r.unitYen * r.quantity) {
        throw Error('invalid_cart');
      }
      seen.add(r.sku);
      amount += r.lineYen;
      cart[r.sku] = r.quantity;
      clean.push({sku:r.sku, quantity:r.quantity,
                  unitYen:r.unitYen, lineYen:r.lineYen});
    }
    if (!whole(amount) || amount > MAX_YEN ||
        !whole(displayedAmountYen) || displayedAmountYen !== amount) {
      throw Error('display_amount_mismatch');
    }
    clean.sort((a,b) => a.sku.localeCompare(b.sku));
    return {cart, rows:clean, amount};
  }

  function compare(snap, quote, approvedTermsSha256) {
    if (!quote || typeof quote !== 'object' || Array.isArray(quote) ||
        quote.server_verified !== true || quote.payment_link_created !== false ||
        quote.currency !== 'JPY' || quote.terms_sha256 !== approvedTermsSha256 ||
        quote.shipping_yen !== 0 || quote.subtotal_yen !== snap.amount ||
        quote.amount_yen !== snap.amount ||
        !Array.isArray(quote.line_items) ||
        quote.line_items.length !== snap.rows.length) {
      throw Error('server_quote_mismatch');
    }
    const remote = new Map();
    for (const r of quote.line_items) {
      if (!r || !SKU.test(r.sku) || remote.has(r.sku) ||
          typeof r.name !== 'string' || !r.name.trim() ||
          typeof r.size !== 'string' || !r.size.trim() ||
          !whole(r.quantity) || !whole(r.unit_yen) ||
          !whole(r.line_yen) || r.line_yen !== r.quantity * r.unit_yen) {
        throw Error('server_quote_mismatch');
      }
      remote.set(r.sku, r);
    }
    for (const r of snap.rows) {
      const v = remote.get(r.sku);
      if (!v || v.quantity !== r.quantity ||
          v.unit_yen !== r.unitYen || v.line_yen !== r.lineYen) {
        throw Error('server_quote_mismatch');
      }
    }
    return Object.freeze({
      verified:true, amountYen:snap.amount, shippingYen:0,
      termsSha256:approvedTermsSha256,
      // The caller must recheck the live cart and displayed total after await.
      cartFingerprint:JSON.stringify(snap.rows.map(r=>[r.sku,r.quantity,r.unitYen]))
    });
  }

  async function verify({rows, displayedAmountYen, approvedTermsSha256,
                         fetchImpl=global.fetch.bind(global)} = {}) {
    const snap = snapshot(rows, displayedAmountYen);
    // Terms must originate from the exact owner-approved text displayed to
    // the buyer; blindly adopting a digest supplied by the API is forbidden.
    if (!DIGEST.test(approvedTermsSha256) || typeof fetchImpl !== 'function') {
      throw Error('seller_terms_not_approved');
    }
    const opts = {credentials:'same-origin', mode:'same-origin',
                  cache:'no-store', redirect:'error'};
    const configResp = await fetchImpl('/api/shop/checkout/config', {
      ...opts, method:'GET', headers:{Accept:'application/json'}
    });
    if (!configResp || configResp.status !== 200) {
      throw Error('checkout_not_available');
    }
    const config = await configResp.json();
    if (!config || config.ready !== true ||
        config.shipping_included !== true ||
        config.approved_terms_sha256 !== approvedTermsSha256 ||
        typeof config.csrf_token !== 'string' ||
        !DIGEST.test(config.csrf_token)) {
      throw Error('seller_terms_not_approved');
    }
    const quoteResp = await fetchImpl('/api/shop/checkout/quote', {
      ...opts, method:'POST',
      headers:{'Content-Type':'application/json',
               Accept:'application/json', 'X-Shop-CSRF':config.csrf_token},
      body:JSON.stringify({cart:snap.cart,terms_sha256:approvedTermsSha256})
    });
    if (!quoteResp || quoteResp.status !== 200) {
      throw Error('server_quote_unavailable');
    }
    return compare(snap,await quoteResp.json(),approvedTermsSha256);
  }
  Object.defineProperty(global,'BigPawShopQuote',{
    value:Object.freeze({snapshot,compare,verify}),
    configurable:false,writable:false
  });
})(window);
