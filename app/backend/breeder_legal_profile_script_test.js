'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const path = process.argv[2] || '/app/breeder-profile-edit.html';
const html = fs.readFileSync(path, 'utf8');
const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)]
  .filter(([, attrs]) => !/\bsrc\s*=/.test(attrs))
  .map(([, , body]) => body);
if (!scripts.length) throw new Error('No inline scripts found in breeder profile page');
for (const [index, source] of scripts.entries()) {
  new vm.Script(source, { filename: `${path}#inline-${index + 1}` });
}
const legalScript = scripts.find(source => source.includes('loadBreederLegal'));
if (!legalScript) throw new Error('Legal profile loader is missing');
for (const token of [
  "const legalUrl='/breeder/legal-display'+(selectedBreederId?'?breederId='+encodeURIComponent(selectedBreederId):'')",
  "field('legalOperatorName').value=b.operatorName||''",
  "field('legalRegistrationDateEdit').value=b.registrationDate||''",
  "field('legalExpiresOn').value=b.expiresOn||''",
  "field('legalAnimalManagerEdit').value=b.animalManager||''",
  "note.textContent=b.confirmed?",
]) {
  if (!legalScript.includes(token)) throw new Error(`Operator legal loader is missing expected behavior: ${token}`);
}
const ids = [
  'legalDisplayStatus', 'legalConsentRow', 'legalDisplaySave', 'legalPublicConfirm',
  'legalOfficeName', 'legalOfficeAddress', 'legalRegistrationNo', 'legalOperatorName',
  'legalBusinessType', 'legalRegistrationDateEdit', 'legalExpiresOn',
  'legalAnimalManagerEdit', 'legalDisplayForm',
];
const elements = Object.fromEntries(ids.map(id => [id, {
  id, value: '', textContent: '', readOnly: false, required: false, checked: false,
  style: {}, listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; },
}]));
const requests = [];
const context = {
  selectedBreederId: 'breeder-test-123',
  document: { getElementById(id) { return elements[id]; } },
  window: { refreshBreederLegalAlert: async () => {} },
  BigPawAPI: { async request(path) {
    requests.push(path);
    return {
      officeName: 'テスト事業所', officeAddress: '東京都テスト区', registrationNo: '第123号',
      operatorName: 'テスト事業者', businessType: '販売', registrationDate: '2024-04-01',
      expiresOn: '2029-03-31', animalManager: 'テスト責任者', confirmed: true,
    };
  } },
  encodeURIComponent, console,
};
vm.runInNewContext(legalScript, context, { filename: `${path}#operator-legal-loader` });
new Promise(resolve => setImmediate(resolve)).then(() => {
  if (requests[0] !== '/breeder/legal-display?breederId=breeder-test-123') {
    throw new Error(`Operator GET did not use the selected breeder scope: ${requests[0]}`);
  }
  for (const [id, expected] of Object.entries({
    legalOfficeName: 'テスト事業所', legalOfficeAddress: '東京都テスト区',
    legalRegistrationNo: '第123号', legalOperatorName: 'テスト事業者',
    legalBusinessType: '販売', legalRegistrationDateEdit: '2024-04-01',
    legalExpiresOn: '2029-03-31', legalAnimalManagerEdit: 'テスト責任者',
  })) {
    const actual = id === 'legalOfficeAddress' || id === 'legalRegistrationNo'
      ? elements[id].textContent : elements[id].value;
    if (actual !== expected) throw new Error(`${id} was not populated: ${actual}`);
  }
  if (!elements.legalOperatorName.readOnly || elements.legalConsentRow.style.display !== 'none'
      || elements.legalDisplaySave.style.display !== 'none') {
    throw new Error('Operator legal preview unexpectedly allows edits or publication');
  }
  console.log(`BREEDER_LEGAL_PROFILE_SCRIPT_OK|inline=${scripts.length}|operator_scoped_read=1|fields_populated=8|read_only=1|syntax=valid`);
}).catch(error => { console.error(error); process.exitCode = 1; });
