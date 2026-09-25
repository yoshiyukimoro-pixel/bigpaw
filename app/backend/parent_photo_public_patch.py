from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

old="""            con=db(); hidden=con.execute('SELECT 1 FROM uploads WHERE stored_name=? AND puppy_id IS NULL LIMIT 1',(name,)).fetchone(); con.close()
            if hidden: return str(ROOT / '__not_public__')
            return str(UPLOADS / name)"""
new="""            con=db()
            hidden=con.execute(\"\"\"SELECT 1 FROM uploads u
                WHERE u.stored_name=? AND u.puppy_id IS NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM parent_dogs pd
                    WHERE pd.image_url=('/uploads/' || u.stored_name)
                  )
                LIMIT 1\"\"\",(name,)).fetchone()
            con.close()
            if hidden: return str(ROOT / '__not_public__')
            return str(UPLOADS / name)"""
assert s.count(old)==1,('parent_photo_public_marker',s.count(old))
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('PARENT_PHOTO_PUBLIC_OK|parent_dog_refs=public|unbound_uploads=private',flush=True)
