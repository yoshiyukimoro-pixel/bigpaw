#!/usr/bin/env python3
from pathlib import Path

ROOT = Path('/app')
SERVER = ROOT / 'backend' / 'server.py'
FORM = ROOT / 'breeder-puppy-new.html'
SEARCH = ROOT / 'search.html'
REBUILT_SEARCH = ROOT / 'search-list-rebuild.html'


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
# This patch deliberately runs from final_release_gate.py, after all earlier
# Docker build patches. Markers below therefore target the FINAL transformed
# server/form shape, not the repository's raw source shape.
s = SERVER.read_text(encoding='utf-8')

column_marker = "    ensure_column(con,'puppies','published_at','INTEGER')\n"
column_block = column_marker + "    ensure_column(con,'puppies','appeal_point',\"TEXT DEFAULT ''\")\n" + \
    "    default_appeal='🐾良血統×即お迎え！2回目ワクチン完了でお散歩OK✨'\n" + \
    "    con.execute(\"UPDATE puppies SET appeal_point=? WHERE COALESCE(appeal_point,'')='' AND status='募集中' AND breed='スタンダードプードル' AND birth='2026-07-01' AND area='埼玉県' AND (breeder_name='DOG44' OR breeder_id IN (SELECT id FROM breeders WHERE kennel_name='DOG44'))\",(default_appeal,))\n"
s = replace_once(s, column_marker, column_block, 'server_column_and_initial_value')

# puppy_health_status_patch.py has already expanded puppy_json at this point.
json_marker = "      'geneticTestStatus':d.get('genetic_test_status','') or '','birth':d['birth'],'desc':d['description'],\n"
json_replacement = "      'geneticTestStatus':d.get('genetic_test_status','') or '','birth':d['birth'],'desc':d['description'],'appealPoint':d.get('appeal_point','') or '',\n"
s = replace_once(s, json_marker, json_replacement, 'server_json_payload')

create_marker = "            pid=make_id('p_'); breed=body.get('breed','その他大型犬'); gender=body.get('gender','男の子')\n"
create_replacement = "            appeal_point=str(body.get('appealPoint','')).strip()\n            if len(appeal_point)>30: con.close(); return self.send_json({'error':'appeal_point_too_long','message':'アピールポイントは30文字以内で入力してください。'},400)\n" + create_marker
s = replace_once(s, create_marker, create_replacement, 'server_create_validation')

# Health-status persistence is already inserted immediately before this audit line.
audit_marker = "            audit(con,u['id'],'puppy_created','puppy',pid,review_status); con.commit(); r=con.execute('SELECT * FROM puppies WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(puppy_json(r),201)\n"
audit_replacement = "            con.execute('UPDATE puppies SET appeal_point=? WHERE id=?',(appeal_point,pid))\n" + audit_marker
s = replace_once(s, audit_marker, audit_replacement, 'server_create_store')

# The final allowed map already includes the four health-status fields.
allowed_marker = "            allowed={'status':'status','price':'price','desc':'description','name':'name','imageUrl':'image_url','breed':'breed','breedKey':'breed_key','gender':'gender','color':'color','birth':'birth','weight':'weight','adultMin':'adult_min','adultMax':'adult_max','father':'father','mother':'mother','health':'health','healthStatus':'health_status','vaccineStatus':'vaccine_status','microchipStatus':'microchip_status','geneticTestStatus':'genetic_test_status'}\n"
allowed_replacement = "            if 'appealPoint' in body:\n                body['appealPoint']=str(body.get('appealPoint','')).strip()\n                if len(body['appealPoint'])>30: con.close(); return self.send_json({'error':'appeal_point_too_long','message':'アピールポイントは30文字以内で入力してください。'},400)\n            allowed={'status':'status','price':'price','desc':'description','name':'name','imageUrl':'image_url','breed':'breed','breedKey':'breed_key','gender':'gender','color':'color','birth':'birth','weight':'weight','adultMin':'adult_min','adultMax':'adult_max','father':'father','mother':'mother','health':'health','healthStatus':'health_status','vaccineStatus':'vaccine_status','microchipStatus':'microchip_status','geneticTestStatus':'genetic_test_status','appealPoint':'appeal_point'}\n"
s = replace_once(s, allowed_marker, allowed_replacement, 'server_edit_field')

compile(s, str(SERVER), 'exec')
SERVER.write_text(s, encoding='utf-8')

# -------------------- breeder create / edit form --------------------
f = FORM.read_text(encoding='utf-8')

form_marker = '<div class="field" style="margin-top:18px"><label>紹介文</label><textarea id="desc">人が大好きで穏やかな子です。親犬情報・健康情報も公開しています。</textarea></div>'
form_replacement = '<div class="field" style="margin-top:18px"><label>アピールポイント（30文字以内）</label><input id="appealPoint" type="text" placeholder="例：🐾良血統×即お迎え！2回目ワクチン完了でお散歩OK✨" autocomplete="off"><small id="appealPointCount" class="muted" style="display:block;margin-top:6px">0 / 30文字</small></div>' + form_marker
f = replace_once(f, form_marker, form_replacement, 'form_field')

