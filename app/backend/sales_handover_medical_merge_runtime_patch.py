#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'backend' / 'server.py'
SETTINGS = ROOT / 'breeder-sales-handover.html'
PUPPY_RENDERER = ROOT / 'assets' / 'puppy-sales-handover-public.js'
BREEDER_RENDERER = ROOT / 'assets' / 'sales-handover-public.js'
PUPPY_DETAIL = ROOT / 'puppy-detail.html'
BREEDER_DETAIL = ROOT / 'breeder-detail.html'
STABLE_GALLERY = ROOT / 'assets' / 'puppy-detail-stable-gallery.js'

# This patch only reorganizes the sales/handover medical-cost presentation.
# Protect the known-good Safari gallery asset byte-for-byte.
gallery_before = STABLE_GALLERY.read_bytes()

# 1) Enforce BIG PAW policy server-side: microchip cost is always included.
s = SERVER.read_text(encoding='utf-8')
old_bool_loop = """    for key in ('vaccineIncluded','sameDayVisit','healthExamIncluded','microchipIncluded'):\n        out[key]=_sales_nullable_bool(body.get(key))\n"""
new_bool_loop = """    for key in ('vaccineIncluded','sameDayVisit','healthExamIncluded'):\n        out[key]=_sales_nullable_bool(body.get(key))\n    out['microchipIncluded']=True\n"""
if old_bool_loop in s:
    assert s.count(old_bool_loop) == 1, ('medical_bool_loop_count', s.count(old_bool_loop))
    s = s.replace(old_bool_loop, new_bool_loop, 1)
elif new_bool_loop not in s:
    raise RuntimeError('MEDICAL_MERGE_SERVER_POLICY_MARKER_MISSING')
SERVER.write_text(s, encoding='utf-8')

# 2) Merge the breeder settings UI into one section without changing stored keys.
h = SETTINGS.read_text(encoding='utf-8')
old_vaccine = '''<section class="card pad section-card"><h2>ワクチン代</h2><div class="choice-row"><label><input type="radio" name="vaccineIncluded" value="1"> 子犬代に含む</label><label><input type="radio" name="vaccineIncluded" value="0"> 子犬代に含まない</label></div><div class="field" style="margin-top:14px"><label>説明文</label><textarea id="vaccineNote" maxlength="1000" rows="4" placeholder="例：6種混合ワクチン1回接種につき別途○○円（税込）"></textarea></div></section>'''
old_health = '''<section class="card pad section-card"><h2>健康診断・マイクロチップ</h2><div class="field-row"><div class="field"><label>健康診断費</label><div class="choice-row" style="margin-top:8px"><label><input type="radio" name="healthExamIncluded" value="1"> 子犬代に含む</label><label><input type="radio" name="healthExamIncluded" value="0"> 含まない</label></div></div><div class="field"><label>マイクロチップ費</label><div class="choice-row" style="margin-top:8px"><label><input type="radio" name="microchipIncluded" value="1"> 子犬代に含む</label><label><input type="radio" name="microchipIncluded" value="0"> 含まない</label></div></div></div><div class="field" style="margin-top:14px"><label>補足</label><textarea id="healthNote" maxlength="1000" rows="4" placeholder="費用や実施時期について"></textarea></div></section>'''
merged = '''<section class="card pad section-card"><h2>ワクチン・マイクロチップ・健康診断</h2><div class="field"><label>混合ワクチン代</label><div class="choice-row" style="margin-top:8px"><label><input type="radio" name="vaccineIncluded" value="1"> 子犬代に含む</label><label><input type="radio" name="vaccineIncluded" value="0"> 子犬代に含まない</label></div></div><div class="field" style="margin-top:14px"><label>ワクチンの説明</label><textarea id="vaccineNote" maxlength="1000" rows="4" placeholder="例：6種混合ワクチン1回接種につき別途○○円（税込）"></textarea></div><div class="field" style="margin-top:18px"><label>マイクロチップ</label><div class="notice" style="margin-top:8px">装着済み・生体価格に含む（固定）</div><div class="help">BIG PAWではマイクロチップ費用は生体価格に含む設定で固定しています。</div></div><div class="field" style="margin-top:18px"><label>健康診断費</label><div class="choice-row" style="margin-top:8px"><label><input type="radio" name="healthExamIncluded" value="1"> 子犬代に含む</label><label><input type="radio" name="healthExamIncluded" value="0"> 子犬代に含まない</label></div></div><div class="field" style="margin-top:14px"><label>健康診断の説明</label><textarea id="healthNote" maxlength="1000" rows="4" placeholder="健康診断の費用や実施時期について"></textarea></div></section>'''
if old_vaccine in h and old_health in h:
    assert h.count(old_vaccine) == 1 and h.count(old_health) == 1
    h = h.replace(old_vaccine, merged, 1).replace(old_health, '', 1)
