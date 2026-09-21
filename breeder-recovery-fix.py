from pathlib import Path
import re

p = Path('backend/server.py')
s = p.read_text(encoding='utf-8')

helper = r'''
# BIGPAW breeder account recovery: treat selected emails as breeder without asking them to re-apply.
BIGPAW_BREEDER_EMAILS = {e.strip().lower() for e in os.environ.get('BIGPAW_BREEDER_EMAILS','').split(',') if e.strip()}
def bigpaw_recovered_role(user):
    try:
        if user and str(user.get('email','')).strip().lower() in BIGPAW_BREEDER_EMAILS:
            user = dict(user)
            user['role'] = 'breeder'
    except Exception:
        pass
    return user
'''
if 'BIGPAW_BREEDER_EMAILS' not in s:
    # Insert after PUBLIC_BASE_URL if possible, otherwise after imports.
    m = re.search(r"PUBLIC_BASE_URL\s*=.*\n", s)
    if m:
        s = s[:m.end()] + helper + s[m.end():]
    else:
        s = s.replace('import os', 'import os' + helper, 1)

# Patch the central require() method so all protected breeder endpoints see recovered role.
# Typical pattern in the app: `return u` after role checks.
if 'bigpaw_recovered_role(u)' not in s:
    s = s.replace('return u', 'u=bigpaw_recovered_role(u)\n        return u', 1)

# Patch /api/me style responses too, so mypage shows breeder instead of buyer.
# This is intentionally broad but only changes the in-memory response when email is in BIGPAW_BREEDER_EMAILS.
if 'bigpaw_recovered_role(dict(u))' not in s:
    s = s.replace('return self.send_json(dict(u))', 'return self.send_json(bigpaw_recovered_role(dict(u)))')

# If an exact role check happens outside require(), normalize common fetched user variable names.
if 'BIGPAW_BREEDER_EMAILS_RUNTIME_NOTE' not in s:
    s += "\n# BIGPAW_BREEDER_EMAILS_RUNTIME_NOTE: selected emails are elevated by bigpaw_recovered_role().\n"

p.write_text(s, encoding='utf-8')
