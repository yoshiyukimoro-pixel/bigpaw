from pathlib import Path

p=Path('/app/breeder-puppy-new.html')
s=p.read_text(encoding='utf-8')
old='1枚目がメイン写真です。写真を選び直すとメイン写真から順に差し替えます。JPG / PNG / WebP・各8MBまで'
new='1枚目がメイン写真です。公開写真はすべて同じ正方形サイズで表示します。写真を選んだ後「写真を調整」から位置・拡大を調整できます。JPG / PNG / WebP・各8MBまで'
if old in s:s=s.replace(old,new,1)
tag='<script src="assets/breeder-puppy-photo-normalize.js?v=20260926b"></script>'
if tag not in s:
    assert '</body>' in s,'breeder_puppy_body_missing'
    s=s.replace('</body>',tag+'</body>',1)
p.write_text(s,encoding='utf-8')
print('PUPPY_PHOTO_CONSISTENCY_OK|public_ratio=1x1|breeder_adjust=enabled|upload=client_square_compressed|public_originals=guarded',flush=True)
