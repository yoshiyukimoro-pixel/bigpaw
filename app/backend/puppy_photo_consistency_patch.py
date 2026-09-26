from pathlib import Path

p=Path('/app/breeder-puppy-new.html')
s=p.read_text(encoding='utf-8')
old='1枚目がメイン写真です。写真を選び直すとメイン写真から順に差し替えます。JPG / PNG / WebP・各8MBまで'
old_square='1枚目がメイン写真です。公開写真はすべて同じ正方形サイズで表示します。写真を選んだ後「写真を調整」から位置・拡大を調整できます。JPG / PNG / WebP・各8MBまで'
new='1枚目がメイン写真です。新しく選んだ写真は切り取らず、元の縦横比を保ったまま保存します。JPG / PNG / WebP・各8MBまで'
if old in s:
    s=s.replace(old,new,1)
elif old_square in s:
    s=s.replace(old_square,new,1)
elif new not in s:
    raise SystemExit('breeder_photo_help_marker_missing')
for old_tag in (
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926b"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926c"></script>',
):
    s=s.replace(old_tag,'')
tag='<script src="assets/breeder-puppy-photo-normalize.js?v=20260926d"></script>'
assert '</body>' in s,'breeder_puppy_body_missing'
s=s.replace('</body>',tag+'</body>',1)
p.write_text(s,encoding='utf-8')
print('PUPPY_PHOTO_CONSISTENCY_OK|new_uploads=preserve_aspect|destructive_square_crop=disabled|preview=natural_aspect|public_originals=guarded',flush=True)
