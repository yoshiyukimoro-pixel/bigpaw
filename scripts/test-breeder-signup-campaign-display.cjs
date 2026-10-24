#!/usr/bin/env node
'use strict';
// Read-only rendering regression: no real API writes, no customer or quota changes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../app');
const js = fs.readFileSync(path.join(root, 'assets/first100-campaign.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'breeder-register.html'), 'utf8');
const flush = async () => { for(let n=0;n<8;n++) await Promise.resolve(); };

async function scenario(name, signup, data, expected, visible=true) {
  const el = {
    hidden: true, dataset: {}, innerHTML: '',
    classList: { add(){} },
    closest: selector => signup && selector==='.breeder-signup-promo' ? {} : null
  };
  const document = {
    querySelectorAll: selector => selector==='[data-bp-first100]' ? [el] : [],
    createElement: () => ({ textContent: '' }),
    head: { appendChild(){} },
    addEventListener(){}
  };
  const fetch = async (url, opts) => {
    assert.equal(url, '/api/campaign/first100');
    assert.equal(opts.cache, 'no-store');
    return { ok: true, json: async () => data };
  };
  vm.runInNewContext(js, { document, fetch, Date, Number, String, Array, Error, console:{warn(){} }});
  await flush();
  assert.equal(el.hidden, !visible, name+' visibility');
  if(visible) assert(el.innerHTML.includes(expected), name+' '+expected);
  if(signup && visible && data.status==='active') {
    assert(el.innerHTML.includes('通常成約手数料5％ → 0％'), name+' free rate');
  }
  console.log('PASS', name);
}

(async () => {
  const active = {status:'active',eligible:true,remaining:100,remainingLabel:'100頭',endsAt:1808500000};
  await scenario('signup 100', true, active, '残り100頭・受付中！');
  await scenario('signup 21', true, {...active,remaining:21,remainingLabel:'21頭'}, '残り21頭・受付中！');
  await scenario('signup 20 privacy', true, {...active,remaining:null,remainingLabel:'残りわずか'}, '残りわずか・受付中！');
  await scenario('signup not eligible', true, {...active,eligible:false}, '', false);
  await scenario('signup sold out', true, {...active,status:'sold_out',eligible:false}, '先着100頭に達したため終了しました');
  await scenario('signup ended', true, {...active,status:'ended',eligible:false}, 'キャンペーン期間は終了しました');
  await scenario('other consumers unchanged', false, active, '<span class="bp-first100-status">100頭</span>');
  for(const id of ['accountStep','verifyStep','applicationStep','registrationProof'])
    assert(html.includes('id="'+id+'"'), 'registration flow preserved: '+id);
  assert(html.includes('body .breeder-signup-promo .bp-first100[data-state="active"] .bp-first100-status'));
  assert(html.includes('border:2px solid #e8a12a'));
  assert(html.includes('background:#fffaf1'));
  console.log('BREEDER_SIGNUP_CAMPAIGN_DISPLAY_OK|dashboard_match|quota_privacy|closed_state|scoped_style|registration_preserved');
})().catch(err=>{console.error(err);process.exitCode=1;});
