"""Build safety gate for city-only location display and automatic visit guidance.

Runs in the isolated/test build *after* all existing build patches and gates.
No customer data and no outgoing email are accessed.
"""
from pathlib import Path
import ast
import re

ROOT=Path('/app')
server=(ROOT/'backend/server.py').read_text(encoding='utf-8')
tree=ast.parse(server)
fn={node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
names=('safe_public_prefecture','city_level_public_location')
assert all(n in fn for n in names),'MISSING_CITY_HELPER'
code=compile(ast.Module(body=[fn[n] for n in names],type_ignores=[]),'<safe_city>', 'exec')
env={'re':re}
exec(code,env)
city=env['city_level_public_location']
pref=env['safe_public_prefecture']

positive=[
 ('埼玉県','埼玉県さいたま市西区宝来123-4','埼玉県さいたま市'),
 ('埼玉県','埼玉県秩父市大宮123-4','埼玉県秩父市'),
 ('東京都','東京都八王子市南大沢1-1','東京都八王子市'),
 ('大阪府','大阪府大阪市北区梅田1-2-3','大阪府大阪市'),
 ('北海道','北海道札幌市中央区大通西1','北海道札幌市'),
 ('愛知県','名古屋市中村区名駅1-1','愛知県名古屋市'),
 ('埼玉県','〒331-0000 埼玉県さいたま市西区宝来1','埼玉県さいたま市'),
 ('千葉県','千葉県市川市南八幡1','千葉県市川市'),
 ('三重県','三重県四日市市羽津1','三重県四日市市'),
]
negative=[
 ('埼玉県','埼玉県秩父郡小鹿野町123','埼玉県'),
 ('埼玉県','埼玉県さいたま市西区','埼玉県さいたま市'),
 ('埼玉県','埼玉県秩父市秩父町','埼玉県秩父市'),
 ('東京都','東京都新宿区西新宿1-1','東京都'),
 ('埼玉県','東京都八王子市南大沢1','埼玉県'),
 ('埼玉県','埼玉県さいたま市西区宝来1-2-3 090-1234-5678','埼玉県さいたま市'),
 ('埼玉県','', '埼玉県'),
 ('その他','さいたま市西区',''),
]
for p,a,want in positive+negative:
    got=city(p,a)
    assert got==want,('CITY_ONLY_FAIL',p,a,got,want)
assert pref('埼玉県さいたま市西区')=='埼玉県','SAFE_PREFECTURE_PREFIX'
# Exercise the real public serializer, not just a source-code presence check.
# A JSON response must not contain ANY private visit contact field or its value.
safe_serializer=fn['public_breeder_json']
sandbox=dict(env)
sandbox['sanitize_public_profile']=lambda t,*args: t
exec(compile(ast.Module(body=[safe_serializer],type_ignores=[]),'<public_serializer>','exec'),sandbox)
private_row={'id':'b_test','kennel_name':'PRIVATE DOG44','prefecture':'埼玉県',
             'visit_address':'埼玉県さいたま市西区飯田123-45',
             'visit_phone':'090-1111-2222','visit_access':'駐車場住所の機密情報',
             'registration_no':'PRIVATE-123','user_id':'u_private','profile':'大切に育てています。'}
public_data=sandbox['public_breeder_json'](private_row)
assert public_data['public_area']=='埼玉県さいたま市','PUBLIC_CITY_SERIALIZER'
for private_key in ('visit_address','visit_phone','visit_access','registration_no','user_id'):
    assert private_key not in public_data,('PUBLIC_PRIVATE_KEY_LEAK',private_key)
assert all(secret not in str(public_data) for secret in ('西区','飯田123','090-1111','PRIVATE DOG44','駐車場住所の機密情報')),'PUBLIC_PRIVATE_VALUE_LEAK'

assert all('区' not in city(p,a) and '丁目' not in city(p,a) and '郡' not in city(p,a) and '町' not in city(p,a) for p,a,_ in positive[:7]),'NO_DISTRICT_LEAK'

# Scan actual final, built-in-place files, not the patch source.
for name in ('breeders.html','breeder-detail.html','breeder-register.html','breeder-profile-edit.html','inquiry.html','messages.html'):
    assert (ROOT/name).exists(),('PAGE_MISSING',name)
list_html=(ROOT/'breeders.html').read_text(encoding='utf-8')
detail=(ROOT/'breeder-detail.html').read_text(encoding='utf-8')
messages=(ROOT/'messages.html').read_text(encoding='utf-8')
inquiry=(ROOT/'inquiry.html').read_text(encoding='utf-8')
assert "public_area||x.prefecture" in list_html,'BREEDER_CITY_SEARCH_MISSING'
assert "b.public_area||b.prefecture" in detail,'DETAIL_CITY_MISSING'
assert "getElementById('name').textContent" in detail,'DETAIL_LOADING_COLLISION_UNFIXED'
assert 'id="visitInfoAuto"' in messages,'AUTO_NOTICE_MISSING'
assert "me?.role!=='buyer'" in messages,'AUTO_NOTICE_NOT_BUYER_ONLY'
assert "v.status!=='confirmed'" in messages,'AUTO_NOTICE_AFTER_CONFIRMATION'
assert '詳細住所・当日連絡先を自動案内' in inquiry,'INQUIRY_NOTICE_MISSING'
assert "AS public_visit_address" in server,'PUPPY_CITY_QUERY_MISSING'
assert "d['public_area']=public_area" in server,'BREEDER_CITY_API_MISSING'
assert "d['area']=area" in server,'PUPPY_CITY_API_MISSING'
assert "'visit_address','visit_phone','visit_access'" in server,'PRIVATE_FIELDS_NOT_HIDDEN'
assert 'visitContact' in server,'VISIT_CONTACT_RETURN_LOST'
assert "private_visit_mail" in server,'VISIT_AUTO_EMAIL_LOST'
assert "visit_status=='confirmed'" in server,'VISIT_CONFIRMATION_RULE_LOST'
assert "if selected!==id" not in messages,'INVALID_JS_GUARD'  # JS must use strict comparison.
assert 'if(selected!==id)return;' in messages,'MESSAGE_RACE_GUARD_MISSING'
compile(server,str(ROOT/'backend/server.py'),'exec')
print('PUBLIC_CITY_AUTO_GUIDANCE_GATE_OK|city_only=9+8|district_leak=blocked|no_manual_entry|buyer_notice=preconfirm_only|private_fields=excluded|confirmed_visit_mail=preserved',flush=True)
