/* Square-hosted Sandbox testing panel automation.
   Inputs from private runner temp file. Never log Square link or order ID.
   Nothing is paid in production; testing panel simulates test card payment. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');

const input=process.env.SHOP_PANEL_JSON;
if(!input)throw Error('Missing isolated test session');
const state=JSON.parse(fs.readFileSync(input,'utf8'));
const link=new URL(state.link_url);
assert.equal(link.protocol,'https:');
assert.equal(link.hostname,'sandbox.square.link');
assert.equal(state.amount_yen,21450);
assert.equal(state.shipping_yen,0);

async function clickNamed(page,label){
  const button=page.getByRole('button',{name:label,exact:true});
  if(await button.count()){
    // The final "Test Payment" button can share its label with a stepper.
    // Prefer the last visible action, not the earlier progress indicator.
    const count=await button.count();
    console.log('SQUARE_SANDBOX_PANEL_CONTROL_'+label.replace(/ /g,'_')+'_COUNT='+count);
    await button.last().click();
    return;
  }
  const link=page.getByRole('link',{name:label,exact:true});
  if(await link.count()){await link.first().click();return;}
  const input=page.locator('input[type=submit]');
  const matches=input.filter({hasText:label});
  if(await matches.count()){await matches.first().click();return;}
  // Square may use an accessible non-button control.
  const candidate=page.getByText(label,{exact:true});
  if(await candidate.count()){await candidate.last().click();return;}
  throw Error('Expected Sandbox panel control unavailable: '+label);
}

(async()=>{
  let stage='browser-launch';
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:900}});
    page.on('dialog',dialog=>dialog.accept().catch(()=>{}));
    stage='navigate';
    await page.goto(link.href,{waitUntil:'domcontentloaded',timeout:45000});
    await page.waitForLoadState('networkidle',{timeout:10000}).catch(()=>{});
    stage='verify-host';
    const host=new URL(page.url()).hostname;
    assert(['sandbox.square.link','connect.squareupsandbox.com'].includes(host),
      'Unexpected Square panel host');
    stage='overview';
    const bodyText=await page.locator('body').innerText();
    assert(/Sandbox Testing Panel/i.test(bodyText),'Not the official Sandbox testing panel');
    assert(/Overview/i.test(bodyText),'Sandbox overview unavailable');
    stage='click-next';
    await clickNamed(page,'Next');
    stage='test-payment-visible';
    await page.getByText('Test Payment',{exact:true}).first().waitFor({timeout:15000});
    stage='click-test-payment';
    await clickNamed(page,'Test Payment');
    stage='wait-for-panel-update';
    // Hosted testing panel may vary text/DOM by rollout. Only the fresh
    // Square Orders + Payments API checks in the NEXT step may claim paid.
    await page.waitForTimeout(3500);
    const finalText=await page.locator('body').innerText({timeout:15000});
    const uiSuccess=/Your test payment was successful/i.test(finalText);
    const uiComplete=/Checkout Complete/i.test(finalText);
    console.log('SQUARE_SANDBOX_HOSTED_PANEL_ATTEMPTED: Next and Test Payment '
      +'controls clicked; success_text='+uiSuccess+'; completion_step='+uiComplete
      +'; awaiting independent Square Orders/Payments API verification.');
  }catch(err){
    // Error messages from URLs may contain checkout identifiers; never print
    // error objects. Print only a fixed error code.
    console.error('SQUARE_SANDBOX_HOSTED_PANEL_FAILED stage='+stage+'; no identifiers printed');
    process.exitCode=1;
  }finally{await browser.close();}
})();
