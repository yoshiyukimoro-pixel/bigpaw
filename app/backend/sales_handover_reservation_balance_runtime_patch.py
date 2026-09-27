#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUPPY_RENDERER = ROOT / 'assets' / 'puppy-sales-handover-public.js'
BREEDER_RENDERER = ROOT / 'assets' / 'sales-handover-public.js'
PUPPY_DETAIL = ROOT / 'puppy-detail.html'
BREEDER_DETAIL = ROOT / 'breeder-detail.html'
STABLE_GALLERY = ROOT / 'assets' / 'puppy-detail-stable-gallery.js'

gallery_before = STABLE_GALLERY.read_bytes()

# Keep stored breeder settings untouched. Only reorganize the public presentation
# so reservation money and remaining balance cannot be mistaken for one another.
p = PUPPY_RENDERER.read_text(encoding='utf-8')
old_reservation_logic = """      const reservation=Number(s.reservationAmount||0)>0?yen(s.reservationAmount):'';\n      const reservationDetail=[s.balanceTiming,s.reservationNote].filter(Boolean).join('／');\n      const sameDay=visit(s.sameDayVisit);\n"""
new_reservation_logic = r"""      const reservation=Number(s.reservationAmount||0)>0?yen(s.reservationAmount):'';
      const cleanReservationNote=text=>(String(text||'').match(/[^。！？!?]+[。！？!?]?/g)||[])
        .map(x=>x.trim())
        .filter(x=>x&&!/(残金|キャンセル|返金)/.test(x))
        .join('');
      const reservationDetail=cleanReservationNote(s.reservationNote);
      const balanceTiming=String(s.balanceTiming||'').trim().replace(/[。.]$/,'');
      const balanceDetail=balanceTiming?`生体代金から予約金を差し引いた残金は、${balanceTiming}${/に$/.test(balanceTiming)?'':'に'}お支払いください。`:'';
      const sameDay=visit(s.sameDayVisit);
"""
assert p.count(old_reservation_logic) == 1, ('reservation_balance_puppy_logic_marker', p.count(old_reservation_logic))
p = p.replace(old_reservation_logic, new_reservation_logic, 1)

old_puppy_rows = """        row('予約金',reservation,reservationDetail),\n        row('当日の見学',sameDay,s.visitNote||''),\n"""
new_puppy_rows = """        row('予約金',reservation,reservationDetail),\n        row('残金のお支払い',balanceTiming,balanceDetail),\n        row('当日の見学',sameDay,s.visitNote||''),\n"""
assert p.count(old_puppy_rows) == 1, ('reservation_balance_puppy_rows_marker', p.count(old_puppy_rows))
p = p.replace(old_puppy_rows, new_puppy_rows, 1)
PUPPY_RENDERER.write_text(p, encoding='utf-8')

# Keep breeder public detail consistent with puppy detail.
b = BREEDER_RENDERER.read_text(encoding='utf-8')
old_breeder_logic = """      const reservation=yen(s.reservationAmount);\n"""
new_breeder_logic = r"""      const reservation=yen(s.reservationAmount);
      const cleanReservationNote=text=>(String(text||'').match(/[^。！？!?]+[。！？!?]?/g)||[])
        .map(x=>x.trim())
        .filter(x=>x&&!/(残金|キャンセル|返金)/.test(x))
        .join('');
      const reservationDetail=cleanReservationNote(s.reservationNote);
      const balanceTiming=String(s.balanceTiming||'').trim().replace(/[。.]$/,'');
      const balanceDetail=balanceTiming?`生体代金から予約金を差し引いた残金は、${balanceTiming}${/に$/.test(balanceTiming)?'':'に'}お支払いください。`:'';
"""
assert b.count(old_breeder_logic) == 1, ('reservation_balance_breeder_logic_marker', b.count(old_breeder_logic))
b = b.replace(old_breeder_logic, new_breeder_logic, 1)

old_breeder_row = "${row('予約金',reservation,[s.balanceTiming,s.reservationNote].filter(Boolean).join('／'))}"
new_breeder_rows = "${row('予約金',reservation,reservationDetail)}\n        ${row('残金のお支払い',balanceTiming,balanceDetail)}"
assert b.count(old_breeder_row) == 1, ('reservation_balance_breeder_row_marker', b.count(old_breeder_row))
b = b.replace(old_breeder_row, new_breeder_rows, 1)
BREEDER_RENDERER.write_text(b, encoding='utf-8')

# Cache-bust only the two independent sales/handover renderer assets.
pd = PUPPY_DETAIL.read_text(encoding='utf-8')
pd_old = '<script src="assets/puppy-sales-handover-public.js?v=20260928c"></script>'
pd_new = '<script src="assets/puppy-sales-handover-public.js?v=20260928d"></script>'
assert pd.count(pd_old) == 1, ('reservation_balance_puppy_cache_marker', pd.count(pd_old))
pd = pd.replace(pd_old, pd_new, 1)
PUPPY_DETAIL.write_text(pd, encoding='utf-8')

bd = BREEDER_DETAIL.read_text(encoding='utf-8')
bd_old = '<script src="assets/sales-handover-public.js?v=20260928c"></script>'
bd_new = '<script src="assets/sales-handover-public.js?v=20260928d"></script>'
assert bd.count(bd_old) == 1, ('reservation_balance_breeder_cache_marker', bd.count(bd_old))
bd = bd.replace(bd_old, bd_new, 1)
BREEDER_DETAIL.write_text(bd, encoding='utf-8')

pv = PUPPY_RENDERER.read_text(encoding='utf-8')
bv = BREEDER_RENDERER.read_text(encoding='utf-8')
checks = {
    'puppy_reservation_row': "row('予約金',reservation,reservationDetail)" in pv,
    'puppy_balance_row': "row('残金のお支払い',balanceTiming,balanceDetail)" in pv,
    'puppy_balance_copy': '生体代金から予約金を差し引いた残金は、' in pv,
    'puppy_reservation_excludes_balance_cancel': "!/(残金|キャンセル|返金)/.test(x)" in pv,
    'breeder_reservation_row': "row('予約金',reservation,reservationDetail)" in bv,
    'breeder_balance_row': "row('残金のお支払い',balanceTiming,balanceDetail)" in bv,
    'puppy_cache_busted': 'puppy-sales-handover-public.js?v=20260928d' in PUPPY_DETAIL.read_text(encoding='utf-8'),
    'breeder_cache_busted': 'sales-handover-public.js?v=20260928d' in BREEDER_DETAIL.read_text(encoding='utf-8'),
    'stable_gallery_unchanged': STABLE_GALLERY.read_bytes() == gallery_before,
}
failed = [k for k,v in checks.items() if not v]
if failed:
    raise RuntimeError('SALES_HANDOVER_RESERVATION_BALANCE_FAIL|' + '|'.join(failed))

print('SALES_HANDOVER_RESERVATION_BALANCE_OK|reservation=separate|balance=separate|duplicate_balance_cancel_removed_from_reservation_public_copy|saved_data=untouched|puppy_public=updated|breeder_public=updated|stable_gallery=byte_preserved', flush=True)
