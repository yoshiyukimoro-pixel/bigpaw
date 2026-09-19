from pathlib import Path
import re
out=[]
for fn in ['admin.html','breeder-puppy-new.html','assets/api.js','backend/server.py']:
 p=Path(fn)
 out.append('\n===== '+fn+' =====\n')
 if not p.exists():
  out.append('MISSING\n'); continue
 s=p.read_text(encoding='utf-8')
 if fn!='backend/server.py':
  out.append(s[:30000])
 else:
  pats=['CREATE TABLE IF NOT EXISTS puppies','CREATE TABLE IF NOT EXISTS uploads',"'/api/puppies'",'/api/breeder/puppies','do_PATCH','do_DELETE','/api/uploads']
  for pat in pats:
   i=s.find(pat)
   out.append('\n--- '+pat+' ---\n'+(s[max(0,i-2500):i+6500] if i>=0 else 'NOT FOUND'))
Path('final-inspection.txt').write_text(''.join(out),encoding='utf-8')
