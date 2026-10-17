"""CI/release gate: free comparison tool and approval controls are server-enforced."""
from pathlib import Path
ROOT=Path('/app')
html=(ROOT/'operator-breeders.html').read_text(encoding='utf-8')
srv=(ROOT/'backend/server.py').read_text(encoding='utf-8')
signup=(ROOT/'breeder-register.html').read_text(encoding='utf-8')
assert 'id="documentReview"' in html and 'id="reviewProofImage"' in html
assert '登録証と申請を照合' in html and '8項目確認して承認' in html
assert 'openDocumentReview' in html and 'approveManually' in html
assert 'image/' in html and 'URL.revokeObjectURL' in html
assert 'id="reviewFieldList"' in html and 'reviewApproveButton' in html
assert 'proofViewed:true' in html and 'legalDocumentChecklist' in html
assert 'class="review-grid"' in html and 'grid-template-columns:1fr' in html
assert 'const LEGAL_KEYS=[' in html
for key in ('operatorName','officeName','officeAddress','businessType','registrationNo','registrationDate','expiresOn','animalManager'):
    assert "'"+key+"'" in html and "'"+key+"'" in srv,('FIELD_MISSING',key)
assert "body.get('proofViewed') is not True" in srv,'SERVER_PROOF_GATE'
assert "'document_check_required'" in srv,'SERVER_CHECKLIST_GATE'
assert "proof_row['mime_type']" in srv,'REGISTRATION_IMAGE_MIME_FIELD'
assert "'breeder_registration_proof_manually_checked'" in srv,'AUDIT_EVENT'
assert '登録証と申請を照合' in html and "review('\${a.id}','approved')" not in html, 'DIRECT_APPROVAL_BYPASS'
assert 'id="legalOfficeNameSignup" required' in signup,'REQUIRED_OFFICE_FIELD_MISSING'
assert "legalOfficeName:byId('legalOfficeNameSignup').value" in signup,'REQUIRED_OFFICE_NOT_SUBMITTED'
# Human comparison contains no chargeable API or external model call.
for word in ('api.openai.com','/v1/responses','/v1/chat/completions','ocr.space','gemini'):
    assert word not in html,('EXTERNAL_AI_CALLED',word)
print('FREE_MANUAL_PROOF_GATE_OK|eight_fields|proof_image|operator_only|server_approval_guard|document_audit|no_paid_api|office_signup_required',flush=True)
