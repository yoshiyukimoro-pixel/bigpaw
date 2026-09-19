from pathlib import Path
s=Path("backend/server.py").read_text(encoding="utf-8",errors="replace")
for key in ["def puppy_json", 'path == "/api/puppies"', 'path.startswith("/api/puppies/")']:
 i=s.find(key)
 print("\n=== "+key+" ===")
 print(s[max(0,i-1500):i+6500] if i>=0 else "NOT FOUND")
