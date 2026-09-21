from pathlib import Path
import re

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
mail = 'yoshiyukimoro@gmail.com'

script = f'''
<script id="bigpaw-hide-breeder-login-panel-when-authenticated">
(function(){{
  if(!/(^|\/)breeder-admin\.html$/.test(location.pathname)) return;
  const ownerMail = '{mail}';
  let okCache = null;
  async function isBreederLoggedIn(){{
    if(okCache !== null) return okCache;
    try{{
      const r = await fetch('/api/me', {{credentials:'include', cache:'no-store'}});
      if(!r.ok) return okCache = false;
      const u = await r.json();
      const role = String(u.role || '');
      const email = String(u.email || '').trim().toLowerCase();
      return okCache = (role === 'breeder' || role === 'operator' || email === ownerMail);
    }}catch(e){{
      return okCache = false;
    }}
  }}
  function looksLikeLoginPanel(el){{
    const txt = (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim();
    if(!txt) return false;
    return txt.includes('ブリーダーログインが必要です') ||
           (txt.includes('ブリーダーアカウントでログインしてください') && txt.includes('ログイン'));
  }}
  function bestPanel(el){{
    let cur = el;
    for(let i=0;i<6 && cur && cur.parentElement;i++,cur=cur.parentElement){{
      const t = (cur.innerText || cur.textContent || '').replace(/\s+/g,' ').trim();
      if(t.includes('ブリーダーログインが必要です') && t.length < 260) return cur;
    }}
    return el;
  }}
  async function hideBadPanel(){{
    if(!(await isBreederLoggedIn())) return; // 未ログインなら消さない
    const all = Array.from(document.querySelectorAll('body *'));
    for(const el of all){{
      if(!looksLikeLoginPanel(el)) continue;
      const target = bestPanel(el);
      target.style.setProperty('display','none','important');
      target.setAttribute('data-bigpaw-hidden-login-panel','1');
    }}
  }}
  document.addEventListener('DOMContentLoaded', hideBadPanel);
  new MutationObserver(hideBadPanel).observe(document.documentElement, {{childList:true, subtree:true, characterData:true}});
  setInterval(function(){{ okCache=null; hideBadPanel(); }}, 800);
}})();
</script>
'''

for fn in ['breeder-admin.html']:
    p = root / fn
    if not p.exists():
        continue
    html = p.read_text(encoding='utf-8', errors='replace')
    html = re.sub(r'<script id="bigpaw-hide-breeder-login-panel-when-authenticated">.*?</script>\s*', '', html, flags=re.S)
    if '</body>' in html:
        html = html.replace('</body>', script + '</body>')
    else:
        html += script
    p.write_text(html, encoding='utf-8')

print('BIGPAW_HIDE_BREEDER_LOGIN_PANEL_WHEN_AUTHENTICATED_OK')
