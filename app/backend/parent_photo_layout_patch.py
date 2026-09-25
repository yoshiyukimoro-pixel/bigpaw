from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

# Persistent crop/focus controls for parent-dog photos.
marker="    ensure_column(con,'breeders','billing_suspension_reason',\"TEXT DEFAULT ''\")\n"
extra=(marker+
"    ensure_column(con,'parent_dogs','image_pos_x','REAL NOT NULL DEFAULT 50')\n"
"    ensure_column(con,'parent_dogs','image_pos_y','REAL NOT NULL DEFAULT 50')\n"
"    ensure_column(con,'parent_dogs','image_zoom','REAL NOT NULL DEFAULT 1.0')\n")
assert s.count(marker)==1,('parent_layout_schema_marker',s.count(marker))
s=s.replace(marker,extra,1)

# Legacy/dev seed inserts must remain valid after columns are added.
seed="INSERT INTO parent_dogs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)"
seed_explicit="INSERT INTO parent_dogs(id,breeder_id,name,sex,breed,color,height_cm,weight_kg,genetics,health_summary,notes,image_url,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)"
assert s.count(seed)>=2,('parent_seed_insert_count',s.count(seed))
s=s.replace(seed,seed_explicit)

# Parent registration stores optional display position/zoom.
old="""            pid=make_id('pd_'); con.execute('INSERT INTO parent_dogs(id,breeder_id,name,sex,breed,color,height_cm,weight_kg,genetics,health_summary,notes,image_url,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (pid,breeder_id,body.get('name',''),body.get('sex','父犬'),body.get('breed',''),body.get('color',''),body.get('heightCm') or None,body.get('weightKg') or None,body.get('genetics',''),body.get('healthSummary',''),body.get('notes',''),body.get('imageUrl',''),now()))"""
new="""            pos_x=max(0.0,min(100.0,float(body.get('imagePosX',50) or 50)))
            pos_y=max(0.0,min(100.0,float(body.get('imagePosY',50) or 50)))
            zoom=max(1.0,min(3.0,float(body.get('imageZoom',1) or 1)))
            pid=make_id('pd_'); con.execute('''INSERT INTO parent_dogs(id,breeder_id,name,sex,breed,color,height_cm,weight_kg,genetics,health_summary,notes,image_url,image_pos_x,image_pos_y,image_zoom,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (pid,breeder_id,body.get('name',''),body.get('sex','父犬'),body.get('breed',''),body.get('color',''),body.get('heightCm') or None,body.get('weightKg') or None,body.get('genetics',''),body.get('healthSummary',''),body.get('notes',''),body.get('imageUrl',''),pos_x,pos_y,zoom,now()))"""
assert s.count(old)==1,('parent_create_layout_marker',s.count(old))
s=s.replace(old,new,1)

# Breeders may adjust only their own parent-dog photo/genetic tests; operator may adjust any.
patch_marker="        mlist=re.fullmatch(r'/api/operator/listings/([^/]+)',path)\n"
route="""        mpd=re.fullmatch(r'/api/parent-dogs/([^/]+)',path)
        if mpd:
            u=self.require(['breeder','operator']);
            if not u:return
            body=self.json_body(); con=db(); d=con.execute('SELECT * FROM parent_dogs WHERE id=?',(mpd.group(1),)).fetchone()
            if not d: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or d['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            sets=[]; args=[]
            if 'imagePosX' in body: sets.append('image_pos_x=?'); args.append(max(0.0,min(100.0,float(body.get('imagePosX') or 50))))
            if 'imagePosY' in body: sets.append('image_pos_y=?'); args.append(max(0.0,min(100.0,float(body.get('imagePosY') or 50))))
            if 'imageZoom' in body: sets.append('image_zoom=?'); args.append(max(1.0,min(3.0,float(body.get('imageZoom') or 1))))
            if 'imageUrl' in body: sets.append('image_url=?'); args.append(str(body.get('imageUrl') or ''))
            if 'genetics' in body: sets.append('genetics=?'); args.append(str(body.get('genetics') or '')[:4000])
            if not sets: con.close(); return self.send_json(dict(d))
            args.append(d['id']); con.execute('UPDATE parent_dogs SET '+','.join(sets)+' WHERE id=?',args); audit(con,u['id'],'parent_dog_updated','parent_dog',d['id'],','.join(body.keys())); con.commit(); out=con.execute('SELECT * FROM parent_dogs WHERE id=?',(d['id'],)).fetchone(); con.close(); return self.send_json(dict(out))
"""
assert s.count(patch_marker)==1,('parent_patch_route_marker',s.count(patch_marker))
s=s.replace(patch_marker,route+patch_marker,1)

