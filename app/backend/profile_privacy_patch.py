from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

# Add privacy-aware public profile validation. Rough access guidance is allowed,
# but information that identifies the actual kennel remains blocked.
marker="def public_puppy_json(r):\n"
helper=r'''def _profile_norm(value):
    return re.sub(r'[\s\u3000\-ー‐‑–—−－・,，.。/／]+','',str(value or '')).lower()

def _private_address_tokens(private_address, prefecture=''):
    addr=_profile_norm(private_address)
    pref=_profile_norm(prefecture)
    if pref and addr.startswith(pref):
        addr=addr[len(pref):]
    if not addr:
        return []
    tokens=[]
    for pat in (r'^(.+?市.+?区)',r'^(.+?市)',r'^(.+?区)',r'^(.+?郡.+?町)',r'^(.+?町)',r'^(.+?村)'):
        m=re.match(pat,addr)
        if m:
            tokens.append(m.group(1))
    return [x for i,x in enumerate(tokens) if len(x)>=2 and x not in tokens[:i]]

def public_profile_privacy_issue(text, kennel_name='', representative='', private_address='', prefecture=''):
    t=str(text or '').strip()
    if not t:
        return ''
    if public_profile_has_direct_contact(t):
        return 'direct_contact'
    if re.search(r'(?<!\d)[0-9０-９]{3}[-ー－]?[0-9０-９]{4}(?!\d)',t):
        return 'postal_code'
    norm=_profile_norm(t)
    for value,code in ((kennel_name,'kennel_name'),(representative,'representative_name')):
        v=_profile_norm(value)
        if len(v)>=2 and v in norm:
            return code
    full_addr=_profile_norm(private_address)
    if len(full_addr)>=4 and full_addr in norm:
        return 'address'
    for token in _private_address_tokens(private_address,prefecture):
        if token in norm:
            return 'address'
    # Exact street-level addresses remain blocked. Rough guidance such as
    # "与野インターから車で10分" or "○○駅から徒歩15分" is intentionally allowed.
    if re.search(r'(?:都|道|府|県).{0,24}(?:市|区|郡|町|村).{0,24}(?:[0-9０-９]|丁目|番地|番|号)',t):
        return 'address'
    return ''

def sanitize_public_profile(text, kennel_name='', private_address='', prefecture=''):
    lines=[]
    for line in str(text or '').splitlines():
        if public_profile_privacy_issue(line,kennel_name,'',private_address,prefecture):
            continue
        lines.append(line)
    return '\n'.join(lines).strip()

def public_puppy_json(r):
'''
assert s.count(marker)==1,('privacy_helper_marker',s.count(marker))
s=s.replace(marker,helper,1)

# Capture private identity before public_breeder_json removes/anonymizes it, then redact unsafe legacy lines.
a="    pref=(d.get('prefecture') or '').strip()\n    # Never expose private breeder identity/contact/review material through public APIs."
b="    pref=(d.get('prefecture') or '').strip()\n    private_kennel=(d.get('kennel_name') or '').strip()\n    private_visit=(d.get('visit_address') or '').strip() if 'visit_address' in d else ''\n    # Never expose private breeder identity/contact/review material through public APIs."
assert s.count(a)==1,('privacy_public_capture_marker',s.count(a))
s=s.replace(a,b,1)
a="    d['profile']=profile.strip()"
b="    profile=sanitize_public_profile(profile,private_kennel,private_visit,pref)\n    d['profile']=profile.strip()"
assert s.count(a)==1,('privacy_public_sanitize_marker',s.count(a))
s=s.replace(a,b,1)

# Breeder application: reject private identity/location data in the public profile before saving.
a="            if public_profile_has_direct_contact(public_profile): return self.send_json({'error':'direct_contact_not_allowed','message':'公開プロフィールには電話番号・メール・LINE・SNS・外部サイトURLを掲載できません。'},400)"
b="            privacy_issue=public_profile_privacy_issue(public_profile,body.get('kennelName',''),body.get('representative',''),body.get('visitAddress',''),body.get('prefecture',''))\n            if privacy_issue: return self.send_json({'error':'public_profile_private_info','message':'公開プロフィールには犬舎名・代表者名・市区町村以下の住所・郵便番号・電話番号・メール・LINE・SNS・外部サイトURLなど、犬舎を特定できる情報は掲載できません。ICや駅からの所要時間など大まかなアクセス案内は掲載できます。'},400)"
assert s.count(a)==1,('privacy_application_guard_marker',s.count(a))
s=s.replace(a,b,1)

# Profile edit: validate against the stored kennel name, representative and private visit address as well.
a="""            body=self.json_body();
            if 'profile' in body and public_profile_has_direct_contact(body.get('profile','')): return self.send_json({'error':'direct_contact_not_allowed','message':'公開プロフィールには電話番号・メール・LINE・SNS・外部サイトURLを掲載できません。'},400)
            con=db(); b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone() if u['role']=='breeder' else con.execute('SELECT * FROM breeders WHERE id=?',(body.get('id',''),)).fetchone()
            if not b: con.close(); return self.send_json({'error':'not_found'},404)"""
b="""            body=self.json_body();
            con=db(); b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone() if u['role']=='breeder' else con.execute('SELECT * FROM breeders WHERE id=?',(body.get('id',''),)).fetchone()
            if not b: con.close(); return self.send_json({'error':'not_found'},404)
            if 'profile' in body:
                rep=con.execute('SELECT representative FROM breeder_applications WHERE user_id=? ORDER BY updated_at DESC LIMIT 1',(b['user_id'],)).fetchone() if b['user_id'] else None
                representative=(rep['representative'] if rep else '')
                privacy_issue=public_profile_privacy_issue(body.get('profile',''),body.get('kennelName',b['kennel_name']),representative,body.get('visitAddress',b['visit_address'] if 'visit_address' in b.keys() else ''),body.get('prefecture',b['prefecture']))
                if privacy_issue:
                    con.close(); return self.send_json({'error':'public_profile_private_info','message':'紹介文は一般公開です。犬舎名・代表者名・市区町村以下の住所・郵便番号・電話番号・メール・LINE・SNS・外部サイトURLなど、犬舎を特定できる情報は記載できません。ICや駅からの所要時間など大まかなアクセス案内は記載できます。'},400)"""
assert s.count(a)==1,('privacy_profile_edit_guard_marker',s.count(a))
s=s.replace(a,b,1)

p.write_text(s,encoding='utf-8')
print('PROFILE_PRIVACY_GUARD_OK|kennel_name=blocked|representative=blocked|exact_address=blocked|rough_access=allowed',flush=True)

# Final build gate: after every backend patch has run, fail the deployment if
# role separation or ownership checks have accidentally regressed.
exec(Path('/app/backend/security_regression_check.py').read_text(encoding='utf-8'), {'__name__':'__main__'})
