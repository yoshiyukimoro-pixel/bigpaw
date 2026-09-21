from pathlib import Path
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
email = 'yoshiyukimoro@gmail.com'

old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = "if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!=email: return self.send_json({'error':'forbidden'},403)"
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit('upload permission anchor not found')

# Allow the Gmail breeder account to read breeder listing management even if the stored DB role is still buyer.
old2 = "if path=='/api/breeder/puppies':\n            u=self.require(['breeder','operator']);\n            if not u:return"
new2 = "if path=='/api/breeder/puppies':\n            u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!=email: return self.send_json({'error':'forbidden'},403)"
if old2 in s:
    s = s.replace(old2, new2, 1)
elif new2 not in s:
    raise SystemExit('breeder puppies permission anchor not found')

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert new in q
assert new2 in q
print('UPLOAD_AND_BREEDER_LIST_PERMISSION_FIX_OK')
