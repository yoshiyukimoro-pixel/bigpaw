from pathlib import Path
import re

p=Path('/app/breeder-puppy-new.html')
s=p.read_text(encoding='utf-8')
old_texts=(
    '1枚目がメイン写真です。写真を選び直すとメイン写真から順に差し替えます。JPG / PNG / WebP・各8MBまで',
    '1枚目がメイン写真です。公開写真はすべて同じ正方形サイズで表示します。写真を選んだ後「写真を調整」から位置・拡大を調整できます。JPG / PNG / WebP・各8MBまで',
    '1枚目がメイン写真です。新しく選んだ写真は切り取らず、元の縦横比を保ったまま保存します。JPG / PNG / WebP・各8MBまで',
    '1枚目がメイン写真です。掲載枠は正方形です。「写真を調整」から写真全体が入った状態を起点に、位置・拡大縮小をブリーダー様ご自身で調整できます。JPG / PNG / WebP・各8MBまで',
    '1枚目がメイン写真です。掲載枠は正方形です。「写真を調整」で元写真を見ながら、白い正方形枠に合わせて位置・拡大縮小をブリーダー様ご自身で決められます。JPG / PNG / WebP・各8MBまで',
)
new='編集時は登録済み写真を残したまま、新しく選んだ写真だけを追加します。登録済み＋追加予定で最大10枚です。掲載枠は正方形で「写真を調整」から位置・拡大縮小を変更できます。JPG / PNG / WebP・各8MBまで'
if new not in s:
    for old in old_texts:
        if old in s:
            s=s.replace(old,new,1)
            break
    else:
        raise SystemExit('breeder_photo_help_marker_missing')

# Editing must append newly chosen files instead of replacing the pending selection.
old_change="photo.addEventListener('change',()=>{selectedPhotos=[...photo.files].slice(0,10);syncPhotoInput();renderSelectedPhotos()});"
new_change="photo.addEventListener('change',()=>{const incoming=[...photo.files];const saved=editId&&Array.isArray(window.persistedPhotos)?window.persistedPhotos.length:0;const room=Math.max(0,10-saved-selectedPhotos.length);if(incoming.length>room)alert('写真は登録済み写真を含めて最大10枚までです。');selectedPhotos=selectedPhotos.concat(incoming.slice(0,room));syncPhotoInput();renderSelectedPhotos()});"
if new_change not in s:
    assert s.count(old_change)==1,('photo_additive_change_marker',s.count(old_change))
    s=s.replace(old_change,new_change,1)

# On edit, only upload the remaining number of slots and do not silently replace the current main photo.
old_files="const fs=[...photo.files].slice(0,10);"
new_files="const savedPhotoCount=editId&&Array.isArray(window.persistedPhotos)?window.persistedPhotos.length:0;const fs=[...photo.files].slice(0,Math.max(0,10-savedPhotoCount));"
if new_files not in s:
    assert s.count(old_files)==1,('photo_slot_limit_marker',s.count(old_files))
    s=s.replace(old_files,new_files,1)
old_main="if(i===0&&up.url)puppy=await BigPawBridge.updatePuppy(puppy.id,{imageUrl:up.url})"
new_main="if((!editId||savedPhotoCount===0)&&i===0&&up.url)puppy=await BigPawBridge.updatePuppy(puppy.id,{imageUrl:up.url})"
if new_main not in s:
    assert s.count(old_main)==1,('photo_edit_main_guard_marker',s.count(old_main))
    s=s.replace(old_main,new_main,1)

# Remove the legacy full-screen editor so only the unified crop-overlay editor remains.
s,n=re.subn(r'\s*<script id="bigpaw-final-photo-editor">.*?</script>\s*','\n',s,count=1,flags=re.S|re.I)
if 'id="bigpaw-final-photo-editor"' in s:
    raise SystemExit('legacy_photo_editor_still_present')

for old_tag in (
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926b"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926c"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926d"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926e"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926f"></script>',
    '<script src="assets/breeder-puppy-photo-normalize.js?v=20260926g"></script>',
    '<script src="assets/breeder-puppy-photo-append.js?v=20260926a"></script>',
):
    s=s.replace(old_tag,'')
normalize='<script src="assets/breeder-puppy-photo-normalize.js?v=20260926g"></script>'
append='<script src="assets/breeder-puppy-photo-append.js?v=20260926a"></script>'
assert '</body>' in s,'breeder_puppy_body_missing'
s=s.replace('</body>',normalize+append+'</body>',1)
p.write_text(s,encoding='utf-8')
print('PUPPY_PHOTO_CONSISTENCY_OK|square_frame=fixed|editor=crop_overlay|edit_upload=append_existing|existing_photos=preserved|total_limit=10|edit_main=preserved|combined_preview=enabled|asset_append=20260926a',flush=True)
