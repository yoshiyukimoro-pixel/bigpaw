from pathlib import Path
# Public pages: never expose kennel names; use prefecture + breeder ID.
for fn in ['breeders.html','breeder-detail.html','puppy-detail.html','search.html']:
 p=Path(fn)
 if not p.exists(): continue
 s=p.read_text(encoding='utf-8',errors='replace')
 # Public breeder list exact renderer.
 s=s.replace('${esc(b.kennel_name)}</b><div class="muted">${esc(b.prefecture)}</div>','${esc(b.prefecture||"")}のBIGPAW認定ブリーダー</b><div class="muted">ブリーダーID：${esc(b.id||"")}</div>')
 # Generic client-rendered kennel name references on public pages.
 s=s.replace('${esc(b.kennel_name)}','${esc((b.prefecture||"")+"のBIGPAW認定ブリーダー")}')
 s=s.replace('${BigPaw.esc(b.kennel_name)}','${BigPaw.esc((b.prefecture||"")+"のBIGPAW認定ブリーダー")}')
 p.write_text(s,encoding='utf-8')

# Registration: clarify kennel name is internal-only, not public identity.
p=Path('breeder-register.html')
if p.exists():
 s=p.read_text(encoding='utf-8',errors='replace')
 s=s.replace('犬舎名','犬舎名（運営審査用・非公開）')
 p.write_text(s,encoding='utf-8')
