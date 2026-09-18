from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8')
old="""    def seed_user(uid,role,email,pw,last,first,display):
        r=con.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone()
        if r: return
        salt,digest=hash_password(pw)
        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                    (uid,role,email,last,first,display,salt,digest,now()))
"""
new="""    def seed_user(uid,role,email,pw,last,first,display):
        r=con.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
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
if old not in s:
    raise SystemExit('seed_user target not found')
p.write_text(s.replace(old,new,1),encoding='utf-8')
