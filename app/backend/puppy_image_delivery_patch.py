from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

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

# Public list images use a lighter card variant; detail overrides the hero separately.
public_anchor="def public_puppy_json(r):\n    d=puppy_json(r)\n    if not d: return None\n"
public_new=public_anchor+"    if str(d.get('imageUrl') or '').startswith('/uploads/'):\n        d['imageUrl']='/media/'+quote(Path(str(d['imageUrl'])).name)+'?kind=card'\n"
if "'?kind=card'" not in s:
    assert s.count(public_anchor)==1,('public_media_anchor',s.count(public_anchor))
    s=s.replace(public_anchor,public_new,1)

# Optimized public media route. Every rendered variant is square so all puppy
# photos occupy exactly the same public frame. Existing originals are preserved.
get_anchor="        parsed=urlparse(self.path); path=parsed.path; q=parse_qs(parsed.query)\n"
media_route="""        mm=re.fullmatch(r'/media/([^/]+)',path)
        if mm:
            name=Path(mm.group(1)).name
            if name!=mm.group(1): return self.send_json({'error':'not_found'},404)
            src=UPLOADS/name
            if not src.exists() or not src.is_file(): return self.send_json({'error':'not_found'},404)
            con=db(); ur=con.execute('SELECT puppy_id FROM uploads WHERE stored_name=? LIMIT 1',(name,)).fetchone(); con.close()
            if ur and not ur['puppy_id']: return self.send_json({'error':'not_found'},404)
            kind=(q.get('kind') or ['hero'])[0]
            widths={'thumb':240,'card':720,'hero':1200}
            safe_kind=kind if kind in widths else 'hero'
            requested=widths[safe_kind]
            dest=PUPPY_IMAGE_CACHE/(name+'.'+safe_kind+'.webp')
            try:
                with PUPPY_IMAGE_LOCK:
                    if (not dest.exists()) or dest.stat().st_mtime < src.stat().st_mtime:
                        with Image.open(src) as im:
                            im=ImageOps.exif_transpose(im)
                            if im.mode!='RGB': im=im.convert('RGB')
                            side=max(1,min(im.size[0],im.size[1],requested))
                            im=ImageOps.fit(im,(side,side),method=Image.Resampling.LANCZOS,centering=(0.5,0.5))
                            quality=76 if safe_kind=='thumb' else (80 if safe_kind=='card' else 82)
                            tmp=dest.with_suffix(dest.suffix+'.tmp')
                            im.save(tmp,'WEBP',quality=quality,method=4)
                            tmp.replace(dest)
                raw=dest.read_bytes()
                self.send_response(200); self.send_header('Content-Type','image/webp'); self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','public, max-age=31536000, immutable'); self.end_headers(); self.wfile.write(raw); return
            except Exception as exc:
                print('PUPPY_MEDIA_ERROR|'+type(exc).__name__,flush=True)
                raw=src.read_bytes(); ext=src.suffix.lower(); ctype='image/jpeg' if ext in ('.jpg','.jpeg') else ('image/png' if ext=='.png' else ('image/webp' if ext=='.webp' else 'application/octet-stream'))
                self.send_response(200); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','public, max-age=86400'); self.end_headers(); self.wfile.write(raw); return
"""
if "mm=re.fullmatch(r'/media/([^/]+)',path)" not in s:
    assert s.count(get_anchor)==1,('media_route_anchor',s.count(get_anchor))
    s=s.replace(get_anchor,get_anchor+media_route,1)

# Public puppy-detail payload: square hero-sized main/gallery URLs. The browser
# derives tiny thumb URLs from the same stored names for the thumbnail strip.
photo_old="out['photos']=['/uploads/'+x['stored_name'] for x in ph]"
photo_new="out['imageUrl']=('/media/'+quote(Path(str(r['image_url'])).name)+'?kind=hero') if str(r['image_url'] or '').startswith('/uploads/') else out.get('imageUrl',''); out['photos']=['/media/'+quote(x['stored_name'])+'?kind=hero' for x in ph]"
assert s.count(photo_old)==1,('photo_payload_marker',s.count(photo_old))
s=s.replace(photo_old,photo_new,1)

p.write_text(s,encoding='utf-8')

print('PUPPY_IMAGE_DELIVERY_OK|hero=max1200_square|card=max720_square|thumb=max240_square|format=webp|cache=immutable|originals=preserved|public_only=guarded',flush=True)
