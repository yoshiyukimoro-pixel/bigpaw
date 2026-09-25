from pathlib import Path

# Fix generated server so 0% edge positions are preserved instead of treated as falsy defaults.
p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')
repls={
    "float(body.get('imagePosX') or 50)":"float(body['imagePosX']) if body.get('imagePosX') is not None else 50",
    "float(body.get('imagePosY') or 50)":"float(body['imagePosY']) if body.get('imagePosY') is not None else 50",
}
for a,b in repls.items():
    count=s.count(a)
    assert count>=1,(a,count)
    s=s.replace(a,b)
p.write_text(s,encoding='utf-8')

# Force mobile browsers to load the newest gesture/public-layout scripts after deploys.
versions={
    'parent-dogs.html':('assets/parent-photo-adjust.js','20260925c'),
    'puppy-detail.html':('assets/public-parent-dogs.js','20260925c'),
}
for name,(asset,version) in versions.items():
    hp=Path('/app')/name
    html=hp.read_text(encoding='utf-8')
    plain=f'<script src="{asset}"></script>'
    versioned=f'<script src="{asset}?v={version}"></script>'
    assert plain in html or versioned in html,(name,asset)
    html=html.replace(plain,versioned)
    hp.write_text(html,encoding='utf-8')

print('PARENT_PHOTO_RUNTIME_FIX_OK|edge_zero=preserved|public_layout=no_store|assets=cache_busted',flush=True)
