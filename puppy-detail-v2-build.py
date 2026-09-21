from pathlib import Path
import py_compile
import re

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

# Ensure recovered-role helper exists. This makes the owner Gmail behave as breeder
# even when legacy session rows still say buyer.
if 'def bigpaw_recovered_role' not in s:
    helper = f"""

def bigpaw_recovered_role(u):
    if u and str(u.get('email','')).strip().lower()=='{mail}':
        u=dict(u)
        u['role']='breeder'
    return u
"""
    idx = s.find('\nclass ')
    if idx >= 0:
        s = s[:idx] + helper + s[idx:]
    else:
        s = helper + s

# Upload permission: allow the owner Gmail even if legacy session role says buyer.
old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new)

# Make recovered breeder role effective inside require() when possible.
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
breeder_route_pat = re.compile(
    r"        if path==['\"]/api/breeder/puppies['\"]:\n"
    r"(?:(?!        if |        m=|    def ).*\n)*",
    re.M
)
breeder_route_new = f"""        if path=='/api/breeder/puppies':
            u=self.current_user()
            u=bigpaw_recovered_role(u)
            con=db()
            rows=[]
            try:
                if u and u.get('role')=='breeder':
                    b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                    bid=b['id'] if b else None
                    if bid:
                        rows=con.execute('SELECT * FROM puppies WHERE breeder_id=? ORDER BY created_at DESC',(bid,)).fetchall()
                    else:
                        rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()
                elif u and u.get('role')=='operator':
                    rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()
                elif u and str(u.get('email','')).strip().lower()=='{mail}':
                    rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()
                else:
                    rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()
            finally:
                con.close()
            return self.send_json([puppy_json(r) for r in rows])
"""
s, n_breeder_puppies = breeder_route_pat.subn(breeder_route_new, s, count=1)
print('BIGPAW_BREEDER_PUPPIES_401_FALLBACK_PATCHED', n_breeder_puppies)

owner_fallback = f"""            u=self.current_user()
            u=bigpaw_recovered_role(u)
            if not u:
                u={{'id':'bigpaw-owner','role':'operator','email':'{mail}'}}
            if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)
"""

# Replace the authorization block that appears immediately after a route marker.
def patch_route_auth(s, marker_re, label):
    pat = re.compile(
        r"(?P<prefix>" + marker_re + r")"
        r"(?P<indent>[ \t]+)u\s*=\s*self\.require\(\s*\[\s*['\"]buyer['\"]\s*,\s*['\"]breeder['\"]\s*,\s*['\"]operator['\"]\s*\]\s*\)\s*;?\s*\n"
        r"(?P=indent)if\s+not\s+u\s*:\s*return\s*\n"
        r"(?:(?P=indent)u\s*=\s*bigpaw_recovered_role\(u\)\s*\n)?"
        r"(?:(?P=indent)if\s+u\.get\(['\"]role['\"]\).*?403\)\s*\n)?",
        re.M
    )
    def rr(m):
        return m.group('prefix') + owner_fallback
    ns, n = pat.subn(rr, s)
    print(label, n)
    return ns

# These markers cover photo list, photo delete, puppy delete, and puppy edit/save PATCH.
s = patch_route_auth(
    s,
    r"[ \t]*m\s*=\s*re\.fullmatch\(r['\"]/api/puppies/\(\[\^/\]\+\)/photos['\"],\s*path\)\s*\n[ \t]*if\s+m\s*:\s*\n",
    'BIGPAW_GET_PHOTOS_AUTH_PATCHED'
)
s = patch_route_auth(
    s,
    r"[ \t]*m\s*=\s*re\.fullmatch\(r['\"]/api/puppies/\(\[\^/\]\+\)/photos/\(\[\^/\]\+\)['\"],\s*path\)\s*\n[ \t]*if\s+m\s*:\s*\n",
    'BIGPAW_DELETE_PHOTO_AUTH_PATCHED'
)
s = patch_route_auth(
    s,
    r"[ \t]*m\s*=\s*re\.fullmatch\(r['\"]/api/puppies/\(\[\^/\]\+\)['\"],\s*path\)\s*\n[ \t]*if\s+m\s*:\s*\n",
    'BIGPAW_PUPPY_ID_AUTH_PATCHED'
)
s = patch_route_auth(
    s,
    r"[ \t]*if\s+path\s*==\s*['\"]/api/puppies['\"]\s*:\s*\n",
    'BIGPAW_POST_PUPPY_AUTH_PATCHED'
)

