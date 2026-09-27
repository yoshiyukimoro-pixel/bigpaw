from pathlib import Path

server_path = Path('/app/backend/server.py')
s = server_path.read_text(encoding='utf-8')

# sales_handover_settings_patch.py injects code through a Python triple-quoted
# string. Ensure the generated server contains a literal \\n escape sequence,
# not an actual newline inside the quoted Python string.
broken = "            public_text='\n'.join(str(clean.get(k,'') or '') for k in SALES_HANDOVER_TEXT_LIMITS)\n"
fixed = "            public_text='\\n'.join(str(clean.get(k,'') or '') for k in SALES_HANDOVER_TEXT_LIMITS)\n"

if broken in s:
    s = s.replace(broken, fixed, 1)
elif fixed not in s:
    raise SystemExit('SALES_HANDOVER_POSTBUILD_FIX_FAIL|target_missing')

# Fail the Docker build immediately if any generated server syntax is invalid.
compile(s, str(server_path), 'exec')
server_path.write_text(s, encoding='utf-8')

# iPhone Safari can place its bottom browser controls over a sticky bottom save
# bar. On this page only, keep the desktop sticky bar unchanged but make the
# mobile save area normal document flow with enough bottom safe space so taps
# always reach the button. No other page or shared stylesheet is changed.
page_path = Path('/app/breeder-sales-handover.html')
page = page_path.read_text(encoding='utf-8')
old = "@media(max-width:800px){.layout{grid-template-columns:1fr}.side{display:none}.main{padding:70px 14px 18px}.field-row{grid-template-columns:1fr}.settings-wrap{max-width:none}}"
new = "@media(max-width:800px){.layout{grid-template-columns:1fr}.side{display:none}.main{padding:70px 14px calc(90px + env(safe-area-inset-bottom))}.field-row{grid-template-columns:1fr}.settings-wrap{max-width:none}.savebar{position:static;bottom:auto;-webkit-backdrop-filter:none;backdrop-filter:none;padding:14px 0 calc(16px + env(safe-area-inset-bottom));z-index:auto}.savebar .btn{min-height:54px;touch-action:manipulation}}"
if old in page:
    page = page.replace(old, new, 1)
elif new not in page:
    raise SystemExit('SALES_HANDOVER_POSTBUILD_FIX_FAIL|mobile_savebar_target_missing')
page_path.write_text(page, encoding='utf-8')

# Build-time acceptance checks for the isolated mobile save fix.
page_check = page_path.read_text(encoding='utf-8')
if 'saveBtn' not in page_check or "addEventListener('click',save)" not in page_check:
    raise SystemExit('SALES_HANDOVER_POSTBUILD_FIX_FAIL|save_handler_missing')
if '.savebar{position:static;bottom:auto' not in page_check:
    raise SystemExit('SALES_HANDOVER_POSTBUILD_FIX_FAIL|mobile_savebar_not_fixed')

print('SALES_HANDOVER_POSTBUILD_FIX_OK|server_syntax=valid|newline_escape=literal|mobile_save_tap=safe_flow', flush=True)
