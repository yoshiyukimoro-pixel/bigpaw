#!/usr/bin/env python3
from pathlib import Path

ROOT = Path('/app')
SERVER = ROOT / 'backend' / 'server.py'
FORM = ROOT / 'breeder-puppy-new.html'
SEARCH = ROOT / 'search.html'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'APPEAL_POINT_PATCH_FAIL|{label}|count={count}')
    return text.replace(old, new, 1)


def replace_n(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f'APPEAL_POINT_PATCH_FAIL|{label}|count={count}|expected={expected}')
    return text.replace(old, new)


# -------------------- backend / persistence --------------------
s = SERVER.read_text(encoding='utf-8')

column_marker = "    ensure_column(con,'puppies','published_at','INTEGER')\n"
column_block = column_marker + "    ensure_column(con,'puppies','appeal_point',\"TEXT DEFAULT ''\")\n" + \
    "    default_appeal='🐾良血統×即お迎え！2回目ワクチン完了でお散歩OK✨'\n" + \
    "    con.execute(\"UPDATE puppies SET appeal_point=? WHERE COALESCE(appeal_point,'')='' AND status='募集中' AND breed='スタンダードプードル' AND birth='2026-07-01' AND area='埼玉県' AND (breeder_name='DOG44' OR breeder_id IN (SELECT id FROM breeders WHERE kennel_name='DOG44'))\",(default_appeal,))\n"
s = replace_once(s, column_marker, column_block, 'server_column_and_initial_value')

json_marker = "      'adultMax':d['adult_max'],'health':bool(d['health']),'birth':d['birth'],'desc':d['description'],\n"
json_replacement = "      'adultMax':d['adult_max'],'health':bool(d['health']),'birth':d['birth'],'desc':d['description'],'appealPoint':d.get('appeal_point',''),\n"
s = replace_once(s, json_marker, json_replacement, 'server_json_payload')

create_marker = "            pid=make_id('p_'); breed=body.get('breed','その他大型犬'); gender=body.get('gender','男の子')\n"
create_replacement = "            appeal_point=str(body.get('appealPoint','')).strip()\n            if len(appeal_point)>30: con.close(); return self.send_json({'error':'appeal_point_too_long','message':'アピールポイントは30文字以内で入力してください。'},400)\n" + create_marker
s = replace_once(s, create_marker, create_replacement, 'server_create_validation')

audit_marker = "            audit(con,u['id'],'puppy_created','puppy',pid,review_status); con.commit(); r=con.execute('SELECT * FROM puppies WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(puppy_json(r),201)\n"
audit_replacement = "            con.execute('UPDATE puppies SET appeal_point=? WHERE id=?',(appeal_point,pid))\n" + audit_marker
s = replace_once(s, audit_marker, audit_replacement, 'server_create_store')

allowed_marker = "            allowed={'status':'status','price':'price','desc':'description','name':'name','imageUrl':'image_url','breed':'breed','breedKey':'breed_key','gender':'gender','color':'color','birth':'birth','weight':'weight','adultMin':'adult_min','adultMax':'adult_max','father':'father','mother':'mother','health':'health'}\n"
allowed_replacement = "            if 'appealPoint' in body:\n                body['appealPoint']=str(body.get('appealPoint','')).strip()\n                if len(body['appealPoint'])>30: con.close(); return self.send_json({'error':'appeal_point_too_long','message':'アピールポイントは30文字以内で入力してください。'},400)\n            allowed={'status':'status','price':'price','desc':'description','name':'name','imageUrl':'image_url','breed':'breed','breedKey':'breed_key','gender':'gender','color':'color','birth':'birth','weight':'weight','adultMin':'adult_min','adultMax':'adult_max','father':'father','mother':'mother','health':'health','appealPoint':'appeal_point'}\n"
s = replace_once(s, allowed_marker, allowed_replacement, 'server_edit_field')

compile(s, str(SERVER), 'exec')
SERVER.write_text(s, encoding='utf-8')

# -------------------- breeder create / edit form --------------------
f = FORM.read_text(encoding='utf-8')

