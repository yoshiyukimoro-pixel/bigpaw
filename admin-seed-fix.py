from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8')
needle="        salt,digest=hash_password(pw)\n        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',"
repl="        existing=con.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone()\n        if existing:\n            if uid == 'u_admin' and role == 'operator': con.execute('UPDATE users SET email=? WHERE id=?',(email,uid))\n            return\n        salt,digest=hash_password(pw)\n        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',"
if needle in s:
    s=s.replace(needle,repl,1)

# BIGPAW breeder account recovery: selected emails work as breeder accounts without re-applying.
helper = """
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
"""
if 'BIGPAW_BREEDER_EMAILS' not in s:
    import re
    m = re.search(r"PUBLIC_BASE_URL\s*=.*\n", s)
    if m:
        s = s[:m.end()] + helper + s[m.end():]
    else:
        s = s.replace('import os', 'import os\n' + helper, 1)

# Normalize the central session/role response where possible.
if 'bigpaw_recovered_role(u)' not in s:
    s = s.replace('return u', 'u=bigpaw_recovered_role(u)\n        return u', 1)

# Make /api/me show breeder too.
if 'bigpaw_recovered_role(dict(u))' not in s:
    s = s.replace('return self.send_json(dict(u))', 'return self.send_json(bigpaw_recovered_role(dict(u)))')

p.write_text(s,encoding='utf-8')
