#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUPPY_RENDERER = ROOT / 'assets' / 'puppy-sales-handover-public.js'
BREEDER_RENDERER = ROOT / 'assets' / 'sales-handover-public.js'
PUPPY_DETAIL = ROOT / 'puppy-detail.html'
BREEDER_DETAIL = ROOT / 'breeder-detail.html'
STABLE_GALLERY = ROOT / 'assets' / 'puppy-detail-stable-gallery.js'

gallery_before = STABLE_GALLERY.read_bytes()

# Public puppy detail: use clearer included/not-included wording and normalize
# the breeder-entered vaccine fee line without changing the saved data.
p = PUPPY_RENDERER.read_text(encoding='utf-8')
old_included = "const included=v=>v===true?'生体価格に含まれます':v===false?'生体価格とは別途必要です':'';"
new_included = "const included=v=>v===true?'生体価格に含まれます':v===false?'生体価格には含まれません':'';"
assert p.count(old_included) == 1, ('vaccine_copy_included_marker', p.count(old_included))
p = p.replace(old_included, new_included, 1)

old_logic = """      if(vaccine) medicalParts.push('混合ワクチン：'+vaccine);\n      if(s.vaccineNote) medicalParts.push(s.vaccineNote);\n"""
new_logic = r"""      const vaccineNote=String(s.vaccineNote||'')
        .replace(/ワクチン接種代として\s*別途\s*([0-9０-９,，]+)\s*円/g,'ワクチン代：別途 $1円')
        .replace(/ワクチン代として\s*別途\s*([0-9０-９,，]+)\s*円/g,'ワクチン代：別途 $1円')
        .replace(/ワクチン代[:：]\s*別途\s*([0-9０-９,，]+)\s*円/g,'ワクチン代：別途 $1円');
      if(vaccine) medicalParts.push('混合ワクチン：'+vaccine);
      if(vaccineNote) medicalParts.push(vaccineNote);
"""
assert p.count(old_logic) == 1, ('vaccine_copy_puppy_logic_marker', p.count(old_logic))
p = p.replace(old_logic, new_logic, 1)
PUPPY_RENDERER.write_text(p, encoding='utf-8')

# Public breeder detail: keep the same wording and fee-line normalization.
b = BREEDER_RENDERER.read_text(encoding='utf-8')
old_medical = "      const medical=`混合ワクチン：${yn(s.vaccineIncluded)} ／ マイクロチップ：装着済み・生体価格に含まれます ／ 健康診断：${yn(s.healthExamIncluded)}`;\n"
new_medical = r"""      const vaccineStatus=s.vaccineIncluded===true?'生体価格に含まれます':s.vaccineIncluded===false?'生体価格には含まれません':'未設定';
      const vaccineNote=String(s.vaccineNote||'')
        .replace(/ワクチン接種代として\s*別途\s*([0-9０-９,，]+)\s*円/g,'ワクチン代：別途 $1円')
        .replace(/ワクチン代として\s*別途\s*([0-9０-９,，]+)\s*円/g,'ワクチン代：別途 $1円')
        .replace(/ワクチン代[:：]\s*別途\s*([0-9０-９,，]+)\s*円/g,'ワクチン代：別途 $1円');
      const medical=`混合ワクチン：${vaccineStatus} ／ マイクロチップ：装着済み・生体価格に含まれます ／ 健康診断：${yn(s.healthExamIncluded)}`;
"""
assert b.count(old_medical) == 1, ('vaccine_copy_breeder_logic_marker', b.count(old_medical))
b = b.replace(old_medical, new_medical, 1)
old_detail = "${row('ワクチン・マイクロチップ・健康診断',medical,[s.vaccineNote,s.healthNote].filter(Boolean).join('／'))}"
new_detail = "${row('ワクチン・マイクロチップ・健康診断',medical,[vaccineNote,s.healthNote].filter(Boolean).join('／'))}"
assert b.count(old_detail) == 1, ('vaccine_copy_breeder_detail_marker', b.count(old_detail))
b = b.replace(old_detail, new_detail, 1)
BREEDER_RENDERER.write_text(b, encoding='utf-8')

# Cache-bust only the independent sales/handover renderer assets so iPhone Safari
# cannot keep the previous wording.
pd = PUPPY_DETAIL.read_text(encoding='utf-8')
pd_old = '<script src="assets/puppy-sales-handover-public.js?v=20260928b"></script>'
pd_new = '<script src="assets/puppy-sales-handover-public.js?v=20260928c"></script>'
assert pd.count(pd_old) == 1, ('vaccine_copy_puppy_cache_marker', pd.count(pd_old))
pd = pd.replace(pd_old, pd_new, 1)
PUPPY_DETAIL.write_text(pd, encoding='utf-8')

bd = BREEDER_DETAIL.read_text(encoding='utf-8')
bd_old = '<script src="assets/sales-handover-public.js?v=20260928b"></script>'
bd_new = '<script src="assets/sales-handover-public.js?v=20260928c"></script>'
assert bd.count(bd_old) == 1, ('vaccine_copy_breeder_cache_marker', bd.count(bd_old))
bd = bd.replace(bd_old, bd_new, 1)
BREEDER_DETAIL.write_text(bd, encoding='utf-8')

pv = PUPPY_RENDERER.read_text(encoding='utf-8')
bv = BREEDER_RENDERER.read_text(encoding='utf-8')
checks = {
    'puppy_not_included_copy': '混合ワクチン：'+"'" not in '',
    'puppy_clear_not_included': '生体価格には含まれません' in pv,
    'puppy_old_copy_removed': '生体価格とは別途必要です' not in pv,
    'puppy_fee_formatter': 'ワクチン代：別途 $1円' in pv,
    'breeder_clear_not_included': '生体価格には含まれません' in bv,
    'breeder_fee_formatter': 'ワクチン代：別途 $1円' in bv,
    'puppy_cache_busted': 'puppy-sales-handover-public.js?v=20260928c' in PUPPY_DETAIL.read_text(encoding='utf-8'),
    'breeder_cache_busted': 'sales-handover-public.js?v=20260928c' in BREEDER_DETAIL.read_text(encoding='utf-8'),
    'stable_gallery_unchanged': STABLE_GALLERY.read_bytes() == gallery_before,
}
failed = [k for k,v in checks.items() if not v]
if failed:
    raise RuntimeError('SALES_HANDOVER_VACCINE_COPY_FAIL|' + '|'.join(failed))

print('SALES_HANDOVER_VACCINE_COPY_OK|not_included=clear|fee_line=normalized|saved_data=untouched|puppy_public=updated|breeder_public=updated|stable_gallery=byte_preserved', flush=True)
