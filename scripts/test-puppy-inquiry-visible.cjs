#!/usr/bin/env node
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const url = 'file://' + path.resolve(__dirname, '../app/puppy-detail.html');
    for (const [label, viewport, position] of [
      ['iphone', {width: 390, height: 844}, 'fixed'],
      ['desktop', {width: 1280, height: 800}, 'static'],
    ]) {
      const page = await browser.newPage({ viewport });
      await page.goto(url + '?id=p_inquiry_test');
      const bar = page.locator('#bigpawPuppyContactShortcut');
      const link = page.locator('#bigpawPuppyContactShortcutLink');
      await link.waitFor({state:'visible', timeout:10000});
      const href = await link.getAttribute('href');
      assert.equal(href, 'inquiry.html?id=p_inquiry_test');
      const css = await bar.evaluate(el => ({
        position: getComputedStyle(el).position,
        bottom: el.getBoundingClientRect().bottom,
        viewport: innerHeight
      }));
      assert.equal(css.position, position, label);
      if (position === 'fixed') {
        assert.ok(Math.abs(css.bottom - css.viewport) < 3, label + ' button must touch bottom of screen');
        assert.ok(await page.locator('#inq').count() === 1, 'original inquiry link kept');
      }
      await link.click();
      await page.waitForURL('**/inquiry.html?id=p_inquiry_test');
      assert.equal(await page.locator('form#inquiryForm').count(), 1, 'inquiry form reachable');
      await page.close();
      console.log('PUPPY_INQUIRY_BROWSER_OK|' + label);
    }
    const noIdPage = await browser.newPage();
    await noIdPage.goto(url);
    assert.equal(await noIdPage.locator('#bigpawPuppyContactShortcut').isVisible(), false);
    await noIdPage.close();
    console.log('PUPPY_INQUIRY_BROWSER_OK|missing_id_hidden');
    // Browser-level regression: operator/breeder 403 must explain the correct account.
    // Intercept the API method locally: never submit a real inquiry or send mail.
    const inquiryPage = await browser.newPage({viewport:{width:390,height:844}});
    const messages = [];
    inquiryPage.on('dialog', async dialog => { messages.push(dialog.message()); await dialog.accept(); });
    await inquiryPage.goto('file://' + path.resolve(__dirname, '../app/inquiry.html') + '?id=p_inquiry_test');
    await inquiryPage.evaluate(() => {
      p = {id:'p_inquiry_test'};
      puppyReady = true;
      BigPawBridge.addInquiry = async () => { throw Object.assign(new Error('forbidden'), {status:403,data:{error:'forbidden'}}); };
      document.querySelector('#message').value = 'テスト';
    });
    await inquiryPage.evaluate(() => sendInquiry({preventDefault(){}}));
    assert.equal(messages.length, 1);
    assert.match(messages[0], /一般会員（購入希望者）専用/);
    assert.match(messages[0], /運営・ブリーダー用アカウント/);
    assert.doesNotMatch(messages[0], /時間をおいて/);
    await inquiryPage.close();
    console.log('PUPPY_INQUIRY_BROWSER_OK|buyer_only_error_clear');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