# Public puppy detail receives only safe parent presentation fields for the selected sire/dam.
old="out=public_puppy_json(r); ph=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(r['id'],)).fetchall(); out['photos']=['/uploads/'+x['stored_name'] for x in ph]; con.close(); return self.send_json(out,200)"
new="""out=public_puppy_json(r); ph=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(r['id'],)).fetchall(); out['photos']=['/uploads/'+x['stored_name'] for x in ph]
            parent_out={}
            if r['breeder_id']:
                for key,sex,name in (('father','父犬',r['father']),('mother','母犬',r['mother'])):
                    if not str(name or '').strip(): continue
                    pd=con.execute('''SELECT name,sex,breed,color,genetics,image_url,image_pos_x,image_pos_y,image_zoom FROM parent_dogs
                        WHERE breeder_id=? AND name=? ORDER BY CASE WHEN sex=? THEN 0 ELSE 1 END, created_at DESC LIMIT 1''',(r['breeder_id'],str(name).strip(),sex)).fetchone()
                    if pd:
                        parent_out[key]={'name':pd['name'],'sex':pd['sex'],'breed':pd['breed'],'color':pd['color'],'genetics':pd['genetics'] or '',
                            'imageUrl':pd['image_url'] or '','imagePosX':float(pd['image_pos_x'] if pd['image_pos_x'] is not None else 50),'imagePosY':float(pd['image_pos_y'] if pd['image_pos_y'] is not None else 50),
                            'imageZoom':float(pd['image_zoom'] if pd['image_zoom'] is not None else 1)}
            out['parentDogs']=parent_out; con.close(); return self.send_json(out,200)"""
assert s.count(old)==1,('public_parent_payload_marker',s.count(old))
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')

# Load enhanced photo UI only on relevant pages.
for html_name,asset in [('parent-dogs.html','assets/parent-photo-adjust.js'),('puppy-detail.html','assets/public-parent-dogs.js')]:
    hp=Path('/app')/html_name
    html=hp.read_text(encoding='utf-8')
    tag=f'<script src="{asset}"></script>'
    if tag not in html:
        assert '</body>' in html,('parent_layout_html_body_missing',html_name)
        html=html.replace('</body>',tag+'</body>',1)
        hp.write_text(html,encoding='utf-8')

# Structured genetic-test editors/displays.
for html_name,tag in [
    ('parent-dogs.html','<script src="assets/parent-genetics.js?v=20260925a"></script>'),
    ('puppy-detail.html','<script src="assets/public-parent-genetics.js?v=20260925a"></script>')
]:
    hp=Path('/app')/html_name
    html=hp.read_text(encoding='utf-8')
    if tag not in html:
        assert '</body>' in html,('parent_genetics_html_body_missing',html_name)
        html=html.replace('</body>',tag+'</body>',1)
        hp.write_text(html,encoding='utf-8')

# Breed-aware genetic-test suggestions and easy parent-management entry points.
page_tags={
    'parent-dogs.html':[
        '<script src="assets/breed-data.js?v=20260925a"></script>',
        '<script src="assets/breed-genetics-data.js?v=20260925a"></script>',
        '<script src="assets/breed-genetics-suggestions.js?v=20260925a"></script>'
    ],
    'admin.html':['<script src="assets/breeder-parent-entry.js?v=20260925a"></script>'],
    'breeder-profile-edit.html':['<script src="assets/breeder-parent-entry.js?v=20260925a"></script>']
}
for html_name,tags in page_tags.items():
    hp=Path('/app')/html_name
    html=hp.read_text(encoding='utf-8')
    for tag in tags:
        if tag not in html:
            assert '</body>' in html,('breed_genetics_ui_body_missing',html_name)
            html=html.replace('</body>',tag+'</body>',1)
    hp.write_text(html,encoding='utf-8')

# Apply edge-position preservation and mobile cache-busting after the generated routes/tags exist.
exec(Path('/app/backend/parent_photo_runtime_fix.py').read_text(encoding='utf-8'))

print('PARENT_PHOTO_LAYOUT_OK|position_xy=stored|zoom=stored|public_puppy_parents=attached|genetics=editable_public|breed_suggestions=60|parent_entry=prominent|owner_scoped=1',flush=True)
