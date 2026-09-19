from pathlib import Path
for fn in ['breeders.html','operator-admin.html','operator-breeders.html','backend/server.py']:
 f=Path(fn)
 if not f.exists(): continue
 t=f.read_text(encoding='utf-8',errors='replace')
 print('BADMINFILE|'+fn)
 for term in ['募集中','price','breeder','puppies','operator']:
  i=t.lower().find(term.lower())
  if i>=0: print('BADMIN|'+term+'|'+t[max(0,i-1800):i+6500].replace('\n',' § '))
