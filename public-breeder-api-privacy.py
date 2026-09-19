from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8',errors='replace')
helper=r'''
def public_breeder_json(row):
    d=dict(row)
    pref=(d.get('prefecture') or '').strip()
    # Never expose private breeder identity/contact/review material through public APIs.
    for k in ('user_id','registration_no','registration_proof','registration_proof_path','email','phone','address','postal_code','line','line_id','instagram','sns','website','url'):
        d.pop(k,None)
    d['kennel_name']=(pref+'のBIGPAW認定ブリーダー') if pref else 'BIGPAW認定ブリーダー'
    profile=(d.get('profile') or '')
    import re as _re
    profile=_re.sub(r'\[REGISTRATION_PROOF\][^\s<]*','',profile)
    profile=_re.sub(r'https?://\S+','',profile)
    profile=_re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','',profile)
    profile=_re.sub(r'(?<!\d)(?:0\d{1,4}[-ー－]?\d{1,4}[-ー－]?\d{3,4})(?!\d)','',profile)
    profile=_re.sub(r'(?i)(?:LINE|Instagram|インスタグラム|インスタ|SNS)\s*[:：]?\s*[@\w.\-]+','',profile)
    d['profile']=profile.strip()
    return d

'''
anchor="def rate_limited(key, limit=10, window=60):"
if 'def public_breeder_json(row):' not in s and anchor in s:s=s.replace(anchor,helper+anchor)
s=s.replace("return self.send_json([dict(r) for r in rows])","return self.send_json([public_breeder_json(r) for r in rows])",1)
old="out=dict(b); out['puppies']=[puppy_json(x) for x in puppies]; out['reviews']=[dict(x) for x in reviews]"
new="out=public_breeder_json(b); out['puppies']=[puppy_json(x) for x in puppies]; out['reviews']=[dict(x) for x in reviews]"
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
