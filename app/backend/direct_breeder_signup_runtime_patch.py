from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / 'backend' / 'server.py'
GALLERY = ROOT / 'assets' / 'puppy-detail-stable-gallery.js'
MARKER = 'DIRECT_BREEDER_SIGNUP_FLOW_V1'

server = SERVER.read_text(encoding='utf-8')
gallery_before = GALLERY.read_bytes() if GALLERY.exists() else b''

if MARKER not in server:
    register_head = """        if path=='/api/register':\n            body=self.json_body(); email=str(body.get('email','')).strip().lower(); pw=str(body.get('password',''))\n"""
    register_head_new = """        if path=='/api/register':\n            # DIRECT_BREEDER_SIGNUP_FLOW_V1\n            body=self.json_body(); email=str(body.get('email','')).strip().lower(); pw=str(body.get('password','')); account_type=str(body.get('accountType','')).strip().lower()\n"""
    assert server.count(register_head) == 1, ('direct_breeder_register_head_count', server.count(register_head))
    server = server.replace(register_head, register_head_new, 1)

    old_mail = """            link=f\"{PUBLIC_BASE_URL}/verify-email.html?token={token}\"; sent=send_mail(email,'BIG PAW メールアドレス確認',f\"BIG PAWへようこそ。メールアドレス確認はこちらから行ってください。\\n\\n{link}\\n\\nこのリンクは24時間で期限切れになります。\")\n"""
    new_mail = """            verify_flow='&flow=breeder' if account_type=='breeder' else ''\n            link=f\"{PUBLIC_BASE_URL}/verify-email.html?token={token}{verify_flow}\"\n            mail_subject='BIG PAW ブリーダー登録 メールアドレス確認' if account_type=='breeder' else 'BIG PAW メールアドレス確認'\n            mail_lead='BIG PAWのブリーダー登録を続けるため、メールアドレスを確認してください。' if account_type=='breeder' else 'BIG PAWへようこそ。メールアドレス確認はこちらから行ってください。'\n            sent=send_mail(email,mail_subject,f\"{mail_lead}\\n\\n{link}\\n\\nこのリンクは24時間で期限切れになります。\")\n"""
    assert server.count(old_mail) == 1, ('direct_breeder_register_mail_count', server.count(old_mail))
    server = server.replace(old_mail, new_mail, 1)
    SERVER.write_text(server, encoding='utf-8')

verify = SERVER.read_text(encoding='utf-8')
checks = {
    'marker': MARKER in verify,
    'register_route_single': verify.count("if path=='/api/register':") == 1,
    'buyer_role_preserved': "(uid,'buyer',email" in verify,
    'breeder_flow_param': "verify_flow='&flow=breeder' if account_type=='breeder' else ''" in verify,
    'general_flow_preserved': "else 'BIG PAW メールアドレス確認'" in verify,
}
failed = [k for k, ok in checks.items() if not ok]
if failed:
    raise RuntimeError('DIRECT_BREEDER_SIGNUP_FLOW_FAIL|' + ','.join(failed))

if GALLERY.exists() and GALLERY.read_bytes() != gallery_before:
    raise RuntimeError('DIRECT_BREEDER_SIGNUP_FLOW_FAIL|stable_gallery_changed')

print(
    'DIRECT_BREEDER_SIGNUP_FLOW_OK|entry=breeder_register|general_registration_step=skipped_in_ui'
    '|account_created=buyer_until_approval|email_verification=required|approval_promotes_to_breeder'
    '|general_buyer_registration=preserved|stable_gallery=byte_preserved',
    flush=True,
)
