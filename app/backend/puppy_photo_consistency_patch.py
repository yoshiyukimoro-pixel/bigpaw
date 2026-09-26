from pathlib import Path
import re

p=Path('/app/breeder-puppy-new.html')
s=p.read_text(encoding='utf-8')
old_texts=(
    '1枚目がメイン写真です。写真を選び直すとメイン写真から順に差し替えます。JPG / PNG / WebP・各8MBまで',
    '1枚目がメイン写真です。公開写真はすべて同じ正方形サイズで表示します。写真を選んだ後「写真を調整」から位置・拡大を調整できます。JPG / PNG / WebP・各8MBまで',
    '1枚目がメイン写真です。新しく選んだ写真は切り取らず、元の縦横比を保ったまま保存します。JPG / PNG / WebP・各8MBまで',
)
new='1枚目がメイン写真です。掲載枠は正方形です。「写真を調整」から写真全体が入った状態を起点に、位置・拡大縮小をブリーダー様ご自身で調整できます。JPG / PNG / WebP・各8MBまで'
if new not in s:
    for old in old_texts:
        if old in s:
            s=s.replace(old,new,1)
            break
    else:
        raise SystemExit('breeder_photo_help_marker_missing')

# Remove the legacy full-screen editor that always started from cover/crop.
s,n=re.subn(r'\s*<script id="bigpaw-final-photo-editor">.*?</script>\s*','\n',s,count=1,flags=re.S|re.I)
if 'id="bigpaw-final-photo-editor"' in s:
    raise SystemExit('legacy_photo_editor_still_present')

for old_tag in (
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926b"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926c"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926d"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926e"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926f"></script>',
):
    s=s.replace(old_tag,'')
tag='<script src="assets/breeder-puppy-photo-normalize.js?v=20260926f"></script>'
assert '</body>' in s,'breeder_puppy_body_missing'
s=s.replace('</body>',tag+'</body>',1)
p.write_text(s,encoding='utf-8')
print('PUPPY_PHOTO_CONSISTENCY_OK|square_frame=fixed|initial=contain|breeder_pinch_pan=enabled|adjusted_square_saved=enabled|auto_cover_crop=disabled|legacy_final_editor=removed|asset_version=20260926f',flush=True)
