from pathlib import Path
p=Path('mypage.html')
s=p.read_text(encoding='utf-8')
if 'mypage-favorites-sync.js' not in s:\n s=s.replace('</body>','<script src="/mypage-favorites-sync.js"></script></body>')\nif 'mypage-verify-state-fix.js' not in s:
 s=s.replace('</body>','<script src="/mypage-verify-state-fix.js"></script></body>')
p.write_text(s,encoding='utf-8')
