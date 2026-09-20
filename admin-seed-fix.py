from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8')
needle="        salt,digest=hash_password(pw)\n        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',"
repl="        if uid == 'u_admin' and role == 'operator':\n            pw = os.environ.get('BIGPAW_OWNER_SETUP_KEY') or pw\n        existing=con.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone()\n        if existing:\n            if uid == 'u_admin' and role == 'operator':\n                salt,digest=hash_password(pw)\n                con.execute('UPDATE users SET email=?, salt=?, password_hash=? WHERE id=?',(email,salt,digest,uid))\n            return\n        salt,digest=hash_password(pw)\n        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',"
if needle not in s: raise SystemExit('hash insertion point not found')
p.write_text(s.replace(needle,repl,1),encoding='utf-8')
