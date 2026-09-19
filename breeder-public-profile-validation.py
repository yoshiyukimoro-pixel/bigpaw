from pathlib import Path
p=Path("backend/server.py")
s=p.read_text(encoding="utf-8",errors="replace")
needle="def public_puppy_json(r):"
if "def public_profile_has_direct_contact(" not in s:
 fn="""def public_profile_has_direct_contact(text):
    t=str(text or '')
    checks=[
      r'https?://|www\\.',
      r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}',
      r'(?<!\\d)(?:0\\d{1,4}[-ー‐–— ]?\\d{1,4}[-ー‐–— ]?\\d{3,4})(?!\\d)',
      r'(?i)(?:LINE|Instagram|インスタ|SNS|X|Twitter|Facebook|TikTok)\\s*[:：＠@]?',
    ]
    return any(re.search(x,t,re.I) for x in checks)

"""
 s=s.replace(needle,fn+needle)
# Application POST validation.
old="body=self.json_body(); required=['kennelName','representative','prefecture','primaryBreed','registrationNo','expiresOn']"
new="body=self.json_body(); required=['kennelName','representative','prefecture','primaryBreed','registrationNo','expiresOn']; public_profile=str(body.get('profile','')).strip();\n            if public_profile_has_direct_contact(public_profile): return self.send_json({'error':'direct_contact_not_allowed','message':'公開プロフィールには電話番号・メール・LINE・SNS・外部サイトURLを掲載できません。'},400)"
s=s.replace(old,new,1)
# Profile PATCH validation before DB open.
old2="body=self.json_body(); con=db(); b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone() if u['role']=='breeder' else con.execute('SELECT * FROM breeders WHERE id=?',(body.get('id',''),)).fetchone()"
new2="body=self.json_body();\n            if 'profile' in body and public_profile_has_direct_contact(body.get('profile','')): return self.send_json({'error':'direct_contact_not_allowed','message':'公開プロフィールには電話番号・メール・LINE・SNS・外部サイトURLを掲載できません。'},400)\n            con=db(); b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone() if u['role']=='breeder' else con.execute('SELECT * FROM breeders WHERE id=?',(body.get('id',''),)).fetchone()"
s=s.replace(old2,new2,1)
p.write_text(s,encoding="utf-8")
