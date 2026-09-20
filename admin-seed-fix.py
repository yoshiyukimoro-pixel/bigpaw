from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8')
needle="        salt,digest=hash_password(pw)\n        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',"
repl="        existing=con.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone()\n        if existing:\n            if uid == 'u_admin' and role == 'operator': con.execute('UPDATE users SET email=? WHERE id=?',(email,uid))\n            return\n        salt,digest=hash_password(pw)\n        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',"
if needle not in s: raise SystemExit('hash insertion point not found')
p.write_text(s.replace(needle,repl,1),encoding='utf-8')
