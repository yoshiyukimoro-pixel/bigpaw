from pathlib import Path

# BIGPAW operator role fix
# Purpose: accounts registered through the operator/admin flow must not become normal users.

p = Path('backend/server.py')
s = p.read_text(encoding='utf-8')

if 'BIGPAW_OPERATOR_ROLE_FIX' not in s:
    # Insert after JSON body parsing in POST handler.
    markers = [
        "data=json.loads(body.decode('utf-8') or '{}')",
        "data = json.loads(body.decode('utf-8') or '{}')",
    ]
    marker = next((m for m in markers if m in s), None)
    if not marker:
        raise SystemExit('BIGPAW_OPERATOR_ROLE_FIX: request JSON marker not found')

    inject = """
            # BIGPAW_OPERATOR_ROLE_FIX
            try:
                _path = self.path.split('?', 1)[0]
                if _path in ('/api/register', '/api/signup'):
                    _op = data.get('operator_signup') or data.get('operatorSignup') or data.get('operator')
                    if str(_op).lower() in ('1', 'true', 'yes', 'operator', 'admin'):
                        data['role'] = 'operator'
                        data['user_type'] = 'operator'
                        data['account_type'] = 'operator'
            except Exception:
                pass
"""
    s = s.replace(marker, marker + inject, 1)

# Make common role assignments respect data['role'] when present.
for old, new in [
    ("role=data.get('role','user')", "role=data.get('role') or 'user'"),
    ("role = data.get('role','user')", "role = data.get('role') or 'user'"),
    ("role=data.get('role') or 'user'", "role=data.get('role') or 'user'"),
    ("role = data.get('role') or 'user'", "role = data.get('role') or 'user'"),
]:
    s = s.replace(old, new)

p.write_text(s, encoding='utf-8')

# Frontend marker: operator pages mark the session; register page adds an operator flag to register JSON requests.
js = Path('operator-role-fix.js')
js.write_text("""
(()=>{
  const K='bigpaw_operator_register';
  if(location.pathname.endsWith('/operator-admin.html')||location.pathname.endsWith('/operator-breeders.html')) sessionStorage.setItem(K,'1');
  if(sessionStorage.getItem(K)==='1'){
    const oldFetch=window.fetch;
    window.fetch=function(input, init){
      try{
        const url=String(typeof input==='string'?input:(input&&input.url)||'');
        if(url.includes('/api/register') && init && init.body){
          const b=JSON.parse(init.body);
          b.operator_signup=true; b.role='operator'; b.user_type='operator'; b.account_type='operator';
          init={...init, body:JSON.stringify(b)};
        }
      }catch(e){}
      return oldFetch.call(this,input,init).then(r=>{
        try{ if(location.pathname.endsWith('/mypage.html')) location.href='/operator-admin.html'; }catch(e){}
        return r;
      });
    };
  }
})();
""", encoding='utf-8')

tag='<script src="/operator-role-fix.js"></script>'
for name in ['operator-admin.html','operator-breeders.html','register.html','login.html','mypage.html']:
    f=Path(name)
    if f.exists():
        t=f.read_text(encoding='utf-8',errors='replace')
        if tag not in t:
            t=t.replace('</body>', tag+'</body>') if '</body>' in t else t+tag
        f.write_text(t,encoding='utf-8')

print('BIGPAW_OPERATOR_ROLE_FIX applied')
