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
# Add change detection around the existing UPDATE in the *final patched* editor,
# preserving other build-patch logic, moderation, auditing and ownership checks.
mark="allowed={'status':'status'"
pos=s.index(mark)
if pos<0: raise RuntimeError('RANK_REFRESH_PATCH_ANCHOR_FAIL|edit map')
end=s.index("return self.send_json(puppy_json(r))",pos)
piece=s[pos:end]
if piece.count("            if sets:")!=1: raise RuntimeError('RANK_REFRESH_PATCH_ANCHOR_FAIL|edit if sets')
piece=piece.replace("            if sets:", "            if sets:\n                before=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()",1)
update="con.execute('UPDATE puppies SET '+','.join(sets)+' WHERE id=?',args)"
if piece.count(update)!=1: raise RuntimeError('RANK_REFRESH_PATCH_ANCHOR_FAIL|edit UPDATE count='+str(piece.count(update)))
compare="('name','breed','breed_key','gender','color','birth','price','description','image_url','weight','adult_min','adult_max','father','mother','health')"
extended=(update
          +"; after=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()"
          +"; maybe_bump_puppy_rank(con,m.group(1),any(before[k]!=after[k] for k in "+compare+"))")
piece=piece.replace(update,extended,1)
s=s[:pos]+piece+s[end:]
# Hook right before successful uploaded-photo response so upstream image
# processing/persistence may evolve without breaking this feature.
upload_reply="return self.send_json({'id':upid,'url':'/uploads/'+stored},201)"
if s.count(upload_reply)!=1: raise RuntimeError('RANK_REFRESH_PATCH_ANCHOR_FAIL|upload response|count='+str(s.count(upload_reply)))
s=s.replace(upload_reply,"""if puppy_id and puppy_id!='breeder-proof':
                _rankcon=db()
                try:
                    maybe_bump_puppy_rank(_rankcon,puppy_id,True)
                    _rankcon.commit()
                finally:
                    _rankcon.close()
            """+upload_reply,1)
p.write_text(s,encoding='utf-8')
print('FIVE_DAY_RANK_PATCH_OK|persisted_rank_date|5days|genuine_content_or_new_photo|no_op_denied|status_not_refresh|created_date_preserved|search_order',flush=True)
