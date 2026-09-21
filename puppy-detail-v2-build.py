from pathlib import Path
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit('upload permission anchor not found')

old2 = "if path=='/api/breeder/puppies':\n            u=self.require(['breeder','operator']);\n            if not u:return"
new2 = f"if path=='/api/breeder/puppies':\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old2 in s:
    s = s.replace(old2, new2, 1)
elif new2 not in s:
    raise SystemExit('breeder puppies permission anchor not found')

# Safe, narrow permission broadening for per-puppy photo-list route.
# This does not mutate DB or public search, and it does not fail the build if the exact route shape differs.
photo_old = "u=self.require(['breeder','operator']);\n            if not u:return\n            pid=path.split('/')[3]"
photo_new = f"u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)\n            pid=path.split('/')[3]"
if photo_old in s and photo_new not in s:
    s = s.replace(photo_old, photo_new, 1)

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q
assert new in q
assert new2 in q
print('UPLOAD_BREEDER_LIST_AND_PHOTO_READ_FIX_OK')
