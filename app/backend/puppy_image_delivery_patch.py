from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')
MEDIA_VERSION='20260926j1'

# Pillow-backed display variants. Originals remain untouched in /data/uploads.
import_anchor='from email.policy import default as email_policy\n'
if 'from PIL import Image, ImageOps' not in s:
    assert s.count(import_anchor)==1,('pillow_import_anchor',s.count(import_anchor))
    s=s.replace(import_anchor,import_anchor+'from PIL import Image, ImageOps\n',1)

cache_anchor="BREED_IMAGE_CACHE = DATA_DIR / 'breed-images'\nBREED_IMAGE_CACHE.mkdir(parents=True, exist_ok=True)\n"
cache_new=cache_anchor+"PUPPY_IMAGE_CACHE = DATA_DIR / 'puppy-display-images'\nPUPPY_IMAGE_CACHE.mkdir(parents=True, exist_ok=True)\nPUPPY_IMAGE_LOCK = threading.Lock()\n"
if "PUPPY_IMAGE_CACHE = DATA_DIR / 'puppy-display-images'" not in s:
    assert s.count(cache_anchor)==1,('image_cache_anchor',s.count(cache_anchor))
    s=s.replace(cache_anchor,cache_new,1)

# Public list images always use a small, versioned card variant. Versioning is
# intentional: earlier immutable media responses must never be reused by Safari.
public_anchor="def public_puppy_json(r):\n    d=puppy_json(r)\n    if not d: return None\n"
public_new=public_anchor+f"    if str(d.get('imageUrl') or '').startswith('/uploads/'):\n        d['imageUrl']='/media/'+quote(Path(str(d['imageUrl'])).name)+'?kind=card&v={MEDIA_VERSION}'\n"
if f"?kind=card&v={MEDIA_VERSION}" not in s:
    assert s.count(public_anchor)==1,('public_media_anchor',s.count(public_anchor))
    s=s.replace(public_anchor,public_new,1)

get_anchor="        parsed=urlparse(self.path); path=parsed.path; q=parse_qs(parsed.query)\n"
route=f"""        # Never send a puppy-bound original to a normal public page. Older/stale
        # detail scripts can still point at /uploads; redirect those requests to a
        # lightweight, versioned rendered variant before Safari decodes the original.
        rawm=re.fullmatch(r'/uploads/([^/]+)',path)
        if rawm and (q.get('original') or ['0'])[0] != '1':
            name=Path(rawm.group(1)).name
            con=db(); ur=con.execute('SELECT puppy_id FROM uploads WHERE stored_name=? LIMIT 1',(name,)).fetchone(); con.close()
            if ur and ur['puppy_id']:
                self.send_response(302); self.send_header('Location','/media/'+quote(name)+'?kind=card&v={MEDIA_VERSION}')
                self.send_header('Cache-Control','no-store'); self.end_headers(); return

        mm=re.fullmatch(r'/media/([^/]+)',path)
        if mm:
            name=Path(mm.group(1)).name
            if name!=mm.group(1): return self.send_json({{'error':'not_found'}},404)
            src=UPLOADS/name
            if not src.exists() or not src.is_file(): return self.send_json({{'error':'not_found'}},404)
            con=db(); ur=con.execute('SELECT puppy_id FROM uploads WHERE stored_name=? LIMIT 1',(name,)).fetchone(); con.close()
            if ur and not ur['puppy_id']: return self.send_json({{'error':'not_found'}},404)
            kind=(q.get('kind') or ['hero'])[0]
            widths={{'thumb':140,'card':480,'hero':800}}
            safe_kind=kind if kind in widths else 'hero'
            requested=widths[safe_kind]
            # v2 JPEG cache avoids any stale/corrupt WebP objects already held by Safari.
            dest=PUPPY_IMAGE_CACHE/(name+'.v2.'+safe_kind+'.jpg')
            try:
                with PUPPY_IMAGE_LOCK:
                    if (not dest.exists()) or dest.stat().st_mtime < src.stat().st_mtime:
                        with Image.open(src) as im:
                            im=ImageOps.exif_transpose(im)
                            if im.mode!='RGB': im=im.convert('RGB')
                            side=max(1,min(im.size[0],im.size[1],requested))
                            im=ImageOps.fit(im,(side,side),method=Image.Resampling.LANCZOS,centering=(0.5,0.5))
                            quality=70 if safe_kind=='thumb' else (74 if safe_kind=='card' else 78)
                            tmp=dest.with_suffix(dest.suffix+'.tmp')
                            im.save(tmp,'JPEG',quality=quality,optimize=True,progressive=True)
                            tmp.replace(dest)
                raw=dest.read_bytes()
                self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','public, max-age=31536000, immutable'); self.end_headers(); self.wfile.write(raw); return
            except Exception as exc:
                # Never fall back to a multi-megabyte original on the public route.
                print('PUPPY_MEDIA_ERROR|'+type(exc).__name__,flush=True)
                return self.send_json({{'error':'image_variant_failed'}},503)
"""
if "mm=re.fullmatch(r'/media/([^/]+)',path)" not in s:
    assert s.count(get_anchor)==1,('media_route_anchor',s.count(get_anchor))
    s=s.replace(get_anchor,get_anchor+route,1)

# A public detail page must never build an unbounded photo strip. The product UI
# allows 10 photos, so cap legacy/duplicated upload rows here as a server guard.
photo_query_old="ph=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(r['id'],)).fetchall()"
photo_query_new="ph=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=? ORDER BY created_at,id LIMIT 10',(r['id'],)).fetchall()"
if photo_query_old in s:
    s=s.replace(photo_query_old,photo_query_new,1)
elif photo_query_new not in s:
    raise SystemExit(('photo_query_marker_missing',s.count(photo_query_old),s.count(photo_query_new)))

# Public puppy-detail payload uses only versioned rendered URLs. Thumbnails are
# derived by the browser from the same stored name using kind=thumb.
photo_old="out['photos']=['/uploads/'+x['stored_name'] for x in ph]"
photo_new=f"out['imageUrl']=('/media/'+quote(Path(str(r['image_url'])).name)+'?kind=hero&v={MEDIA_VERSION}') if str(r['image_url'] or '').startswith('/uploads/') else out.get('imageUrl',''); out['photos']=['/media/'+quote(x['stored_name'])+'?kind=hero&v={MEDIA_VERSION}' for x in ph]"
assert s.count(photo_old)==1,('photo_payload_marker',s.count(photo_old))
s=s.replace(photo_old,photo_new,1)

p.write_text(s,encoding='utf-8')
print('PUPPY_IMAGE_DELIVERY_OK|hero=max800_square|card=max480_square|thumb=max140_square|format=jpeg|cache_version=20260926j1|detail_photos=max10|raw_public_uploads=redirected|original_fallback=disabled|originals=preserved',flush=True)
