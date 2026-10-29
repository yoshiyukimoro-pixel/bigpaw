'use strict';
/* Browser-only Square Sandbox UI checks; mocked HTTP and Square URL, NO real payments. */
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');

const SHOP = fs.readFileSync('app/shop.html', 'utf8');
assert(!SHOP.includes('shop-sandbox-checkout.js'), 'Production shop must NOT include Sandbox checkout script');
const PREVIEW = SHOP.replace('</body>', '<script src="shop-sandbox-checkout.js" defer></script>\n</body>');
const CART = fs.readFileSync('app/shop-cart-preview.js', 'utf8');
const CHECKOUT = fs.readFileSync('shop_payments/preview_checkout.js', 'utf8');

async function run() {
  let ready = false;
  let orderState = 'payment_pending';
  const submitted = [];
  const server = http.createServer(async (req, res) => {
    const route = req.url.split('?')[0];
    const json = data => {res.writeHead(200, {'Content-Type':'application/json', 'Cache-Control':'no-store'});res.end(JSON.stringify(data));};
    if (req.method === 'GET' && route === '/shop.html') {
      res.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});res.end(PREVIEW);return;
    }
    if (req.method === 'GET' && route === '/shop-cart-preview.js') {
      res.writeHead(200, {'Content-Type':'text/javascript; charset=utf-8'});res.end(CART);return;
    }
    if (req.method === 'GET' && route === '/shop-sandbox-checkout.js') {
      res.writeHead(200, {'Content-Type':'text/javascript; charset=utf-8'});res.end(CHECKOUT);return;
    }
    if (req.method === 'GET' && route === '/api/shop/sandbox/config') {
      json({sandbox:true,ready,csrf_token:'mock-browser-csrf',real_payments:false,shipping_included:true});return;
    }
    if (req.method === 'GET' && route === '/api/shop/sandbox/order/FOOD12345678901234567890123456789012') {
      json({order_status:orderState});return;
    }
    if (req.method === 'POST' && route === '/api/shop/sandbox/checkout') {
      let body = '';for await (const chunk of req) body += chunk;
      submitted.push(JSON.parse(body));
      json({sandbox:true,checkout_url:'https://sandbox.square.link/u/BIGPAW_TEST_ONLY',
        order_id:'FOOD12345678901234567890123456789012',amount_yen:21450,shipping_yen:0});
      return;
    }
    res.writeHead(404);res.end('');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const root = 'http://127.0.0.1:' + server.address().port;
  try {
    for (const [name, browserType] of [['Chrome', chromium], ['iPhone Safari', webkit]]) {
      const submissionsBefore = submitted.length;
      const browser = await browserType.launch({headless:true});
      try {
        const page = await browser.newPage({viewport:name==='Chrome'?{width:1250,height:850}:{width:390,height:844}});
        const errors = [];page.on('pageerror',err=>errors.push(err.message));
        ready = false;
        await page.goto(root + '/shop.html?item=A02');
        await page.locator('#previewAddToCart').click();
        await page.waitForSelector('#squareSandboxCheckout');
        assert.equal(await page.locator('#squareSandboxCheckout').isDisabled(),true,
          name + ' checkout disabled while Square Sandbox credentials are absent');
        assert.match(await page.locator('#squareSandboxNotice').innerText(), /設定/);
        assert.equal(submitted.length, submissionsBefore, 'must never submit when not configured');

        ready = true;
        await page.reload();
        await page.locator('#previewCartOpen').click();
        await page.waitForFunction(() => !document.querySelector('#squareSandboxCheckout').disabled);
        assert.match(await page.locator('#squareSandboxCheckout').innerText(),/Squareのテスト決済画面/);
        await page.route('https://sandbox.square.link/u/BIGPAW_TEST_ONLY', route =>
          route.fulfill({status:200, contentType:'text/html',
            body:'<!doctype html><html><body><h1>Square Sandbox mock checkout</h1></body></html>'}));
        await page.locator('#squareSandboxCheckout').click();
        await page.waitForURL('https://sandbox.square.link/u/BIGPAW_TEST_ONLY');
        assert.match(await page.locator('h1').innerText(), /Square Sandbox mock/);
        assert(submitted.length > 0, 'checkout API receives selected cart');
        assert.deepEqual(Object.keys(submitted.at(-1)).sort(), ['attempt_id','cart']);
        assert.deepEqual(submitted.at(-1).cart, {A02:1});
        assert.match(submitted.at(-1).attempt_id,
          /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
        // Returning from Square alone must not imply a successful payment.
        orderState = 'payment_pending';
        await page.goto(root + '/shop.html?item=A02');
        await page.locator('#previewCartOpen').click();
        await page.waitForSelector('#squareSandboxStatusButton:visible');
        await page.locator('#squareSandboxStatusButton').click();
        assert.match(await page.locator('#squareSandboxStatusResult').innerText(),
          /確認待ち/,name + ' returning from checkout never assumes a payment');
        orderState = 'paid';
        await page.locator('#squareSandboxStatusButton').click();
        assert.match(await page.locator('#squareSandboxStatusResult').innerText(),
          /テスト決済完了を確認済み/,name + ' verified sandbox payment state');
        assert.deepEqual(errors, [], 'no JavaScript errors');
        console.log('SHOP_SQUARE_UI_OK|' + name + '|sandbox_checkout_only|no_real_payment');
      } finally {
        await browser.close();
      }
    }
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
}
run().catch(error => {console.error(error);process.exit(1);});
