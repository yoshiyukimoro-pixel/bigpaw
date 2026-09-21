from pathlib import Path
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p = root / 'backend/server.py'
s = p.read_text(encoding='utf-8')
email = 'yoshiyukimoro@gmail.com'

old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = "if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!=email: return self.send_json({'error':'forbidden'},403)"
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    print('upload permission already patched or anchor not found')

# This project has multiple generated auth gates. Patch all breeder-list role gates that still require breeder/operator only.
patterns = [
    "u=self.require(['breeder','operator']);\n            if not u:return",
    "u=self.require(['breeder','operator'])\n            if not u:return",
]
for pat in patterns:
    if pat in s:
        s = s.replace(
            pat,
            "u=self.require(['buyer','breeder','operator']);\n            if not u:return\n            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!=email: return self.send_json({'error':'forbidden'},403)",
        )

p.write_text(s, encoding='utf-8')
py_compile.compile(str(p), doraise=True)
q = p.read_text(encoding='utf-8')
assert "str(u.get('email','')).strip().lower()!=email" in q
print('UPLOAD_AND_BREEDER_LIST_PERMISSION_FIX_OK')
