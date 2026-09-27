#!/usr/bin/env python3
from pathlib import Path

SERVER = Path('/app/backend/server.py')
s = SERVER.read_text(encoding='utf-8')

target = "        if path=='/api/breeder/sales-handover-settings':\n"
post_start = s.index('    def do_POST(self):')
delete_start = s.index('    def do_DELETE(self):')
patch_start = s.index('    def do_PATCH(self):')

prefix = s[:post_start]
post = s[post_start:delete_start]
between = s[delete_start:patch_start]
patch = s[patch_start:]

# sales_handover_settings_patch.py historically inserted the write route by
# searching everything after do_POST for /api/breeder-profile. That marker is
# in do_PATCH, so the POST route could land in do_PATCH and POST returned 404.
# Move only that isolated route; do not touch puppy/search/gallery code.
if target not in post:
    if target not in patch:
        raise RuntimeError('SALES_HANDOVER_SAVE_FIX_FAIL|write_route_missing')
    route_start = patch.index(target)
    next_marker = "        if path=='/api/breeder-profile':\n"
    route_end = patch.index(next_marker, route_start)
    route = patch[route_start:route_end]
    patch = patch[:route_start] + patch[route_end:]

    post_anchor = "        path=urlparse(self.path).path\n"
    if post.count(post_anchor) != 1:
        raise RuntimeError('SALES_HANDOVER_SAVE_FIX_FAIL|post_anchor_count='+str(post.count(post_anchor)))
    post = post.replace(post_anchor, post_anchor + route, 1)

s = prefix + post + between + patch
SERVER.write_text(s, encoding='utf-8')
compile(s, str(SERVER), 'exec')

post_start = s.index('    def do_POST(self):')
delete_start = s.index('    def do_DELETE(self):')
patch_start = s.index('    def do_PATCH(self):')
post = s[post_start:delete_start]
patch = s[patch_start:]
assert post.count(target) == 1, ('sales_handover_post_route_count', post.count(target))
assert target not in patch, 'sales_handover_route_must_not_be_in_patch'
print('SALES_HANDOVER_SAVE_ROUTE_OK|method=POST|patch_shadow=removed|puppy_detail=untouched', flush=True)
