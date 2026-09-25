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
new_css=".result-grid{display:block}.result-card{display:block;overflow:hidden;margin:0 0 14px;border-radius:16px;text-decoration:none;color:inherit;content-visibility:auto;contain-intrinsic-size:280px}.result-title{font-size:18px;font-weight:900;padding:13px 14px 8px;color:#38252e}.result-row{display:grid;grid-template-columns:minmax(0,48%) minmax(0,52%);gap:0;padding:0 12px 13px;align-items:start}.result-pic-wrap{position:relative;min-width:0}.result-pic{width:100%;aspect-ratio:1/1;background:#f8f4f6;overflow:hidden;display:grid;place-items:center;font-size:55px;border-radius:8px;border:1px solid #eee5e9}.result-pic img{width:100%;height:100%;object-fit:contain;object-position:center;display:block;background:#f8f4f6}.result-gender{position:absolute;right:5px;bottom:5px;padding:3px 7px;border-radius:5px;background:rgba(255,255,255,.95);border:1px solid #d8e4f4;color:#3d75a8;font-size:12px;font-weight:900;line-height:1.2}.result-info{min-width:0;padding:2px 0 0 14px}.result-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:13px;margin-bottom:8px}.result-status{display:inline-flex;align-items:center;padding:3px 7px;border-radius:5px;background:#e7f4e8;color:#3c7744;border:1px solid #b9dcbf;font-weight:800}.result-line{font-size:14px;line-height:1.55;color:#54484e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.result-info .price{font-size:22px!important;color:#e85f7d;font-weight:900;margin-top:8px;white-space:nowrap}.result-appeal{font-size:12px;line-height:1.5;color:#81747a;margin-top:7px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.result-breeder{font-size:12px;line-height:1.4;color:#b85d82;margin-top:8px;font-weight:800}.result-card:active{transform:scale(.996)}"
if old_css in s:
    s=s.replace(old_css,new_css,1)
elif new_css not in s:
    raise SystemExit(('search_result_css_marker_missing',s.count(old_css),s.count(new_css)))

old_media="@media(min-width:700px){.result-grid{grid-template-columns:repeat(3,1fr)}.result-pic{height:170px}}"
new_media="@media(min-width:700px){.result-card{margin-bottom:16px}.result-title{font-size:20px}.result-row{grid-template-columns:320px minmax(0,1fr)}.result-info{padding-left:20px}.result-line{font-size:15px}.result-info .price{font-size:24px!important}.result-appeal{font-size:13px}}"
if old_media in s:
    s=s.replace(old_media,new_media,1)
elif new_media not in s:
    raise SystemExit(('search_result_media_marker_missing',s.count(old_media),s.count(new_media)))

old_card="`<a class=\"card result-card\" href=\"puppy-detail.html?id=${encodeURIComponent(p.id)}\"><div class=\"result-pic\">${p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" alt=\"${BigPaw.esc(p.breed)}\">`:'🐾'}</div><div class=\"pad\"><h3 style=\"font-size:15px\">${BigPaw.esc(p.breed)}｜${BigPaw.esc(p.gender)}</h3><div class=\"muted\">${BigPaw.esc(p.color)}・${BigPaw.esc(p.area)}</div><div class=\"price\" style=\"font-size:20px\">${BigPaw.currency(p.price)}</div></div></a>`"
new_card="`<a class=\"card result-card\" href=\"puppy-detail.html?id=${encodeURIComponent(p.id)}\"><div class=\"result-title\">${BigPaw.esc(p.breed)}</div><div class=\"result-row\"><div class=\"result-pic-wrap\"><div class=\"result-pic\">${p.imageUrl?`<img src=\"${BigPaw.esc(String(p.imageUrl).replace('kind=card','kind=list'))}\" alt=\"${BigPaw.esc(p.breed)}\" loading=\"lazy\" decoding=\"async\" fetchpriority=\"low\">`:'🐾'}</div>${p.gender?`<span class=\"result-gender\">${BigPaw.esc(p.gender)}</span>`:''}</div><div class=\"result-info\"><div class=\"result-meta\"><span class=\"result-status\">${BigPaw.esc(p.status||'募集中')}</span><span>${BigPaw.esc(p.area||'')}</span></div><div class=\"result-line\">誕生：${BigPaw.esc(String(p.birth||'未登録').replace(/-/g,'/'))}</div><div class=\"result-line\">毛色：${BigPaw.esc(p.color||'未登録')}</div><div class=\"price\">${BigPaw.currency(p.price)} <span style=\"font-size:12px;color:#5c5357;font-weight:700\">(税込)</span></div>${p.desc?`<div class=\"result-appeal\">${BigPaw.esc(p.desc)}</div>`:''}<div class=\"result-breeder\">この子の詳細を見る ›</div></div></div></a>`"
if old_card in s:
    s=s.replace(old_card,new_card,1)
elif new_card not in s:
    raise SystemExit(('search_result_card_marker_missing',s.count(old_card),s.count(new_card)))

p.write_text(s,encoding='utf-8')
print(f'PUBLIC_SEARCH_LIST_OK|layout=photo_left_info_right|mobile=two_column|min_breeder_style=1|image=full_contain|list_variant=preserve_aspect|lazy=enabled|offscreen=content_visibility|birth_color_gender_price=shown|breeder_identity=hidden|renderdiag_removed={removed_diag}',flush=True)
