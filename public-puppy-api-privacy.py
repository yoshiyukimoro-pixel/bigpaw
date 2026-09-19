from pathlib import Path
p=Path("backend/server.py")
s=p.read_text(encoding="utf-8",errors="replace")
needle="def parse_cookie_header(raw: str):"
if "def public_puppy_json(" not in s:
    fn="""def public_puppy_json(r):
    d=puppy_json(r)
    if not d: return None
    area=(d.get('area') or '').strip()
    d['breeder']=(area+'のBIGPAW認定ブリーダー') if area else 'BIGPAW認定ブリーダー'
    return d

"""
    s=s.replace(needle,fn+needle)
s=s.replace("return self.send_json([puppy_json(r) for r in rows])\n        m=re.fullmatch(r'/api/puppies/([^/]+)',path)","return self.send_json([public_puppy_json(r) for r in rows])\n        m=re.fullmatch(r'/api/puppies/([^/]+)',path)",1)
s=s.replace("return self.send_json(puppy_json(r),200) if r else self.send_json({'error':'not_found'},404)\n        if path=='/api/breeders':","return self.send_json(public_puppy_json(r),200) if r else self.send_json({'error':'not_found'},404)\n        if path=='/api/breeders':",1)
s=s.replace("out['puppies']=[puppy_json(x) for x in puppies]; out['reviews']","out['puppies']=[public_puppy_json(x) for x in puppies]; out['reviews']",1)
p.write_text(s,encoding="utf-8")
