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

# Make recovered breeder role effective inside require().
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

# Direct diagnostic for /api/breeder/puppies because 401 may be returned before require() logging.
def route_diag_code(ind):
    return (
        f"{ind}try:\n"
        f"{ind}    _bp_cookie=self.headers.get('Cookie','')\n"
        f"{ind}    _bp_user=self.current_user()\n"
        f"{ind}    print('BIGPAW_BREEDER_PUPPIES_DIAG|path=' + str(getattr(self,'path','')) + '|cookie_present=' + str(bool(_bp_cookie)) + '|cookie_len=' + str(len(_bp_cookie)) + '|user=' + repr(_bp_user))\n"
        f"{ind}except Exception as _bp_e:\n"
        f"{ind}    print('BIGPAW_BREEDER_PUPPIES_DIAG_ERROR|' + repr(_bp_e))\n"
    )

if 'BIGPAW_BREEDER_PUPPIES_DIAG|' not in s:
    inserted = False
    route_patterns = [
        r"(?P<indent>[ \t]*)if\s+path\.startswith\(\s*['\"]\/api\/breeder\/puppies['\"]\s*\)\s*:\s*\n",
        r"(?P<indent>[ \t]*)if\s+path\s*==\s*['\"]\/api\/breeder\/puppies['\"]\s*:\s*\n",
        r"(?P<indent>[ \t]*)if\s+self\.path\.startswith\(\s*['\"]\/api\/breeder\/puppies['\"]\s*\)\s*:\s*\n",
        r"(?P<indent>[ \t]*)if\s+self\.path\s*==\s*['\"]\/api\/breeder\/puppies['\"]\s*:\s*\n",
    ]
    for pat in route_patterns:
        rgx = re.compile(pat)
        m = rgx.search(s)
        if m:
            base_ind = m.group('indent')
            body_ind = base_ind + '    '
            pos = m.end()
            s = s[:pos] + route_diag_code(body_ind) + s[pos:]
            inserted = True
            break
    if not inserted:
        # Startup snippet to locate the exact route shape without changing runtime behavior.
        startup = r'''
try:
    from pathlib import Path as _BPPath
    _bp_src = _BPPath(__file__).read_text(encoding='utf-8', errors='replace')
    _bp_i = _bp_src.find('/api/breeder/puppies')
    print('BIGPAW_BREEDER_PUPPIES_ROUTE_NOT_PATCHED|idx=' + str(_bp_i) + '|snippet=' + _bp_src[max(0,_bp_i-1200):_bp_i+2200].replace('\n','\\n')[:3400])
except Exception as _bp_e:
    print('BIGPAW_BREEDER_PUPPIES_ROUTE_NOT_PATCHED_ERROR|' + repr(_bp_e))
'''
        if 'BIGPAW_BREEDER_PUPPIES_ROUTE_NOT_PATCHED|' not in s:
            anchor = 'import os\n'
            if anchor in s:
                s = s.replace(anchor, anchor + startup + '\n', 1)
            else:
                s = startup + '\n' + s

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

print('BIGPAW_DIRECT_BREEDER_PUPPIES_DIAG_PATCH_OK')
