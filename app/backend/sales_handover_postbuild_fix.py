from pathlib import Path

p = Path('/app/backend/server.py')
s = p.read_text(encoding='utf-8')

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
compile(s, str(p), 'exec')
p.write_text(s, encoding='utf-8')
print('SALES_HANDOVER_POSTBUILD_FIX_OK|server_syntax=valid|newline_escape=literal', flush=True)
