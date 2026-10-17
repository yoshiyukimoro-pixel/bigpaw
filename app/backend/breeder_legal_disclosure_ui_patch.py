"""Render approved breeders' legal advertisement information only after confirmation."""
from pathlib import Path

ROOT=Path('/app')
def once(src,old,new,label):
    assert src.count(old)==1,(label,src.count(old))
    return src.replace(old,new,1)

# New applicants add just two required fields. All other legal values, including
# address and business registration number, are already entered in the form.
p=ROOT/'breeder-register.html'
h=p.read_text(encoding='utf-8')
h=once(h,'犬舎名（運営審査用・非公開） *','犬舎名（法定表示として詳細ページに公開） *','signup_kennel_label')
h=once(h,'本人確認・審査のため運営のみが使用します。一般ユーザーには公開されません。',
       '一覧には犬舎名を表示しませんが、法律で必要なブリーダー詳細の法定表示欄には掲載します。','signup_kennel_explanation')
h=once(h,'第一種動物取扱業 登録番号（非公開） *','第一種動物取扱業 登録番号（法定表示で公開） *','signup_registration_label')
h=once(h,'審査・登録確認用です。一般公開ページには表示しません。',
       '登録番号は法定表示として詳細ページに公開されます。','signup_registration_explanation')
h=once(h,'<label>登録有効期限 *</label><input id="expiresOn" type="date" required>',
       '<label>登録有効期限 *</label><input id="expiresOn" type="date" required>','signup_expiry_field_exists')
h=once(h,'<label>登録有効期限 *</label><input id="expiresOn" type="date" required></div></div>',
       '<label>登録有効期限 *</label><input id="expiresOn" type="date" required></div><div class="field"><label>登録年月日 *</label><input id="legalRegistrationDate" type="date" required></div><div class="field"><label>動物取扱責任者の氏名 *</label><input id="legalAnimalManager" required autocomplete="name"></div></div>','signup_extra_fields')
h=once(h,'<div class="field"><label>公開プロフィール</label>',
       '<div class="field"><label><input type="checkbox" id="legalAdConsent" required> 登録事業所の法定情報の一般公開を確認しました *</label><small class="muted">第一種動物取扱業の広告に必要な氏名・犬舎名・登録事業所住所・種別・登録番号・登録年月日・有効期限・動物取扱責任者名は、承認後のブリーダー詳細ページなどで公開します。電話番号・メール・アクセス案内は公開しません。見学日時が確定したお客様には登録済み住所と当日の連絡先を自動案内します。</small></div><div class="field"><label>公開プロフィール</label>','signup_disclosure_consent')
h=once(h,'expiresOn:byId(\'expiresOn\').value,profile:',
       "expiresOn:byId('expiresOn').value,legalRegistrationDate:byId('legalRegistrationDate').value,legalAnimalManager:byId('legalAnimalManager').value,legalAdConsent:byId('legalAdConsent').checked,profile:",
       'signup_legal_api')
p.write_text(h,encoding='utf-8')

