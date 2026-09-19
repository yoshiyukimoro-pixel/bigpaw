from pathlib import Path
p=Path('operator-breeders.html')
s=p.read_text(encoding='utf-8',errors='replace')
needle='<div id="apps" class="tablelike">'
repl='<div class="card pad" style="margin-bottom:14px"><b>登録後の管理</b><p class="muted">登録情報・公開ページ・掲載中の子犬を確認できます。</p><div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn btn-sub" href="operator-listings.html">子犬掲載管理</a><a class="btn btn-sub" href="operator-deals.html">成約管理</a><a class="btn btn-sub" href="operator-support.html">問い合わせ管理</a></div></div><div id="apps" class="tablelike">'
if needle in s and '登録後の管理' not in s:s=s.replace(needle,repl,1)
p.write_text(s,encoding='utf-8')
