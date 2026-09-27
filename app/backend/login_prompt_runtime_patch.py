#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = ROOT / 'messages.html'
LOGIN = ROOT / 'login.html'

m = MESSAGES.read_text(encoding='utf-8')
marker = 'BIGPAW_LOGIN_PROMPT_V1'

if marker not in m:
    css_old = '</style></head><body>'
    css_new = '''#loginPromptOverlay{position:fixed;inset:0;background:rgba(35,28,39,.42);display:none;align-items:center;justify-content:center;padding:20px;z-index:9999}#loginPromptOverlay.show{display:flex}#loginPromptBox{width:min(92vw,420px);background:#fff;border-radius:22px;padding:24px;box-shadow:0 18px 60px rgba(0,0,0,.2);text-align:center}#loginPromptBox h3{margin:0 0 10px;font-size:23px;color:#59465f}#loginPromptBox p{margin:0 0 18px;color:#7d7080;line-height:1.7}#loginPromptActions{display:grid;gap:10px}#loginPromptActions .btn{width:100%;box-sizing:border-box}/* BIGPAW_LOGIN_PROMPT_V1 */</style></head><body>'''
    if css_old not in m:
        raise RuntimeError('LOGIN_PROMPT_PATCH_FAIL|messages_style_marker_missing')
    m = m.replace(css_old, css_new, 1)

    modal_old = '<script src="assets/app.js"></script><script src="assets/api.js"></script><script src="assets/bridge.js"></script><script>'
    modal_new = '''<div id="loginPromptOverlay" role="dialog" aria-modal="true" aria-labelledby="loginPromptTitle"><div id="loginPromptBox"><h3 id="loginPromptTitle">ログインが必要です</h3><p>この画面を利用するにはログインしてください。<br>ログイン後、このメッセージ画面に戻ります。</p><div id="loginPromptActions"><a id="loginPromptGo" class="btn btn-main" href="login.html">ログインする</a><button class="btn btn-sub" type="button" onclick="hideLoginPrompt()">閉じる</button></div></div></div><script src="assets/app.js"></script><script src="assets/api.js"></script><script src="assets/bridge.js"></script><script>'''
    if modal_old not in m:
        raise RuntimeError('LOGIN_PROMPT_PATCH_FAIL|messages_script_marker_missing')
    m = m.replace(modal_old, modal_new, 1)

    js_old = "let selected=null,inquiries=[],me=null;const breederFilter=new URLSearchParams(location.search).get('breeder')||'';"
    js_new = """let selected=null,inquiries=[],me=null;const breederFilter=new URLSearchParams(location.search).get('breeder')||'';
function currentReturnPath(){return location.pathname+location.search+location.hash}
function showLoginPrompt(){const o=document.getElementById('loginPromptOverlay');const a=document.getElementById('loginPromptGo');if(a)a.href='login.html?next='+encodeURIComponent(currentReturnPath());if(o)o.classList.add('show')}
function hideLoginPrompt(){const o=document.getElementById('loginPromptOverlay');if(o)o.classList.remove('show')}
"""
    if js_old not in m:
        raise RuntimeError('LOGIN_PROMPT_PATCH_FAIL|messages_js_marker_missing')
    m = m.replace(js_old, js_new, 1)

    catch_old = "try{me=await BigPawBridge.me().catch(()=>null);if(me)applyRoleUI();inquiries=await BigPawBridge.inquiries();if(me?.role==='operator'&&breederFilter)inquiries=inquiries.filter(x=>String(x.breeder_id||'')===String(breederFilter))}catch(e){threads.innerHTML='<div class=\"notice\">ログインするとメッセージを利用できます。</div>';return}"
    catch_new = "try{me=await BigPawBridge.me().catch(()=>null);if(!me)throw new Error('not_authenticated');applyRoleUI();inquiries=await BigPawBridge.inquiries();if(me?.role==='operator'&&breederFilter)inquiries=inquiries.filter(x=>String(x.breeder_id||'')===String(breederFilter))}catch(e){roleNotice.textContent='ログインが必要です';threads.innerHTML='<div class=\"notice\">ログインするとメッセージを利用できます。</div>';showLoginPrompt();return}"
    if catch_old not in m:
        raise RuntimeError('LOGIN_PROMPT_PATCH_FAIL|messages_auth_marker_missing')
    m = m.replace(catch_old, catch_new, 1)
    MESSAGES.write_text(m, encoding='utf-8')

l = LOGIN.read_text(encoding='utf-8')
login_marker = 'BIGPAW_SAFE_NEXT_V1'
if login_marker not in l:
    role_old = "function requestedRole(){return new URLSearchParams(location.search).get('role')||''}"
    role_new = """function requestedRole(){return new URLSearchParams(location.search).get('role')||''}
function safeNext(){const n=new URLSearchParams(location.search).get('next')||'';if(!n||!n.startsWith('/')||n.startsWith('//'))return '';try{const u=new URL(n,location.origin);return u.origin===location.origin?(u.pathname+u.search+u.hash):''}catch(e){return ''}} // BIGPAW_SAFE_NEXT_V1"""
    if role_old not in l:
        raise RuntimeError('LOGIN_PROMPT_PATCH_FAIL|login_role_marker_missing')
    l = l.replace(role_old, role_new, 1)

    redirect_old = "location.href=role==='breeder'?'admin.html':'mypage.html'"
    redirect_new = "const next=safeNext();location.href=next||(role==='breeder'?'admin.html':'mypage.html')"
    if redirect_old not in l:
        raise RuntimeError('LOGIN_PROMPT_PATCH_FAIL|login_redirect_marker_missing')
    l = l.replace(redirect_old, redirect_new, 1)
    LOGIN.write_text(l, encoding='utf-8')

# Validation
m2 = MESSAGES.read_text(encoding='utf-8')
l2 = LOGIN.read_text(encoding='utf-8')
assert marker in m2
assert 'showLoginPrompt()' in m2
assert 'login.html?next=' in m2
assert login_marker in l2
assert 'const next=safeNext()' in l2
print('LOGIN_PROMPT_OK|messages=modal|login_return=same_page|safe_next=same_origin', flush=True)
