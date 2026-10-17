"""Give each breeder a legal office name independent of BIG PAW kennel branding.

Previously legal officeName was tied to breeders.kennel_name; editing it would
change a breeder's brand and could change linked puppy records. Keep both apart.
All changes are additive and preserve previously confirmed legal disclosures.
"""
from pathlib import Path

ROOT=Path('/app')
server=ROOT/'backend/server.py'
src=server.read_text(encoding='utf-8')

def replace_once(s,old,new,tag):
    assert s.count(old)==1,(tag,s.count(old))
    return s.replace(old,new,1)

src=replace_once(src,
    '    ensure_column(con,\'breeder_applications\',\'legal_ad_consent\',"INTEGER NOT NULL DEFAULT 0")',
    '    ensure_column(con,\'breeder_applications\',\'legal_ad_consent\',"INTEGER NOT NULL DEFAULT 0")\n'
    '    ensure_column(con,\'breeder_legal_disclosures\',\'office_name\',"TEXT NOT NULL DEFAULT \'\'")',
    'add_separate_office_name_schema')
src=replace_once(src,
    'SELECT b.kennel_name,b.visit_address,b.registration_no,',
    'SELECT b.kennel_name,b.visit_address,b.registration_no,l.office_name,',
    'public_legal_office_sql')
src=replace_once(src,
    "'operatorName':row['operator_name'],'officeName':row['kennel_name'],",
    "'operatorName':row['operator_name'],'officeName':row['office_name'] or row['kennel_name'],",
    'public_legal_office_response')
src=replace_once(src,
    "'officeName':b['kennel_name'],'officeAddress':b['visit_address'],",
    "'officeName':d.get('office_name') or b['kennel_name'],'officeAddress':b['visit_address'],",
    'breeder_legal_office_edit_read')
src=replace_once(src,
    "            operator_name=str(data.get('operatorName','')).strip()",
    "            operator_name=str(data.get('operatorName','')).strip()\n"
    "            office_name=str(data.get('officeName') or b['kennel_name']).strip()",
    'breeder_legal_office_input')
src=replace_once(src,
    "            if not all((operator_name,registration_date,expires_on,manager,business_type,",
    "            if not all((operator_name,office_name,registration_date,expires_on,manager,business_type,",
    'legal_office_required')
src=replace_once(src,
    '''                breeder_id,operator_name,registration_date,expires_on,animal_manager,business_type,confirmed,updated_at)
                VALUES(?,?,?,?,?,?,1,?)
                ON CONFLICT(breeder_id) DO UPDATE SET operator_name=excluded.operator_name,''',
    '''                breeder_id,office_name,operator_name,registration_date,expires_on,animal_manager,business_type,confirmed,updated_at)
                VALUES(?,?,?,?,?,?,?,1,?)
                ON CONFLICT(breeder_id) DO UPDATE SET office_name=excluded.office_name,operator_name=excluded.operator_name,''',
    'legal_office_insert_upsert')
src=replace_once(src,
    "                (b['id'],operator_name,registration_date,expires_on,manager,business_type,now()))",
    "                (b['id'],office_name,operator_name,registration_date,expires_on,manager,business_type,now()))",
    'legal_office_saved_value')
compile(src,str(server),'exec')
server.write_text(src,encoding='utf-8')

page=ROOT/'breeder-profile-edit.html'
h=page.read_text(encoding='utf-8')
h=replace_once(h,
    '<div class="fact"><span>事業所の名称</span><b id="legalOfficeName">確認中</b></div>',
    '<div class="fact"><label for="legalOfficeName">事業所の名称（登録証どおり） *</label>'
    '<input id="legalOfficeName" required placeholder="例：ドックフォーティーフォー">'
    '<small class="muted">ブランド名・犬舎名とは別に設定できます。こちらだけ変更しても子犬情報は変わりません。</small></div>',
    'editable_office_name_form')
h=replace_once(h,
    "field('legalOfficeName').textContent=b.officeName||'未登録';",
    "field('legalOfficeName').value=b.officeName||'';",
    'editable_office_name_initial_value')
h=replace_once(h,
    "          operatorName:field('legalOperatorName').value,",
    "          operatorName:field('legalOperatorName').value,\n"
    "          officeName:field('legalOfficeName').value,",
    'editable_office_name_payload')
page.write_text(h,encoding='utf-8')
print('INDEPENDENT_LEGAL_OFFICE_NAME_PATCH_OK|separate_column=1|brand_preserved=1|editable=1|legal_public_response=1|existing_records_fallback=1',flush=True)
