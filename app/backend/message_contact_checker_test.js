'use strict';

const assert = require('node:assert/strict');
const { inspectMessage, sendAfterCheck } = require('../assets/message-contact-checker.js');

async function run() {
  assert.deepEqual(inspectMessage('見学の日程を相談させてください。').contactTypes, []);
  assert.equal(inspectMessage('メールは dog@example.jp です').contactTypes.includes('email'), true);
  assert.equal(inspectMessage('電話は090-1234-5678です').contactTypes.includes('phone'), true);
  assert.equal(inspectMessage('LINEで日程相談できます').contactTypes.includes('line'), true);
  assert.equal(inspectMessage('https://example.jp/profile').contactTypes.includes('external_url'), true);
  assert.equal(inspectMessage('住所は〒330-0000です').contactTypes.includes('postal_or_address'), true);
  assert.equal(inspectMessage('埼玉県さいたま市浦和区1-2-3').contactTypes.includes('postal_or_address'), true);
  assert.equal(inspectMessage('@dog44').contactTypes.includes('social_account'), true);
  assert.deepEqual(inspectMessage('10月19日にお迎え予定です').contactTypes, []);
  assert.equal(inspectMessage('LINEビデオで見学しましょう').evasionIntent, false);
  assert.equal(inspectMessage('成約手数料は5%ですか？').evasionIntent, false);
  assert.equal(inspectMessage('サイトを通さず直接購入すれば手数料を払わずに済みます').evasionIntent, true);

  let sent = 0, confirms = 0, alerts = 0;
  const send = async () => { sent++; };
  assert.equal(await sendAfterCheck('通常の問い合わせです', {confirm:()=>{confirms++;return true;},alert:()=>{alerts++;},send}), true);
  assert.equal(sent, 1);
  assert.equal(await sendAfterCheck('連絡先はdog@example.jpです', {confirm:()=>{confirms++;return false;},alert:()=>{alerts++;},send}), false);
  assert.equal(sent, 1);
  assert.equal(await sendAfterCheck('LINEを交換しましょう', {confirm:()=>{confirms++;return true;},alert:()=>{alerts++;},send}), true);
  assert.equal(sent, 2);
  assert.equal(await sendAfterCheck('BIG PAWを通さず購入すれば手数料を払わずに済みます', {confirm:()=>{confirms++;return true;},alert:()=>{alerts++;},send}), false);
  assert.equal(sent, 2);
  assert.equal(confirms, 2);
  assert.equal(alerts, 1);

  const input = { value: '連絡先はdog@example.jpです' };
  let wrappedSends = 0, accepted = false, warned = 0;
  global.document = { getElementById: id => id === 'msg' ? input : null, body: { classList: { contains: () => false } } };
  global.confirm = () => accepted;
  global.alert = () => { warned++; };
  global.sendMsg = async () => { wrappedSends++; };
  require('../assets/message-contact-checker.js').install();
  await global.sendMsg();
  assert.equal(wrappedSends, 0);
  accepted = true;
  await global.sendMsg();
  assert.equal(wrappedSends, 1);
  input.value = 'BIG PAWを通さず購入すれば手数料を払わずに済みます';
  await global.sendMsg();
  assert.equal(wrappedSends, 1);
  assert.equal(warned, 1);
  console.log('MESSAGE_CONTACT_CHECKER_OK|contacts=warn_with_consent|evasion=blocked|normal=unchanged');
}

run().catch(error => { console.error(error); process.exitCode = 1; });
