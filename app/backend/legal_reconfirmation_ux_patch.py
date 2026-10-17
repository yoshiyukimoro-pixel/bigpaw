"""Avoid prompting breeders to reconfirm an unchanged, already published legal notice.

Keep publication explicit for first-time, incomplete, expired or changed statutory
data, but hide the consent checkbox/submit button for confirmed unchanged records.
No server legal authorization bypass: checkbox is still mandatory on write.
"""
from pathlib import Path

P=Path('/app/breeder-profile-edit.html')
s=P.read_text(encoding='utf-8')

def once(src, old, new, label):
    assert src.count(old)==1,(label,src.count(old))
    return src.replace(old,new,1)

# Keep the controls absent during initial fetch to avoid flashing an unchecked
# public-consent box for breeders with an existing valid confirmation.
s=once(s,
  '<div class="field"><label><input type="checkbox" id="legalPublicConfirm" required> 上記の法定情報を一般公開することを確認しました *</label></div>',
  '<div class="field" id="legalPublicConfirmRow" style="display:none"><label><input type="checkbox" id="legalPublicConfirm" required> 上記の法定情報を一般公開することを確認しました *</label></div>',
  'consent_container')

s=once(s,
  '<button type="submit" id="legalDisplaySave" class="btn btn-main btn-wide">内容を確認して法定表示を公開する</button>',
  '<button type="submit" id="legalDisplaySave" class="btn btn-main btn-wide" style="display:none">変更内容を確認して法定表示を公開する</button>',
  'publish_button_initially_hidden')

old="""    note.textContent=b.confirmed?'✓ 法定表示は一般公開中です。':'法定表示は未公開です。内容を確認し、チェックして公開してください。';
    field('legalDisplayForm').addEventListener('submit',async function(e){"""
new="""    const legalFieldIds=['legalOfficeName','legalOperatorName','legalBusinessType',
      'legalRegistrationDateEdit','legalExpiresOn','legalAnimalManagerEdit'];
    const legalSnapshot=()=>JSON.stringify(legalFieldIds.map(id=>field(id).value.trim()));
    const consent=field('legalPublicConfirm');
    const consentRow=field('legalPublicConfirmRow');
    const publishButton=field('legalDisplaySave');
    const initialStatus=await BigPawAPI.request('/breeder/legal-status').catch(()=>null);
    let published=!!(b.confirmed && initialStatus && initialStatus.complete);
    let savedSnapshot=legalSnapshot();
    const renderLegalConfirmation=()=>{
      const changed=legalSnapshot()!==savedSnapshot;
      const needsConfirmation=!published||changed;
      consentRow.style.display=needsConfirmation?'block':'none';
      publishButton.style.display=needsConfirmation?'block':'none';
      consent.required=needsConfirmation;
      if(!needsConfirmation){
        consent.checked=false;
        note.textContent='✓ 法定表示は公開確認済みです。変更がなければ再確認は不要です。';
      }else if(published){
        note.textContent='法定情報を変更しました。保存・公開する場合だけ、チェックを入れてください。';
      }else{
        note.textContent='法定表示に未確認の内容があります。入力内容を確認し、チェックして公開してください。';
      }
    };
    for(const id of legalFieldIds){
      field(id).addEventListener('input',()=>{
        consent.checked=false;
        renderLegalConfirmation();
      });
      field(id).addEventListener('change',()=>{
        consent.checked=false;
        renderLegalConfirmation();
      });
    }
    // A separate profile save can invalidate the legal address/registration-number
    // confirmation. Refresh from the persisted server status immediately afterward.
    window.refreshLegalReviewAfterProfileSave=async()=>{
      try{
        const [state,live]=await Promise.all([
          BigPawAPI.request('/breeder/legal-status'),
          BigPawAPI.request('/breeder/legal-display')
        ]);
        published=!!(state.complete && live.confirmed);
        field('legalOfficeAddress').textContent=live.officeAddress||'未登録';
        field('legalRegistrationNo').textContent=live.registrationNo||'未登録';
        renderLegalConfirmation();
        await window.refreshBreederLegalAlert?.();
      }catch(error){
        published=false;
        renderLegalConfirmation();
      }
    };
    // Hook successful existing profile saves without coupling to their UI messages.
    // This also catches registration-number and address changes that revoke consent.
    const saveProfileOriginal=BigPawAPI.updateBreederProfile.bind(BigPawAPI);
    BigPawAPI.updateBreederProfile=async(...args)=>{
      const result=await saveProfileOriginal(...args);
      await window.refreshLegalReviewAfterProfileSave?.();
      return result;
    };
    renderLegalConfirmation();
    field('legalDisplayForm').addEventListener('submit',async function(e){"""
s=once(s,old,new,'consent_is_required_only_for_changes')
s=once(s,
   "      e.preventDefault();\n      const btn=field('legalDisplaySave');",
   "      e.preventDefault();\n      if(published && legalSnapshot()===savedSnapshot){\n        note.textContent='✓ 法定表示は公開確認済みです。変更がなければ再確認は不要です。';\n        return;\n      }\n      const btn=field('legalDisplaySave');",
   'prevent_unchanged_enter_submission')
# On successful PATCH, update from the server's saved authoritative state:
# do not use localStorage and do not mark expired/incomplete data complete.
old="""        note.textContent='✓ 法定情報を保存・公開しました。';
        await window.refreshBreederLegalAlert?.();"""
new="""        const nowStatus=await BigPawAPI.request('/breeder/legal-status').catch(()=>null);
        published=!!(nowStatus && nowStatus.complete);
        savedSnapshot=legalSnapshot();
        consent.checked=false;
        renderLegalConfirmation();
        await window.refreshBreederLegalAlert?.();"""
s=once(s,old,new,'clear_checkbox_and_hide_after_success')
P.write_text(s,encoding='utf-8')
print('LEGAL_RECONFIRM_ONLY_ON_CHANGE_OK|confirmed_unchanged_hidden|new_changes_require_consent|after_confirm_auto_hidden|profile_revalidation|existing_alert_preserved',flush=True)
