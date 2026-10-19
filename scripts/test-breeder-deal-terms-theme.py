from pathlib import Path

html = Path("app/terms.html").read_text(encoding="utf-8")
mobile_nav = Path("app/mobile-global-nav.js").read_text(encoding="utf-8")
assert 'if(location.hash==="#deal-scope")document.documentElement.setAttribute("data-bp-page-theme","breeder")' in html
assert '.breeder-terms-section{margin:18px 0;padding:18px;border:1px solid #b9d7f5' in html
assert 'background:#f3f8ff;color:#405a73' in html
assert '.breeder-terms-section h2{margin-top:0;color:#315f89}' in html
assert '<section id="deal-scope" class="breeder-terms-section">' in html
assert '</section><h2>8. 禁止事項</h2>' in html
assert 'html[data-bp-page-theme="breeder"] body{background:#f3f8ff!important;color:#405a73!important}' in html
assert 'html[data-bp-page-theme="breeder"] body .card{border-color:#d6e3f0!important' in html
assert "if(path.endsWith('/terms.html')&&location.hash==='#deal-scope') return 'breeder';" in mobile_nav
assert 'html[data-bp-mobile-tone="breeder"]{--bp-menu-bg:#f3f8ff;--bp-menu-border:#c5dced;--bp-menu-text:#315f89;--bp-menu-current:#dceeff}' in mobile_nav
print("BREEDER_DEAL_TERMS_BLUE_OK|anchor_theme|blue_clause|general_terms_default_preserved", flush=True)
