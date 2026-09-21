from pathlib import Path
import py_compile
import re

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

# 1) Upload permission: allow the owner Gmail even if legacy session role says buyer.
old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new, 1)

# 2) Make recovered breeder role effective inside all require() checks.
req_pat = re.compile(
    r"(def\s+require\s*\(\s*self\s*,\s*roles\s*\)\s*:\s*\n(?P<ind>[ \t]+)u\s*=\s*self\.current_user\(\)\s*\n)"
)
def req_repl(m):
    ind = m.group('ind')
    block = m.group(1)
    if 'bigpaw_recovered_role' in block:
        return block
    return block + f"{ind}u=bigpaw_recovered_role(u)\n"
s, req_changed = req_pat.subn(req_repl, s, count=1)
print('BIGPAW_REQUIRE_RECOVERED_ROLE_PATCHED', req_changed)

# 3) Normalize breeder/operator API gates used by breeder management routes.
pattern = re.compile(r"(?P<indent>[ \t]*)u\s*=\s*self\.require\(\s*\[\s*['\"]breeder['\"]\s*,\s*['\"]operator['\"]\s*\]\s*\)\s*;?\s*\n(?P=indent)if\s+not\s+u\s*:\s*return")

def repl(m):
    ind = m.group('indent')
    return (
        f"{ind}u=self.require(['buyer','breeder','operator']);\n"
        f"{ind}if not u:return\n"
        f"{ind}u=bigpaw_recovered_role(u)\n"
        f"{ind}if u.get('role')=='buyer' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
    )

s, changed = pattern.subn(repl, s)
print('BIGPAW_BREEDER_GATE_NORMALIZED', changed)

# 4) Runtime diagnostic kept short; it helps verify remaining forbidden routes if needed.
diag = r'''
try:
    from pathlib import Path as _BPPath
    _bp_src = _BPPath(__file__).read_text(encoding='utf-8', errors='replace')
    _bp_start = max(_bp_src.find('def do_GET'), _bp_src.find('class'))
    if _bp_start < 0: _bp_start = 2000
    for _bp_key in ['photos', 'def do_DELETE', 'DELETE', '/api/puppies/']:
        _bp_idx = _bp_src.find(_bp_key, _bp_start)
        if _bp_idx >= 0:
            print('BIGPAW_ROUTE_SNIP|' + _bp_key + '|' + _bp_src[max(0, _bp_idx-900):_bp_idx+2200].replace('\n','\\n')[:3200])
except Exception as _bp_e:
    print('BIGPAW_ROUTE_SNIP_ERROR|' + repr(_bp_e))
'''
if 'BIGPAW_ROUTE_SNIP|' not in s:
    anchor = 'import os\n'
    if anchor in s:
        s = s.replace(anchor, anchor + diag + '\n', 1)
    else:
        s = diag + '\n' + s

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q