p=ROOT/'breeder-profile-edit.html'
h=p.read_text(encoding='utf-8')
panel='''<section class="section" style="max-width:850px;margin:12px auto 40px"><form class="card pad" id="legalDisplayForm">
<h2>第一種動物取扱業の法定表示</h2>
<p class="muted">法律上必要な項目は、確認後に一般公開されます。子犬一覧の地域表示は引き続き「都道府県＋市」までです。詳しい登録事業所住所はブリーダー詳細の法定表示欄に掲載します。</p>
<div class="notice">法定表示のために住所を再入力する必要はありません。上の「見学場所の住所」を登録事業所の所在地として使用します。電話番号・駐車場情報は公開されません。</div>
<div class="fact-grid"><div class="fact"><span>事業所の名称</span><b id="legalOfficeName">確認中</b></div><div class="fact"><span>登録事業所の所在地</span><b id="legalOfficeAddress">確認中</b></div><div class="fact"><span>登録番号</span><b id="legalRegistrationNo">確認中</b></div></div>
<div class="form-grid" style="margin-top:16px">
<div class="field"><label>事業者の氏名・法人名 *</label><input id="legalOperatorName" required></div>
<div class="field"><label>第一種動物取扱業の種別 *</label><input id="legalBusinessType" value="販売" required></div>
<div class="field"><label>登録年月日 *</label><input id="legalRegistrationDateEdit" type="date" required></div>
<div class="field"><label>有効期間の末日 *</label><input id="legalExpiresOn" type="date" required></div>
<div class="field"><label>動物取扱責任者の氏名 *</label><input id="legalAnimalManagerEdit" required></div></div>
<div class="field"><label><input type="checkbox" id="legalPublicConfirm" required> 上記の法定情報を一般公開することを確認しました *</label></div>
<div id="legalDisplayStatus" class="notice" style="margin:12px 0">表示情報を読み込み中です。</div>
<button type="submit" id="legalDisplaySave" class="btn btn-main btn-wide">内容を確認して法定表示を公開する</button>
</form></section>'''
h=once(h,'</form></section></main>','</form></section>'+panel+'</main>','profile_legal_panel')
script='''<script>
(async function loadBreederLegal(){
  const field=id=>document.getElementById(id);
  const note=field('legalDisplayStatus');
  try{
    const b=await BigPawAPI.request('/breeder/legal-display');
    field('legalOfficeName').textContent=b.officeName||'未登録';
    field('legalOfficeAddress').textContent=b.officeAddress||'未登録';
    field('legalRegistrationNo').textContent=b.registrationNo||'未登録';
    field('legalOperatorName').value=b.operatorName||'';
    field('legalBusinessType').value=b.businessType||'販売';
    field('legalRegistrationDateEdit').value=b.registrationDate||'';
    field('legalExpiresOn').value=b.expiresOn||'';
    field('legalAnimalManagerEdit').value=b.animalManager||'';
    note.textContent=b.confirmed?'✓ 法定表示は一般公開中です。':'法定表示は未公開です。内容を確認し、チェックして公開してください。';
    field('legalDisplayForm').addEventListener('submit',async function(e){
      e.preventDefault();
      const btn=field('legalDisplaySave');
      btn.disabled=true;
      note.textContent='法定情報を確認して保存しています…';
      try{
        await BigPawAPI.request('/breeder/legal-display',{method:'PATCH',body:{
          operatorName:field('legalOperatorName').value,
          businessType:field('legalBusinessType').value,
          registrationDate:field('legalRegistrationDateEdit').value,
          expiresOn:field('legalExpiresOn').value,
          animalManager:field('legalAnimalManagerEdit').value,
          confirmPublicDisclosure:field('legalPublicConfirm').checked
        }});
        note.textContent='✓ 法定情報を保存・公開しました。';
      }catch(err){note.textContent='法定情報を保存できませんでした。入力内容をご確認ください。';}
      finally{btn.disabled=false;}
    });
  }catch(e){note.textContent='ログインしてから法定情報を確認してください。';}
})();
</script>'''
h=once(h,'</body></html>',script+'</body></html>','profile_legal_script')
p.write_text(h,encoding='utf-8')

# Render exact eight statutory items in the breeder's detail card.
labels=(('operatorName','第一種動物取扱業者の氏名・名称'),('officeName','事業所の名称'),
        ('officeAddress','事業所の所在地'),('businessType','第一種動物取扱業の種別'),
        ('registrationNo','登録番号'),('registrationDate','登録年月日'),
        ('expiresOn','有効期間の末日'),('animalManager','動物取扱責任者の氏名'))
