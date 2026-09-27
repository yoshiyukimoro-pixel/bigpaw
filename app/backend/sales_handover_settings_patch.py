from pathlib import Path

ROOT = Path('/app')
server_path = ROOT / 'backend' / 'server.py'
s = server_path.read_text(encoding='utf-8')

# 1) Independent table. Existing breeder/puppy/upload schemas are not changed.
marker = "    con = db(); con.executescript(SCHEMA)\n"
insert = """    con = db(); con.executescript(SCHEMA)
    con.execute('''CREATE TABLE IF NOT EXISTS breeder_sales_handover_settings(
        breeder_id TEXT PRIMARY KEY REFERENCES breeders(id) ON DELETE CASCADE,
        settings_json TEXT NOT NULL DEFAULT '{}',
        updated_at INTEGER NOT NULL
    )''')
"""
assert s.count(marker) == 1, ('sales_handover_schema_marker', s.count(marker))
s = s.replace(marker, insert, 1)

# 2) Normalize/whitelist only fields used by the isolated settings page.
marker = "def puppy_json(r):\n"
helper = r'''SALES_HANDOVER_ALLOWED_PEDIGREE = ('JKC','日本犬保存会','秋田犬保存会')
SALES_HANDOVER_TEXT_LIMITS = {
    'pedigreeOther1':80,'pedigreeOther2':80,'pedigreeNote':1000,
    'vaccineNote':1000,'balanceTiming':200,'reservationNote':2000,
    'visitNote':1000,'handoverText':2000,'healthNote':1000,'cancellationPolicy':2000,
}

def _sales_nullable_bool(v):
    if v is None: return None
    if isinstance(v,bool): return v
    if isinstance(v,(int,float)): return bool(v)
    x=str(v).strip().lower()
    if x in ('1','true','yes','on'): return True
    if x in ('0','false','no','off'): return False
    return None

def normalize_sales_handover_settings(body):
    body=body if isinstance(body,dict) else {}
    orgs=body.get('pedigreeOrganizations',[])
    if not isinstance(orgs,list): orgs=[]
    out={'pedigreeOrganizations':[x for x in SALES_HANDOVER_ALLOWED_PEDIGREE if x in {str(v).strip() for v in orgs}]}
    for key,limit in SALES_HANDOVER_TEXT_LIMITS.items():
        out[key]=str(body.get(key,'') or '').strip()[:limit]
    for key in ('vaccineIncluded','sameDayVisit','healthExamIncluded','microchipIncluded'):
        out[key]=_sales_nullable_bool(body.get(key))
    try: amount=int(body.get('reservationAmount') or 0)
    except (TypeError,ValueError): amount=0
    try: days=int(body.get('minHandoverDays') or 0)
    except (TypeError,ValueError): days=0
    out['reservationAmount']=max(0,min(10000000,amount))
    out['minHandoverDays']=max(0,min(365,days))
    return out

def sales_handover_row_json(row):
    if not row: return {}
    try:
        data=json.loads(row['settings_json'] or '{}')
    except Exception:
        data={}
    return normalize_sales_handover_settings(data)

def puppy_json(r):
'''
assert s.count(marker) == 1, ('sales_handover_helper_marker', s.count(marker))
s = s.replace(marker, helper, 1)

# 3) GET routes: own breeder settings + read-only public settings for an approved breeder.
get_start = s.index('    def do_GET(self):')
post_start = s.index('    def do_POST(self):')
get_part = s[get_start:post_start]
marker = "        if path=='/api/breeder-profile':\n"
route = """        if path=='/api/breeder/sales-handover-settings':
            u=self.require(['breeder','operator'])
            if not u:return
            con=db()
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            else:
                bid=(q.get('breederId') or [''])[0]
                b=con.execute('SELECT id FROM breeders WHERE id=?',(bid,)).fetchone() if bid else None
            if not b: con.close(); return self.send_json({'error':'breeder_not_found'},404)
            row=con.execute('SELECT settings_json,updated_at FROM breeder_sales_handover_settings WHERE breeder_id=?',(b['id'],)).fetchone()
            out=sales_handover_row_json(row); out['breederId']=b['id']; out['configured']=bool(row)
            if row: out['updatedAt']=row['updated_at']
            con.close(); return self.send_json(out)
        msh=re.fullmatch(r'/api/breeders/([^/]+)/sales-handover-settings',path)
        if msh:
            con=db(); sync_breeder_billing_suspension(con,msh.group(1)); con.commit()
            b=con.execute("SELECT id FROM breeders WHERE id=? AND review_status='approved' AND COALESCE(billing_suspended,0)=0",(msh.group(1),)).fetchone()
            if not b: con.close(); return self.send_json({'error':'not_found'},404)
            row=con.execute('SELECT settings_json,updated_at FROM breeder_sales_handover_settings WHERE breeder_id=?',(b['id'],)).fetchone()
            out=sales_handover_row_json(row); out['configured']=bool(row)
            if row: out['updatedAt']=row['updated_at']
            con.close(); return self.send_json(out)
"""
assert get_part.count(marker) == 1, ('sales_handover_get_marker', get_part.count(marker))
get_part = get_part.replace(marker, route + marker, 1)
s = s[:get_start] + get_part + s[post_start:]

