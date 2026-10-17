"""Require the registered office name separately from the kennel brand at signup.

The other seven legal advertising particulars already have fields and server
validation. This adds the missing eighth field, keeps it distinct from
kennel branding, and propagates the approved legal office identity.
"""
from pathlib import Path

ROOT=Path('/app')
SERVER=ROOT/'backend/server.py'

def once(s,old,new,label):
    assert s.count(old)==1,(label,s.count(old))
    return s.replace(old,new,1)

s=SERVER.read_text(encoding='utf-8')
s=once(s,
   "    ensure_column(con,'breeder_legal_disclosures','office_name',\"TEXT NOT NULL DEFAULT ''\")",
   "    ensure_column(con,'breeder_legal_disclosures','office_name',\"TEXT NOT NULL DEFAULT ''\")\n"
   "    ensure_column(con,'breeder_applications','legal_office_name',\"TEXT NOT NULL DEFAULT ''\")",
   'registered_office_app_schema')
s=once(s,
   "            legal_reg_date=str(body.get('legalRegistrationDate','')).strip()",
   "            legal_office_name=str(body.get('legalOfficeName','')).strip()\n"
   "            legal_reg_date=str(body.get('legalRegistrationDate','')).strip()",
   'office_required_input')
s=once(s,
   "            if not re.fullmatch(r'\\\\d{4}-\\\\d{2}-\\\\d{2}',legal_reg_date) or not legal_manager or not body.get('legalAdConsent'):",
   "            if not legal_office_name or len(legal_office_name)>160 or not re.fullmatch(r'\\\\d{4}-\\\\d{2}-\\\\d{2}',legal_reg_date) or not legal_manager or not body.get('legalAdConsent'):",
   'registered_office_backend_required')
s=once(s,
   "            con.execute('UPDATE breeder_applications SET legal_registration_date=?,legal_animal_manager=?,legal_ad_consent=1 WHERE id=?',\n"
   "                (legal_reg_date,legal_manager,aid))",
   "            con.execute('UPDATE breeder_applications SET legal_office_name=?,legal_registration_date=?,legal_animal_manager=?,legal_ad_consent=1 WHERE id=?',\n"
   "                (legal_office_name,legal_reg_date,legal_manager,aid))",
   'registered_office_persist')
# A pending legacy application without legal details must not be approved. The
# user can submit the missing information with the new application form.
anchor="            con.execute('UPDATE breeder_applications SET status=?,review_note=?,updated_at=? WHERE id=?',(status,note,now(),a['id']))"
replacement="""            if status=='approved':
                mandatory=(a['legal_office_name'],a['representative'],a['visit_address'],
                           a['registration_no'],a['legal_registration_date'],
                           a['expires_on'],a['legal_animal_manager'],a['legal_ad_consent'])
                if not all(mandatory):
                    con.close()
                    return self.send_json({'error':'incomplete_legal_disclosure',
                        'message':'第一種動物取扱業の法定表示情報が不足しています。申請者に再申請を依頼してください。'},409)
            con.execute('UPDATE breeder_applications SET status=?,review_note=?,updated_at=? WHERE id=?',(status,note,now(),a['id']))"""
s=once(s,anchor,replacement,'operator_preapproval_gate')
s=once(s,
   "                if bb and a['legal_ad_consent'] and a['legal_registration_date'] and a['legal_animal_manager'] and a['expires_on'] and a['visit_address'] and a['registration_no']:",
   "                if bb and a['legal_ad_consent'] and a['legal_registration_date'] and a['legal_animal_manager'] and a['expires_on'] and a['visit_address'] and a['registration_no'] and a['legal_office_name']:",
   'approval_require_registered_office')
s=once(s,
    """                        (breeder_id,operator_name,registration_date,expires_on,animal_manager,business_type,confirmed,updated_at)
                        VALUES(?,?,?,?,?,'販売',1,?)''',
                        (bb['id'],a['representative'],a['legal_registration_date'],a['expires_on'],a['legal_animal_manager'],now()))""",
    """                        (breeder_id,office_name,operator_name,registration_date,expires_on,animal_manager,business_type,confirmed,updated_at)
                        VALUES(?,?,?,?,?,?,'販売',1,?)''',
                        (bb['id'],a['legal_office_name'],a['representative'],a['legal_registration_date'],a['expires_on'],a['legal_animal_manager'],now()))""",
    'approved_office_legal_record')
compile(s,str(SERVER),'exec')
SERVER.write_text(s,encoding='utf-8')

p=ROOT/'breeder-register.html'
h=p.read_text(encoding='utf-8')
h=once(h,'犬舎名（法定表示として詳細ページに公開） *',
         '犬舎名・ブランド名 *','signup_brand_label')
h=once(h,'一覧には犬舎名を表示しませんが、法律で必要なブリーダー詳細の法定表示欄には掲載します。',
         'BIG PAW内で使用する犬舎名です。登録証の正式な事業所名が異なる場合は、次の項目に入力してください。','signup_brand_explanation')
h=once(h,
    '<div class="field"><label>代表者名 *</label>',
    '<div class="field"><label>登録証の事業所の名称（法定表示） *</label>'
    '<input id="legalOfficeNameSignup" required maxlength="160" autocomplete="organization"'
    ' placeholder="例：ドックフォーティーフォー">'
    '<small class="muted">第一種動物取扱業の登録証に記載された正式名称を入力してください。'
    '「犬舎名・ブランド名」と違っていても登録できます。審査後は法定表示として公開します。</small></div>'
    '<div class="field"><label>代表者名 *</label>',
    'signup_office_field')
h=once(h,
    "legalRegistrationDate:byId('legalRegistrationDate').value,legalAnimalManager:",
    "legalOfficeName:byId('legalOfficeNameSignup').value,legalRegistrationDate:byId('legalRegistrationDate').value,legalAnimalManager:",
    'signup_office_payload')
p.write_text(h,encoding='utf-8')
print('REGISTERED_OFFICE_SIGNUP_REQUIRED_OK|office=required|legal_dates=required|manager=required|consent=required|approval_gate=required|brand=separate',flush=True)
