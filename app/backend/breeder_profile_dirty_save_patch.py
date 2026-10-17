"""Hide breeder-profile save until an actual user edit; keep legal confirmation separate."""
from pathlib import Path

page = Path('/app/breeder-profile-edit.html')
source = page.read_text(encoding='utf-8')

def change(old, new, label):
    global source
    assert source.count(old) == 1, (label, source.count(old))
    source = source.replace(old, new, 1)

change(
    '<button id="saveBtn" class="btn btn-main btn-wide" style="margin-top:18px" type="submit">',
    '<button id="saveBtn" class="btn btn-main btn-wide" style="margin-top:18px;display:none" type="submit">',
    'initial_save_hidden'
)

controls = """const profileEditableIds=['kennel','prefecture','registration','profile','visitAddress','visitPhone','visitAccess'];
let profileSavedSnapshot=null;
function profileSnapshot(){
  return JSON.stringify(profileEditableIds.map(id=>document.getElementById(id).value));
}
function profileRenderSave(){
  const saveButton=document.getElementById('saveBtn');
  const changed=profileSavedSnapshot!==null&&profileSnapshot()!==profileSavedSnapshot;
  saveButton.style.display=changed?'':'none';
}
function profileMarkLoaded(){
  profileSavedSnapshot=profileSnapshot();
  profileRenderSave();
}
function profileMarkSaved(submittedSnapshot){
  // Do not discard changes typed while a previous save request was in flight.
  profileSavedSnapshot=submittedSnapshot;
  profileRenderSave();
}
profileEditableIds.forEach(id=>{
  const control=document.getElementById(id);
  control.addEventListener('input',profileRenderSave);
  control.addEventListener('change',profileRenderSave);
});
"""
change("let breederId='';", controls+"let breederId='';", 'define_profile_change_tracking')
change(
    "publicProfileLink.href=breederId?'breeder-detail.html?id='+encodeURIComponent(breederId):'breeders.html'}catch(e){",
    "publicProfileLink.href=breederId?'breeder-detail.html?id='+encodeURIComponent(breederId):'breeders.html';profileMarkLoaded()}catch(e){",
    'snapshot_only_after_profile_load'
)
change(
    "async function save(e){e.preventDefault();",
    "async function save(e){e.preventDefault();if(profileSavedSnapshot===null||profileSnapshot()===profileSavedSnapshot)return;",
    'skip_noop_save'
)
change(
    "clearProfileWarning();try{const b=await BigPawAPI.updateBreederProfile(",
    "clearProfileWarning();const profileSubmittedSnapshot=profileSnapshot();try{const b=await BigPawAPI.updateBreederProfile(",
    'capture_submitted_state'
)
change(
    "saveBtn.innerHTML='✓ 保存しました';saveResetTimer=",
    "profileMarkSaved(profileSubmittedSnapshot);saveBtn.innerHTML='✓ 保存しました';saveResetTimer=",
    'hide_after_success_only'
)
change(
    "saveBtn.textContent='保存する';saveResetTimer=null},2200)",
    "saveBtn.textContent='保存する';profileRenderSave();saveResetTimer=null},2200)",
    'recheck_unsaved_edits_after_timer'
)

page.write_text(source,encoding='utf-8')
print('BREEDER_PROFILE_DIRTY_SAVE_PATCH_OK|initial_hidden|edit_shows|revert_hides|successful_save_hides|failed_save_retains|concurrent_edit_preserved',flush=True)
