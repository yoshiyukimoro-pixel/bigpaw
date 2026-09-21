from pathlib import Path
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')

old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = "if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='yoshiyukimoro@gmail.com': return self.send_json({'error':'forbidden'},403)"

if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit('upload permission anchor not found')

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
assert new in server.read_text(encoding='utf-8')
print('UPLOAD_PERMISSION_FIX_OK')
