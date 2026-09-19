from pathlib import Path
p=Path("operator-breeders.html")
s=p.read_text(encoding="utf-8",errors="replace")
marker='<div id="apps" class="tablelike">'
if 'id="breederSearch"' not in s:
    ui='<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px"><input id="breederSearch" placeholder="犬舎名・代表者・都道府県・管理IDで検索" style="flex:1;min-width:240px"><button class="btn btn-sub" type="button" onclick="load()">検索</button></div>'
    s=s.replace(marker,ui+marker)
old="const rows=await BigPawAPI.breederApplications();apps.innerHTML=rows.length?rows.map(a=>"
new="let rows=await BigPawAPI.breederApplications();const q=(document.getElementById('breederSearch')?.value||'').trim().toLowerCase();if(q)rows=rows.filter(a=>[a.kennel_name,a.representative,a.prefecture,a.id,a.email].some(v=>String(v||'').toLowerCase().includes(q)));apps.innerHTML=rows.length?rows.map(a=>"
s=s.replace(old,new)
# Add a separate operator navigation block; links lead to existing real-data management screens.
if 'id="bpUnifiedOps"' not in s:
    ops='<div id="bpUnifiedOps" class="card pad" style="margin-bottom:14px"><b>ブリーダー運営管理</b><p class="muted">登録情報から掲載・成約・問い合わせまで一続きで確認できます。</p><div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn btn-sub" href="operator-listings.html">子犬掲載</a><a class="btn btn-sub" href="operator-deals.html">成約状況</a><a class="btn btn-sub" href="operator-support.html">問い合わせ</a><a class="btn btn-sub" href="operator-revenue.html">売上・手数料</a></div></div>'
    s=s.replace(ui+marker,ops+ui+marker) if 'id="breederSearch"' in s else s.replace(marker,ops+marker)
p.write_text(s,encoding="utf-8")
