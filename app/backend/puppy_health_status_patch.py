#!/usr/bin/env python3
from pathlib import Path
import re

root=Path('/app')
server=root/'backend/server.py'
form=root/'breeder-puppy-new.html'
detail=root/'puppy-detail.html'


def must_replace(text, old, new, label, count=1):
    n=text.count(old)
    if n < count:
        raise SystemExit(f'{label}: expected at least {count}, found {n}')
    return text.replace(old,new,count)

# ---- backend schema / API ----
s=server.read_text(encoding='utf-8')
anchor="    ensure_column(con,'puppies','published_at','INTEGER')"
if "ensure_column(con,'puppies','health_status'" not in s:
    s=must_replace(s,anchor,anchor+"\n    ensure_column(con,'puppies','health_status',\"TEXT DEFAULT ''\")\n    ensure_column(con,'puppies','vaccine_status',\"TEXT DEFAULT ''\")\n    ensure_column(con,'puppies','microchip_status',\"TEXT DEFAULT ''\")\n    ensure_column(con,'puppies','genetic_test_status',\"TEXT DEFAULT ''\")",'schema columns')

json_old="      'adultMax':d['adult_max'],'health':bool(d['health']),'birth':d['birth'],'desc':d['description'],"
json_new="      'adultMax':d['adult_max'],'health':bool(d['health']),'healthStatus':d.get('health_status','') or '',\n      'vaccineStatus':d.get('vaccine_status','') or '','microchipStatus':d.get('microchip_status','') or '',\n      'geneticTestStatus':d.get('genetic_test_status','') or '','birth':d['birth'],'desc':d['description'],"
if "'healthStatus':d.get('health_status'" not in s:
    s=must_replace(s,json_old,json_new,'puppy json')

create_anchor="            audit(con,u['id'],'puppy_created','puppy',pid,review_status); con.commit(); r=con.execute('SELECT * FROM puppies WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(puppy_json(r),201)"
create_new="            con.execute(\"UPDATE puppies SET health_status=?,vaccine_status=?,microchip_status=?,genetic_test_status=? WHERE id=?\",(str(body.get('healthStatus','')).strip(),str(body.get('vaccineStatus','')).strip(),str(body.get('microchipStatus','')).strip(),str(body.get('geneticTestStatus','')).strip(),pid))\n            audit(con,u['id'],'puppy_created','puppy',pid,review_status); con.commit(); r=con.execute('SELECT * FROM puppies WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(puppy_json(r),201)"
if "UPDATE puppies SET health_status=?,vaccine_status=?,microchip_status=?,genetic_test_status=? WHERE id=?" not in s:
    s=must_replace(s,create_anchor,create_new,'create status save')

# This runs after PUPPY_EDIT_FIELDS patch, so extend the already-expanded map.
allowed_old="'father':'father','mother':'mother','health':'health'}"
allowed_new="'father':'father','mother':'mother','health':'health','healthStatus':'health_status','vaccineStatus':'vaccine_status','microchipStatus':'microchip_status','geneticTestStatus':'genetic_test_status'}"
if "'healthStatus':'health_status'" not in s:
    s=must_replace(s,allowed_old,allowed_new,'edit allowed map')
server.write_text(s,encoding='utf-8')

# ---- breeder puppy create/edit UI ----
h=form.read_text(encoding='utf-8')
new_health='''<h2>健康・検査情報</h2><p class="muted" style="margin-top:-4px">実際の状態を選択してください。未確認の項目は「未登録」のままで構いません。</p><input id="health" type="checkbox" hidden><div class="form-grid" id="puppyHealthStatusFields"><div class="field"><label>健康診断</label><select id="healthStatus"><option>未登録</option><option>未実施</option><option>実施済み</option><option>実施済み（異常なし）</option></select></div><div class="field"><label>混合ワクチン</label><select id="vaccineStatus"><option>未登録</option><option>未接種</option><option>1回目接種済み</option><option>2回目接種済み</option><option>3回目接種済み</option><option>接種済み</option></select></div><div class="field"><label>マイクロチップ</label><select id="microchipStatus"><option>未登録</option><option>未装着</option><option>装着済み</option></select></div><div class="field"><label>遺伝子検査</label><select id="geneticTestStatus"><option>未登録</option><option>未実施</option><option>実施済み</option><option>親犬検査情報あり</option></select></div></div>'''
pat=r'<h2>健康情報</h2><div class="form-grid"><label class="fact"><input id="health".*?</div><div id="editOnly"'
h2,n=re.subn(pat,new_health+'<div id="editOnly"',h,count=1,flags=re.S)
if n!=1 and 'id="puppyHealthStatusFields"' not in h:
    raise SystemExit(f'health form replace: {n}')
h=h2 if n==1 else h

