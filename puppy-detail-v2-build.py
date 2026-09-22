from pathlib import Path
import py_compile
import re

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')

# Minimal server-side fix for the breeder edit screen:
# GET /api/puppies/<id>/photos must be readable by logged-in breeder/operator accounts.
owners = "{'yoshiyukimoro@gmail.com','smrhha@i.softbank.jp','yoshi_chu@yahoo.co.jp'}"
s = s.replace("str(u.get('email','')).strip().lower()=='yoshiyukimoro@gmail.com'", f"str(u.get('email','')).strip().lower() in {owners}")
s = s.replace("str(u.get('email','')).strip().lower()!='yoshiyukimoro@gmail.com'", f"str(u.get('email','')).strip().lower() not in {owners}")

marker = "m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)"
i = s.find(marker)
patched = 0
if i >= 0:
    j = s.find("        m=", i + len(marker))
    k = s.find("        if ", i + len(marker))
    ends = [x for x in [j,k] if x > i]
    end = min(ends) if ends else min(len(s), i + 3000)
    block = s[i:end]
    block2 = re.sub(
        r"(?P<indent>[ \t]+)u\s*=\s*self\.require\([^\n]+\)\s*;?\s*\n(?P=indent)if\s+not\s+u\s*:\s*return\s*\n(?:(?P=indent)if\s+u\.get\(['\"]role['\"]\).*?403\)\s*\n)?",
        "            u=self.current_user()\n            if not u:\n                return self.send_json({'error':'unauthorized'},401)\n",
        block,
        count=1
    )
    if block2 != block:
        s = s[:i] + block2 + s[end:]
        patched = 1

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
print('BIGPAW_PHOTOS_AUTH_MIN_PATCHED', patched)
