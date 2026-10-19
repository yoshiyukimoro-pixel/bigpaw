(function (root) {
  'use strict';

  const CONTACT_RULES = [
    ['email', /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i],
    ['phone', /(?:\+81[\s().-]*0?|0)(?:70|80|90)[\s().-]*\d{4}[\s().-]*\d{4}(?!\d)|\b0\d{1,4}[-ー−]\d{1,4}[-ー−]\d{3,4}\b/],
    ['external_url', /(?:https?:\/\/|www\.)\S+/i],
    ['line', /(?:\bLINE\b|ライン|line\.me|lin\.ee)(?:\s*(?:ID|id|：|:|は|で|から|交換))?/i],
    ['social_account', /(?:Instagram|インスタ(?:グラム)?|TikTok|Facebook|Twitter|X(?:の)?アカウント)\s*(?:ID|id|：|:|@|は|で)?|(?:^|\s)@[A-Z0-9_.-]{3,}/i],
    ['postal_or_address', /(?:〒\s*\d{3}[-ー−]?\d{4}|\b\d{3}[-ー−]\d{4}\b|住所|自宅住所|犬舎住所|(?:北海道|東京都|(?:京都|大阪)府|[一-龠]{2,3}県).{0,24}(?:市|区|町|村).{0,20}\d+[-ー−]\d+[-ー−]?\d*)/]
  ];
  const EVASION_RULES = [
    /(?:BIG\s*PAW|サイト|運営)を通さず.{0,16}(?:買|購入|取引|契約)/i,
    /(?:手数料|成約報告).{0,14}(?:回避|逃れ|払わずに済|支払わずに済|報告しないで|避けるため)/,
    /(?:報告せず|申請せず).{0,14}(?:取引|購入|契約|お迎え|成約)/,
    /(?:サイト外|直接).{0,12}(?:取引|契約|購入).{0,16}(?:手数料|成約報告).{0,8}(?:避け|不要|かからな|払わな)/i
  ];

  function normalize(value) {
    return String(value || '').normalize('NFKC').replace(/[\u200B-\u200D\uFEFF]/g, '');
  }

  function inspectMessage(value) {
    const text = normalize(value);
    return {
      contactTypes: CONTACT_RULES.filter(([, rule]) => rule.test(text)).map(([type]) => type),
      evasionIntent: EVASION_RULES.some(rule => rule.test(text))
    };
  }

  async function sendAfterCheck(value, actions) {
    const result = inspectMessage(value);
    if (result.evasionIntent) {
      actions.alert('成約報告や手数料を避ける目的のサイト外取引を促す文面は送信できません。内容を修正してください。');
      return false;
    }
    if (result.contactTypes.length) {
      const approved = actions.confirm('連絡先情報が含まれている可能性があります。LINE・電話・メール等は双方の合意のうえで共有できますが、BIG PAWで知り合った取引の成約報告は必要です。共有相手と内容を確認して送信しますか？');
      if (!approved) return false;
    }
    await actions.send();
    return true;
  }

  function install() {
    if (!root.document || !root.document.getElementById('msg') || typeof root.sendMsg !== 'function' || root.__bigpawMessageContactCheckerInstalled) return;
    const input = root.document.getElementById('msg');
    const originalSend = root.sendMsg;
    root.sendMsg = async function () {
      if (root.document.body.classList.contains('operator-view')) return originalSend();
      return sendAfterCheck(input.value, {
        alert: message => root.alert(message),
        confirm: message => root.confirm(message),
        send: () => originalSend()
      });
    };
    root.__bigpawMessageContactCheckerInstalled = true;
  }

  const api = { inspectMessage, sendAfterCheck, install };
  root.BigPawMessageContactChecker = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  install();
})(typeof window !== 'undefined' ? window : globalThis);
