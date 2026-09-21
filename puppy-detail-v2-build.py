from pathlib import Path
import py_compile
import re

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

# 1) Upload permission: allow the owner Gmail even if legacy session role says buyer.
old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new, 1)

# 2) Normalize breeder/operator API gates used by breeder management routes.
# Robust form catches spacing variants of require(['breeder','operator']).
pattern = re.compile(r"(?P<indent>[ \t]*)u\s*=\s*self\.require\(\s*\[\s*['\"]breeder['\"]\s*,\s*['\"]operator['\"]\s*\]\s*\)\s*;?\s*\n(?P=indent)if\s+not\s+u\s*:\s*return")

def repl(m):
    ind = m.group('indent')
    return (
        f"{ind}u=self.require(['buyer','breeder','operator']);\n"
        f"{ind}if not u:return\n"
        f"{ind}if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
    )

s, changed = pattern.subn(repl, s)
print('BIGPAW_BREEDER_GATE_NORMALIZED', changed)

# 2.5) Runtime diagnostic: Railway build output is sparse, so print snippets when the app starts.
diag = r'''
try:
    from pathlib import Path as _BPPath
    _bp_src = _BPPath(__file__).read_text(encoding='utf-8', errors='replace')
    for _bp_key in ['photos', 'do_DELETE', 'DELETE', '/api/puppies/']:
        _bp_idx = _bp_src.find(_bp_key)
        if _bp_idx >= 0:
            print('BIGPAW_ROUTE_SNIP|' + _bp_key + '|' + _bp_src[max(0, _bp_idx-900):_bp_idx+2200].replace('\n','\\n')[:3200])
except Exception as _bp_e:
    print('BIGPAW_ROUTE_SNIP_ERROR|' + repr(_bp_e))
'''
if 'BIGPAW_ROUTE_SNIP|' not in s:
    # Insert after imports when possible; otherwise prepend.
    anchor = 'import os\n'
    if anchor in s:
        s = s.replace(anchor, anchor + diag + '\n', 1)
    else:
        s = diag + '\n' + s

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q

# 3) Create a dedicated breeder admin page from the current breeder management screen.
admin = root / 'admin.html'
breeder_admin = root / 'breeder-admin.html'
if admin.exists():
    breeder_admin.write_text(admin.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')

if breeder_admin.exists():
    bs = breeder_admin.read_text(encoding='utf-8', errors='replace')
    bs = bs.replace('管理', 'ブリーダー管理', 1)
    bs = bs.replace('掲載管理', 'ブリーダー掲載管理')
    breeder_admin.write_text(bs, encoding='utf-8')

# 4) Send breeder users from mypage to breeder-admin.html, not generic admin.html.
for fn in ['mypage.html', 'my-page.html', 'account.html']:
    p = root / fn
    if not p.exists():
        continue
    ms = p.read_text(encoding='utf-8', errors='replace')
    ms = ms.replace('admin.html', 'breeder-admin.html')
    p.write_text(ms, encoding='utf-8')

print('BIGPAW_BREEDER_ADMIN_SPLIT_RUNTIME_DIAG_OK')
