from pathlib import Path
for fn in ['operator-breeders.html','operator-listings.html','operator-deals.html','operator-support.html']:
 p=Path(fn)
 if not p.exists(): continue
 s=p.read_text(encoding='utf-8',errors='replace')
 print('\n===FILE '+fn+'===\n')
 print(s[:50000])
