from pathlib import Path

# Final operational patch: notify operator accounts when a breeder applies and
# show the pending application count on the operator dashboard.
exec(Path('/app/backend/breeder_application_notify_patch.py').read_text(encoding='utf-8'), {'__name__':'__main__'})

# Apply operator-only registered-user management only after the existing core
# patches have succeeded. This patch is assertion-guarded, so an unexpected
# source layout stops the build instead of partially changing production.
exec(Path('/app/backend/operator_users_patch.py').read_text(encoding='utf-8'), {'__name__':'__main__'})

# Apply the isolated breeder sales/handover feature before the final regression
# checks. The feature has its own build gate and does not modify puppy-detail/gallery.
exec(Path('/app/backend/sales_handover_settings_patch.py').read_text(encoding='utf-8'), {'__name__':'__main__'})

# Validate and repair the generated server source before any release can pass.
exec(Path('/app/backend/sales_handover_postbuild_fix.py').read_text(encoding='utf-8'), {'__name__':'__main__'})

server = Path('/app/backend/server.py').read_text(encoding='utf-8')
auth = Path('/app/auth-return-fix.js').read_text(encoding='utf-8')

# Syntax validity is part of the release gate, not just textual assertions.
compile(server, '/app/backend/server.py', 'exec')

checks = {
    'buyer_cannot_create_puppy': "if path=='/api/puppies':\n            u=self.require(['breeder','operator']);" in server,
    'buyer_cannot_edit_puppy': "m=re.fullmatch(r'/api/puppies/([^/]+)',path)\n        if m:\n            u=self.require(['breeder','operator']);" in server,
    'buyer_cannot_update_inquiry_status': "iq=re.fullmatch(r'/api/inquiries/([^/]+)',path)\n        if iq:\n            u=self.require(['breeder','operator']);" in server,
    'breeder_edit_is_owner_scoped': "if not b or p['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)" in server,
    'breeder_delete_is_owner_scoped': "if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)" in server,
    'breeder_photo_is_owner_scoped': "owned=con.execute('SELECT 1 FROM puppies WHERE id=? AND breeder_id=?',(puppy_id,bid)).fetchone()" in server,
    'breeder_health_is_owner_scoped': "owned=bool(con.execute('SELECT 1 FROM puppies WHERE id=? AND breeder_id=?',(puppy_id,bid)).fetchone())" in server,
    'parent_dog_create_uses_own_breeder': "b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); breeder_id=b['id'] if b else None" in server,
    'parent_dog_update_is_owner_scoped': "if not b or d['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)" in server,
    'require_uses_persisted_role': "if roles and u['role'] not in roles:" in server,
    'current_user_keeps_database_role': "con.close(); return rowdict(row)" in server,
    'login_returns_database_role': "'role':u['role']" in server,
    'operator_api_is_operator_only': "if path=='/api/operator/listings':\n            u=self.require(['operator']);" in server,
    'operator_breeders_api_is_operator_only': "if path=='/api/operator/breeders':\n            u=self.require(['operator']);" in server,
    'operator_users_api_is_operator_only': "if path=='/api/operator/users':\n            u=self.require(['operator'])" in server,
    'operator_user_detail_api_is_operator_only': "mu=re.fullmatch(r'/api/operator/users/([^/]+)',path)\n        if mu:\n            u=self.require(['operator'])" in server,
    'operator_user_email_api_is_operator_only': "mu=re.fullmatch(r'/api/operator/users/([^/]+)/email',path)\n        if mu:\n            u=self.require(['operator'])" in server,
    'operator_user_dashboard_link_exists': 'href="operator-users.html"' in Path('/app/operator-admin.html').read_text(encoding='utf-8'),
    'operator_breeder_detail_is_guarded': "'/operator-breeder-detail.html'" in auth,
    'operator_launch_check_is_guarded': "'/launch-checklist.html'" in auth,
    'buyer_mypage_is_buyer_only': "const buyerOnly=['/mypage.html','/my-page.html'];" in auth,
    'sales_handover_page_is_breeder_only': "'/breeder-sales-handover.html'" in auth,
    'sales_handover_api_is_guarded': "if path=='/api/breeder/sales-handover-settings':\n            u=self.require(['breeder','operator'])" in server,
    'sales_handover_keeps_puppy_detail_isolated': 'sales-handover-public.js' not in Path('/app/puppy-detail.html').read_text(encoding='utf-8'),
}

protected_pages=[
    'admin.html','breeder-puppy-new.html','breeder-inquiries.html','breeder-billing.html',
    'breeder-deal-report.html','breeder-profile-edit.html','breeder-sales-handover.html','breeder-invoice.html','parent-dogs.html','health-records.html',
    'operator-admin.html','operator-users.html','operator-user-detail.html','operator-breeders.html','operator-breeder-detail.html','operator-listings.html',
    'operator-deals.html','operator-support.html','operator-deal-reports.html','operator-revenue.html',
    'operator-reports.html','operator-invoices.html','operator-automations.html','operator-audit.html',
    'operator-backups.html','project-status.html','backend-status.html','launch-checklist.html','mypage.html'
]
for name in protected_pages:
    fp=Path('/app')/name
    if fp.exists():
        checks['page_guard_'+name] = 'auth-return-fix.js' in fp.read_text(encoding='utf-8')

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('SECURITY_REGRESSION_FAIL|' + '|'.join(failed))

print(
    'SECURITY_REGRESSION_OK|server_syntax=valid|buyer_create_edit=blocked|breeder_cross_edit=blocked|parent_dog_update=owner_scoped|operator_role=preserved|operator_pages=guarded|operator_users=guarded|sales_handover=guarded|protected_entries=guarded',
    flush=True,
)
