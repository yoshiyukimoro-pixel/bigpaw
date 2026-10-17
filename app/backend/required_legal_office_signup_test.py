"""Regression: new breeder application must include all eight statutory items."""
from pathlib import Path
root=Path('/app')
s=(root/'backend/server.py').read_text(encoding='utf-8')
h=(root/'breeder-register.html').read_text(encoding='utf-8')
assert "ensure_column(con,'breeder_applications','legal_office_name'" in s,'NEW_OFFICE_COLUMN_MISSING'
assert "legal_office_name=str(body.get('legalOfficeName','')).strip()" in s,'BACKEND_INPUT_MISSING'
assert "or not legal_office_name or" in s,'OFFICE_NAME_REQUIRED'
assert "UPDATE breeder_applications SET legal_office_name=?" in s,'OFFICE_NOT_PERSISTED'
assert "if not all(mandatory):" in s and "'incomplete_legal_disclosure'" in s,'OPERATOR_APPROVAL_GATE_MISSING'
assert "a['legal_office_name']" in s,'APPROVED_OFFICE_FROM_REGISTRATION_MISSING'
for t in ('id="legalOfficeNameSignup" required','id="legalRegistrationDate" type="date" required',
          'id="legalAnimalManager" required','id="legalAdConsent" required','id="registrationNo" required',
          'id="visitAddress"','id="expiresOn" type="date" required','id="registrationProof"'):
    assert t in h, ('FORM_MISSING',t)
assert "legalOfficeName:byId('legalOfficeNameSignup').value" in h,'FORM_NOT_SUBMITTED'
assert '犬舎名・ブランド名' in h and '登録証の事業所の名称' in h,'BRAND_AND_OFFICE_NOT_SEPARATE'
print('REQUIRED_LEGAL_OFFICE_SIGNUP_GATE_OK|all_eight_fields|office_separate|incomplete_denied|operator_gate|no_repeat_entry',flush=True)
