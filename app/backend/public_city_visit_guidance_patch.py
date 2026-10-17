"""Public location: prefecture + municipality ending 市 only.
No ward, town, street, postcode or direct contact appears in public APIs.
Existing private visit details are reused automatically, without breeder re-entry.
This build patch is deliberately applied after all existing release patches.
"""
from pathlib import Path

ROOT=Path('/app')
SERVER=ROOT/'backend/server.py'

def replace_once(src, old, new, label):
    assert src.count(old)==1, (label, src.count(old))
    return src.replace(old,new,1)

s=SERVER.read_text(encoding='utf-8')

# Existing prefecture values are editable. Even if they inadvertently contain
# an address, public APIs expose ONLY the prefecture name.
anchor="def public_breeder_json(row):\n"
helper=r'''def safe_public_prefecture(value):
    raw=str(value or '').strip()
    m=re.match(r'^(北海道|東京都|京都府|大阪府|[一-龯]{2,4}県)',raw)
    return m.group(1) if m else ''

def city_level_public_location(prefecture, private_visit_address):
    """Fail closed: never expose a ward, town, district, house number or postcode."""
    pref=safe_public_prefecture(prefecture)
    if not pref:
        return ''
    address=str(private_visit_address or '').strip()
    address=re.sub(r'^\s*〒?\s*[0-9０-９]{3}[-ー－]?[0-9０-９]{4}\s*','',address).strip()
    # If the submitted address starts with a different prefecture, do not infer.
    other=re.match(r'^(北海道|東京都|京都府|大阪府|[一-龯]{2,4}県)',address)
    if other and other.group(1)!=pref:
        return pref
    if address.startswith(pref):
        address=address[len(pref):].lstrip()
    # Anchor at the beginning: NEVER look for a later 市 inside a street name.
    # Municipalities ending 町/村 and Tokyo wards deliberately fall back to pref.
    m=re.match(r'^([一-龯ぁ-ゖァ-ヴー]{1,18}?市)',address)
    if not m:
        return pref
    city=m.group(1)
    # 四日市市 contains 市 twice; do not truncate the municipal name.
    if city=='四日市' and address.startswith('四日市市'):
        city='四日市市'
    if '郡' in city or '区' in city or len(city)>15:
        return pref
    return pref+city

'''
s=replace_once(s,anchor,helper+anchor,'insert_city_helper')

# Sensitive visit address is used only to compute a trusted city-level label.
# Never include the underlying address field in public output.
s=replace_once(s,
    "    pref=(d.get('prefecture') or '').strip()\n    private_kennel=(d.get('kennel_name') or '').strip()",
    "    pref=safe_public_prefecture(d.get('prefecture'))\n    public_area=city_level_public_location(pref,d.get('visit_address'))\n    d['prefecture']=pref\n    d['public_area']=public_area\n    private_kennel=(d.get('kennel_name') or '').strip()",
    'public_breeder_location')
s=replace_once(s,
    "    d['kennel_name']=(pref+'のBIGPAW認定ブリーダー') if pref else 'BIGPAW認定ブリーダー'",
    "    d['kennel_name']=(public_area+'のBIGPAW認定ブリーダー') if public_area else 'BIGPAW認定ブリーダー'",
    'public_breeder_label')

old_puppy="""    area=(d.get('area') or '').strip()
    d['breeder']=(area+'のBIGPAW認定ブリーダー') if area else 'BIGPAW認定ブリーダー'
    return d"""
new_puppy="""    fields=r.keys() if hasattr(r,'keys') else ()
    if 'public_prefecture' in fields:
        area=city_level_public_location(r['public_prefecture'],r['public_visit_address'])
    else:
        area=safe_public_prefecture(d.get('area'))
    d['area']=area
    d['breeder']=(area+'のBIGPAW認定ブリーダー') if area else 'BIGPAW認定ブリーダー'
    return d"""
s=replace_once(s,old_puppy,new_puppy,'public_puppy_location')

# Reuse the existing LEFT JOIN to fetch private location server side, but only
# return the redacted city field via public_puppy_json.
s=replace_once(s,
    'sql="SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status=',
    'sql="SELECT p.*,b.prefecture AS public_prefecture,b.visit_address AS public_visit_address FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status=',
    'public_puppies_join')
old_detail_query='con.execute("SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='
new_detail_query='con.execute("SELECT p.*,b.prefecture AS public_prefecture,b.visit_address AS public_visit_address FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='
assert s.count(old_detail_query)==2, ('public_puppy_detail_and_photo_join',s.count(old_detail_query))
s=s.replace(old_detail_query,new_detail_query,2)
# Nested public puppy cards use the same redacted municipality. Keep original
# photo/gallery SQL unchanged.
s=replace_once(s,
    "out['puppies']=[public_puppy_json(x) for x in puppies]",
    "out['puppies']=[dict(public_puppy_json(x),area=out['public_area'],breeder=out['kennel_name']) for x in puppies]",
    'breeder_nested_puppy_area')
SERVER.write_text(s,encoding='utf-8')

