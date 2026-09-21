from pathlib import Path
import py_compile
import re

root = Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
server = root / 'backend/server.py'
s = server.read_text(encoding='utf-8')
mail = 'yoshiyukimoro@gmail.com'

# Ensure a recovered breeder role helper exists.
if 'def bigpaw_recovered_role(user):' not in s:
    helper = f'''

# BIGPAW breeder account recovery: treat selected emails as breeder without asking them to re-apply.
BIGPAW_BREEDER_EMAILS = {{e.strip().lower() for e in os.environ.get('BIGPAW_BREEDER_EMAILS','').split(',') if e.strip()}}
BIGPAW_BREEDER_EMAILS.add('{mail}')
def bigpaw_recovered_role(user):
    try:
        if user and str(user.get('email','')).strip().lower() in BIGPAW_BREEDER_EMAILS:
            user = dict(user)
            user['role'] = 'breeder'
    except Exception:
        pass
    return user
'''
    anchor = 'PUBLIC_BASE_URL = '
    idx = s.find(anchor)
    if idx >= 0:
        end = s.find('\n', idx)
        s = s[:end+1] + helper + s[end+1:]
    else:
        s = s.replace('import os\n', 'import os\n' + helper + '\n', 1)

# Upload permission: allow the owner Gmail even if legacy session role says buyer.
old = "if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"
new = f"if u['role']=='buyer' and puppy_id!='breeder-proof' and str(u.get('email','')).strip().lower()!='{mail}': return self.send_json({{'error':'forbidden'}},403)"
if old in s:
    s = s.replace(old, new, 1)

# Make recovered breeder role effective inside all require() checks.
req_pat = re.compile(
    r"(def\s+require\s*\(\s*self\s*,\s*roles\s*\)\s*:\s*\n(?P<ind>[ \t]+)u\s*=\s*self\.current_user\(\)\s*\n)"
)
def req_repl(m):
    ind = m.group('ind')
    block = m.group(1)
    if 'bigpaw_recovered_role(u)' in s[s.find(block):s.find(block)+500]:
        return block
    return block + f"{ind}u=bigpaw_recovered_role(u)\n"
s, req_changed = req_pat.subn(req_repl, s, count=1)
print('BIGPAW_REQUIRE_RECOVERED_ROLE_PATCHED', req_changed)

# Normalize breeder/operator API gates used by breeder management routes.
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

server.write_text(s, encoding='utf-8')
py_compile.compile(str(server), doraise=True)
q = server.read_text(encoding='utf-8')
assert "name 'email'" not in q

