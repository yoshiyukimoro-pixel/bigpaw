from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8',errors='replace')
for term in ['/api/breeders','breeders','kennel_name']:
 print('\n===',term,'===')
 start=0
 for _ in range(12):
  i=s.find(term,start)
  if i<0: break
  print(s[max(0,i-900):i+2200])
  start=i+len(term)
