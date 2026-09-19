from pathlib import Path
s=Path("backend/server.py").read_text(encoding="utf-8",errors="replace")
for key in ["/api/puppies", "puppy_json(r)"]:
 print("\nKEY",key)
 start=0
 while True:
  i=s.find(key,start)
  if i<0: break
  print("\n---",i,"---\n",s[max(0,i-900):i+2200])
  start=i+1
