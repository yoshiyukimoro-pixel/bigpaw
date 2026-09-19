from pathlib import Path
p=Path('breeder-register.html')
s=p.read_text(encoding='utf-8',errors='replace')
s=s.replace('<label>犬舎名（運営審査用・非公開） *</label><input id="kennel" placeholder="DOG44" required>','<label>犬舎名（運営審査用・非公開） *</label><input id="kennel" placeholder="例：DOG44" required><small class="muted">本人確認・審査のため運営のみが使用します。一般ユーザーには公開されません。</small>')
s=s.replace('<label>第一種動物取扱業 登録番号 *</label><input id="registrationNo" required>','<label>第一種動物取扱業 登録番号（非公開） *</label><input id="registrationNo" required><small class="muted">審査・登録確認用です。一般公開ページには表示しません。</small>')
s=s.replace('<label>第一種動物取扱業 登録証の写し *</label><input id="registrationProof" type="file" accept="image/*,.pdf" required><small class="muted">登録証の写真またはPDFをアップロードしてください。</small>','<label>第一種動物取扱業 登録証の写し（非公開） *</label><input id="registrationProof" type="file" accept="image/*,.pdf" required><small class="muted">運営審査専用です。登録証の写真またはPDFをアップロードしてください。一般公開されません。</small>')
s=s.replace('<div class="field"><label>犬舎紹介</label><textarea id="profile" placeholder="飼育環境、繁殖方針、お迎え後のサポートなど"></textarea></div>','<div class="field"><label>公開プロフィール</label><textarea id="profile" placeholder="飼育環境、繁殖方針、お迎え後のサポートなど"></textarea><small class="muted">一般公開されます。犬舎名・氏名・電話番号・メール・住所・LINE・SNS・外部サイトURLなど、直接連絡につながる情報は入力しないでください。</small></div>')
p.write_text(s,encoding='utf-8')
