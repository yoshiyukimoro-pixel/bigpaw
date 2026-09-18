from pathlib import Path
import re
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8')
pattern=r"(    def seed_user\(uid,role,email,pw,last,first,display\):\n)(.*?)(?=\n    admin_email=)"
m=re.search(pattern,s,re.S)
if not m:
    raise SystemExit('seed_user block not found')
body="""        r=con.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
        if r: return
        existing=con.execute('SELECT id FROM users WHERE id=?',(uid,)).fetchone()
        if existing:
            if uid == 'u_admin' and role == 'operator':
                con.execute('UPDATE users SET email=? WHERE id=?',(email,uid))
            return
        salt,digest=hash_password(pw)
        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                    (uid,role,email,last,first,display,salt,digest,now()))
"""
s=s[:m.start()]+m.group(1)+body+s[m.end():]
p.write_text(s,encoding='utf-8')
