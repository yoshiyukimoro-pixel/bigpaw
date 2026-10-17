from pathlib import Path
page=Path('/app/breeder-profile-edit.html')
s=page.read_text(encoding='utf-8')
def change(a,b):
    global s
    assert s.count(a)==1, ('legal_ux_anchor',s.count(a),a[:50])
    s=s.replace(a,b,1)

change('<div class="field"><label><input type="checkbox" id="legalPublicConfirm" required>',
       '<div class="field" id="legalConsentRow" style="display:none"><label><input type="checkbox" id="legalPublicConfirm" required>')
change('<button type="submit" id="legalDisplaySave" class="btn btn-main btn-wide">',
       '<button type="submit" id="legalDisplaySave" class="btn btn-main btn-wide" style="display:none">')
change("  const note=field('legalDisplayStatus');\n  try{", """  const note=field('legalDisplayStatus');
  const tracked=['legalOfficeName','legalOperatorName','legalBusinessType','legalRegistrationDateEdit','legalExpiresOn','legalAnimalManagerEdit'];
  const snapshot=()=>JSON.stringify(tracked.map(id=>field(id).value.trim()));
  let baseline=null,complete=false;
  function renderLegalActions(){
    const changed=baseline!==null&&snapshot()!==baseline;
    const needed=!complete||changed;
    field('legalConsentRow').style.display=needed?'':'none';
    field('legalDisplaySave').style.display=needed?'':'none';
    field('legalPublicConfirm').required=needed;
    if(!needed)field('legalPublicConfirm').checked=false;
    note.textContent=changed?'法定情報を変更しました。チェックして公開してください。'
       :complete?'✓ 公開確認済みです。変更がなければ再確認は不要です。'
       :'法定表示に不足・未確認の情報があります。確認して公開してください。';
  }
  async function refreshLegalActions(){
    try{
      const status=await BigPawAPI.request('/breeder/legal-status');
      complete=status.complete===true;
    }catch(e){complete=false}
    field('legalPublicConfirm').checked=false;
    renderLegalActions();
  }
  window.refreshLegalUx=async function(){
    field('legalOfficeAddress').textContent=field('visitAddress').value.trim()||'未登録';
    field('legalRegistrationNo').textContent=field('registration').value.trim()||'未登録';
    await refreshLegalActions();
    await window.refreshBreederLegalAlert?.();
  };
  try{""")
change("    note.textContent=b.confirmed?'✓ 法定表示は一般公開中です。':'法定表示は未公開です。内容を確認し、チェックして公開してください。';",
       """    baseline=snapshot();
    tracked.forEach(id=>field(id).addEventListener('input',()=>{
      field('legalPublicConfirm').checked=false;
      renderLegalActions();
    }));
    await refreshLegalActions();""")
change("        note.textContent='✓ 法定情報を保存・公開しました。';\n        await window.refreshBreederLegalAlert?.();",
       """        baseline=snapshot();
        await refreshLegalActions();
        await window.refreshBreederLegalAlert?.();""")
change("      try{\n        await BigPawAPI.request('/breeder/legal-display'",
       "      const submittedFields=snapshot();\n      try{\n        await BigPawAPI.request('/breeder/legal-display'")
change("        baseline=snapshot();\n        await refreshLegalActions();",
       "        baseline=submittedFields;\n        await refreshLegalActions();")
change("publicProfileLink.href=breederId?'breeder-detail.html?id='+encodeURIComponent(breederId):'breeders.html';msg.innerHTML='<div class=\"notice\">✓ 保存しました。",
       "publicProfileLink.href=breederId?'breeder-detail.html?id='+encodeURIComponent(breederId):'breeders.html';void window.refreshLegalUx?.();msg.innerHTML='<div class=\"notice\">✓ 保存しました。")
page.write_text(s,encoding='utf-8')
print('BREEDER_LEGAL_REPEAT_CONFIRM_FIX_OK|unchanged_hidden|edits_reconfirm|saved_auto_hide|profile_rechecks',flush=True)