form_marker = '<div class="field" style="margin-top:18px"><label>紹介文</label><textarea id="desc">人が大好きで穏やかな子です。親犬情報・健康情報も公開しています。</textarea></div>'
form_replacement = '<div class="field" style="margin-top:18px"><label>アピールポイント（30文字以内）</label><input id="appealPoint" type="text" placeholder="例：🐾良血統×即お迎え！2回目ワクチン完了でお散歩OK✨" autocomplete="off"><small id="appealPointCount" class="muted" style="display:block;margin-top:6px">0 / 30文字</small></div>' + form_marker
f = replace_once(f, form_marker, form_replacement, 'form_field')

edit_map_marker = 'mother:d.mother,desc:d.desc,status:d.status};'
edit_map_replacement = 'mother:d.mother,appealPoint:d.appealPoint,desc:d.desc,status:d.status};'
f = replace_once(f, edit_map_marker, edit_map_replacement, 'form_edit_load')

sync_marker = "Object.entries(m).forEach(([k,v])=>{const e=document.getElementById(k);if(e&&v!=null)e.value=v});health.checked=!!d.health;"
sync_replacement = "Object.entries(m).forEach(([k,v])=>{const e=document.getElementById(k);if(e&&v!=null)e.value=v});syncAppealPointCount();health.checked=!!d.health;"
f = replace_once(f, sync_marker, sync_replacement, 'form_counter_after_edit_load')

payload_marker = 'father:father.value,mother:mother.value,health:health.checked,desc:desc.value,area:'
payload_replacement = 'father:father.value,mother:mother.value,health:health.checked,appealPoint:appealPoint.value,desc:desc.value,area:'
f = replace_n(f, payload_marker, payload_replacement, 2, 'form_save_payloads')

init_marker = "initEdit();\nfunction bigpawBreedKey"
init_replacement = "function syncAppealPointCount(){const e=document.getElementById('appealPoint'),c=document.getElementById('appealPointCount');if(!e||!c)return;let chars=Array.from(e.value||'');if(chars.length>30){e.value=chars.slice(0,30).join('');chars=Array.from(e.value)}c.textContent=chars.length+' / 30文字'}\nconst appealPointInput=document.getElementById('appealPoint');if(appealPointInput){appealPointInput.addEventListener('input',syncAppealPointCount);syncAppealPointCount()}\ninitEdit();\nfunction bigpawBreedKey"
f = replace_once(f, init_marker, init_replacement, 'form_counter_runtime')

if 'id="appealPoint"' not in f or 'appealPoint:appealPoint.value' not in f or '30文字以内' not in f:
    raise SystemExit('APPEAL_POINT_PATCH_FAIL|form_postcheck')
FORM.write_text(f, encoding='utf-8')

# -------------------- public search result placement --------------------
q = SEARCH.read_text(encoding='utf-8')

style_marker = '#results .result-info .price{font-size:22px!important;line-height:1.35!important;color:#ed5a70!important;font-weight:900!important;margin:7px 0 0!important;white-space:nowrap!important}\n'
style_replacement = '#results .result-point{font-size:13px!important;line-height:1.45!important;color:#b84f76!important;font-weight:900!important;margin:7px 0 3px!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}\n' + style_marker
q = replace_once(q, style_marker, style_replacement, 'search_appeal_style')

card_marker = '<div class="result-line">毛色：${esc(p.color||\'未登録\')}</div><div class="price">${money(p.price)} <span style="font-size:12px;color:#5c5357;font-weight:700">(税込)</span></div>'
card_replacement = '<div class="result-line">毛色：${esc(p.color||\'未登録\')}</div>${p.appealPoint?`<div class="result-point">${esc(p.appealPoint)}</div>`:\'\'}<div class="price">${money(p.price)} <span style="font-size:12px;color:#5c5357;font-weight:700">(税込)</span></div>'
q = replace_once(q, card_marker, card_replacement, 'search_appeal_position')

if 'p.appealPoint' not in q or 'class="result-point"' not in q:
    raise SystemExit('APPEAL_POINT_PATCH_FAIL|search_postcheck')
SEARCH.write_text(q, encoding='utf-8')

print('APPEAL_POINT_PATCH_OK|limit=30|breeder_input=enabled|public_search=under_color|initial_dog44_value=filled', flush=True)
