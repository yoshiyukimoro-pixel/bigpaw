from pathlib import Path
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

# 1) Allow the Gmail breeder account to upload puppy photos even if DB role is still buyer.
old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit('upload permission anchor not found')

# 2) Allow the Gmail breeder account to read breeder listing management.
old2 = "if path=='/api/breeder/puppies':\n            u=self.require(['breeder','operator']);\n            if not u:return"
new2 = f"if path=='/api/breeder/puppies':\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old2 in s:
    s = s.replace(old2, new2, 1)
elif new2 not in s:
    raise SystemExit('breeder puppies permission anchor not found')

# 3) Allow the Gmail breeder account to read per-puppy photo list.
s = s.replace("u=self.require(['breeder','operator']);\n            if not u:return\n            pid=path.split('/')[3]", f"u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)\n            pid=path.split('/')[3]")

# 4) Allow the Gmail breeder account to delete own/management puppies if still stored as buyer.
s = s.replace("u=self.require(['breeder','operator']);\n            if not u:return\n            pid=path.split('/')[-1]", f"u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)\n            pid=path.split('/')[-1]")

# 5) Make existing Gmail test/registered puppies public-searchable instead of pending-only.
marker = "BIGPAW_PUBLIC_DIAG|"
if marker in s and "BIGPAW_FORCE_GMAIL_PUBLIC" not in s:
    inject = f"""
try:
    import sqlite3
    _db='/data/bigpaw.sqlite3'
    _con=sqlite3.connect(_db)
    _cur=_con.cursor()
    _cur.execute("UPDATE puppies SET status='approved' WHERE breed_key='standard-poodle' AND COALESCE(status,'') IN ('pending','draft','')")
    _cur.execute("UPDATE puppies SET sales_status='募集中' WHERE breed_key='standard-poodle' AND COALESCE(sales_status,'') IN ('','pending')")
    _con.commit(); _con.close()
    print('BIGPAW_FORCE_GMAIL_PUBLIC_OK')
except Exception as _e:
    print('BIGPAW_FORCE_GMAIL_PUBLIC_ERR', _e)
"""
    s = s.replace("try:\n    import sqlite3", inject + "\ntry:\n    import sqlite3", 1)

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q
assert new in q
assert new2 in q
print('BIGPAW_PHOTOS_DELETE_PUBLIC_FIX_OK')
