from pathlib import Path
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

# Always prepend a safe startup DB public-state fix once.
startup_code = """
# BIGPAW_FORCE_PUBLIC_STARTUP_BLOCK
try:
    import sqlite3 as _bigpaw_sqlite3
    _bigpaw_db='/data/bigpaw.sqlite3'
    _bigpaw_con=_bigpaw_sqlite3.connect(_bigpaw_db)
    _bigpaw_cur=_bigpaw_con.cursor()
    _bigpaw_cur.execute("UPDATE puppies SET status='approved' WHERE breed_key='standard-poodle' AND COALESCE(status,'') IN ('pending','draft','')")
    _bigpaw_cur.execute("UPDATE puppies SET sales_status='募集中' WHERE breed_key='standard-poodle' AND COALESCE(sales_status,'') IN ('','pending')")
    _bigpaw_con.commit()
    _bigpaw_con.close()
    print('BIGPAW_FORCE_PUBLIC_STARTUP_OK')
except Exception as _bigpaw_e:
    print('BIGPAW_FORCE_PUBLIC_STARTUP_ERR', _bigpaw_e)
# BIGPAW_FORCE_PUBLIC_STARTUP_BLOCK_END
"""
if 'BIGPAW_FORCE_PUBLIC_STARTUP_BLOCK' not in s:
    s = startup_code + "\n" + s

# Allow the Gmail breeder account to upload puppy photos even if DB role is still buyer.
old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new, 1)

# Allow the Gmail breeder account to read breeder listing management.
old2 = "if path=='/api/breeder/puppies':\n            u=self.require(['breeder','operator']);\n            if not u:return"
new2 = f"if path=='/api/breeder/puppies':\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old2 in s:
    s = s.replace(old2, new2, 1)

# Broaden common breeder/operator gates that are used by photo-list and delete routes.
common_old = "u=self.require(['breeder','operator']);\n            if not u:return\n            pid=path.split('/')[3]"
common_new = f"u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)\n            pid=path.split('/')[3]"
s = s.replace(common_old, common_new)

common_old2 = "u=self.require(['breeder','operator']);\n            if not u:return\n            pid=path.split('/')[-1]"
common_new2 = f"u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)\n            pid=path.split('/')[-1]"
s = s.replace(common_old2, common_new2)

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q
assert "BIGPAW_FORCE_PUBLIC_STARTUP_BLOCK" in q
print('BIGPAW_FORCE_PUBLIC_AND_PHOTO_ACCESS_PATCH_OK')
