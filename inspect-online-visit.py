from pathlib import Path
s=Path("backend/server.py").read_text(encoding="utf-8",errors="replace")
for key in ["CREATE TABLE IF NOT EXISTS visits","/visit", "INSERT INTO visits","UPDATE visits"]:
 print("\n===",key,"===")
 start=0
 while True:
  i=s.find(key,start)
  if i<0: break
  print(s[max(0,i-900):i+2600]); start=i+len(key)
for f in ["puppy-detail.html","messages.html"]:
 q=Path(f)
 if q.exists():
  t=q.read_text(encoding="utf-8",errors="replace")
  print("\n===FILE",f,"===\n",t[:30000])
