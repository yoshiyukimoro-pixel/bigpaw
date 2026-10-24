#!/usr/bin/env python3
"""Apply the organic 5-day refresh to the *final, post-Docker-patch* server.

Never change the immutable original publish date. Give one rank refresh only
after 120 hours AND a real, substantive edit to an approved, open listing.
"""
from pathlib import Path
p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')
def once(a,b,label):
    global s
    n=s.count(a)
    if n!=1: raise RuntimeError('RANK_REFRESH_PATCH_ANCHOR_FAIL|'+label+'|count='+str(n))
    s=s.replace(a,b,1)

once("    ensure_column(con,'puppies','published_at','INTEGER')",
     "    ensure_column(con,'puppies','published_at','INTEGER')\n    ensure_column(con,'puppies','last_ranked_at','INTEGER')","schema")
once("def puppy_json(r):",
"""def maybe_bump_puppy_rank(con, puppy_id, real_edit):
    if not real_edit or not puppy_id: return False
    r=con.execute('SELECT created_at,published_at,last_ranked_at,status,review_status FROM puppies WHERE id=?',(puppy_id,)).fetchone()
    if not r or r['status']!='募集中' or r['review_status']!='approved': return False
    last=int(r['last_ranked_at'] or r['published_at'] or r['created_at'] or 0)
    t=now()
    if not last or t-last<5*24*60*60: return False
    con.execute('UPDATE puppies SET last_ranked_at=? WHERE id=?',(t,puppy_id))
    return True

def puppy_json(r):""","rank helper")
once("'imageUrl':d['image_url'],'createdAt':d['created_at'],",
     "'imageUrl':d['image_url'],'createdAt':d['created_at'],\n       'rankAt':d['last_ranked_at'] or d['published_at'] or d['created_at'],\n       'rankUpdatedAt':d['last_ranked_at'],\n       'rankAvailableAt':int(d['last_ranked_at'] or d['published_at'] or d['created_at'] or 0)+432000,","json rank time")
once("sql+=' ORDER BY p.created_at DESC'",
     "sql+=' ORDER BY COALESCE(p.last_ranked_at,p.published_at,p.created_at) DESC,p.created_at DESC,p.id DESC'","public ordering")
# Persistent status-change and save no-op are not a real content edit.
old="""            if sets:
                args.append(m.group(1)); con.execute('UPDATE puppies SET '+','.join(sets)+' WHERE id=?',args); audit(con,u['id'],'puppy_updated','puppy',m.group(1),','.join(body.keys())); con.commit()"""
new="""            if sets:
                before=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
                args.append(m.group(1))
                con.execute('UPDATE puppies SET '+','.join(sets)+' WHERE id=?',args)
                after=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
                meaningful_fields=('name','breed','breed_key','gender','color','birth','price','description','image_url','weight','adult_min','adult_max','father','mother','health')
                actually_changed=any(before[k]!=after[k] for k in meaningful_fields)
                # No credit for clicking Save unchanged or toggling listing status only.
                maybe_bump_puppy_rank(con,m.group(1),actually_changed)
                audit(con,u['id'],'puppy_updated','puppy',m.group(1),','.join(body.keys()))
                con.commit()"""
once(old,new,"edit detection")
old="""            con.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(upid,u['id'],(None if puppy_id=='breeder-proof' else puppy_id or None),original,stored,mime,now())); con.commit(); con.close()"""
new="""            con.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(upid,u['id'],(None if puppy_id=='breeder-proof' else puppy_id or None),original,stored,mime,now()))
            # Adding an actual photo counts as a meaningful listing update,
            # including if the main photo itself does not change.
            if puppy_id and puppy_id!='breeder-proof': maybe_bump_puppy_rank(con,puppy_id,True)
            con.commit(); con.close()"""
once(old,new,"photo add")
p.write_text(s,encoding='utf-8')
print('FIVE_DAY_RANK_PATCH_OK|persisted_rank_date|5days|genuine_content_or_new_photo|no_op_denied|status_not_refresh|created_date_preserved|search_order',flush=True)
