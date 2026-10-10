#!/usr/bin/env python3
"""Fail-closed, additive build integration for opt-in favorite change messages.

Run after all existing BIG PAW build-time patches. Never edit source/main.
"""
from pathlib import Path

path=Path(__file__).with_name('server.py')
src=path.read_text(encoding='utf-8')
if 'from favorite_updates import (' in src:
    print('FAVORITE_INTEGRATION_ALREADY_APPLIED',flush=True)
    raise SystemExit(0)

def replace_once(old,new):
    global src
    count=src.count(old)
    if count!=1:raise SystemExit(f'FAVORITE_INTEGRATION_FAILED|anchor={old[:85]!r}|count={count}')
    src=src.replace(old,new,1)

replace_once('from email.policy import default as email_policy\n',
'''from email.policy import default as email_policy
from favorite_updates import (
    ensure_schema as ensure_favorite_schema,
    queue_change as queue_favorite_change,
    record_view as record_puppy_view,
    engagement as favorite_engagement,
    deliver_due as deliver_favorite_updates,
)
''')
replace_once("    ensure_column(con,'users','email_verified','INTEGER NOT NULL DEFAULT 0')",
"""    ensure_column(con,'users','email_verified','INTEGER NOT NULL DEFAULT 0')
    ensure_column(con,'users','favorite_email_enabled','INTEGER NOT NULL DEFAULT 0')
    ensure_favorite_schema(con)""")
replace_once("def run_automations_once():\n",
"""def run_automations_once():
    # Run favorite digests from the existing automation cycle, without changing
    # the return shape or clobbering other runtime-added automation jobs.
    deliver_favorite_updates(db,PUBLIC_BASE_URL)
""")
get_anchor="""        if path=='/api/favorites':
            u=self.require(['buyer']);"""
replace_once(get_anchor,'''        if path=='/api/favorite-notifications/settings':
            u=self.require(['buyer'])
            if not u:return
            return self.send_json({'enabled':bool(u.get('favorite_email_enabled',0))})
        if path=='/api/breeder/engagement':
            u=self.require(['breeder','operator'])
            if not u:return
            con=db()
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                breeder_id=b['id'] if b else ''
            else:
                breeder_id=(q.get('breederId') or [''])[0]
                if not breeder_id:
                    con.close()
                    return self.send_json({'error':'breeder_id_required'},400)
            data=favorite_engagement(con,breeder_id) if breeder_id else {}
            con.close()
            return self.send_json({'puppies':data})
'''+get_anchor)
post_anchor="""        m=re.fullmatch(r'/api/favorites/([^/]+)',path)
        if m:"""
replace_once(post_anchor,'''        vm=re.fullmatch(r'/api/puppies/([^/]+)/view',path)
        if vm:
            current=self.current_user()
            if current and current['role'] in ('breeder','operator'):
                return self.send_json({'ok':True,'counted':False})
            if rate_limited('puppy_view:'+self.client_address[0],120,3600):
                return self.send_json({'ok':True,'counted':False})
            body=self.json_body()
            visitor=body.get('visitorId','') if isinstance(body,dict) else ''
            con=db()
            counted=record_puppy_view(con,vm.group(1),visitor,
                self.client_address[0],self.headers.get('User-Agent',''))
            con.commit();con.close()
            return self.send_json({'ok':True,'counted':counted})
'''+post_anchor)
replace_once("""            con.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(upid,u['id'],(None if puppy_id=='breeder-proof' else puppy_id or None),original,stored,mime,now())); con.commit(); con.close()""",
"""            con.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(upid,u['id'],(None if puppy_id=='breeder-proof' else puppy_id or None),original,stored,mime,now()))
            if puppy_id and puppy_id!='breeder-proof':
                queue_favorite_change(con,puppy_id,'photo',photo_url='/uploads/'+stored)
            con.commit(); con.close()""")
patch_anchor="""    def do_PATCH(self):
        path=urlparse(self.path).path
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        if path=='/api/me':"""
replace_once(patch_anchor,'''    def do_PATCH(self):
        path=urlparse(self.path).path
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        if path=='/api/favorite-notifications/settings':
            u=self.require(['buyer'])
            if not u:return
            body=self.json_body()
            if not isinstance(body,dict) or type(body.get('enabled')) is not bool:
                return self.send_json({'error':'enabled_boolean_required'},400)
            enabled=int(body['enabled'])
            con=db()
            con.execute('UPDATE users SET favorite_email_enabled=? WHERE id=?',(enabled,u['id']))
            con.commit();con.close()
            return self.send_json({'enabled':bool(enabled)})
        if path=='/api/me':''')
replace_once("""                args.append(m.group(1)); con.execute('UPDATE puppies SET '+','.join(sets)+' WHERE id=?',args); audit(con,u['id'],'puppy_updated','puppy',m.group(1),','.join(body.keys())); con.commit()""",
"""                args.append(m.group(1)); con.execute('UPDATE puppies SET '+','.join(sets)+' WHERE id=?',args)
                if 'price' in body and int(p['price'])!=int(body['price']):
                    queue_favorite_change(con,p['id'],'price',old_price=int(p['price']),new_price=int(body['price']))
                if 'imageUrl' in body and str(p['image_url'] or '')!=str(body['imageUrl'] or ''):
                    queue_favorite_change(con,p['id'],'photo',photo_url=str(body['imageUrl'] or ''))
                if 'desc' in body and str(p['description'] or '')!=str(body['desc'] or ''):
                    queue_favorite_change(con,p['id'],'description')
                if 'status' in body and str(p['status'] or '')!=str(body['status'] or ''):
                    queue_favorite_change(con,p['id'],'status')
                audit(con,u['id'],'puppy_updated','puppy',m.group(1),','.join(body.keys())); con.commit()""")
replace_once("""                con.execute('UPDATE puppies SET image_url=? WHERE id=?',(('/uploads/'+nxt['stored_name']) if nxt else '',puppy['id']))
            con.commit(); con.close()""",
"""                con.execute('UPDATE puppies SET image_url=? WHERE id=?',(('/uploads/'+nxt['stored_name']) if nxt else '',puppy['id']))
            if con.execute('SELECT 1 FROM uploads WHERE puppy_id=? LIMIT 1',(puppy['id'],)).fetchone():
                current=con.execute('SELECT image_url FROM puppies WHERE id=?',(puppy['id'],)).fetchone()
                queue_favorite_change(con,puppy['id'],'photo',photo_url=current['image_url'] if current else '')
            con.commit(); con.close()""")
compile(src,str(path),'exec')
path.write_text(src,encoding='utf-8')
print('FAVORITE_INTEGRATION_OK|settings=enabled|batch_mail=enabled|analytics=enabled|photo_event=enabled',flush=True)