# puppy_health_status_patch.py extends the edit map after status, so patch the
# stable parent/description segment instead of relying on the object ending.
edit_map_marker = 'father:d.father,mother:d.mother,desc:d.desc,status:d.status,'
edit_map_replacement = 'father:d.father,mother:d.mother,appealPoint:d.appealPoint,desc:d.desc,status:d.status,'
f = replace_once(f, edit_map_marker, edit_map_replacement, 'form_edit_load')

sync_marker = "Object.entries(m).forEach(([k,v])=>{const e=document.getElementById(k);if(e&&v!=null)e.value=v});if(health)health.checked=!!d.health;"
sync_replacement = "Object.entries(m).forEach(([k,v])=>{const e=document.getElementById(k);if(e&&v!=null)e.value=v});syncAppealPointCount();if(health)health.checked=!!d.health;"
f = replace_once(f, sync_marker, sync_replacement, 'form_counter_after_edit_load')

# Both create and edit payloads have already been expanded with health statuses.
payload_marker = "geneticTestStatus:document.getElementById('geneticTestStatus').value,desc:desc.value,area:"
payload_replacement = "geneticTestStatus:document.getElementById('geneticTestStatus').value,appealPoint:appealPoint.value,desc:desc.value,area:"
f = replace_n(f, payload_marker, payload_replacement, 2, 'form_save_payloads')

init_marker = "initEdit();\nfunction bigpawBreedKey"
init_replacement = "function syncAppealPointCount(){const e=document.getElementById('appealPoint'),c=document.getElementById('appealPointCount');if(!e||!c)return;let chars=Array.from(e.value||'');if(chars.length>30){e.value=chars.slice(0,30).join('');chars=Array.from(e.value)}c.textContent=chars.length+' / 30文字'}\nconst appealPointInput=document.getElementById('appealPoint');if(appealPointInput){appealPointInput.addEventListener('input',syncAppealPointCount);syncAppealPointCount()}\ninitEdit();\nfunction bigpawBreedKey"
f = replace_once(f, init_marker, init_replacement, 'form_counter_runtime')

# Never show a successful save message until the value has been read back from
# the server. This prevents a false "saved" message if any future patch drops
# the field from the update pipeline.
verify_anchor = "async function savePuppy(e){e.preventDefault();"
verify_helper = "async function verifyAppealPointPersistence(id,expected){const rows=await BigPawBridge.breederPuppies();const saved=rows.find(x=>String(x.id)===String(id));const actual=saved?String(saved.appealPoint||''):'';const wanted=String(expected||'').trim();if(!saved||actual!==wanted)throw new Error('アピールポイントの保存確認に失敗しました。保存完了にはしていません。');return saved}\n" + verify_anchor
f = replace_once(f, verify_anchor, verify_helper, 'form_persistence_verify_helper')

success_marker = "alert(editId?'変更を保存しました。':'子犬情報を掲載しました。');location.href='admin.html'"
success_replacement = "if(editId)await verifyAppealPointPersistence(puppy.id,appealPoint.value);alert(editId?'変更を保存しました。':'子犬情報を掲載しました。');location.href='admin.html'"
f = replace_once(f, success_marker, success_replacement, 'form_persistence_verify_before_success')

if (
    'id="appealPoint"' not in f
    or f.count('appealPoint:appealPoint.value') != 2
    or 'appealPoint:d.appealPoint' not in f
    or 'verifyAppealPointPersistence' not in f
    or '30文字以内' not in f
):
    raise SystemExit('APPEAL_POINT_PATCH_FAIL|form_postcheck')
FORM.write_text(f, encoding='utf-8')

# -------------------- legacy/fallback public search --------------------
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

# -------------------- live rebuilt public search --------------------
# start_live.py installs this file over search.html in production, so it must
# independently contain the same appeal-point rendering.
if not REBUILT_SEARCH.exists():
    raise SystemExit('APPEAL_POINT_PATCH_FAIL|rebuilt_search_missing')
r = REBUILT_SEARCH.read_text(encoding='utf-8')

rebuilt_style_marker = '    .bp-meta{font-size:14px;line-height:1.62;color:var(--bp-muted);overflow-wrap:anywhere}\n'
rebuilt_style_replacement = rebuilt_style_marker + '    .bp-appeal{font-size:13px;line-height:1.45;color:#b84f76;font-weight:900;margin-top:5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}\n'
r = replace_once(r, rebuilt_style_marker, rebuilt_style_replacement, 'rebuilt_search_appeal_style')

rebuilt_card_marker = "                +'<div class=\"bp-meta\">毛色：'+esc(p.color||'—')+'</div>'\n"
rebuilt_card_replacement = rebuilt_card_marker + "                +(p.appealPoint?'<div class=\"bp-appeal\">'+esc(p.appealPoint)+'</div>':'')\n"
r = replace_once(r, rebuilt_card_marker, rebuilt_card_replacement, 'rebuilt_search_appeal_position')

if 'p.appealPoint' not in r or 'class=\"bp-appeal\"' not in r:
    raise SystemExit('APPEAL_POINT_PATCH_FAIL|rebuilt_search_postcheck')
REBUILT_SEARCH.write_text(r, encoding='utf-8')

print('APPEAL_POINT_PATCH_OK|limit=30|breeder_input=enabled|edit_readback=enabled|save_verified_before_success=enabled|public_search=under_color|live_rebuilt_search=patched|initial_dog44_value=filled', flush=True)
