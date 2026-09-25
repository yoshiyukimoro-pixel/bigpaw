from pathlib import Path

server = Path('/app/backend/server.py').read_text(encoding='utf-8')
auth = Path('/app/auth-return-fix.js').read_text(encoding='utf-8')

checks = {
    'buyer_cannot_create_puppy': "if path=='/api/puppies':\n            u=self.require(['breeder','operator']);" in server,
    'buyer_cannot_edit_puppy': "m=re.fullmatch(r'/api/puppies/([^/]+)',path)\n        if m:\n            u=self.require(['breeder','operator']);" in server,
    'buyer_cannot_update_inquiry_status': "iq=re.fullmatch(r'/api/inquiries/([^/]+)',path)\n        if iq:\n            u=self.require(['breeder','operator']);" in server,
    'breeder_edit_is_owner_scoped': "if not b or p['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)" in server,
    'breeder_delete_is_owner_scoped': "if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)" in server,
    'breeder_photo_is_owner_scoped': "owned=con.execute('SELECT 1 FROM puppies WHERE id=? AND breeder_id=?',(puppy_id,bid)).fetchone()" in server,
    'require_uses_persisted_role': "if roles and u['role'] not in roles:" in server,
    'current_user_keeps_database_role': "con.close(); return rowdict(row)" in server,
    'login_returns_database_role': "'role':u['role']" in server,
    'operator_api_is_operator_only': "if path=='/api/operator/listings':\n            u=self.require(['operator']);" in server,
    'operator_breeder_detail_is_guarded': "'/operator-breeder-detail.html'" in auth,
    'operator_launch_check_is_guarded': "'/launch-checklist.html'" in auth,
    'buyer_mypage_is_buyer_only': "const buyerOnly=['/mypage.html','/my-page.html'];" in auth,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('SECURITY_REGRESSION_FAIL|' + '|'.join(failed))

print(
    'SECURITY_REGRESSION_OK|buyer_create_edit=blocked|breeder_cross_edit=blocked|operator_role=preserved|operator_pages=guarded',
    flush=True,
)
