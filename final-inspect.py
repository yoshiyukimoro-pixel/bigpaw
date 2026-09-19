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

# Inspect DELETE/PATCH/puppy route implementation for safe editor completion.
from pathlib import Path
p=Path('backend/server.py')
if p.exists():
 t=p.read_text(encoding='utf-8')
 with open('delete-inspection.txt','w',encoding='utf-8') as o:
  for needle in ['def do_DELETE','def do_PATCH','/api/puppies/','puppies SET','DELETE FROM puppies','DELETE FROM uploads']:
   i=t.find(needle)
   o.write('\\n### '+needle+' ###\\n')
   o.write(t[max(0,i-2500):i+7000] if i>=0 else 'NOT FOUND')

# Compact route signature inspection (single-line output for Railway logs).
p=Path('backend/server.py')
if p.exists():
 t=p.read_text(encoding='utf-8')
 needles=['def do_POST','def do_PATCH','def do_DELETE','def do_PUT']
 parts=[]
 for n in needles:
  i=t.find(n); parts.append(n+':'+(t[i:i+14000].replace('\\n',' § ') if i>=0 else 'NOT_FOUND'))
 print('ROUTEINSPECT|'+'|'.join(parts))

# Compact upload/photo API inspection.
p=Path('backend/server.py')
if p.exists():
 t=p.read_text(encoding='utf-8')
 hits=[]
 for needle in ["/api/uploads","INSERT INTO uploads","SELECT * FROM uploads","SELECT stored_name FROM uploads","def puppy_json"]:
  start=0
  while True:
   i=t.find(needle,start)
   if i<0:break
   hits.append(t[max(0,i-700):i+1800].replace("\\n"," § "))
   start=i+len(needle)
 print("PHOTOINSPECT|"+" || ".join(hits[:12]))
