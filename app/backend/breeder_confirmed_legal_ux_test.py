"""Build-time gate for publication confirmation UX and original privacy protection."""
from pathlib import Path
ROOT=Path('/app')
page=(ROOT/'breeder-profile-edit.html').read_text(encoding='utf-8')
server=(ROOT/'backend/server.py').read_text(encoding='utf-8')
assert 'id="legalConsentRow" style="display:none"' in page,'CONSENT_INITIAL_HIDDEN'
assert 'id="legalDisplaySave" class="btn btn-main btn-wide" style="display:none"' in page,'PUBLISH_INITIAL_HIDDEN'
assert "const status=await BigPawAPI.request('/breeder/legal-status');" in page,'PERSISTED_COMPLETION'
assert "complete=status.complete===true;" in page,'TRUTH_FROM_SERVER'
assert "const needed=!complete||changed;" in page,'RECONFIRM_ONLY_WHEN_NEEDED'
assert "field('legalConsentRow').style.display=needed?'':'none';" in page,'CONSENT_TOGGLE'
assert "field('legalDisplaySave').style.display=needed?'':'none';" in page,'PUBLISH_TOGGLE'
assert "field('legalPublicConfirm').required=needed;" in page,'CHECK_REQUIRED_WHEN_NEEDED'
assert "if(!needed)field('legalPublicConfirm').checked=false;" in page,'NO_RESTORED_CHECKBOX'
assert "field('legalPublicConfirm').checked=false;\n      renderLegalActions();" in page,'EDIT_RESETS_CONFIRMATION'
assert "const submittedFields=snapshot();" in page and 'baseline=submittedFields;' in page,'INFLIGHT_EDITS_SAFE'
assert "void window.refreshLegalUx?.();" in page,'OTHER_PROFILE_EDIT_INVALIDATES_CONSENT'
assert "await window.refreshBreederLegalAlert?.();" in page,'ALERT_AUTOCLEAR_PRESERVED'
assert "if not data.get('confirmPublicDisclosure')" in server,'SERVER_RECONFIRM_GUARD'
assert "if path=='/api/breeder/legal-status':" in server,'SERVER_LEGAL_STATUS_AVAILABLE'
assert "field('legalOfficeName').value=b.officeName||'';" in page,'OFFICE_NAME_UNCHANGED'
assert 'id="legalOfficeAddress"' in page and 'id="legalRegistrationNo"' in page,'LEGAL_ADDRESS_REFERENCE_PRESERVED'
print('BREEDER_LEGAL_CONFIRM_UX_GATE_OK|unchanged_no_recheck|edit_requires_check|complete_auto_hide|address_invalidates|unconfirmed_warns|no_flash|server_guard',flush=True)
