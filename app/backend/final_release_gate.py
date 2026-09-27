#!/usr/bin/env python3
from pathlib import Path

ROOT=Path('/app')
SERVER=ROOT/'backend'/'server.py'
s=SERVER.read_text(encoding='utf-8')
compile(s,str(SERVER),'exec')

target="        if path=='/api/breeder/sales-handover-settings':\n"
get_start=s.index('    def do_GET(self):')
post_start=s.index('    def do_POST(self):')
delete_start=s.index('    def do_DELETE(self):')
patch_start=s.index('    def do_PATCH(self):')
get_part=s[get_start:post_start]
post_part=s[post_start:delete_start]
patch_part=s[patch_start:]

checks={
    'sales_get_route_in_get': target in get_part,
    'sales_post_route_in_post': target in post_part,
    'sales_route_not_in_patch': target not in patch_part,
    'sales_table_present': 'CREATE TABLE IF NOT EXISTS breeder_sales_handover_settings' in s,
    'support_reply_post_present': "msupport_reply=re.fullmatch(r'/api/operator/support/([^/]+)/reply',path)" in post_part,
    'buyer_puppy_create_blocked': "if path=='/api/puppies':\n            u=self.require(['breeder','operator']);" in post_part,
    'photo_order_api_preserved_in_patch': "/api/puppies/([^/]+)/photos/order" in patch_part,
    'sales_page_guarded': "'/breeder-sales-handover.html'" in (ROOT/'auth-return-fix.js').read_text(encoding='utf-8'),
    'puppy_detail_isolated': 'sales-handover-public.js' not in (ROOT/'puppy-detail.html').read_text(encoding='utf-8'),
    'mobile_save_tap_fix_preserved': '.savebar{position:static;bottom:auto' in (ROOT/'breeder-sales-handover.html').read_text(encoding='utf-8'),
}
failed=[k for k,v in checks.items() if not v]
if failed:
    raise SystemExit('FINAL_RELEASE_GATE_FAIL|'+'|'.join(failed))
print('FINAL_RELEASE_GATE_OK|server_syntax=valid|sales_get=GET|sales_save=POST|support_reply=preserved|photo_order=PATCH_preserved|mobile_save_tap=preserved|puppy_detail=untouched',flush=True)
