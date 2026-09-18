from pathlib import Path
files=['backend/server.py','breeder-fee-agreement.html','operator-breeders.html','breeder-puppy-new.html','mypage.html','assets/api.js','assets/workflow.js']
out=[]
for fn in files:
 p=Path(fn)
 if not p.exists(): continue
 out.append('=== '+fn+' ===')
 for i,line in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines()):
  if any(k in line.lower() for k in ['breeder','application','approve','puppy','審査','申請','承認','子犬','email_verified','password','login','hash_password','admin_email']):
   out.append(f'{i+1}: {line[:1600]}')
Path('inspection.txt').write_text('\n'.join(out),encoding='utf-8')

p=Path('operator-breeders.html')
if p.exists():
 lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
 out.append('=== operator-breeders.html FULL ===')
 for i,line in enumerate(lines): out.append(f'{i+1}: {line[:4000]}')
Path('inspection.txt').write_text('\n'.join(out),encoding='utf-8')

p=Path('backend/server.py')
lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
out.append('=== UPLOAD HANDLER ===')
for i,line in enumerate(lines):
 if '/api/uploads' in line or 'UPLOADS' in line or 'stored' in line and 'upload' in line.lower():
  for j in range(max(0,i-12),min(len(lines),i+45)): out.append(f'{j+1}: {lines[j][:4000]}')
Path('inspection.txt').write_text('\n'.join(out),encoding='utf-8')

p=Path('backend/server.py'); lines=p.read_text(encoding='utf-8',errors='replace').splitlines(); out.append('=== STATIC SERVE ===');
for i,line in enumerate(lines):
 if 'SimpleHTTPRequestHandler' in line or 'translate_path' in line or "'/uploads'" in line or 'UPLOADS /' in line or 'send_head' in line:
  for j in range(max(0,i-10),min(len(lines),i+35)): out.append(f'{j+1}: {lines[j][:4000]}')
Path('inspection.txt').write_text('\n'.join(out),encoding='utf-8')

p=Path('backend/server.py'); lines=p.read_text(encoding='utf-8',errors='replace').splitlines(); out.append('=== PATCH BREEDER APPLICATION ===');
for i,line in enumerate(lines):
 if 'breeder-applications' in line and ('PATCH' in line or 'fullmatch' in line or 'path' in line):
  for j in range(max(0,i-15),min(len(lines),i+80)): out.append(f'{j+1}: {lines[j][:4000]}')
Path('inspection.txt').write_text('\n'.join(out),encoding='utf-8')

p=Path('backend/server.py'); lines=p.read_text(encoding='utf-8',errors='replace').splitlines(); out.append('=== DO PATCH ===');
for i,line in enumerate(lines):
 if 'def do_PATCH' in line:
  for j in range(i,min(len(lines),i+130)): out.append(f'{j+1}: {lines[j][:4000]}')
Path('inspection.txt').write_text('\n'.join(out),encoding='utf-8')
