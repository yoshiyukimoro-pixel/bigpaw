"""Regression: legal confirmation appears only when actually needed.

Protect server-side consent check, persisted status, existing breeder blue theme,
both forms, and legal alerts. No new paid services or data changes.
"""
from pathlib import Path
root=Path('/app')
h=(root/'breeder-profile-edit.html').read_text(encoding='utf-8')
s=(root/'backend/server.py').read_text(encoding='utf-8')
admin=(root/'admin.html').read_text(encoding='utf-8')
assert h.count('id="legalDisplayForm"')==1,'legal form missing'
assert h.count('id="legalPublicConfirmRow"')==1,'consent row missing'
assert '<div class="field" id="legalPublicConfirmRow" style="display:none">' in h,'first render flashes unchecked consent'
assert 'id="legalDisplaySave" class="btn btn-main btn-wide" style="display:none"' in h,'first render flashes submit'
assert 'const initialStatus=await BigPawAPI.request(\'/breeder/legal-status\')' in h,'persisted server check missing'
assert 'let published=!!(b.confirmed && initialStatus && initialStatus.complete);' in h,'consent wrongly skipped for legacy/incomplete'
assert 'const changed=legalSnapshot()!==savedSnapshot;' in h,'unchanged detection missing'
assert 'const needsConfirmation=!published||changed;' in h,'confirmation visibility wrong'
assert "consentRow.style.display=needsConfirmation?'block':'none';" in h
assert "publishButton.style.display=needsConfirmation?'block':'none';" in h
assert 'consent.required=needsConfirmation;' in h,'required consent on changed missing'
assert 'consent.checked=false;' in h,'checkbox must not stay checked after editing or publishing'
assert "savedSnapshot=legalSnapshot();" in h
assert "await window.refreshLegalReviewAfterProfileSave?.();" in h,'profile changes must recheck persisted consent'
assert "window.refreshLegalReviewAfterProfileSave=async()=>{" in h
assert "field('legalOfficeAddress').textContent=live.officeAddress||'未登録';" in h,'office address must refresh'
assert "field('legalRegistrationNo').textContent=live.registrationNo||'未登録';" in h,'registration number must refresh'
assert "published=!!(state.complete && live.confirmed);" in h,'stale confirmation risk'
assert "await window.refreshBreederLegalAlert?.();" in h,'existing auto-dismiss alert missing'
assert "if not data.get('confirmPublicDisclosure')" in s,'API consent gate must stay'
assert "if path=='/api/breeder/legal-status':" in s,'server status unchanged'
assert "if(state.complete){panel.style.display='none'" in admin,'breeder dashboard must auto-dismiss'
assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in h,'2-column legal editor lost'
assert '#eef6ff' in h,'breeder blue styling lost'
assert 'legalOfficeName' in h and 'officeName:field(' in h,'legal name independent of brand'
assert 'api.openai.com' not in h,'paid AI introduced'
print('LEGAL_RECONFIRM_UX_GATE_OK|unchecked_hidden_by_default|confirmed_unchanged_no_repeat|incomplete_still_required|changes_reenable|original_consent_server_enforced|profile_rechecks|breeder_blue_preserved|dashboard_alerts_preserved|no_paid_ai',flush=True)
