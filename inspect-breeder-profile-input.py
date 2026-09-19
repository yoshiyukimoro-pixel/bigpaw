from pathlib import Path
s=Path("backend/server.py").read_text(encoding="utf-8",errors="replace")
for key in ["breeder-applications", "applyBreeder", "profile=body.get", "registrationProofUrl"]:
 print("\n===",key,"===")
 start=0
 while True:
  i=s.find(key,start)
  if i<0: break
  print(s[max(0,i-1000):i+3500])
  start=i+len(key)
