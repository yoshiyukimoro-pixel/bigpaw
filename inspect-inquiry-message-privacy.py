from pathlib import Path
s=Path("backend/server.py").read_text(encoding="utf-8",errors="replace")
for key in ["/messages", "/api/inquiries/", "INSERT INTO messages", "body.get('message'", "body.get('body'"]:
 print("\n===",key,"===")
 start=0
 n=0
 while True:
  i=s.find(key,start)
  if i<0 or n>=12: break
  print("\n---\n"+s[max(0,i-1000):i+3000])
  start=i+len(key); n+=1
