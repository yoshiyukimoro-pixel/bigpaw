from pathlib import Path
import re
import py_compile

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p = root / 'backend/server.py'
s = p.read_text(encoding='utf-8')

marker = "m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)"
i = s.find(marker)
if i >= 0:
    ends = [x for x in [s.find('        m=', i + 1), s.find('        if path', i + 1)] if x > i]
    end = min(ends) if ends else min(len(s), i + 3000)
    block = s[i:end]
    block = block.replace("u=self.require(['breeder','operator'])", "u=self.require(['buyer','breeder','operator'])")
    block = block.replace('u=self.require(["breeder","operator"])', 'u=self.require(["buyer","breeder","operator"])')
    block = block.replace("if u.get('role')=='buyer': return self.send_json({'error':'forbidden'},403)", "if u.get('role')=='buyer' and str(u.get('email','')).strip().lower() not in {'yoshiyukimoro@gmail.com','smrhha@i.softbank.jp','yoshi_chu@yahoo.co.jp'}: return self.send_json({'error':'forbidden'},403)")
    block = block.replace("if u['role']=='buyer': return self.send_json({'error':'forbidden'},403)", "if u['role']=='buyer' and str(u.get('email','')).strip().lower() not in {'yoshiyukimoro@gmail.com','smrhha@i.softbank.jp','yoshi_chu@yahoo.co.jp'}: return self.send_json({'error':'forbidden'},403)")
    s = s[:i] + block + s[end:]

p.write_text(s, encoding='utf-8')
py_compile.compile(str(p), doraise=True)
print('BIGPAW_PHOTO_AUTH_FIX_OK')

# BIGPAW deploy trigger 2026-09-22: ensure Railway rebuilds photo authorization fix.