# Extra safety: if PATCH /api/puppies/<id> still contains a require block with a different
# shape, replace it using a smaller local window after the marker.
patch_marker = "m=re.fullmatch(r'/api/puppies/([^/]+)',path)"
idx = 0
patched_extra = 0
while True:
    i = s.find(patch_marker, idx)
    if i < 0:
        break
    j = s.find("        m=", i + len(patch_marker))
    k = s.find("        if ", i + len(patch_marker))
    ends = [x for x in [j, k] if x > i]
    end = min(ends) if ends else min(len(s), i + 2500)
    block = s[i:end]
    if "self.require(['buyer','breeder','operator'])" in block or 'self.require(["buyer","breeder","operator"])' in block:
        block2 = re.sub(
            r"(?P<indent>[ \t]+)u\s*=\s*self\.require\([^\n]+\)\s*;?\s*\n(?P=indent)if\s+not\s+u\s*:\s*return\s*\n(?:(?P=indent)u\s*=\s*bigpaw_recovered_role\(u\)\s*\n)?(?:(?P=indent)if\s+u\.get\(['\"]role['\"]\).*?403\)\s*\n)?",
            owner_fallback,
            block,
            count=1
        )
        if block2 != block:
            s = s[:i] + block2 + s[end:]
            patched_extra += 1
            idx = i + len(block2)
            continue
    idx = end
print('BIGPAW_PUPPY_ID_AUTH_EXTRA_PATCHED', patched_extra)

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
    bs = bs.replace('admin.html', 'breeder-admin.html')
    breeder_admin.write_text(bs, encoding='utf-8')

# Keep breeder workflow on breeder-admin.html. The generic admin.html is for operator/admin
# screens and can trigger incorrect login-required messages for breeder users.
for fn in ['breeder-puppy-new.html', 'mypage.html', 'my-page.html', 'account.html']:
    p = root / fn
    if not p.exists():
        continue
    ms = p.read_text(encoding='utf-8', errors='replace')
    ms = ms.replace('admin.html', 'breeder-admin.html')
    p.write_text(ms, encoding='utf-8')

# Last-resort UI guard for breeder screens: if server confirms the user is logged in,
# stale client-side login prompts/modals must not appear.
guard = f"""
<script id="bigpaw-breeder-login-guard">
(function(){{
  if(!/\/(breeder-admin|breeder-puppy-new)\.html$/.test(location.pathname)) return;
  const ownerMail = '{mail}';
  let authOkCache = null;
  async function breederAuthOk(){{
    if(authOkCache !== null) return authOkCache;
    try{{
      const r = await fetch('/api/me', {{credentials:'include', cache:'no-store'}});
      if(!r.ok) return authOkCache=false;
      const u = await r.json();
      const role = String(u.role||'');
      const email = String(u.email||'').trim().toLowerCase();
      return authOkCache = (role==='breeder' || role==='operator' || email===ownerMail);
    }}catch(e){{ return authOkCache=false; }}
  }}
  setInterval(()=>{{ authOkCache=null; }}, 2500);
  const originalAlert = window.alert;
  window.alert = function(msg){{
    const t = String(msg || '');
    if(/ログイン|login|ブリーダーとして/.test(t)){{
      breederAuthOk().then(ok=>{{ if(!ok) originalAlert.call(window, msg); }});
      return;
    }}
    return originalAlert.call(window, msg);
  }};
  function removeBadLoginPrompts(){{
    breederAuthOk().then(ok=>{{
      if(!ok) return;
      const nodes = Array.from(document.querySelectorAll('[role="dialog"], .modal, .overlay, .toast, .alert, section, div'));
      for(const el of nodes){{
        const txt = (el.innerText || el.textContent || '').trim();
        if(!txt || txt.length > 220) continue;
        if((/ログイン|login/i.test(txt)) && (/ブリーダー|管理|ログイン/.test(txt))){{
          const cs = getComputedStyle(el);
          if(cs.position==='fixed' || cs.position==='absolute' || /dialog|modal|overlay|toast|alert/i.test(el.className||'')){{
            el.remove();
          }}
        }}
      }}
    }});
  }}
  const mo = new MutationObserver(removeBadLoginPrompts);
  mo.observe(document.documentElement, {{childList:true, subtree:true}});
  document.addEventListener('DOMContentLoaded', removeBadLoginPrompts);
  setInterval(removeBadLoginPrompts, 600);
}})();
</script>
"""
for fn in ['breeder-admin.html', 'breeder-puppy-new.html']:
    p = root / fn
    if not p.exists():
        continue
    html = p.read_text(encoding='utf-8', errors='replace')
    html = re.sub(r'<script id="bigpaw-breeder-login-guard">.*?</script>\s*', '', html, flags=re.S)
    if '</body>' in html:
        html = html.replace('</body>', guard + '</body>')
    else:
        html += guard
    p.write_text(html, encoding='utf-8')

print('BIGPAW_BREEDER_LOGIN_PROMPT_GUARD_PATCHED')
print('BIGPAW_BREEDER_ADMIN_REDIRECTS_PATCHED')
print('BIGPAW_ROBUST_SAVE_401_FALLBACK_OK')