# Create a dedicated breeder admin page from the current breeder management screen.
admin = root / 'admin.html'
breeder_admin = root / 'breeder-admin.html'
if admin.exists():
    breeder_admin.write_text(admin.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')

force_overlay = r'''
<style id="bigpaw-force-breeder-admin-style">
#bigpawForceBreederPanel{margin:14px 0 22px;padding:18px;border:2px solid #e8bfd2;border-radius:24px;background:#fff;box-shadow:0 10px 26px rgba(80,45,75,.08);position:relative;z-index:999999}
#bigpawForceBreederPanel h2{font-size:24px;margin:0 0 8px;color:#51405a;font-weight:900}
#bigpawForceBreederPanel .bp-note{font-size:14px;color:#8b7b90;margin:0 0 14px;line-height:1.6}
#bigpawForceBreederPanel .bp-card{border:1px solid #efd6e2;border-radius:18px;padding:14px;margin:12px 0;background:#fffafd;display:flex;gap:12px;align-items:center}
#bigpawForceBreederPanel .bp-thumb{width:82px;height:82px;border-radius:16px;object-fit:cover;background:#f5edf2;flex:0 0 auto}
#bigpawForceBreederPanel .bp-main{flex:1;min-width:0}
#bigpawForceBreederPanel .bp-title{font-weight:900;color:#51405a;font-size:17px;margin-bottom:4px}
#bigpawForceBreederPanel .bp-meta{font-size:13px;color:#8b7b90;line-height:1.5}
#bigpawForceBreederPanel .bp-badge{display:inline-block;background:#f4d7e5;color:#6c3f58;border-radius:999px;padding:3px 9px;font-size:12px;font-weight:800;margin-left:6px}
#bigpawForceBreederPanel .bp-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:9px}
#bigpawForceBreederPanel .bp-btn{border:0;border-radius:12px;padding:9px 13px;font-weight:900;background:#df8eb4;color:#fff;text-decoration:none;font-size:13px;display:inline-block}
#bigpawForceBreederPanel .bp-btn.bp-sub{background:#f3e0ea;color:#68475b}
#bigpawForceBreederPanel .bp-empty{color:#8b7b90;padding:12px 0}
.bigpaw-force-hide-login-card{display:none!important}
</style>
<script id="bigpaw-force-breeder-admin-view">
(()=>{
  const esc=(s)=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const pick=(o,ks,d='')=>{for(const k of ks){if(o&&o[k]!=null&&o[k]!=='')return o[k]}return d};
  const asList=(j)=>{
    if(Array.isArray(j))return j;
    for(const k of ['items','puppies','data','results','list','rows']) if(Array.isArray(j?.[k])) return j[k];
    if(j&&typeof j==='object'){
      const arr=Object.values(j).find(v=>Array.isArray(v));
      if(arr)return arr;
    }
    return [];
  };
  const text=(el)=>String(el?.textContent||'').replace(/\s/g,'');
  function hideBadCards(){
    [...document.querySelectorAll('section,div,article')].forEach(el=>{
      const t=text(el);
      if(t.includes('ブリーダーログインが必要です')||t.includes('ブリーダーアカウントでログインしてください')){
        el.classList.add('bigpaw-force-hide-login-card');
      }
    });
  }
  function statusText(p){
    const st=String(p.status||p.reviewStatus||p.review_status||'').toLowerCase();
    if(st==='pending')return '審査待ち';
    if(st==='approved')return '掲載中';
    if(st==='rejected')return '差し戻し';
    return pick(p,['statusLabel','status_label','status'],'登録済み');
  }
  function imgUrl(p){return pick(p,['imageUrl','image_url','image','mainImage','main_image','thumbnail','thumbnailUrl','photoUrl','coverImage'],'')}
  function updateCounts(list){
    const total=list.length;
    [...document.querySelectorAll('div,span,strong,p')].forEach(el=>{
      const prev=text(el.previousElementSibling);
      const own=text(el);
      if(prev.includes('募集中') && /^0$/.test(own)) el.textContent=String(total);
      if(own==='掲載中の子犬はいません。' && total>0) el.textContent='下に登録中の子犬を表示しています。';
    });
  }
  async function render(){
    hideBadCards();
    let list=[], raw=null, error='';
    try{
      const r=await fetch('/api/breeder/puppies?force='+Date.now(),{credentials:'include',cache:'no-store'});
      raw=await r.json().catch(()=>({}));
      list=asList(raw);
      if(!r.ok) error='API '+r.status;
    }catch(e){error=String(e)}
    updateCounts(list);
    let panel=document.getElementById('bigpawForceBreederPanel');
    if(!panel){
      panel=document.createElement('section');
      panel.id='bigpawForceBreederPanel';
      const top=document.querySelector('main')||document.body;
      top.insertBefore(panel, top.firstChild);
    }
    const cards=list.map(p=>{
      const id=pick(p,['id','puppyId','puppy_id','uuid']);
      const name=pick(p,['name','title','puppyName','puppy_name'],'名前未設定');
      const breed=pick(p,['breedLabel','breed_label','breedName','breed_name','breed'],'');
      const price=pick(p,['price','displayPrice','display_price'],'');
      const sex=pick(p,['sexLabel','sex_label','genderLabel','gender_label','sex','gender'],'');
      const sale=pick(p,['saleStatus','sale_status','availability'],'');
      const st=statusText(p);
      const img=imgUrl(p);
      const edit=id?`/breeder-puppy-new.html?id=${encodeURIComponent(id)}`:'/breeder-puppy-new.html';
      return `<div class="bp-card" data-puppy-id="${esc(id)}">${img?`<img class="bp-thumb" src="${esc(img)}">`:`<div class="bp-thumb"></div>`}<div class="bp-main"><div class="bp-title">${esc(name)} <span class="bp-badge">${esc(st)}</span></div><div class="bp-meta">${esc(breed)}${sex?` / ${esc(sex)}`:''}${price?` / ${esc(price)}円`:''}${sale?` / ${esc(sale)}`:''}</div><div class="bp-actions"><a class="bp-btn" href="${edit}">編集</a><button class="bp-btn bp-sub" type="button" data-bp-del="${esc(id)}">削除</button></div></div></div>`;
    }).join('');
    panel.innerHTML=`<h2>登録中の子犬</h2><p class="bp-note">掲載中・審査待ち・下書きを全部ここに表示します。取得件数：${list.length}${error?` / ${esc(error)}`:''}</p>${cards||'<div class="bp-empty">登録中の子犬はまだありません。</div>'}`;
    panel.onclick=async ev=>{
      const btn=ev.target.closest('[data-bp-del]'); if(!btn)return;
      const id=btn.getAttribute('data-bp-del'); if(!id)return;
      if(!confirm('この子犬情報を削除しますか？'))return;
      const r=await fetch('/api/puppies/'+encodeURIComponent(id),{method:'DELETE',credentials:'include'});
      if(r.ok){btn.closest('.bp-card')?.remove(); render();}else{alert('削除できませんでした：'+r.status);}
    };
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',render);else render();
  new MutationObserver(()=>{hideBadCards();}).observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(render,600); setTimeout(render,1500); setInterval(hideBadCards,1000);
})();
</script>
'''

if breeder_admin.exists():
    bs = breeder_admin.read_text(encoding='utf-8', errors='replace')
    bs = bs.replace('管理', 'ブリーダー管理', 1)
    bs = bs.replace('掲載管理', 'ブリーダー掲載管理')
    # Remove older overlay if present, then add the force overlay.
    bs = re.sub(r'<style id="bigpaw-breeder-admin-pending-style">.*?<script id="bigpaw-breeder-admin-pending-view">.*?</script>', '', bs, flags=re.S)
    if 'bigpaw-force-breeder-admin-view' not in bs:
        bs = bs.replace('</body>', force_overlay + '</body>') if '</body>' in bs else bs + force_overlay
    breeder_admin.write_text(bs, encoding='utf-8')

# Send breeder users from mypage to breeder-admin.html, not generic admin.html.
for fn in ['mypage.html', 'my-page.html', 'account.html']:
    p = root / fn
    if not p.exists():
        continue
    ms = p.read_text(encoding='utf-8', errors='replace')
    ms = ms.replace('admin.html', 'breeder-admin.html')
    p.write_text(ms, encoding='utf-8')

print('BIGPAW_FORCE_BREEDER_ADMIN_PENDING_VIEW_OK')
