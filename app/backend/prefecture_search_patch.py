#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PREFS=[
('北海道','hokkaido','北海道'),
('青森県','aomori','東北'),('岩手県','iwate','東北'),('宮城県','miyagi','東北'),('秋田県','akita','東北'),('山形県','yamagata','東北'),('福島県','fukushima','東北'),
('茨城県','ibaraki','関東'),('栃木県','tochigi','関東'),('群馬県','gunma','関東'),('埼玉県','saitama','関東'),('千葉県','chiba','関東'),('東京都','tokyo','関東'),('神奈川県','kanagawa','関東'),
('新潟県','niigata','甲信越・北陸'),('富山県','toyama','甲信越・北陸'),('石川県','ishikawa','甲信越・北陸'),('福井県','fukui','甲信越・北陸'),('山梨県','yamanashi','甲信越・北陸'),('長野県','nagano','甲信越・北陸'),
('岐阜県','gifu','東海'),('静岡県','shizuoka','東海'),('愛知県','aichi','東海'),('三重県','mie','東海'),
('滋賀県','shiga','近畿'),('京都府','kyoto','近畿'),('大阪府','osaka','近畿'),('兵庫県','hyogo','近畿'),('奈良県','nara','近畿'),('和歌山県','wakayama','近畿'),
('鳥取県','tottori','中国'),('島根県','shimane','中国'),('岡山県','okayama','中国'),('広島県','hiroshima','中国'),('山口県','yamaguchi','中国'),
('徳島県','tokushima','四国'),('香川県','kagawa','四国'),('愛媛県','ehime','四国'),('高知県','kochi','四国'),
('福岡県','fukuoka','九州・沖縄'),('佐賀県','saga','九州・沖縄'),('長崎県','nagasaki','九州・沖縄'),('熊本県','kumamoto','九州・沖縄'),('大分県','oita','九州・沖縄'),('宮崎県','miyazaki','九州・沖縄'),('鹿児島県','kagoshima','九州・沖縄'),('沖縄県','okinawa','九州・沖縄')]
assert len(PREFS)==47

# grouped prefecture options; values are the actual Japanese prefecture names so old/new records filter reliably.
groups=[]
for region in ['北海道','東北','関東','甲信越・北陸','東海','近畿','中国','四国','九州・沖縄']:
    rows=[p for p in PREFS if p[2]==region]
    groups.append('<optgroup label="'+region+'">'+''.join(f'<option value="{name}">{name}</option>' for name,_,_ in rows)+'</optgroup>')
OPTIONS='<option value="all">全国</option>'+''.join(groups)

# Search page: 47-prefecture selector, exact prefecture filtering, and URL query hydration.
p=ROOT/'search.html'
s=p.read_text(encoding='utf-8')
s,n=re.subn(r'<select id="fArea" class="pickrow" style="appearance:auto">.*?</select>', '<select id="fArea" class="pickrow" style="appearance:auto">'+OPTIONS+'</select>', s, count=1, flags=re.S)
assert n==1, ('search_area_select',n)
old="if(a!=='all'){if(a==='other')list=list.filter(p=>!['saitama','tokyo','kanagawa','chiba','gunma','tochigi'].includes(p.areaKey));else if(!['hokkaido','tohoku'].includes(a))list=list.filter(p=>p.areaKey===a)}"
new="if(a!=='all')list=list.filter(p=>String(p.area||'').trim()===a)"
assert old in s, 'search_area_filter_marker'
s=s.replace(old,new,1)
old_load="async function load(){try{all=await BigPawBridge.puppies();const b=qs.get('breed');if(b)fBreed.value=b;render()}catch(e){count.textContent='0頭';results.innerHTML='<div class=\"card empty\">データを読み込めませんでした。</div>'}}load();"
new_load="async function load(){try{all=await BigPawBridge.puppies();const b=qs.get('breed'),a=qs.get('area'),g=qs.get('gender');if(b)fBreed.value=b;if(a&&[...fArea.options].some(o=>o.value===a))fArea.value=a;if(g&&['male','female'].includes(g)){gender=g;choose(genderSeg,gender)}render()}catch(e){count.textContent='0頭';results.innerHTML='<div class=\"card empty\">データを読み込めませんでした。</div>'}}load();"
assert old_load in s, 'search_query_hydration_marker'
s=s.replace(old_load,new_load,1)
p.write_text(s,encoding='utf-8')

# Home page: replace the short prefecture selector with the same nationwide selector.
p=ROOT/'index.html'
s=p.read_text(encoding='utf-8')
s,n=re.subn(r'<select id="area">.*?</select>', '<select id="area">'+OPTIONS+'</select>', s, count=1, flags=re.S)
assert n==1, ('home_area_select',n)
p.write_text(s,encoding='utf-8')

# Backend: every breeder prefecture gets a stable area key instead of falling back to "other".
p=ROOT/'backend'/'server.py'
s=p.read_text(encoding='utf-8')
full_map='AREA_KEYS={'+','.join(repr(name)+':'+repr(key) for name,key,_ in PREFS)+'}'
s,n=re.subn(r"AREA_KEYS=\{[^\n]*\}", full_map, s, count=1)
assert n==1, ('server_area_keys',n)
p.write_text(s,encoding='utf-8')

# Local fallback: keep the same complete mapping for offline/demo behavior.
p=ROOT/'assets'/'app.js'
s=p.read_text(encoding='utf-8')
local_map='const m={'+','.join(repr(name)+':'+repr(key) for name,key,_ in PREFS)+'};return m[name]||\'other\''
s,n=re.subn(r"const m=\{'埼玉県':'saitama'.*?\};return m\[name\]\|\|'other'", local_map, s, count=1)
assert n==1, ('local_area_keys',n)
p.write_text(s,encoding='utf-8')

print('PREFECTURE_SEARCH_OK|prefectures=47|search=grouped|home=grouped|url_area=hydrated|backend_keys=47',flush=True)
