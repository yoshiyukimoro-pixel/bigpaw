"""Build gate: a breeder must not repeatedly press Save without changes."""
from pathlib import Path
page=Path('/app/breeder-profile-edit.html').read_text(encoding='utf-8')
server=Path('/app/backend/server.py').read_text(encoding='utf-8')
checks={
 'INITIAL_BUTTON_HIDDEN': 'id="saveBtn" class="btn btn-main btn-wide" style="margin-top:18px;display:none"',
 'ALL_PROFILE_FIELDS_TRACKED': "const profileEditableIds=['kennel','prefecture','registration','profile','visitAddress','visitPhone','visitAccess'];",
 'LOAD_BASELINE': "profileMarkLoaded()}catch(e){",
 'DIRTY_COMPARED_TO_SAVED': "profileSnapshot()!==profileSavedSnapshot;",
 'UNCHANGED_BUTTON_HIDDEN': "saveButton.style.display=changed?'':'none';",
 'INPUT_WATCH': "control.addEventListener('input',profileRenderSave);",
 'DATE_AND_AUTOFILL_WATCH': "control.addEventListener('change',profileRenderSave);",
 'NOOP_SAVE_BLOCKED': "if(profileSavedSnapshot===null||profileSnapshot()===profileSavedSnapshot)return;",
 'SUBMITTED_SNAPSHOT': "const profileSubmittedSnapshot=profileSnapshot();try{const b=await BigPawAPI.updateBreederProfile(",
 'SUCCESS_UPDATES_BASELINE': "profileMarkSaved(profileSubmittedSnapshot);saveBtn.innerHTML='✓ 保存しました';",
 'EDIT_DURING_SAVE_SAFE': "profileSavedSnapshot=submittedSnapshot;",
 'TIMER_RECALCULATES': "saveBtn.textContent='保存する';profileRenderSave();saveResetTimer=null},2200)",
 'PROFILE_VALIDATION_PRESERVED': "public_profile_privacy_issue" ,
 'LEGAL_CONSENT_PRESERVED': "id=\"legalPublicConfirm\" required",
 'LEGAL_STATUS_PRESERVED': "await refreshLegalActions();",
 'LEGAL_ALERT_PRESERVED': "window.refreshBreederLegalAlert"
}
for name,needle in checks.items():
    content=server if name=='PROFILE_VALIDATION_PRESERVED' else page
    assert needle in content,name
assert page.count('id="saveBtn"')==1, 'ONE_SAVE_BUTTON'
assert 'async function save(e){e.preventDefault();' in page,'SAVE_HANDLER_PRESERVED'
assert 'saveBtn.disabled=false;saveBtn.textContent=' in page,'SAVE_REENABLED'
print('BREEDER_PROFILE_DIRTY_SAVE_GATE_OK|untouched_hidden|edit_show|revert_hide|success_hide|failure_retry|legal_independent',flush=True)
