from pathlib import Path
import re

p=Path('/app/search.html')
s=p.read_text(encoding='utf-8')

# Remove the old client render diagnostic. It serializes DOM/computed-style data
# into repeated /__renderdiag requests and is not part of the product UI.
removed_diag=0
for block in re.findall(r'<script\b[^>]*>.*?</script>',s,flags=re.S|re.I):
    if '__renderdiag' in block:
        s=s.replace(block,'',1); removed_diag+=1

old_css=".result-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.result-card{overflow:hidden}.result-pic{height:145px;background:#f8e9ef;overflow:hidden;display:grid;place-items:center;font-size:55px}.result-pic img{width:100%;height:100%;object-fit:cover}"
new_css=".result-grid{display:block}.result-card{display:block;overflow:hidden;margin:0 0 14px;border-radius:16px;text-decoration:none;color:inherit;content-visibility:auto;contain-intrinsic-size:250px}.result-title{font-size:18px;font-weight:900;padding:13px 14px 8px;color:#38252e}.result-row{display:grid;grid-template-columns:minmax(0,44%) minmax(0,56%);gap:0;padding:0 12px 13px}.result-pic{width:100%;aspect-ratio:1/1;background:#f8e9ef;overflow:hidden;display:grid;place-items:center;font-size:55px;border-radius:10px}.result-pic img{width:100%;height:100%;object-fit:cover;display:block}.result-info{min-width:0;padding:2px 0 0 14px}.result-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:13px;margin-bottom:8px}.result-status{display:inline-flex;align-items:center;padding:3px 7px;border-radius:5px;background:#e7f4e8;color:#3c7744;border:1px solid #b9dcbf;font-weight:800}.result-line{font-size:14px;line-height:1.5;color:#54484e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.result-info .price{font-size:22px!important;color:#e85f7d;font-weight:900;margin-top:8px;white-space:nowrap}.result-breeder{font-size:13px;line-height:1.4;color:#7a6b72;margin-top:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.result-card:active{transform:scale(.996)}"
if old_css in s:
    s=s.replace(old_css,new_css,1)
elif new_css not in s:
    raise SystemExit(('search_result_css_marker_missing',s.count(old_css),s.count(new_css)))

old_media="@media(min-width:700px){.result-grid{grid-template-columns:repeat(3,1fr)}.result-pic{height:170px}}"
new_media="@media(min-width:700px){.result-card{margin-bottom:16px}.result-title{font-size:20px}.result-row{grid-template-columns:300px minmax(0,1fr)}.result-info{padding-left:20px}.result-line{font-size:15px}.result-info .price{font-size:24px!important}}"
if old_media in s:
    s=s.replace(old_media,new_media,1)
elif new_media not in s:
    raise SystemExit(('search_result_media_marker_missing',s.count(old_media),s.count(new_media)))

old_card="`<a class=\"card result-card\" href=\"puppy-detail.html?id=${encodeURIComponent(p.id)}\"><div class=\"result-pic\">${p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" alt=\"${BigPaw.esc(p.breed)}\">`:'🐾'}</div><div class=\"pad\"><h3 style=\"font-size:15px\">${BigPaw.esc(p.breed)}｜${BigPaw.esc(p.gender)}</h3><div class=\"muted\">${BigPaw.esc(p.color)}・${BigPaw.esc(p.area)}</div><div class=\"price\" style=\"font-size:20px\">${BigPaw.currency(p.price)}</div></div></a>`"
new_card="`<a class=\"card result-card\" href=\"puppy-detail.html?id=${encodeURIComponent(p.id)}\"><div class=\"result-title\">${BigPaw.esc(p.breed)}</div><div class=\"result-row\"><div class=\"result-pic\">${p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" alt=\"${BigPaw.esc(p.breed)}\" loading=\"lazy\" decoding=\"async\" fetchpriority=\"low\">`:'🐾'}</div><div class=\"result-info\"><div class=\"result-meta\"><span class=\"result-status\">${BigPaw.esc(p.status||'募集中')}</span><span>${BigPaw.esc(p.area||'')}</span></div><div class=\"result-line\">誕生：${BigPaw.esc(String(p.birth||'未登録').replace(/-/g,'/'))}</div><div class=\"result-line\">毛色：${BigPaw.esc(p.color||'未登録')}</div><div class=\"result-line\">性別：${BigPaw.esc(p.gender||'')}</div><div class=\"price\">${BigPaw.currency(p.price)} <span style=\"font-size:12px;color:#5c5357;font-weight:700\">(税込)</span></div><div class=\"result-breeder\">${BigPaw.esc(p.breeder||'')}</div></div></div></a>`"
if old_card in s:
    s=s.replace(old_card,new_card,1)
elif new_card not in s:
    raise SystemExit(('search_result_card_marker_missing',s.count(old_card),s.count(new_card)))

p.write_text(s,encoding='utf-8')
print(f'PUBLIC_SEARCH_LIST_OK|layout=photo_left_info_right|mobile=single_column|image=square|lazy=enabled|offscreen=content_visibility|birth_color_gender_price=shown|renderdiag_removed={removed_diag}',flush=True)
