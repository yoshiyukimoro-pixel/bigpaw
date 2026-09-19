from pathlib import Path
p=Path('operator-breeders.html')
s=p.read_text(encoding='utf-8',errors='replace')
s=s.replace('<h1>ブリーダー審査</h1><p>第一種動物取扱業情報・犬舎情報を確認して承認します。</p>','<h1>ブリーダー管理</h1><p>新規審査と、承認済みブリーダーの登録情報・掲載状況を管理します。</p>')
s=s.replace('<div id="apps" class="tablelike">','<div class="chips" style="margin-bottom:14px"><span class="chip">審査待ち</span><span class="chip">承認済み</span><span class="chip">差し戻し</span></div><div id="apps" class="tablelike">')
s=s.replace("<b>${esc(a.kennel_name)}</b>｜${esc(a.primary_breed)}<br>","<b>${esc(a.kennel_name)}</b>｜${esc(a.primary_breed)}<br><span class=\"muted\">管理ID：${esc(a.id)}</span><br>")
s=s.replace("第一種動物取扱業 登録証の写しを確認</a></div>","第一種動物取扱業 登録証の写しを確認</a> <a class=\"btn btn-sub\" href=\"breeders.html\" target=\"_blank\">公開ページ確認</a></div>")
p.write_text(s,encoding='utf-8')
