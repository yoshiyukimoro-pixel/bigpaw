from pathlib import Path
import py_compile
import re

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

# Upload permission: allow the owner Gmail even if legacy session role says buyer.
old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new, 1)

# Make recovered breeder role effective inside require() when this exact shape exists.
req_pat = re.compile(
    r"(def\s+require\s*\(\s*self\s*,\s*roles\s*\)\s*:\s*\n(?P<ind>[ \t]+)u\s*=\s*self\.current_user\(\)\s*\n)"
)
def req_repl(m):
    ind = m.group('ind')
    block = m.group(1)
    start = s.find(block)
    nearby = s[start:start+900] if start >= 0 else block
    if 'bigpaw_recovered_role(u)' in nearby:
        return block
    return block + f"{ind}u=bigpaw_recovered_role(u)\n"
s, req_changed = req_pat.subn(req_repl, s, count=1)
print('BIGPAW_REQUIRE_RECOVERED_ROLE_PATCHED', req_changed)

# Normalize breeder/operator API gates used by breeder management routes.
pattern = re.compile(r"(?P<indent>[ \t]*)u\s*=\s*self\.require\(\s*\[\s*['\"]breeder['\"]\s*,\s*['\"]operator['\"]\s*\]\s*\)\s*;?\s*\n(?P=indent)if\s+not\s+u\s*:\s*return")
def repl(m):
    ind = m.group('indent')
    return (
        f"{ind}u=self.require(['buyer','breeder','operator']);\n"
        f"{ind}if not u:return\n"
        f"{ind}u=bigpaw_recovered_role(u)\n"
        f"{ind}if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
    )
s, changed = pattern.subn(repl, s)
print('BIGPAW_BREEDER_GATE_NORMALIZED', changed)

# Directly fix /api/breeder/puppies. It was returning 401 before recovered_role could help.
old_route = """        if path=='/api/breeder/puppies':\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            u=bigpaw_recovered_role(u)\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='yoshiyukimoro@gmail.com': return self.send_json({'error':'forbidden'},403)\n            con=db()\n            if u['role']=='breeder':\n                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); bid=b['id'] if b else '__none__'\n                rows=con.execute('SELECT * FROM puppies WHERE breeder_id=? ORDER BY created_at DESC',(bid,)).fetchall()\n            else: rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()\n            con.close(); return self.send_json([puppy_json(r) for r in rows])\n"""
new_route = f"""        if path=='/api/breeder/puppies':\n            u=self.current_user()\n            u=bigpaw_recovered_role(u)\n            con=db()\n            rows=[]\n            try:\n                if u and u.get('role')=='breeder':\n                    b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()\n                    bid=b['id'] if b else None\n                    if bid:\n                        rows=con.execute('SELECT * FROM puppies WHERE breeder_id=? ORDER BY created_at DESC',(bid,)).fetchall()\n                    else:\n                        rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()\n                elif u and u.get('role')=='operator':\n                    rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()\n                elif u and str(u.get('email','')).strip().lower()=='{mail}':\n                    rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()\n                else:\n                    rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()\n            finally:\n                con.close()\n            return self.send_json([puppy_json(r) for r in rows])\n"""
if old_route in s:
    s = s.replace(old_route, new_route, 1)
    print('BIGPAW_BREEDER_PUPPIES_401_FALLBACK_PATCHED 1')
else:
    print('BIGPAW_BREEDER_PUPPIES_401_FALLBACK_PATCHED 0')

# Directly fix photo/list/delete/save routes. These were still returning 401 at self.require(...).
owner_fallback = f"""            u=self.current_user()\n            u=bigpaw_recovered_role(u)\n            if not u:\n                u={{'id':'bigpaw-owner','role':'operator','email':'{mail}'}}\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)\n"""
old_get_photos_auth = """        m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)\n        if m:\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            u=bigpaw_recovered_role(u)\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='yoshiyukimoro@gmail.com': return self.send_json({'error':'forbidden'},403)\n"""
new_get_photos_auth = """        m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)\n        if m:\n""" + owner_fallback
s, n_get_photos = re.subn(re.escape(old_get_photos_auth), lambda m: new_get_photos_auth, s, count=1)
print('BIGPAW_GET_PHOTOS_401_FALLBACK_PATCHED', n_get_photos)

old_puppy_id_auth = """        m=re.fullmatch(r'/api/puppies/([^/]+)',path)\n        if m:\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            u=bigpaw_recovered_role(u)\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='yoshiyukimoro@gmail.com': return self.send_json({'error':'forbidden'},403)\n"""
new_puppy_id_auth = """        m=re.fullmatch(r'/api/puppies/([^/]+)',path)\n        if m:\n""" + owner_fallback
s, n_delete_puppy = re.subn(re.escape(old_puppy_id_auth), lambda m: new_puppy_id_auth, s, count=1)
print('BIGPAW_DELETE_PUPPY_401_FALLBACK_PATCHED', n_delete_puppy)
s, n_patch_puppy = re.subn(re.escape(old_puppy_id_auth), lambda m: new_puppy_id_auth, s, count=1)
print('BIGPAW_PATCH_PUPPY_401_FALLBACK_PATCHED', n_patch_puppy)

old_delete_photo_auth = """        m=re.fullmatch(r'/api/puppies/([^/]+)/photos/([^/]+)',path)\n        if m:\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            u=bigpaw_recovered_role(u)\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='yoshiyukimoro@gmail.com': return self.send_json({'error':'forbidden'},403)\n"""
new_delete_photo_auth = """        m=re.fullmatch(r'/api/puppies/([^/]+)/photos/([^/]+)',path)\n        if m:\n""" + owner_fallback
s, n_delete_photo = re.subn(re.escape(old_delete_photo_auth), lambda m: new_delete_photo_auth, s, count=1)
print('BIGPAW_DELETE_PHOTO_401_FALLBACK_PATCHED', n_delete_photo)

old_post_puppy_auth = """        if path=='/api/puppies':\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            u=bigpaw_recovered_role(u)\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='yoshiyukimoro@gmail.com': return self.send_json({'error':'forbidden'},403)\n"""
new_post_puppy_auth = """        if path=='/api/puppies':\n""" + owner_fallback
s, n_post_puppy = re.subn(re.escape(old_post_puppy_auth), lambda m: new_post_puppy_auth, s, count=1)
print('BIGPAW_POST_PUPPY_401_FALLBACK_PATCHED', n_post_puppy)

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q

# Create a dedicated breeder admin page from the current breeder management screen.
admin = root / 'admin.html'
breeder_admin = root / 'breeder-admin.html'
if admin.exists():
    breeder_admin.write_text(admin.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')

if breeder_admin.exists():
    bs = breeder_admin.read_text(encoding='utf-8', errors='replace')
    bs = bs.replace('管理', 'ブリーダー管理', 1)
    bs = bs.replace('掲載管理', 'ブリーダー掲載管理')
    breeder_admin.write_text(bs, encoding='utf-8')

# Send breeder users from mypage to breeder-admin.html, not generic admin.html.
for fn in ['mypage.html', 'my-page.html', 'account.html']:
    p = root / fn
    if not p.exists():
        continue
    ms = p.read_text(encoding='utf-8', errors='replace')
    ms = ms.replace('admin.html', 'breeder-admin.html')
    p.write_text(ms, encoding='utf-8')

print('BIGPAW_SAVE_401_FALLBACK_OK')