elif merged not in h:
    raise RuntimeError('MEDICAL_MERGE_SETTINGS_SECTIONS_MISSING')

old_payload = "healthExamIncluded:boolRadio('healthExamIncluded'),microchipIncluded:boolRadio('microchipIncluded'),healthNote:"
new_payload = "healthExamIncluded:boolRadio('healthExamIncluded'),microchipIncluded:true,healthNote:"
if old_payload in h:
    h = h.replace(old_payload, new_payload, 1)
elif new_payload not in h:
    raise RuntimeError('MEDICAL_MERGE_PAYLOAD_MARKER_MISSING')

old_fill = "setRadio('healthExamIncluded',s.healthExamIncluded);setRadio('microchipIncluded',s.microchipIncluded)"
new_fill = "setRadio('healthExamIncluded',s.healthExamIncluded)"
if old_fill in h:
    h = h.replace(old_fill, new_fill, 1)
elif new_fill not in h:
    raise RuntimeError('MEDICAL_MERGE_FILL_MARKER_MISSING')

if 'name="microchipIncluded"' in h:
    raise RuntimeError('MEDICAL_MERGE_MICROCHIP_RADIO_STILL_PRESENT')
SETTINGS.write_text(h, encoding='utf-8')

# 3) Merge the public puppy-detail rows. Only this independent renderer changes.
p = PUPPY_RENDERER.read_text(encoding='utf-8')
old_health_logic = """      const healthParts=[];\n      if(s.healthExamIncluded!==null) healthParts.push('健康診断：'+included(s.healthExamIncluded));\n      if(s.microchipIncluded!==null) healthParts.push('マイクロチップ：'+included(s.microchipIncluded));\n"""
new_health_logic = """      const medicalParts=[];\n      if(vaccine) medicalParts.push('混合ワクチン：'+vaccine);\n      if(s.vaccineNote) medicalParts.push(s.vaccineNote);\n      medicalParts.push('マイクロチップ：装着済み・生体価格に含まれます');\n      if(s.healthExamIncluded!==null) medicalParts.push('健康診断：'+included(s.healthExamIncluded));\n      if(s.healthNote) medicalParts.push(s.healthNote);\n"""
if old_health_logic in p:
    p = p.replace(old_health_logic, new_health_logic, 1)
elif new_health_logic not in p:
    raise RuntimeError('MEDICAL_MERGE_PUPPY_LOGIC_MISSING')
old_rows = """        row('血統証明書',pedigree,s.pedigreeNote||''),\n        row('ワクチン代',vaccine,s.vaccineNote||''),\n        row('予約金',reservation,reservationDetail),\n        row('当日の見学',sameDay,s.visitNote||''),\n        row('お引き渡し時期',handover,s.handoverText||''),\n        row('健康診断・マイクロチップ',healthParts.join(' ／ '),s.healthNote||''),\n"""
new_rows = """        row('血統証明書',pedigree,s.pedigreeNote||''),\n        row('ワクチン・マイクロチップ・健康診断','',medicalParts.join('\\n')),\n        row('予約金',reservation,reservationDetail),\n        row('当日の見学',sameDay,s.visitNote||''),\n        row('お引き渡し時期',handover,s.handoverText||''),\n"""
if old_rows in p:
    p = p.replace(old_rows, new_rows, 1)
elif new_rows not in p:
    raise RuntimeError('MEDICAL_MERGE_PUPPY_ROWS_MISSING')
PUPPY_RENDERER.write_text(p, encoding='utf-8')

# 4) Merge the public breeder-detail rows too.
b = BREEDER_RENDERER.read_text(encoding='utf-8')
old_health_var = "      const health=`健康診断：${yn(s.healthExamIncluded)} ／ マイクロチップ：${yn(s.microchipIncluded)}`;\n"
new_health_var = "      const medical=`混合ワクチン：${yn(s.vaccineIncluded)} ／ マイクロチップ：装着済み・生体価格に含まれます ／ 健康診断：${yn(s.healthExamIncluded)}`;\n"
if old_health_var in b:
    b = b.replace(old_health_var, new_health_var, 1)
elif new_health_var not in b:
    raise RuntimeError('MEDICAL_MERGE_BREEDER_LOGIC_MISSING')
