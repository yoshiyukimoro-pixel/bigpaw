from pathlib import Path

p=Path(__file__).with_name('server.py')
s=p.read_text(encoding='utf-8')

# 1) Durable schema migration for existing Railway SQLite data.
marker="    ensure_column(con,'puppies','published_at','INTEGER')"
insert="""    ensure_column(con,'puppies','published_at','INTEGER')
    ensure_column(con,'puppies','breeding_allowed','INTEGER NOT NULL DEFAULT 1')
    ensure_column(con,'puppies','breeding_ng_reason',\"TEXT DEFAULT ''\")
    ensure_column(con,'puppies','breeder_sale_allowed','INTEGER NOT NULL DEFAULT 1')
    ensure_column(con,'puppies','breeder_sale_ng_reason',\"TEXT DEFAULT ''\")
    ensure_column(con,'puppies','sales_policy_set','INTEGER NOT NULL DEFAULT 0')"""
assert s.count(marker)==1,('policy_schema_marker',s.count(marker))
s=s.replace(marker,insert,1)

# 2) Fixed-choice normalizer. No free-text reason is persisted.
helper_marker='def puppy_json(r):\n'
helper="""BREEDING_NG_REASONS = (
    '一般家庭で家族として暮らしてほしいため',
    '繁殖目的での販売を行っていないため',
    '体格・サイズ等を考慮し繁殖に向かないため',
    '健康面・遺伝的リスクを考慮しているため',
    '血統・繁殖計画上、繁殖を認めていないため',
    '犬舎の繁殖方針によるため',
)
BREEDER_SALE_NG_REASONS = (
    '一般家庭にお迎えいただきたいため',
    '繁殖目的での販売を行っていないため',
    '同業ブリーダーへの販売を行っていないため',
    '転売・再販売防止のため',
    '血統・繁殖計画上、同業者への販売を行っていないため',
    '犬舎の販売方針によるため',
)

def _policy_bool(value, default=True):
    if value is None: return bool(default)
    if isinstance(value,bool): return value
    if isinstance(value,(int,float)): return bool(value)
    return str(value).strip().lower() not in ('0','false','no','off','不可','販売不可','繁殖不可')

def normalize_sales_policy(body, current=None):
    cur=dict(current) if current is not None else {}
    breeding_default=bool(cur.get('breeding_allowed',1))
    sale_default=bool(cur.get('breeder_sale_allowed',1))
    breeding=_policy_bool(body['breedingAllowed'],breeding_default) if 'breedingAllowed' in body else breeding_default
    sale=_policy_bool(body['breederSaleAllowed'],sale_default) if 'breederSaleAllowed' in body else sale_default
    breeding_reason=str(body.get('breedingNgReason',cur.get('breeding_ng_reason','')) or '').strip()
    sale_reason=str(body.get('breederSaleNgReason',cur.get('breeder_sale_ng_reason','')) or '').strip()
    if breeding:
        breeding_reason=''
    elif breeding_reason not in BREEDING_NG_REASONS:
        breeding_reason=BREEDING_NG_REASONS[0]
    if sale:
        sale_reason=''
    elif sale_reason not in BREEDER_SALE_NG_REASONS:
        sale_reason=BREEDER_SALE_NG_REASONS[0]
    return int(breeding),breeding_reason,int(sale),sale_reason

def puppy_json(r):
"""
assert s.count(helper_marker)==1,('policy_helper_marker',s.count(helper_marker))
s=s.replace(helper_marker,helper,1)

# 3) Expose policy through breeder/operator/public puppy payloads.
old="""      'reviewStatus':d.get('review_status','approved') if isinstance(d,dict) else 'approved','moderationNote':d.get('moderation_note','') if isinstance(d,dict) else ''
    }"""
new="""      'reviewStatus':d.get('review_status','approved') if isinstance(d,dict) else 'approved','moderationNote':d.get('moderation_note','') if isinstance(d,dict) else '',
      'salesPolicySet':bool(d.get('sales_policy_set',0)),
      'breedingAllowed':bool(d.get('breeding_allowed',1)),'breedingNgReason':d.get('breeding_ng_reason',''),
      'breederSaleAllowed':bool(d.get('breeder_sale_allowed',1)),'breederSaleNgReason':d.get('breeder_sale_ng_reason','')
    }"""
assert s.count(old)==1,('policy_json_marker',s.count(old))
s=s.replace(old,new,1)

# 4) Persist choices when creating a puppy, without disturbing existing INSERT shape.
old="""            audit(con,u['id'],'puppy_created','puppy',pid,review_status); con.commit(); r=con.execute('SELECT * FROM puppies WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(puppy_json(r),201)"""
new="""            breeding_allowed,breeding_reason,breeder_sale_allowed,breeder_sale_reason=normalize_sales_policy(body)
            con.execute('UPDATE puppies SET breeding_allowed=?,breeding_ng_reason=?,breeder_sale_allowed=?,breeder_sale_ng_reason=?,sales_policy_set=1 WHERE id=?',(breeding_allowed,breeding_reason,breeder_sale_allowed,breeder_sale_reason,pid))
            audit(con,u['id'],'puppy_created','puppy',pid,review_status); con.commit(); r=con.execute('SELECT * FROM puppies WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(puppy_json(r),201)"""
assert s.count(old)==1,('policy_create_marker',s.count(old))
s=s.replace(old,new,1)

# 5) Persist only normalized fixed choices on edit. This targets the post-Docker gender patch.
old="""            if 'gender' in body: sets.append('gender_key=?'); args.append('female' if body['gender']=='女の子' else 'male')
            if sets:"""
new="""            if 'gender' in body: sets.append('gender_key=?'); args.append('female' if body['gender']=='女の子' else 'male')
            if any(k in body for k in ('breedingAllowed','breedingNgReason','breederSaleAllowed','breederSaleNgReason')):
                breeding_allowed,breeding_reason,breeder_sale_allowed,breeder_sale_reason=normalize_sales_policy(body,p)
                sets.extend(['breeding_allowed=?','breeding_ng_reason=?','breeder_sale_allowed=?','breeder_sale_ng_reason=?','sales_policy_set=1'])
                args.extend([breeding_allowed,breeding_reason,breeder_sale_allowed,breeder_sale_reason])
            if sets:"""
assert s.count(old)==1,('policy_edit_marker',s.count(old))
s=s.replace(old,new,1)

# 6) Load the UI on the breeder editor and public puppy detail without rewriting those large files.
for name in ('breeder-puppy-new.html','puppy-detail.html'):
    hp=Path(__file__).resolve().parents[1]/name
    h=hp.read_text(encoding='utf-8')
    tag='<script src="assets/sales-policy.js"></script>'
    if tag not in h:
        assert '</body>' in h,(name,'missing_body')
        h=h.replace('</body>',tag+'</body>',1)
        hp.write_text(h,encoding='utf-8')

p.write_text(s,encoding='utf-8')
print('SALES_POLICY_OK|fixed_reasons_only|legacy_unset|breeding_and_breeder_sale=enabled',flush=True)
