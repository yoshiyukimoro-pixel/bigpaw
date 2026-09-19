from pathlib import Path
spec={'backend/server.py':[(700,880),(1080,1120),(1438,1470),(1,2200)],'breeder-register.html':[(1,220)],'admin.html':[(1,220)],'mypage.html':[(1,220)],'assets/bridge.js':[(1,180)]}
out=[]
for fn,ranges in spec.items():
 p=Path(fn)
 if not p.exists(): continue
 lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
 out.append('=== '+fn+' ===')
 for a,b in ranges:
  for i in range(a-1,min(b,len(lines))): out.append(f'{i+1}: {lines[i][:2200]}')
Path('inspection2.txt').write_text('\n'.join(out),encoding='utf-8')
