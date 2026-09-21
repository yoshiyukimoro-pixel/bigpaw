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

# 2) Make recovered breeder role effective inside all require() checks, and log why 401 happens.
req_pat = re.compile(
    r"(def\s+require\s*\(\s*self\s*,\s*roles\s*\)\s*:\s*\n(?P<ind>[ \t]+)u\s*=\s*self\.current_user\(\)\s*\n)"
)

def req_repl(m):
    ind = m.group('ind')
    block = m.group(1)
    start = s.find(block)
    nearby = s[start:start+900] if start >= 0 else block
    if 'BIGPAW_AUTH_DIAG' in nearby:
        return block
    diag = (
        f"{ind}try:\n"
        f"{ind}    if not u:\n"
        f"{ind}        _bp_cookie=self.headers.get('Cookie','')\n"
        f"{ind}        print('BIGPAW_AUTH_DIAG|path=' + str(getattr(self,'path','')) + '|roles=' + str(roles) + '|cookie_present=' + str(bool(_bp_cookie)) + '|cookie_len=' + str(len(_bp_cookie)))\n"
        f"{ind}except Exception as _bp_e:\n"
        f"{ind}    print('BIGPAW_AUTH_DIAG_ERROR|' + repr(_bp_e))\n"
        f"{ind}u=bigpaw_recovered_role(u)\n"
    )
    return block + diag

s, req_changed = req_pat.subn(req_repl, s, count=1)
print('BIGPAW_REQUIRE_RECOVERED_ROLE_PATCHED', req_changed)

# 3) Normalize breeder/operator API gates used by breeder management routes.
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

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q

# 4) Create a dedicated breeder admin page from the current breeder management screen.
admin = root / 'admin.html'
breeder_admin = root / 'breeder-admin.html'
if admin.exists():
    breeder_admin.write_text(admin.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')

if breeder_admin.exists():
    bs = breeder_admin.read_text(encoding='utf-8', errors='replace')
    bs = bs.replace('管理', 'ブリーダー管理', 1)
    bs = bs.replace('掲載管理', 'ブリーダー掲載管理')
    breeder_admin.write_text(bs, encoding='utf-8')

# 5) Send breeder users from mypage to breeder-admin.html, not generic admin.html.
for fn in ['mypage.html', 'my-page.html', 'account.html']:
    p = root / fn
    if not p.exists():
        continue
    ms = p.read_text(encoding='utf-8', errors='replace')
    ms = ms.replace('admin.html', 'breeder-admin.html')
    p.write_text(ms, encoding='utf-8')

print('BIGPAW_AUTH_DIAG_PATCH_OK')
