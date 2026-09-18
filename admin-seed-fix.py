from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8')
needle="        r=con.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone()\n        if r: return\n        salt,digest=hash_password(pw)"
repl="        r=con.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone()\n        if r: return\n        existing=con.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone()\n        if existing:\n            if uid == 'u_admin' and role == 'operator': con.execute('UPDATE users SET email=? WHERE id=?',(email,uid))\n            return\n        salt,digest=hash_password(pw)"
if needle not in s: raise SystemExit('admin seed insertion point not found')
p.write_text(s.replace(needle,repl,1),encoding='utf-8')
