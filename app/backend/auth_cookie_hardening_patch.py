#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'backend' / 'server.py'
API = ROOT / 'assets' / 'api.js'

server = SERVER.read_text(encoding='utf-8')
api = API.read_text(encoding='utf-8')

# Browser auth: remove bearer-token persistence/use and rely on same-origin cookies.
if 'BIGPAW_COOKIE_AUTH_HARDENED_V1' not in api:
    old = "  const TOKEN='bigpaw_api_token_v1';\n  const API={\n    isLive(){return location.protocol==='http:'||location.protocol==='https:'},\n    token(){return localStorage.getItem(TOKEN)||''},\n    setToken(t){t?localStorage.setItem(TOKEN,t):localStorage.removeItem(TOKEN)},\n"
    new = "  // BIGPAW_COOKIE_AUTH_HARDENED_V1\n  const LEGACY_TOKEN='bigpaw_api_token_v1';\n  try{localStorage.removeItem(LEGACY_TOKEN)}catch(e){}\n  const API={\n    isLive(){return location.protocol==='http:'||location.protocol==='https:'},\n    token(){return ''},\n    setToken(){},\n"
    if old not in api:
        raise RuntimeError('AUTH_HARDEN_FAIL|api_token_block_missing')
    api = api.replace(old, new, 1)

    auth_line = "      if(this.token())headers['Authorization']='Bearer '+this.token();\n"
    if auth_line not in api:
        raise RuntimeError('AUTH_HARDEN_FAIL|authorization_line_missing')
    api = api.replace(auth_line, '', 1)

    fetch_old = "      const res=await fetch('/api'+path,{...opts,headers});"
    fetch_new = "      const res=await fetch('/api'+path,{...opts,headers,credentials:'same-origin'});"
    if fetch_old not in api:
        raise RuntimeError('AUTH_HARDEN_FAIL|fetch_marker_missing')
    api = api.replace(fetch_old, fetch_new, 1)
    API.write_text(api, encoding='utf-8')

# Server auth: production accepts the HttpOnly session cookie, not browser bearer headers.
old_session = """    def session_token(self):
        auth=self.headers.get('Authorization','')
        if auth.startswith('Bearer '):
            return auth[7:].strip()
        return parse_cookie_header(self.headers.get('Cookie','')).get(SESSION_COOKIE_NAME,'')
"""
new_session = """    def session_token(self):
        cookie_token=parse_cookie_header(self.headers.get('Cookie','')).get(SESSION_COOKIE_NAME,'')
        if cookie_token:
            return cookie_token
        if IS_PRODUCTION:
            return ''
        auth=self.headers.get('Authorization','')
        if auth.startswith('Bearer '):
            return auth[7:].strip()
        return ''
"""
if old_session in server:
    server = server.replace(old_session, new_session, 1)
elif new_session not in server:
    raise RuntimeError('AUTH_HARDEN_FAIL|server_session_marker_missing')

# CSRF hardening: authenticated cookie mutations without Origin/Referer are rejected.
old_origin = """        origin=self.headers.get('Origin','')
        if not origin: return True
"""
new_origin = """        origin=self.headers.get('Origin','')
        if not origin:
            referer=self.headers.get('Referer','')
            if referer:
                origin=referer
            else:
                cookie_token=parse_cookie_header(self.headers.get('Cookie','')).get(SESSION_COOKIE_NAME,'')
                return not bool(cookie_token)
"""
if old_origin in server:
    server = server.replace(old_origin, new_origin, 1)
elif new_origin not in server:
    raise RuntimeError('AUTH_HARDEN_FAIL|origin_marker_missing')

old_host = "host=='bigpaw.site' or host.endswith('.bigpaw.site') or host=='bigpaw-site-production.up.railway.app'"
new_host = "host in ('bigpaw.site','www.bigpaw.site','bigpaw-live-production.up.railway.app','bigpaw-site-production.up.railway.app')"
if old_host in server:
    server = server.replace(old_host, new_host, 1)
elif new_host not in server:
    raise RuntimeError('AUTH_HARDEN_FAIL|allowed_host_marker_missing')

SERVER.write_text(server, encoding='utf-8')

# Regression gates.
api_check = API.read_text(encoding='utf-8')
server_check = SERVER.read_text(encoding='utf-8')
assert 'BIGPAW_COOKIE_AUTH_HARDENED_V1' in api_check
assert "localStorage.getItem(TOKEN)" not in api_check
assert "headers['Authorization']='Bearer '+this.token()" not in api_check
assert "credentials:'same-origin'" in api_check
assert "if IS_PRODUCTION:\n            return ''" in server_check
assert "HttpOnly; SameSite=Lax" in server_check
assert "; Secure' if IS_PRODUCTION" in server_check
assert "self.headers.get('Referer','')" in server_check
assert "host.endswith('.bigpaw.site')" not in server_check
print('AUTH_COOKIE_HARDENING_OK|browser_bearer=disabled|cookie=HttpOnly_Secure_SameSiteLax|csrf=origin_referer_guard|production_bearer=disabled', flush=True)
