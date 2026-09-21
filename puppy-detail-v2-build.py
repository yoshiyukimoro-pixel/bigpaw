from pathlib import Path
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

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

# Force existing registered standard-poodle rows to be public-searchable at every startup.
startup_code = """
try:
    import sqlite3
    _db='/data/bigpaw.sqlite3'
    _con=sqlite3.connect(_db)
    _cur=_con.cursor()
    _cur.execute("UPDATE puppies SET status='approved' WHERE breed_key='standard-poodle' AND COALESCE(status,'') IN ('pending','draft','')")
    _cur.execute("UPDATE puppies SET sales_status='募集中' WHERE breed_key='standard-poodle' AND COALESCE(sales_status,'') IN ('','pending')")
    _con.commit()
    print('BIGPAW_FORCE_PUBLIC_STARTUP_OK', _cur.rowcount)
    _con.close()
except Exception as _e:
    print('BIGPAW_FORCE_PUBLIC_STARTUP_ERR', _e)
"""
if "BIGPAW_FORCE_PUBLIC_STARTUP_OK" not in s:
    anchor = "from http.server import SimpleHTTPRequestHandler"
    if anchor in s:
        s = s.replace(anchor, anchor + startup_code, 1)
    else:
        s = startup_code + "\n" + s

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q
assert "BIGPAW_FORCE_PUBLIC_STARTUP_OK" in q
print('BIGPAW_FORCE_PUBLIC_AND_PHOTO_ACCESS_PATCH_OK')
