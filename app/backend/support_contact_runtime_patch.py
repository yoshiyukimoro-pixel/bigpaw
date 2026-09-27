#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'backend' / 'server.py'
server = SERVER.read_text(encoding='utf-8')

old = """            for op in ops: send_mail(op['email'],'BIG PAW 運営問い合わせ',f\"受付番号: {tid}\\nカテゴリ: {category}\\n件名: {subject}\\n送信者: {name} <{email}>\\n\\n{message}\\n\\n{PUBLIC_BASE_URL}/operator-support.html\")
"""
new = """            support_targets={str(op['email']).strip().lower() for op in ops if str(op['email']).strip()}
            support_email=os.environ.get('BIGPAW_SUPPORT_EMAIL','info@bigpaw.site').strip().lower()
            if support_email: support_targets.add(support_email)
            for support_to in sorted(support_targets):
                send_mail(support_to,'BIG PAW 運営問い合わせ',f\"受付番号: {tid}\\nカテゴリ: {category}\\n件名: {subject}\\n送信者: {name} <{email}>\\n\\n{message}\\n\\n{PUBLIC_BASE_URL}/operator-support.html\")
"""

if old in server:
    server = server.replace(old, new, 1)
elif new not in server:
    raise RuntimeError('SUPPORT_CONTACT_FIX_FAIL|support_mail_marker_missing')

SERVER.write_text(server, encoding='utf-8')
compile(server, str(SERVER), 'exec')
assert "BIGPAW_SUPPORT_EMAIL" in server
print('SUPPORT_CONTACT_FIX_OK|recipient=BIGPAW_SUPPORT_EMAIL|default=info@bigpaw.site|operator_copy=preserved', flush=True)