old_map="const m={breed:d.breed,gender:d.gender,color:d.color,birth:d.birth,price:d.price,weight:d.weight,adultMin:d.adultMin,adultMax:d.adultMax,father:d.father,mother:d.mother,desc:d.desc,status:d.status};"
new_map="const m={breed:d.breed,gender:d.gender,color:d.color,birth:d.birth,price:d.price,weight:d.weight,adultMin:d.adultMin,adultMax:d.adultMax,father:d.father,mother:d.mother,desc:d.desc,status:d.status,healthStatus:d.healthStatus||(d.health?'実施済み':'未登録'),vaccineStatus:d.vaccineStatus||'未登録',microchipStatus:d.microchipStatus||'未登録',geneticTestStatus:d.geneticTestStatus||'未登録'};"
if 'vaccineStatus:d.vaccineStatus' not in h:
    h=must_replace(h,old_map,new_map,'edit form hydration')
h=h.replace("health.checked=!!d.health;","if(health)health.checked=!!d.health;",1)

payload_old="health:health.checked,desc:desc.value"
payload_new="health:document.getElementById('healthStatus').value.indexOf('実施済み')===0,healthStatus:document.getElementById('healthStatus').value,vaccineStatus:document.getElementById('vaccineStatus').value,microchipStatus:document.getElementById('microchipStatus').value,geneticTestStatus:document.getElementById('geneticTestStatus').value,desc:desc.value"
if payload_old in h:
    h=h.replace(payload_old,payload_new)
if h.count('healthStatus:document.getElementById')<2:
    raise SystemExit('save payload status fields not injected twice')

# Final guard: whatever save path calls BigPawBridge, always attach the four current selections.
# This prevents later page patches from accidentally dropping the status fields again.
guard='''<script id="bigpaw-health-status-save-guard">(()=>{if(window.__BIGPAW_HEALTH_SAVE_GUARD__)return;window.__BIGPAW_HEALTH_SAVE_GUARD__=1;function vals(){const g=id=>document.getElementById(id);const hs=g('healthStatus'),vs=g('vaccineStatus'),ms=g('microchipStatus'),gs=g('geneticTestStatus');if(!hs||!vs||!ms||!gs)return{};return{health:hs.value.indexOf('実施済み')===0,healthStatus:hs.value,vaccineStatus:vs.value,microchipStatus:ms.value,geneticTestStatus:gs.value}}function install(){if(!window.BigPawBridge||window.__BIGPAW_HEALTH_BRIDGE_WRAPPED__)return false;window.__BIGPAW_HEALTH_BRIDGE_WRAPPED__=1;const u=BigPawBridge.updatePuppy.bind(BigPawBridge),a=BigPawBridge.addPuppy.bind(BigPawBridge);BigPawBridge.updatePuppy=(id,v)=>u(id,Object.assign({},v||{},vals()));BigPawBridge.addPuppy=v=>a(Object.assign({},v||{},vals()));return true}if(!install())setTimeout(install,0);window.addEventListener('pageshow',install)})();</script>'''
if 'bigpaw-health-status-save-guard' not in h:
    if '</body>' not in h: raise SystemExit('health save guard body close missing')
    h=h.replace('</body>',guard+'</body>',1)
form.write_text(h,encoding='utf-8')

# ---- public puppy detail ----
d=detail.read_text(encoding='utf-8')
d=d.replace('<div class="table-row"><div>混合ワクチン</div><div>接種情報を掲載</div></div>','<div class="table-row"><div>混合ワクチン</div><div id="vaccineText">未登録</div></div>',1)
d=d.replace('<div class="table-row"><div>マイクロチップ</div><div>装着情報を掲載</div></div>','<div class="table-row"><div>マイクロチップ</div><div id="microchipText">未登録</div></div>',1)
d=d.replace('<div class="table-row"><div>遺伝子検査</div><div>親犬検査情報を掲載</div></div>','<div class="table-row"><div>遺伝子検査</div><div id="geneticTestText">未登録</div></div>',1)
d=re.sub(r'<div class="table-row"><div>大型犬向け検査</div><div>.*?</div></div>','',d,count=1,flags=re.S)
load_old="healthText.textContent=p.health?'掲載あり':'確認中';"
load_new="healthText.textContent=p.healthStatus||(p.health?'実施済み':'未登録');vaccineText.textContent=p.vaccineStatus||'未登録';microchipText.textContent=p.microchipStatus||'未登録';geneticTestText.textContent=p.geneticTestStatus||'未登録';"
if load_old in d:
    d=d.replace(load_old,load_new,1)
elif 'vaccineText.textContent=p.vaccineStatus' not in d:
    raise SystemExit('public health hydration marker missing')
if '大型犬向け検査' in d:
    raise SystemExit('large-dog test row still present')
detail.write_text(d,encoding='utf-8')

print('PUPPY_HEALTH_STATUS_OK|fields=health_vaccine_microchip_genetics|save_guard=enabled|large_dog_test=removed|public=actual_status',flush=True)
