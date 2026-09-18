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