old_breeder_rows = """        ${row('血統証明書',orgs||'未設定',s.pedigreeNote||'')}\n        ${row('ワクチン代',yn(s.vaccineIncluded),s.vaccineNote||'')}\n        ${row('予約金',reservation,[s.balanceTiming,s.reservationNote].filter(Boolean).join('／'))}\n        ${row('問い合わせ当日の見学',ok(s.sameDayVisit),s.visitNote||'')}\n        ${row('引き渡し時期',handoverDays||'条件を確認してください',s.handoverText||'')}\n        ${row('健康診断・マイクロチップ',health,s.healthNote||'')}\n"""
new_breeder_rows = """        ${row('血統証明書',orgs||'未設定',s.pedigreeNote||'')}\n        ${row('ワクチン・マイクロチップ・健康診断',medical,[s.vaccineNote,s.healthNote].filter(Boolean).join('／'))}\n        ${row('予約金',reservation,[s.balanceTiming,s.reservationNote].filter(Boolean).join('／'))}\n        ${row('問い合わせ当日の見学',ok(s.sameDayVisit),s.visitNote||'')}\n        ${row('引き渡し時期',handoverDays||'条件を確認してください',s.handoverText||'')}\n"""
if old_breeder_rows in b:
    b = b.replace(old_breeder_rows, new_breeder_rows, 1)
elif new_breeder_rows not in b:
    raise RuntimeError('MEDICAL_MERGE_BREEDER_ROWS_MISSING')
BREEDER_RENDERER.write_text(b, encoding='utf-8')

# 5) Cache-bust only the two independent sales/handover renderer assets.
pd = PUPPY_DETAIL.read_text(encoding='utf-8')
pd_old = '<script src="assets/puppy-sales-handover-public.js?v=20260928a"></script>'
pd_new = '<script src="assets/puppy-sales-handover-public.js?v=20260928b"></script>'
if pd_old in pd:
    pd = pd.replace(pd_old, pd_new, 1)
elif pd_new not in pd:
    raise RuntimeError('MEDICAL_MERGE_PUPPY_CACHE_TAG_MISSING')
PUPPY_DETAIL.write_text(pd, encoding='utf-8')

bd = BREEDER_DETAIL.read_text(encoding='utf-8')
bd_old = '<script src="assets/sales-handover-public.js"></script>'
bd_new = '<script src="assets/sales-handover-public.js?v=20260928b"></script>'
if bd_old in bd:
    bd = bd.replace(bd_old, bd_new, 1)
elif bd_new not in bd:
    raise RuntimeError('MEDICAL_MERGE_BREEDER_CACHE_TAG_MISSING')
BREEDER_DETAIL.write_text(bd, encoding='utf-8')

# Final regression gates.
sv = SERVER.read_text(encoding='utf-8')
hv = SETTINGS.read_text(encoding='utf-8')
pv = PUPPY_RENDERER.read_text(encoding='utf-8')
bv = BREEDER_RENDERER.read_text(encoding='utf-8')
checks = {
    'server_microchip_fixed_true': "out['microchipIncluded']=True" in sv,
    'settings_merged_heading': hv.count('ワクチン・マイクロチップ・健康診断') == 1,
    'microchip_not_editable': 'name="microchipIncluded"' not in hv,
    'microchip_fixed_copy': '装着済み・生体価格に含む（固定）' in hv,
    'vaccine_choice_preserved': 'name="vaccineIncluded"' in hv,
    'health_choice_preserved': 'name="healthExamIncluded"' in hv,
    'payload_forces_microchip_true': 'microchipIncluded:true' in hv,
    'puppy_public_merged': "row('ワクチン・マイクロチップ・健康診断'" in pv,
    'puppy_public_fixed_microchip': 'マイクロチップ：装着済み・生体価格に含まれます' in pv,
    'breeder_public_merged': "row('ワクチン・マイクロチップ・健康診断'" in bv,
    'breeder_public_fixed_microchip': 'マイクロチップ：装着済み・生体価格に含まれます' in bv,
    'stable_gallery_unchanged': STABLE_GALLERY.read_bytes() == gallery_before,
}
failed = [k for k,v in checks.items() if not v]
if failed:
    raise RuntimeError('SALES_HANDOVER_MEDICAL_MERGE_FAIL|' + '|'.join(failed))

print('SALES_HANDOVER_MEDICAL_MERGE_OK|ui=single_section|vaccine=selectable|microchip=included_fixed|health_exam=selectable|existing_keys=preserved|puppy_public=merged|breeder_public=merged|stable_gallery=byte_preserved', flush=True)