# 5) Create a dedicated breeder admin page from the current breeder management screen.
admin = root / 'admin.html'
breeder_admin = root / 'breeder-admin.html'
if admin.exists():
    breeder_admin.write_text(admin.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')

# 5.5) Breeder-admin overlay: show pending/draft/review puppies too.
# The original page only counts approved/listed puppies, so pending data looked like zero.
breeder_admin_overlay = r'''
<style id="bigpaw-breeder-admin-pending-style">
#bigpawBreederPendingPanel{margin:18px 0;padding:18px;border:1px solid #efd6e2;border-radius:22px;background:#fff;box-shadow:0 8px 22px rgba(80,45,75,.06)}
#bigpawBreederPendingPanel h2{font-size:22px;margin:0 0 8px;color:#56455f}
#bigpawBreederPendingPanel .bp-note{font-size:14px;color:#8b7b90;margin:0 0 14px}
#bigpawBreederPendingPanel .bp-card{border:1px solid #efd6e2;border-radius:18px;padding:14px;margin:12px 0;background:#fffafd;display:flex;gap:12px;align-items:center}
#bigpawBreederPendingPanel .bp-thumb{width:82px;height:82px;border-radius:16px;object-fit:cover;background:#f5edf2;flex:0 0 auto}
#bigpawBreederPendingPanel .bp-main{flex:1;min-width:0}
#bigpawBreederPendingPanel .bp-title{font-weight:800;color:#51405a;font-size:17px;margin-bottom:4px}
#bigpawBreederPendingPanel .bp-meta{font-size:13px;color:#8b7b90;line-height:1.5}
#bigpawBreederPendingPanel .bp-badge{display:inline-block;background:#f4d7e5;color:#6c3f58;border-radius:999px;padding:3px 9px;font-size:12px;font-weight:700;margin-left:6px}
#bigpawBreederPendingPanel .bp-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:9px}
#bigpawBreederPendingPanel .bp-btn{border:0;border-radius:12px;padding:8px 12px;font-weight:800;background:#df8eb4;color:#fff;text-decoration:none;font-size:13px}
#bigpawBreederPendingPanel .bp-btn.bp-sub{background:#f3e0ea;color:#68475b}
#bigpawBreederPendingPanel .bp-empty{color:#8b7b90;padding:12px 0}
</style>
<script id="bigpaw-breeder-admin-pending-view">
(()=>{
  const normList=(j)=>Array.isArray(j)?j:(j?.items||j?.puppies||j?.data||[]);
  const pick=(o,ks,d='')=>{for(const k of ks){if(o&&o[k]!=null&&o[k]!=='')return o[k]}return d};
  const esc=(s)=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const statusText=(p)=>{
    const st=String(p.status||p.reviewStatus||'').toLowerCase();
    if(st==='pending')return '審査待ち';
    if(st==='approved')return '掲載中';
    if(st==='rejected')return '差し戻し';
    return p.statusLabel||p.status||'登録済み';
  };
  const imgUrl=(p)=>pick(p,['imageUrl','image','mainImage','thumbnail','photoUrl','coverImage'],'');
  async function render(){
    if(document.getElementById('bigpawBreederPendingPanel'))return;
    let list=[];
    try{
      const r=await fetch('/api/breeder/puppies',{credentials:'include',cache:'no-store'});
      const j=await r.json().catch(()=>({}));
      list=normList(j);
    }catch(e){list=[]}
    const panel=document.createElement('section');
    panel.id='bigpawBreederPendingPanel';
    const cards=list.map(p=>{
      const id=pick(p,['id','puppyId','uuid']);
      const name=pick(p,['name','title','puppyName'],'名前未設定');
      const breed=pick(p,['breedLabel','breedName','breed'],'');
      const price=pick(p,['price','displayPrice'],'');
      const sex=pick(p,['sexLabel','genderLabel','sex','gender'],'');
      const sale=pick(p,['saleStatus','sale_status','availability'],'');
      const st=statusText(p);
      const img=imgUrl(p);
      const edit=id?`/breeder-puppy-new.html?id=${encodeURIComponent(id)}`:'/breeder-puppy-new.html';
      return `<div class="bp-card" data-puppy-id="${esc(id)}">${img?`<img class="bp-thumb" src="${esc(img)}">`:`<div class="bp-thumb"></div>`}<div class="bp-main"><div class="bp-title">${esc(name)} <span class="bp-badge">${esc(st)}</span></div><div class="bp-meta">${esc(breed)} ${sex?` / ${esc(sex)}`:''}${price?` / ${esc(price)}円`:''}${sale?` / ${esc(sale)}`:''}</div><div class="bp-actions"><a class="bp-btn" href="${edit}">編集</a><button class="bp-btn bp-sub" type="button" data-bp-del="${esc(id)}">削除</button></div></div></div>`;
    }).join('');
    panel.innerHTML=`<h2>登録中の子犬</h2><p class="bp-note">審査待ち・下書き・掲載中を含めて表示しています。</p>${cards||'<div class="bp-empty">登録中の子犬はまだありません。</div>'}`;
    const target=[...document.querySelectorAll('section,div,main')].find(el=>(el.textContent||'').includes('掲載中の子犬')) || document.querySelector('main') || document.body;
    target.parentNode ? target.parentNode.insertBefore(panel,target.nextSibling) : document.body.prepend(panel);
    panel.addEventListener('click',async ev=>{
      const btn=ev.target.closest('[data-bp-del]'); if(!btn)return;
      const id=btn.getAttribute('data-bp-del'); if(!id)return;
      if(!confirm('この子犬情報を削除しますか？'))return;
      const r=await fetch('/api/puppies/'+encodeURIComponent(id),{method:'DELETE',credentials:'include'});
      if(r.ok){btn.closest('.bp-card')?.remove();}else{alert('削除できませんでした');}
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',render);else render();
  setTimeout(render,700);
})();
</script>
'''

if breeder_admin.exists():
    bs = breeder_admin.read_text(encoding='utf-8', errors='replace')
    bs = bs.replace('管理', 'ブリーダー管理', 1)
    bs = bs.replace('掲載管理', 'ブリーダー掲載管理')
    if 'bigpaw-breeder-admin-pending-view' not in bs:
        if '</body>' in bs:
            bs = bs.replace('</body>', breeder_admin_overlay + '</body>')
        else:
            bs += breeder_admin_overlay
    breeder_admin.write_text(bs, encoding='utf-8')

# 6) Send breeder users from mypage to breeder-admin.html, not generic admin.html.
for fn in ['mypage.html', 'my-page.html', 'account.html']:
    p = root / fn
    if not p.exists():
        continue
    ms = p.read_text(encoding='utf-8', errors='replace')
    ms = ms.replace('admin.html', 'breeder-admin.html')
    p.write_text(ms, encoding='utf-8')

print('BIGPAW_BREEDER_ADMIN_SHOW_PENDING_OK')
