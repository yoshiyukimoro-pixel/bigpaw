from pathlib import Path

p = Path('/app/assets/breed-data.js')
s = p.read_text(encoding='utf-8')

old_sort = """    const sorted=()=>[...(window.BIGPAW_BREEDS||[])].sort((x,y)=>{\n      const xo=!!(x&&x.key===OTHER_KEY),yo=!!(y&&y.key===OTHER_KEY);\n      if(xo!==yo)return xo?1:-1;\n      return String(x.ja||'').localeCompare(String(y.ja||''),'ja');\n    });\n"""

new_sort = """    const kanaRows=[\n      ['あ行','アイウエオヴ'],['か行','カキクケコガギグゲゴ'],['さ行','サシスセソザジズゼゾ'],\n      ['た行','タチツテトダヂヅデド'],['な行','ナニヌネノ'],['は行','ハヒフヘホバビブベボパピプペポ'],\n      ['ま行','マミムメモ'],['や行','ヤユヨ'],['ら行','ラリルレロ'],['わ行','ワヲン']\n    ];\n    function kanaRow(b){\n      if(!b||b.key===OTHER_KEY)return '';\n      if(b.key==='akita')return 'あ行';\n      const c=String(b.ja||'').charAt(0);\n      for(const [label,chars] of kanaRows){if(chars.includes(c))return label;}\n      return '';\n    }\n    const rowOrder=Object.fromEntries(kanaRows.map((r,i)=>[r[0],i]));\n    const sorted=()=>[...(window.BIGPAW_BREEDS||[])].sort((x,y)=>{\n      const xo=!!(x&&x.key===OTHER_KEY),yo=!!(y&&y.key===OTHER_KEY);\n      if(xo!==yo)return xo?1:-1;\n      const xr=rowOrder[kanaRow(x)]??99,yr=rowOrder[kanaRow(y)]??99;\n      if(xr!==yr)return xr-yr;\n      return String(x.ja||'').localeCompare(String(y.ja||''),'ja');\n    });\n"""

old_loop = """      }else{\n        items.forEach(b=>{\n"""

new_loop = """      }else{\n        let lastRow='';\n        items.forEach(b=>{\n          const group=kanaRow(b);\n          if(group&&group!==lastRow){\n            const heading=document.createElement('div');\n            heading.textContent=group;\n            heading.setAttribute('role','presentation');\n            heading.style.cssText='padding:10px 8px 6px;font-size:13px;font-weight:900;color:#8d4564;background:#fff;border-bottom:1px solid #f3e8ed;';\n            list.appendChild(heading);\n            lastRow=group;\n          }\n"""

assert s.count(old_sort) == 1, ('breed_sort_marker_count', s.count(old_sort))
assert s.count(old_loop) == 1, ('breed_loop_marker_count', s.count(old_loop))

s = s.replace(old_sort, new_sort, 1).replace(old_loop, new_loop, 1)
p.write_text(s, encoding='utf-8')

assert "heading.textContent=group" in s
assert "['あ行','アイウエオヴ']" in s
assert "['か行','カキクケコガギグゲゴ']" in s
assert "if(xo!==yo)return xo?1:-1;" in s
print('PUBLIC_BREED_KANA_HEADINGS_OK|headings=hiragana_rows|other=last|image_picker=untouched|breeder_save=untouched', flush=True)
