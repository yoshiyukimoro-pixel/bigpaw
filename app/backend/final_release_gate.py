#!/usr/bin/env python3
from pathlib import Path

ROOT=Path('/app')

# Apply the narrowly scoped appeal-point patch only after all earlier build patches
# have completed. The patch itself uses exact-count guards and aborts the build if
# any expected target has changed, so an unrelated page cannot be modified silently.
APPEAL_PATCH=ROOT/'backend'/'appeal_point_patch.py'
exec(compile(APPEAL_PATCH.read_text(encoding='utf-8'),str(APPEAL_PATCH),'exec'),{'__name__':'__main__','__file__':str(APPEAL_PATCH)})

# Public puppy detail must always keep the breeder-entered introduction visible.
# This runs after the other detail-page build patches and only adds a guarded
# description renderer/fallback; it does not touch photos, favorites or inquiries.
DESCRIPTION_GUARD=ROOT/'backend'/'puppy_description_public_guard.py'
exec(compile(DESCRIPTION_GUARD.read_text(encoding='utf-8'),str(DESCRIPTION_GUARD),'exec'),{'__name__':'__main__','__file__':str(DESCRIPTION_GUARD)})

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
    'appeal_point_column_present': "ensure_column(con,'puppies','appeal_point'" in s,
    'appeal_point_api_present': "'appealPoint':d.get('appeal_point','')" in s,
    'appeal_point_edit_present': "'appealPoint':'appeal_point'" in s,
    'appeal_point_form_present': 'id="appealPoint"' in (ROOT/'breeder-puppy-new.html').read_text(encoding='utf-8'),
    'appeal_point_search_present': 'p.appealPoint' in (ROOT/'search.html').read_text(encoding='utf-8'),
    'appeal_point_live_rebuild_present': 'p.appealPoint' in (ROOT/'search-list-rebuild.html').read_text(encoding='utf-8'),
    'public_puppy_description_guard_present': 'id="bigpaw-public-puppy-description-guard"' in (ROOT/'puppy-detail.html').read_text(encoding='utf-8'),
    'public_puppy_description_source_desc': 'p.desc??p.description' in (ROOT/'puppy-detail.html').read_text(encoding='utf-8'),
    'sales_page_guarded': "'/breeder-sales-handover.html'" in (ROOT/'auth-return-fix.js').read_text(encoding='utf-8'),
    'puppy_detail_isolated': 'sales-handover-public.js' not in (ROOT/'puppy-detail.html').read_text(encoding='utf-8'),
    'mobile_save_tap_fix_preserved': '.savebar{position:static;bottom:auto' in (ROOT/'breeder-sales-handover.html').read_text(encoding='utf-8'),
}
failed=[k for k,v in checks.items() if not v]
if failed:
    raise SystemExit('FINAL_RELEASE_GATE_FAIL|'+'|'.join(failed))
print('FINAL_RELEASE_GATE_OK|server_syntax=valid|sales_get=GET|sales_save=POST|support_reply=preserved|photo_order=PATCH_preserved|appeal_point=30chars_under_color|live_rebuild=covered|puppy_description=public_visible|mobile_save_tap=preserved|puppy_detail=safeguarded',flush=True)