# 4) POST route: breeder can only write own settings; operator must identify breeder explicitly.
post_start = s.index('    def do_POST(self):')
post_part = s[post_start:]
marker = "        if path=='/api/breeder-profile':\n"
route = """        if path=='/api/breeder/sales-handover-settings':
            u=self.require(['breeder','operator'])
            if not u:return
            body=self.json_body(); con=db()
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            else:
                b=con.execute('SELECT id FROM breeders WHERE id=?',(str(body.get('breederId','')),)).fetchone()
            if not b: con.close(); return self.send_json({'error':'breeder_not_found'},404)
            clean=normalize_sales_handover_settings(body)
            # Public condition text must not become a route around BIG PAW direct-contact rules.
            public_text='\n'.join(str(clean.get(k,'') or '') for k in SALES_HANDOVER_TEXT_LIMITS)
            if public_profile_has_direct_contact(public_text):
                con.close(); return self.send_json({'error':'direct_contact_not_allowed','message':'販売・引渡し条件には電話番号・メール・LINE・SNS・外部URLなどの直接連絡先は記載できません。'},400)
            payload=json.dumps(clean,ensure_ascii=False,separators=(',',':'))
            con.execute('''INSERT INTO breeder_sales_handover_settings(breeder_id,settings_json,updated_at) VALUES(?,?,?)
                           ON CONFLICT(breeder_id) DO UPDATE SET settings_json=excluded.settings_json,updated_at=excluded.updated_at''',(b['id'],payload,now()))
            audit(con,u['id'],'sales_handover_settings_updated','breeder',b['id'])
            con.commit(); row=con.execute('SELECT settings_json,updated_at FROM breeder_sales_handover_settings WHERE breeder_id=?',(b['id'],)).fetchone()
            out=sales_handover_row_json(row); out['breederId']=b['id']; out['configured']=True; out['updatedAt']=row['updated_at']
            con.close(); return self.send_json(out)
"""
assert post_part.count(marker) == 1, ('sales_handover_post_marker', post_part.count(marker))
post_part = post_part.replace(marker, route + marker, 1)
s = s[:post_start] + post_part
server_path.write_text(s, encoding='utf-8')

# 5) Protect the new breeder-only page without changing existing role logic.
auth_path = ROOT / 'auth-return-fix.js'
auth = auth_path.read_text(encoding='utf-8')
a = "'/breeder-profile-edit.html','/breeder-invoice.html','/parent-dogs.html','/health-records.html'"
b = "'/breeder-profile-edit.html','/breeder-sales-handover.html','/breeder-invoice.html','/parent-dogs.html','/health-records.html'"
assert auth.count(a) == 1, ('sales_handover_auth_marker', auth.count(a))
auth = auth.replace(a,b,1)
auth_path.write_text(auth,encoding='utf-8')

# 6) Add a navigation entry. This only inserts a link; no existing action is replaced.
for rel in ('breeder-mobile-nav.js','mobile-global-nav.js'):
    p=ROOT/rel
    text=p.read_text(encoding='utf-8')
    anchor="['🏡','犬舎プロフィール','/breeder-profile-edit.html']"
    addition=anchor+",['📦','販売・引渡し設定','/breeder-sales-handover.html']"
    assert text.count(anchor) >= 1, (rel,'sales_handover_nav_marker',text.count(anchor))
    text=text.replace(anchor,addition,1)
    p.write_text(text,encoding='utf-8')

# Desktop breeder dashboard: add one isolated shortcut beside profile editing.
admin_path=ROOT/'admin.html'
admin=admin_path.read_text(encoding='utf-8')
anchor='<a class="btn btn-sub dashboard-action" href="breeder-profile-edit.html" style="margin-top:10px">🏠 犬舎プロフィールを編集</a>'
addition=anchor+'<a class="btn btn-sub dashboard-action" href="breeder-sales-handover.html" style="margin-top:10px">📦 販売・引渡し設定</a>'
assert admin.count(anchor)==1, ('sales_handover_admin_link_marker',admin.count(anchor))
admin=admin.replace(anchor,addition,1)
admin_path.write_text(admin,encoding='utf-8')

# 7) Public breeder page gets only an independent read-only renderer script.
detail_path=ROOT/'breeder-detail.html'
detail=detail_path.read_text(encoding='utf-8')
tag='<script src="assets/sales-handover-public.js"></script>'
if tag not in detail:
    assert '</body>' in detail, 'sales_handover_public_missing_body'
    detail=detail.replace('</body>',tag+'</body>',1)
    detail_path.write_text(detail,encoding='utf-8')

# 8) Extend the existing security gate so the new page is checked like every other breeder page.
sec_path=ROOT/'backend'/'security_regression_check.py'
sec=sec_path.read_text(encoding='utf-8')
a="'breeder-deal-report.html','breeder-profile-edit.html','breeder-invoice.html','parent-dogs.html','health-records.html',"
b="'breeder-deal-report.html','breeder-profile-edit.html','breeder-sales-handover.html','breeder-invoice.html','parent-dogs.html','health-records.html',"
assert sec.count(a)==1, ('sales_handover_security_page_marker',sec.count(a))
sec=sec.replace(a,b,1)
needle="    'buyer_mypage_is_buyer_only': \"const buyerOnly=['/mypage.html','/my-page.html'];\" in auth,\n"
extra=needle+"    'sales_handover_page_is_breeder_only': '/breeder-sales-handover.html' in auth and \"u=self.require(['breeder','operator'])\" in server,\n    'sales_handover_does_not_touch_puppy_detail': 'sales-handover-public.js' not in Path('/app/puppy-detail.html').read_text(encoding='utf-8'),\n"
assert sec.count(needle)==1, ('sales_handover_security_check_marker',sec.count(needle))
sec=sec.replace(needle,extra,1)
sec_path.write_text(sec,encoding='utf-8')

print('SALES_HANDOVER_SETTINGS_OK|storage=isolated_table|api=isolated|page=breeder_only|public=breeder_detail_only|puppy_detail=untouched',flush=True)