# All public pages refer to the same redacted public_area; never show district.
p=ROOT/'breeders.html'
h=p.read_text(encoding='utf-8')
h=replace_once(h,'placeholder="都道府県・紹介文"','placeholder="都道府県・市・紹介文"','breeders_placeholder')
h=replace_once(h,"${x.prefecture||''}", "${x.public_area||x.prefecture||''}",'breeders_filter')
p.write_text(h,encoding='utf-8')

p=ROOT/'breeder-detail.html'
h=p.read_text(encoding='utf-8')
h=replace_once(h,'<span>所在地（都道府県）</span>','<span>所在地（市まで公開）</span>','breeder_detail_location_label')
h=replace_once(h,"area.textContent=b.prefecture||'';pref.textContent=b.prefecture||'-';",
                 "area.textContent=b.public_area||b.prefecture||'';pref.textContent=b.public_area||b.prefecture||'-';",'breeder_detail_city')
assert h.count("name.textContent=")==3, ('breeder_detail_name_cases',h.count("name.textContent="))
h=h.replace("name.textContent=","document.getElementById('name').textContent=")
h=h.replace("profile.textContent=","document.getElementById('profile').textContent=")
h=replace_once(h,'犬舎名・住所・電話番号・SNS等の直接連絡先は公開していません。お問い合わせ・見学調整はBIG PAW内で行います。',
  '見学場所は市まで表示しています。詳細住所・当日の連絡先は、見学日時の確定後にBIG PAWが自動でご案内します。お問い合わせ・見学調整はBIG PAW内で行います。','detail_notice')
p.write_text(h,encoding='utf-8')

# Form wording: nothing extra for breeders to enter; registered private address
# is the sole source of the public city label.
p=ROOT/'breeder-register.html'
h=p.read_text(encoding='utf-8')
h=replace_once(h,'一般公開される所在地は都道府県までです。',
    '一般公開される所在地は都道府県＋市までです。見学先住所から市名を自動判定し、区・町名・番地・当日の連絡先は公開しません。','signup_public_city_explanation')
h=replace_once(h,'一般公開はされません。対面見学の日程をブリーダーが確定した購入希望者にだけ、見学場所と当日の連絡先を案内します。',
    '入力した住所から市までを自動表示します。区・町名以下の詳細住所と当日の連絡先は公開されず、対面見学日時を確定した購入希望者にだけ自動で案内します。','signup_private_explanation')
p.write_text(h,encoding='utf-8')

p=ROOT/'breeder-profile-edit.html'
h=p.read_text(encoding='utf-8')
h=replace_once(h,'<label>都道府県（一般公開）</label>',
  '<label>都道府県（一般公開）</label>','profile_prefecture_label_marker')
# Note above replacement is identity, deliberate marker assertion.
h=replace_once(h,'一般公開される所在地は都道府県までです。',
  '一般公開される所在地は都道府県＋市までです。市名は登録済みの見学先住所から自動判定し、区・町名以下は公開されません。','profile_location_explanation')
h=replace_once(h,'所在地は都道府県まで一般公開され、見学先情報は対面見学確定後の購入希望者にだけ表示されます。',
  '所在地は都道府県＋市まで公開され、詳細住所・連絡先は対面見学確定後の購入希望者にだけ自動案内されます。','profile_saved_notice')
p.write_text(h,encoding='utf-8')

# A non-message system notice, not a fabricated message sent by the breeder.
# It stays visible while the inquiry is not yet confirmed.
p=ROOT/'messages.html'
h=p.read_text(encoding='utf-8')
h=replace_once(h,'<div class="chat" id="chat"></div>',
  '<div id="visitInfoAuto" class="notice" style="display:none;margin-bottom:12px" role="note">🐾 見学場所はブリーダー詳細ページで市まで確認できます。詳細住所・当日の連絡先は、見学日時が確定しましたらBIG PAWから自動でご案内いたします。</div><div class="chat" id="chat"></div>',
  'message_system_notice')
h=replace_once(h,'async function openThread(id){selected=id;',
  """async function refreshAutoVisitNotice(id,q){
    const el=document.getElementById('visitInfoAuto');
    el.style.display='none';
    if(!id||me?.role!=='buyer'||q?.status==='見学確定'||q?.status==='成約済み')return;
    let v=null;
    try{v=await BigPawAPI.visit(id)}catch(e){return}
    if(selected!==id)return;
    if(!v||v.status!=='confirmed')el.style.display='block';
}
async function openThread(id){selected=id;""",
  'message_auto_notice_controller')
h=replace_once(h,'chatStatus.textContent=q.status;setStepActions(true,id);',
  'chatStatus.textContent=q.status;setStepActions(true,id);refreshAutoVisitNotice(id,q);',
  'message_auto_notice_call')
p.write_text(h,encoding='utf-8')

p=ROOT/'inquiry.html'
h=p.read_text(encoding='utf-8')
h=replace_once(h,'確定後に見学場所・当日連絡先をご案内',
  '確定後に詳細住所・当日連絡先を自動案内','inquiry_autoguidance')
p.write_text(h,encoding='utf-8')

print('PUBLIC_CITY_AND_AUTO_VISIT_NOTICE_OK|location=prefecture_plus_city|district=blocked|city=from_existing_visit_address|buyer_guidance=automatic|private_contact=confirmed_only',flush=True)
