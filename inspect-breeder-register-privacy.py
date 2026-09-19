from pathlib import Path
p=Path('breeder-register.html')
if p.exists():
 s=p.read_text(encoding='utf-8',errors='replace')
 for term in ['kennel','犬舎名','registration_no','profile']:
  print('\n===',term,'===')
  start=0
  for _ in range(8):
   i=s.find(term,start)
   if i<0: break
   print(s[max(0,i-700):i+1400])
   start=i+len(term)