p=ROOT/'breeder-detail.html'
h=p.read_text(encoding='utf-8')
h=once(h,'</section></main>',
       '<section class="section" style="margin-top:34px"><div class="card pad"><h2>第一種動物取扱業の法定表示</h2><div id="breederLegalDetails" class="fact-grid">登録内容を確認中です。</div><small class="muted">法律で必要な事業者情報を表示しています。見学調整・お問い合わせはBIG PAW内でお願いします。</small></div></section></section></main>','detail_legal_section_at_bottom')
js='''<script>
(async function renderBreederLegal(){
 const holder=document.getElementById('breederLegalDetails');
 const breederId=new URLSearchParams(location.search).get('id');
 if(!breederId){holder.textContent='ブリーダーを選択してください。';return;}
 try{
  const data=await BigPawAPI.request('/breeders/'+encodeURIComponent(breederId)+'/legal');
  const labels=LEGAL_LABELS;
  holder.innerHTML=labels.map(item=>'<div class="fact"><span>'+BigPaw.esc(item[1])+'</span><b>'+BigPaw.esc(data[item[0]]||'—')+'</b></div>').join('');
 }catch(e){holder.textContent='法定表示情報の確認が必要です。';}
})();
</script>'''
lookup="const LEGAL_LABELS="+__import__('json').dumps([list(x) for x in labels],ensure_ascii=False)+";"
js=js.replace('const labels=LEGAL_LABELS;',lookup+'\n  const labels=LEGAL_LABELS;')
h=once(h,'</body></html>',js+'</body></html>','detail_legal_script')
p.write_text(h,encoding='utf-8')

# Individual puppy listings also show the corresponding legal advertisement.
p=ROOT/'puppy-detail.html'
h=p.read_text(encoding='utf-8')
h=once(h,'<div class="notice" style="margin-top:14px">見学・対面確認を経て契約に進む流れを想定しています。</div>',
       '<div class="card pad" style="margin-top:14px"><h3>第一種動物取扱業の法定表示</h3><div id="puppyLegalDetails">登録内容を確認中です。</div></div><div class="notice" style="margin-top:14px">見学・対面確認を経て契約に進む流れを想定しています。</div>','puppy_legal_section')
function='''async function renderPuppyLegal(breederId){
 const holder=document.getElementById('puppyLegalDetails');
 if(!holder)return;
 if(!breederId){holder.textContent='登録情報を確認中です。';return;}
 try{
  const data=await BigPawAPI.request('/breeders/'+encodeURIComponent(breederId)+'/legal');
  const labels=LEGAL_LABELS;
  holder.innerHTML=labels.map(item=>'<div class="fact" style="margin:8px 0"><span>'+BigPaw.esc(item[1])+'</span><b>'+BigPaw.esc(data[item[0]]||'—')+'</b></div>').join('');
 }catch(e){holder.textContent='法定表示情報の確認が必要です。';}
}
'''
function=lookup+'\n'+function
h=once(h,'async function load(){try{p=await BigPawBridge.puppy(id);if(!p)throw new Error(\'not found\');',
       function+'async function load(){try{p=await BigPawBridge.puppy(id);if(!p)throw new Error(\'not found\');void renderPuppyLegal(p.breederId);',
       'puppy_legal_fetch')
p.write_text(h,encoding='utf-8')

# A legal display is required and distinct from visit-contact sharing.
p=ROOT/'breeders.html'
h=p.read_text(encoding='utf-8')
h=once(h,'公開ページでは犬舎名や直接連絡先を表示せず、問い合わせはBIG PAW内で行います。',
       '一覧では地域を市まで表示します。法令上必要な事業者情報はブリーダー詳細ページに掲載し、お問い合わせはBIG PAW内で行います。','breeder_list_legal_notice')
p.write_text(h,encoding='utf-8')

print('BREEDER_LEGAL_DISCLOSURE_UI_OK|signup=two_fields_and_consent|breeder_profile=no_duplicate_address|public_breeder_eight_fields|public_puppy_eight_fields|buyer_inquiry=unchanged',flush=True)
