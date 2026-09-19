from pathlib import Path
p=Path('breeder-puppy-new.html')
s=p.read_text(encoding='utf-8')
s=s.replace('<h2 style="margin-top:22px">写真・動画</h2>','<div id="editOnly" style="display:none"><h2 style="margin-top:22px">販売設定</h2><div class="field"><label>販売状況</label><select id="status"><option>募集中</option><option>商談中</option><option>成約済み</option><option>非公開</option></select></div></div><h2 style="margin-top:22px">写真</h2>')
s=s.replace('<b>メイン写真を追加</b><span class="muted">JPG / PNG / WebP・8MBまで</span><input id="photo" type="file" accept="image/jpeg,image/png,image/webp" style="display:block;margin:14px auto 0;max-width:100%">','<b>写真を追加（最大10枚）</b><span class="muted">1枚目がメイン写真です。JPG / PNG / WebP・各8MBまで</span><input id="photo" type="file" accept="image/jpeg,image/png,image/webp" multiple style="display:block;margin:14px auto 0;max-width:100%"><div id="photoPreview" style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:14px"></div>')
old="async function savePuppy(e){"
insert="""let editId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId');
photo.addEventListener('change',()=>{photoPreview.innerHTML=[...photo.files].slice(0,10).map((f,i)=>'<div><img src=\\\"'+URL.createObjectURL(f)+'\\\" style=\\\"width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:14px\\\"><small>'+(i===0?'メイン写真':'写真 '+(i+1))+'</small></div>').join('')});
async function initEdit(){if(!editId)return;document.querySelector('h1').textContent='子犬情報を編集';editOnly.style.display='block';const ds=await BigPawBridge.breederPuppies();const d=ds.find(x=>String(x.id)===String(editId))||ds.find(x=>String(x.id)===String(sessionStorage.getItem('bigpawEditPuppyId')||''));if(!d){alert('子犬情報を読み込めませんでした');location.href='admin.html';return;}const m={breed:d.breed,gender:d.gender,color:d.color,birth:d.birth,price:d.price,weight:d.weight,adultMin:d.adultMin,adultMax:d.adultMax,father:d.father,mother:d.mother,desc:d.desc,status:d.status};Object.entries(m).forEach(([k,v])=>{const e=document.getElementById(k);if(e&&v!=null)e.value=v});health.checked=!!d.health;if(d.imageUrl)photoPreview.innerHTML='<div><img src=\\\"'+d.imageUrl+'\\\" style=\\\"width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:14px\\\"><small>現在のメイン写真</small></div>';document.querySelector('.btn-wide').textContent='変更を保存する';}
initEdit();
async function savePuppy(e){"""
s=s.replace(old,insert,1)
s=s.replace("let puppy=await BigPawBridge.addPuppy({name:color.value+'の'+gender.value,","let puppy=editId?await BigPawBridge.updatePuppy(editId,{name:color.value+'の'+gender.value,status:status.value,",1)
s=s.replace("breeder:'DOG44'});if(photo.files[0]&&BigPawBridge.isServerMode()){const up=await BigPawBridge.upload(photo.files[0],puppy.id);if(up.url){puppy=await BigPawBridge.updatePuppy(puppy.id,{imageUrl:up.url})}}","breeder:'DOG44'}):await BigPawBridge.addPuppy({name:color.value+'の'+gender.value,breed:breed.value,gender:gender.value,color:color.value,birth:birth.value,price:Number(price.value),weight:Number(weight.value),adultMin:Number(adultMin.value),adultMax:Number(adultMax.value),father:father.value,mother:mother.value,health:health.checked,desc:desc.value,area:'埼玉県',areaKey:'saitama',breeder:'DOG44'});const fs=[...photo.files].slice(0,10);for(let i=0;i<fs.length;i++){const up=await BigPawBridge.upload(fs[i],puppy.id);if(i===0&&up.url)puppy=await BigPawBridge.updatePuppy(puppy.id,{imageUrl:up.url})}",1)
s=s.replace("alert('子犬情報を保存し、掲載審査へ申請しました。承認後に一般公開されます。');","alert(editId?'変更を保存しました。':'子犬情報を掲載しました。');",1)
p.write_text(s,encoding='utf-8')
# Make Edit independent of fragile query-string links: save the puppy id before navigation.
a=Path('admin.html')
if a.exists():
 x=a.read_text(encoding='utf-8')
 import re
 x=re.sub(r'<a class="btn btn-main" href="breeder-puppy-new\\.html[^\"]*">編集</a>', '<button class="btn btn-main" type="button" onclick="sessionStorage.setItem(\'bigpawEditPuppyId\',String(d.id));location.href=\'breeder-puppy-new.html?id=\'+encodeURIComponent(d.id)">編集</button>', x)
 a.write_text(x,encoding='utf-8')

# Final fallback: derive selected puppy from dashboard card text if URL/session id is unavailable.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 x=x.replace("let editId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId');","let editId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId');")
 x=x.replace("const d=ds.find(x=>String(x.id)===String(editId))||ds.find(x=>String(x.id)===String(sessionStorage.getItem('bigpawEditPuppyId')||''));","let d=ds.find(x=>String(x.id)===String(editId))||ds.find(x=>String(x.id)===String(sessionStorage.getItem('bigpawEditPuppyId')||''));if(!d&&ds.length===1)d=ds[0];")
 p.write_text(x,encoding='utf-8')

# Correct the literal broken anchor produced by the original dashboard template.
a=Path('admin.html')
if a.exists():
 x=a.read_text(encoding='utf-8')
 x=x.replace('href="breeder-puppy-new.html?id=\'+encodeURIComponent(d.id)+\'"','href="breeder-puppy-new.html?id=${encodeURIComponent(d.id)}"')
 x=x.replace('href="breeder-puppy-new.html?id=\'+p.id+\'"','href="breeder-puppy-new.html?id=${encodeURIComponent(d.id)}"')
 a.write_text(x,encoding='utf-8')

# Polish edit-mode labels and add delete control in the editor.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 x=x.replace("document.querySelector('h1').textContent='子犬情報を編集';editOnly.style.display='block';","document.querySelector('h1').textContent='子犬情報を編集';const bc=document.querySelector('.breadcrumb');if(bc)bc.innerHTML='<a href=\"admin.html\">管理画面</a> ＞ 子犬情報を編集';editOnly.style.display='block';")
 x=x.replace("<button class=\"btn btn-main btn-wide\">この内容で掲載する</button>","<button class=\"btn btn-main btn-wide\">この内容で掲載する</button><button id=\"deletePuppyBtn\" type=\"button\" class=\"btn btn-sub btn-wide\" style=\"display:none;margin-top:10px\" onclick=\"deleteCurrentPuppy()\">この子犬の掲載を削除</button>")
 x=x.replace("document.querySelector('.btn-wide').textContent='変更を保存する';","document.querySelector('.btn-wide').textContent='変更を保存する';const db=document.getElementById('deletePuppyBtn');if(db)db.style.display='block';")
 x=x.replace("initEdit();","async function deleteCurrentPuppy(){if(!editId||!confirm('この子犬の掲載を削除しますか？'))return;try{await BigPawAPI.request('/puppies/'+encodeURIComponent(editId),{method:'DELETE'});location.href='admin.html'}catch(e){alert('削除できませんでした')}}\ninitEdit();",1)
 p.write_text(x,encoding='utf-8')

# Improve photo editor UX: clear main/additional slots, replacement preview, and guidance.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 x=x.replace('<b>写真を追加（最大10枚）</b><span class="muted">1枚目がメイン写真です。JPG / PNG / WebP・各8MBまで</span>','<b>写真を編集（最大10枚）</b><span class="muted">1枚目がメイン写真です。写真を選び直すとメイン写真から順に差し替えます。JPG / PNG / WebP・各8MBまで</span>')
 x=x.replace("'<small>現在のメイン写真</small></div>'","'<small>現在のメイン写真</small></div><div class=\\\"muted\\\" style=\\\"grid-column:1/-1\\\">新しい写真を選ぶとプレビューがここに表示されます。</div>'")
 p.write_text(x,encoding='utf-8')

# Add client-side photo ordering/main selection/removal for newly selected photos.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 old="photo.addEventListener('change',()=>{photoPreview.innerHTML=[...photo.files].slice(0,10).map((f,i)=>'<div><img src=\\\"'+URL.createObjectURL(f)+'\\\" style=\\\"width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:14px\\\"><small>'+(i===0?'メイン写真':'写真 '+(i+1))+'</small></div>').join('')});"
 new="""let selectedPhotos=[];
function syncPhotoInput(){const dt=new DataTransfer();selectedPhotos.forEach(f=>dt.items.add(f));photo.files=dt.files}
function renderSelectedPhotos(){photoPreview.innerHTML=selectedPhotos.map((f,i)=>'<div style="border:1px solid #eee;border-radius:14px;padding:8px"><img src="'+URL.createObjectURL(f)+'" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px"><small style="display:block">'+(i===0?'メイン写真':'写真 '+(i+1))+'</small><div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:6px"><button type="button" class="btn btn-sub" onclick="makeMain('+i+')">メインにする</button><button type="button" class="btn btn-sub" onclick="movePhoto('+i+',-1)">←</button><button type="button" class="btn btn-sub" onclick="movePhoto('+i+',1)">→</button><button type="button" class="btn btn-sub" onclick="removePhoto('+i+')">削除</button></div></div>').join('')}
function makeMain(i){const f=selectedPhotos.splice(i,1)[0];selectedPhotos.unshift(f);syncPhotoInput();renderSelectedPhotos()}
function movePhoto(i,n){const j=i+n;if(j<0||j>=selectedPhotos.length)return;[selectedPhotos[i],selectedPhotos[j]]=[selectedPhotos[j],selectedPhotos[i]];syncPhotoInput();renderSelectedPhotos()}
function removePhoto(i){selectedPhotos.splice(i,1);syncPhotoInput();renderSelectedPhotos()}
photo.addEventListener('change',()=>{selectedPhotos=[...photo.files].slice(0,10);syncPhotoInput();renderSelectedPhotos()});"""
 if old in x:x=x.replace(old,new)
 p.write_text(x,encoding='utf-8')

# Force-install photo controls independent of the original listener formatting.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 marker="async function initEdit(){"
 code=r'''let selectedPhotos=[];
function syncPhotoInput(){const dt=new DataTransfer();selectedPhotos.forEach(f=>dt.items.add(f));photo.files=dt.files}
function renderSelectedPhotos(){photoPreview.innerHTML=selectedPhotos.map((f,i)=>'<div style="border:1px solid #eee;border-radius:14px;padding:8px"><img src="'+URL.createObjectURL(f)+'" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px"><small style="display:block">'+(i===0?'メイン写真':'写真 '+(i+1))+'</small><div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:6px"><button type="button" onclick="makeMain('+i+')">メインにする</button><button type="button" onclick="movePhoto('+i+',-1)">←</button><button type="button" onclick="movePhoto('+i+',1)">→</button><button type="button" onclick="removePhoto('+i+')">削除</button></div></div>').join('')}
function makeMain(i){if(i<0||i>=selectedPhotos.length)return;const f=selectedPhotos.splice(i,1)[0];selectedPhotos.unshift(f);syncPhotoInput();renderSelectedPhotos()}
function movePhoto(i,n){const j=i+n;if(j<0||j>=selectedPhotos.length)return;[selectedPhotos[i],selectedPhotos[j]]=[selectedPhotos[j],selectedPhotos[i]];syncPhotoInput();renderSelectedPhotos()}
function removePhoto(i){selectedPhotos.splice(i,1);syncPhotoInput();renderSelectedPhotos()}
photo.onchange=()=>{selectedPhotos=[...photo.files].slice(0,10);syncPhotoInput();renderSelectedPhotos()};
'''
 if marker in x and "function makeMain(i)" not in x:x=x.replace(marker,code+marker,1)
 p.write_text(x,encoding='utf-8')

# Existing-photo editor: show registered main photo with replace/remove controls.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 old="if(d.imageUrl)photoPreview.innerHTML='<div><img src=\\\"'+d.imageUrl+'\\\" style=\\\"width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:14px\\\"><small>現在のメイン写真</small></div><div class=\\\"muted\\\" style=\\\"grid-column:1/-1\\\">新しい写真を選ぶとプレビューがここに表示されます。</div>';"
 new="""if(d.imageUrl){window.existingMainImage=d.imageUrl;photoPreview.innerHTML='<div id="existingMainPhoto" style="border:1px solid #eee;border-radius:14px;padding:8px"><img src="'+d.imageUrl+'" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px"><small style="display:block">現在のメイン写真</small><button type="button" onclick="removeExistingMain()" style="margin-top:6px">この写真を削除</button></div><div class="muted" style="grid-column:1/-1">新しい写真を選ぶと、選んだ1枚目をメイン写真として差し替えできます。</div>';}"""
 if old in x:x=x.replace(old,new)
 marker="async function initEdit(){"
 helper="""function removeExistingMain(){if(!confirm('現在のメイン写真を削除しますか？'))return;window.existingMainImage='';const e=document.getElementById('existingMainPhoto');if(e)e.remove();window.removeExistingMainRequested=true;}\n"""
 if marker in x and "function removeExistingMain()" not in x:x=x.replace(marker,helper+marker,1)
 # Persist clearing the current main photo when no replacement was selected.
 needle="let puppy=editId?await BigPawBridge.updatePuppy(editId,{"
 if needle in x:x=x.replace(needle,"if(editId&&window.removeExistingMainRequested&&photo.files.length===0)await BigPawBridge.updatePuppy(editId,{imageUrl:''});\nlet puppy=editId?await BigPawBridge.updatePuppy(editId,{",1)
 p.write_text(x,encoding='utf-8')

# Add authenticated owner-only puppy DELETE endpoint.
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 anchor="        if path=='/api/me':\n            u=self.require()"
 block="""        m=re.fullmatch(r'/api/puppies/([^/]+)',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            # Do not hard-delete a puppy already referenced by a transaction.
            if con.execute('SELECT 1 FROM inquiries WHERE puppy_id=? LIMIT 1',(puppy['id'],)).fetchone() or con.execute('SELECT 1 FROM deals WHERE puppy_id=? LIMIT 1',(puppy['id'],)).fetchone():
                con.close(); return self.send_json({'error':'puppy_has_transactions','message':'問い合わせ・取引履歴があるため削除できません。非公開に変更してください。'},409)
            uploads=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=?',(puppy['id'],)).fetchall()
            con.execute('DELETE FROM uploads WHERE puppy_id=?',(puppy['id'],))
            con.execute('DELETE FROM favorites WHERE puppy_id=?',(puppy['id'],))
            con.execute('DELETE FROM puppies WHERE id=?',(puppy['id'],))
            audit(con,u['id'],'puppy_deleted','puppy',puppy['id'])
            con.commit(); con.close()
            for row in uploads:
                try:(UPLOADS / row['stored_name']).unlink(missing_ok=True)
                except Exception:pass
            return self.send_json({'ok':True})
"""
 # insert only into do_DELETE section, before /api/me
 pos=x.find("    def do_DELETE(self):")
 if pos>=0 and "puppy_has_transactions" not in x[pos:x.find("    def do_PATCH",pos)]:
  a=x.find(anchor,pos)
  if a>=0:x=x[:a]+block+x[a:]
 p.write_text(x,encoding='utf-8')


# Persistent multi-photo API + existing photo editor.
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 # GET owned puppy photos.
 marker="    def do_DELETE(self):"
 getcode="""        m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            rows=con.execute('SELECT id,stored_name,created_at FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(puppy['id'],)).fetchall()
            out=[{'id':r['id'],'url':'/uploads/'+r['stored_name'],'isMain':('/uploads/'+r['stored_name'])==puppy['image_url']} for r in rows]
            con.close(); return self.send_json(out)
"""
 # insert into do_GET, immediately before do_DELETE marker (same class scope)
 if marker in x and "/photos',path)" not in x:
  x=x.replace(marker,getcode+"\n"+marker,1)
 # DELETE one owned upload.
 dpos=x.find("    def do_DELETE(self):")
 anchor="        if path=='/api/me':\n            u=self.require()"
 photodel="""        m=re.fullmatch(r'/api/puppies/([^/]+)/photos/([^/]+)',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            up=con.execute('SELECT * FROM uploads WHERE id=? AND puppy_id=?',(m.group(2),puppy['id'])).fetchone()
            if not up: con.close(); return self.send_json({'error':'not_found'},404)
            was_main=puppy['image_url']==('/uploads/'+up['stored_name'])
            con.execute('DELETE FROM uploads WHERE id=?',(up['id'],))
            if was_main:
                nxt=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=? ORDER BY created_at,id LIMIT 1',(puppy['id'],)).fetchone()
                con.execute('UPDATE puppies SET image_url=? WHERE id=?',(('/uploads/'+nxt['stored_name']) if nxt else '',puppy['id']))
            con.commit(); con.close()
            try:(UPLOADS/up['stored_name']).unlink(missing_ok=True)
            except Exception:pass
            return self.send_json({'ok':True})
"""
 if dpos>=0 and "photos/([^/]+)" not in x[dpos:]:
  a=x.find(anchor,dpos)
  if a>=0:x=x[:a]+photodel+x[a:]
 p.write_text(x,encoding='utf-8')

p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 # Load all persisted photos after the puppy is loaded.
 needle="health.checked=!!d.health;"
 load="""health.checked=!!d.health;
try{const ps=await BigPawAPI.request('/puppies/'+encodeURIComponent(editId)+'/photos');if(ps&&ps.length){window.persistedPhotos=ps;renderPersistedPhotos();}}catch(e){}"""
 if needle in x and "window.persistedPhotos=ps" not in x:x=x.replace(needle,load,1)
 # Existing persistent photo controls.
 marker="function removeExistingMain(){"
 code="""function renderPersistedPhotos(){if(!window.persistedPhotos)return;photoPreview.innerHTML=window.persistedPhotos.map((p,i)=>'<div style="border:1px solid #eee;border-radius:14px;padding:8px"><img src="'+p.url+'" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px"><small style="display:block">'+(p.isMain?'メイン写真':'登録済み写真')+'</small><div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:6px">'+(!p.isMain?'<button type="button" onclick="setPersistedMain('+i+')">メインにする</button>':'')+'<button type="button" onclick="deletePersistedPhoto('+i+')">削除</button></div></div>').join('')}
async function setPersistedMain(i){const p=window.persistedPhotos&&window.persistedPhotos[i];if(!p)return;await BigPawBridge.updatePuppy(editId,{imageUrl:p.url});window.persistedPhotos.forEach(q=>q.isMain=false);p.isMain=true;renderPersistedPhotos()}
async function deletePersistedPhoto(i){const p=window.persistedPhotos&&window.persistedPhotos[i];if(!p||!confirm('この写真を削除しますか？'))return;try{await BigPawAPI.request('/puppies/'+encodeURIComponent(editId)+'/photos/'+encodeURIComponent(p.id),{method:'DELETE'});window.persistedPhotos.splice(i,1);if(p.isMain&&window.persistedPhotos.length)window.persistedPhotos[0].isMain=true;renderPersistedPhotos()}catch(e){alert('写真を削除できませんでした')}}
"""
 if marker in x and "function renderPersistedPhotos()" not in x:x=x.replace(marker,code+marker,1)
 p.write_text(x,encoding='utf-8')


# Replace confusing reorder arrows with touch-friendly photo crop/position editor.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 # Newly selected photos: remove arrows, add adjustment.
 x=x.replace('<button type="button" onclick="movePhoto(\'+i+\',-1)">←</button><button type="button" onclick="movePhoto(\'+i+\',1)">→</button>','<button type="button" onclick="openPhotoAdjust(i)">写真を調整</button>')
 # Persistent photos: add adjustment button.
 x=x.replace("(!p.isMain?'<button type=\"button\" onclick=\"setPersistedMain('+i+')\">メインにする</button>':'')+'<button type=\"button\" onclick=\"deletePersistedPhoto('+i+')\">削除</button>'","(!p.isMain?'<button type=\"button\" onclick=\"setPersistedMain('+i+')\">メインにする</button>':'')+'<button type=\"button\" onclick=\"openPersistedAdjust('+i+')\">写真を調整</button><button type=\"button\" onclick=\"deletePersistedPhoto('+i+')\">削除</button>'")
 marker="function makeMain(i){"
 editor=r'''let adjustTarget=null,adjustScale=1,adjustX=0,adjustY=0,adjustStart=null;
function ensureAdjustModal(){if(document.getElementById('photoAdjustModal'))return;document.body.insertAdjacentHTML('beforeend','<div id="photoAdjustModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:9999;padding:20px"><div style="max-width:520px;margin:5vh auto;background:white;border-radius:16px;padding:14px"><b>写真を調整</b><div id="adjustFrame" style="margin-top:12px;width:100%;aspect-ratio:1/1;overflow:hidden;background:#eee;touch-action:none;position:relative"><img id="adjustImg" style="width:100%;height:100%;object-fit:cover;transform-origin:center;user-select:none;-webkit-user-drag:none"></div><div style="margin-top:10px">2本指で拡大・縮小、1本指で上下左右に移動できます。</div><div style="display:flex;gap:8px;margin-top:12px"><button type="button" onclick="closePhotoAdjust()">キャンセル</button><button type="button" onclick="applyPhotoAdjust()">決定</button></div></div></div>');const fr=document.getElementById('adjustFrame');fr.addEventListener('pointerdown',adjustDown);fr.addEventListener('pointermove',adjustMove);fr.addEventListener('pointerup',adjustUp);fr.addEventListener('pointercancel',adjustUp);fr.addEventListener('wheel',e=>{e.preventDefault();adjustScale=Math.max(1,Math.min(4,adjustScale+(e.deltaY<0?.1:-.1)));drawAdjust()},{passive:false});}
function drawAdjust(){const im=document.getElementById('adjustImg');if(im)im.style.transform='translate('+adjustX+'px,'+adjustY+'px) scale('+adjustScale+')'}
function openPhotoAdjust(i){const f=selectedPhotos[i];if(!f)return;ensureAdjustModal();adjustTarget={kind:'new',i:i};adjustScale=1;adjustX=0;adjustY=0;document.getElementById('adjustImg').src=URL.createObjectURL(f);document.getElementById('photoAdjustModal').style.display='block';drawAdjust()}
function openPersistedAdjust(i){const p=window.persistedPhotos&&window.persistedPhotos[i];if(!p)return;ensureAdjustModal();adjustTarget={kind:'saved',i:i};adjustScale=1;adjustX=0;adjustY=0;document.getElementById('adjustImg').src=p.url;document.getElementById('photoAdjustModal').style.display='block';drawAdjust()}
function closePhotoAdjust(){const m=document.getElementById('photoAdjustModal');if(m)m.style.display='none';adjustTarget=null}
function adjustDown(e){e.currentTarget.setPointerCapture(e.pointerId);adjustStart={x:e.clientX,y:e.clientY,ox:adjustX,oy:adjustY}}
function adjustMove(e){if(!adjustStart)return;adjustX=adjustStart.ox+e.clientX-adjustStart.x;adjustY=adjustStart.oy+e.clientY-adjustStart.y;drawAdjust()}
function adjustUp(){adjustStart=null}
async function applyPhotoAdjust(){const im=document.getElementById('adjustImg'),fr=document.getElementById('adjustFrame');if(!adjustTarget||!im.complete)return;const size=1000,c=document.createElement('canvas');c.width=c.height=size;const ctx=c.getContext('2d');const iw=im.naturalWidth,ih=im.naturalHeight,base=Math.max(size/iw,size/ih),sc=base*adjustScale,w=iw*sc,h=ih*sc;ctx.drawImage(im,(size-w)/2+adjustX*(size/fr.clientWidth),(size-h)/2+adjustY*(size/fr.clientWidth),w,h);const blob=await new Promise(r=>c.toBlob(r,'image/jpeg',.92));const file=new File([blob],'adjusted-'+Date.now()+'.jpg',{type:'image/jpeg'});if(adjustTarget.kind==='new'){selectedPhotos[adjustTarget.i]=file;syncPhotoInput();renderSelectedPhotos();closePhotoAdjust();return}try{const old=window.persistedPhotos[adjustTarget.i];const up=await BigPawBridge.upload(file,editId);if(old.isMain&&up.url)await BigPawBridge.updatePuppy(editId,{imageUrl:up.url});await BigPawAPI.request('/puppies/'+encodeURIComponent(editId)+'/photos/'+encodeURIComponent(old.id),{method:'DELETE'});window.persistedPhotos[adjustTarget.i]={id:up.id,url:up.url,isMain:old.isMain};renderPersistedPhotos();closePhotoAdjust()}catch(e){alert('写真の調整を保存できませんでした')}}
'''
 if marker in x and "function openPhotoAdjust(i)" not in x:x=x.replace(marker,editor+marker,1)
 p.write_text(x,encoding='utf-8')


# Fix persisted gallery being overwritten by legacy main-photo render; add real iPhone pinch gesture.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 # Do not overwrite the full persisted gallery with the legacy single main image.
 x=x.replace("if(d.imageUrl){window.existingMainImage=d.imageUrl;photoPreview.innerHTML='<div id=\"existingMainPhoto\"", "if(d.imageUrl&&!(window.persistedPhotos&&window.persistedPhotos.length)){window.existingMainImage=d.imageUrl;photoPreview.innerHTML='<div id=\"existingMainPhoto\"")
 # Enhance modal with native two-touch pinch plus one-finger pan.
 old="const fr=document.getElementById('adjustFrame');fr.addEventListener('pointerdown',adjustDown);fr.addEventListener('pointermove',adjustMove);fr.addEventListener('pointerup',adjustUp);fr.addEventListener('pointercancel',adjustUp);"
 new="""const fr=document.getElementById('adjustFrame');fr.addEventListener('pointerdown',adjustDown);fr.addEventListener('pointermove',adjustMove);fr.addEventListener('pointerup',adjustUp);fr.addEventListener('pointercancel',adjustUp);let ts=null;fr.addEventListener('touchstart',e=>{e.preventDefault();if(e.touches.length===2){const a=e.touches[0],b=e.touches[1];ts={kind:'pinch',dist:Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY),scale:adjustScale,x:adjustX,y:adjustY,cx:(a.clientX+b.clientX)/2,cy:(a.clientY+b.clientY)/2}}else if(e.touches.length===1){const a=e.touches[0];ts={kind:'pan',sx:a.clientX,sy:a.clientY,x:adjustX,y:adjustY}}},{passive:false});fr.addEventListener('touchmove',e=>{e.preventDefault();if(!ts)return;if(e.touches.length===2&&ts.kind==='pinch'){const a=e.touches[0],b=e.touches[1],dist=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);adjustScale=Math.max(1,Math.min(4,ts.scale*dist/Math.max(1,ts.dist)));adjustX=ts.x+((a.clientX+b.clientX)/2-ts.cx);adjustY=ts.y+((a.clientY+b.clientY)/2-ts.cy);drawAdjust()}else if(e.touches.length===1&&ts.kind==='pan'){const a=e.touches[0];adjustX=ts.x+a.clientX-ts.sx;adjustY=ts.y+a.clientY-ts.sy;drawAdjust()}},{passive:false});fr.addEventListener('touchend',e=>{if(e.touches.length===0)ts=null},{passive:false});"""
 if old in x:x=x.replace(old,new,1)
 p.write_text(x,encoding='utf-8')


# Correct photo GET route placement inside do_GET and force gallery render after legacy main preview.
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 bad="""        m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            rows=con.execute('SELECT id,stored_name,created_at FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(puppy['id'],)).fetchall()
            out=[{'id':r['id'],'url':'/uploads/'+r['stored_name'],'isMain':('/uploads/'+r['stored_name'])==puppy['image_url']} for r in rows]
            con.close(); return self.send_json(out)

"""
 # remove unreachable copy before do_DELETE
 d=x.find("    def do_DELETE(self):")
 b=x.rfind(bad,0,d)
 if b>=0:x=x[:b]+x[b+len(bad):]
 # place route in do_GET before its final not_found, specifically before do_POST.
 gs=x.find("    def do_GET(self):"); pe=x.find("    def do_POST(self):",gs)
 if gs>=0 and pe>gs and "/photos',path)" not in x[gs:pe]:
  nf=x.rfind("        return self.send_json({'error':'not_found'},404)",gs,pe)
  if nf>=0:x=x[:nf]+bad+x[nf:]
 p.write_text(x,encoding='utf-8')

p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 legacy="""if(d.imageUrl)photoPreview.innerHTML='<div><img src=\\"'+d.imageUrl+'\\" style=\\"width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:14px\\"><small>現在のメイン写真</small></div>';"""
 if legacy in x:x=x.replace(legacy,"if(d.imageUrl&&!(window.persistedPhotos&&window.persistedPhotos.length))photoPreview.innerHTML='<div><img src=\\\"'+d.imageUrl+'\\\" style=\\\"width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:14px\\\"><small>現在のメイン写真</small></div>';if(window.persistedPhotos&&window.persistedPhotos.length)renderPersistedPhotos();",1)
 p.write_text(x,encoding='utf-8')


# Definitive insertion of photo GET route at the top of do_GET (before any early return).
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 route="""        m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            rows=con.execute('SELECT id,stored_name,created_at FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(puppy['id'],)).fetchall()
            out=[{'id':r['id'],'url':'/uploads/'+r['stored_name'],'isMain':('/uploads/'+r['stored_name'])==puppy['image_url']} for r in rows]
            con.close(); return self.send_json(out)
"""
 gs=x.find("    def do_GET(self):")
 pe=x.find("    def do_POST(self):",gs)
 if gs>=0 and pe>gs and "/photos',path)" not in x[gs:pe]:
  pathline=x.find("        path=urlparse(self.path).path",gs,pe)
  if pathline>=0:
   end=x.find("\\n",pathline)+1
   x=x[:end]+route+x[end:]
 p.write_text(x,encoding='utf-8')


# Insert gallery GET after do_GET's actual combined parsed/path assignment.
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 route="""        m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            rows=con.execute('SELECT id,stored_name,created_at FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(puppy['id'],)).fetchall()
            out=[{'id':r['id'],'url':'/uploads/'+r['stored_name'],'isMain':('/uploads/'+r['stored_name'])==puppy['image_url']} for r in rows]
            con.close(); return self.send_json(out)
"""
 gs=x.find("    def do_GET(self):"); pe=x.find("    def do_POST(self):",gs)
 if gs>=0 and pe>gs and "/photos',path)" not in x[gs:pe]:
  needle="        parsed=urlparse(self.path); path=parsed.path; q=parse_qs(parsed.query)\n"
  a=x.find(needle,gs,pe)
  if a>=0:
   a+=len(needle);x=x[:a]+route+x[a:]
 p.write_text(x,encoding='utf-8')


# Force final UI renderers so every photo has an Adjust button; use pointer-based 2-finger pinch.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 marker="async function initEdit(){"
 override=r'''// Final photo UI overrides.
renderSelectedPhotos=function(){photoPreview.innerHTML=selectedPhotos.map((f,i)=>'<div style="border:1px solid #eee;border-radius:14px;padding:8px"><img src="'+URL.createObjectURL(f)+'" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px"><small style="display:block">'+(i===0?'メイン写真':'写真 '+(i+1))+'</small><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px"><button type="button" onclick="makeMain('+i+')">メインにする</button><button type="button" onclick="openPhotoAdjust('+i+')">写真を調整</button><button type="button" onclick="removePhoto('+i+')">削除</button></div></div>').join('')};
renderPersistedPhotos=function(){if(!window.persistedPhotos)return;photoPreview.innerHTML=window.persistedPhotos.map((p,i)=>'<div style="border:1px solid #eee;border-radius:14px;padding:8px"><img src="'+p.url+'" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px"><small style="display:block">'+(p.isMain?'メイン写真':'登録済み写真')+'</small><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">'+(!p.isMain?'<button type="button" onclick="setPersistedMain('+i+')">メインにする</button>':'')+'<button type="button" onclick="openPersistedAdjust('+i+')">写真を調整</button><button type="button" onclick="deletePersistedPhoto('+i+')">削除</button></div></div>').join('')};
ensureAdjustModal=function(){if(document.getElementById('photoAdjustModal'))return;document.body.insertAdjacentHTML('beforeend','<div id="photoAdjustModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:9999;padding:12px"><div style="max-width:520px;margin:3vh auto;background:#fff;border-radius:16px;padding:14px"><b>写真を調整</b><div id="adjustFrame" style="margin-top:12px;width:100%;aspect-ratio:1/1;overflow:hidden;background:#eee;touch-action:none;position:relative"><img id="adjustImg" draggable="false" style="width:100%;height:100%;object-fit:cover;transform-origin:center;user-select:none;-webkit-user-drag:none"></div><div style="margin-top:10px">1本指で移動・2本指で拡大縮小</div><div style="display:flex;gap:8px;margin-top:12px"><button type="button" onclick="closePhotoAdjust()">キャンセル</button><button type="button" onclick="applyPhotoAdjust()">決定</button></div></div></div>');const fr=document.getElementById('adjustFrame'),pts=new Map();let base=null;const calc=()=>{const a=[...pts.values()];if(a.length===1){if(!base)base={n:1,x:a[0].x,y:a[0].y,ox:adjustX,oy:adjustY};adjustX=base.ox+a[0].x-base.x;adjustY=base.oy+a[0].y-base.y;drawAdjust()}else if(a.length>=2){const dist=Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y),cx=(a[0].x+a[1].x)/2,cy=(a[0].y+a[1].y)/2;if(!base||base.n!==2)base={n:2,dist:dist,scale:adjustScale,cx:cx,cy:cy,ox:adjustX,oy:adjustY};adjustScale=Math.max(1,Math.min(4,base.scale*dist/Math.max(1,base.dist)));adjustX=base.ox+cx-base.cx;adjustY=base.oy+cy-base.cy;drawAdjust()}};fr.onpointerdown=e=>{e.preventDefault();fr.setPointerCapture(e.pointerId);pts.set(e.pointerId,{x:e.clientX,y:e.clientY});base=null;calc()};fr.onpointermove=e=>{if(!pts.has(e.pointerId))return;e.preventDefault();pts.set(e.pointerId,{x:e.clientX,y:e.clientY});calc()};const end=e=>{pts.delete(e.pointerId);base=null};fr.onpointerup=end;fr.onpointercancel=end;};
'''
 if marker in x and "// Final photo UI overrides." not in x:x=x.replace(marker,override+marker,1)
 p.write_text(x,encoding='utf-8')


# Keep the original upload when cropping so adjustment is always reversible.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 marker="// Final photo UI overrides."
 patch=r'''// Reversible photo adjustment: always edit from the original source.
const originalPhotoSources=new Map();
const _openPersistedAdjust=openPersistedAdjust;
openPersistedAdjust=function(i){const p=window.persistedPhotos&&window.persistedPhotos[i];if(!p)return;ensureAdjustModal();adjustTarget={kind:'saved',i:i};adjustScale=1;adjustX=0;adjustY=0;const src=p.originalUrl||originalPhotoSources.get(p.id)||p.url;originalPhotoSources.set(p.id,src);p.originalUrl=src;document.getElementById('adjustImg').src=src;document.getElementById('photoAdjustModal').style.display='block';drawAdjust()};
const _openPhotoAdjust=openPhotoAdjust;
openPhotoAdjust=function(i){const f=selectedPhotos[i];if(!f)return;ensureAdjustModal();if(!f._bigpawOriginal)try{Object.defineProperty(f,'_bigpawOriginal',{value:f,writable:true})}catch(e){}adjustTarget={kind:'new',i:i};adjustScale=1;adjustX=0;adjustY=0;const src=f._bigpawOriginal||f;document.getElementById('adjustImg').src=URL.createObjectURL(src);document.getElementById('photoAdjustModal').style.display='block';drawAdjust()};
'''
 if marker in x and "Reversible photo adjustment" not in x:x=x.replace(marker,patch+marker,1)
 # When replacing a selected file with a crop, preserve its original File reference.
 old="selectedPhotos[adjustTarget.i]=file;syncPhotoInput();renderSelectedPhotos();closePhotoAdjust();return"
 new="const prev=selectedPhotos[adjustTarget.i];try{Object.defineProperty(file,'_bigpawOriginal',{value:(prev&&prev._bigpawOriginal)||prev,writable:true})}catch(e){}selectedPhotos[adjustTarget.i]=file;syncPhotoInput();renderSelectedPhotos();closePhotoAdjust();return"
 if old in x:x=x.replace(old,new,1)
 # When replacing a persisted upload, retain originalUrl in client state.
 old2="window.persistedPhotos[adjustTarget.i]={id:up.id,url:up.url,isMain:old.isMain};renderPersistedPhotos();closePhotoAdjust()"
 new2="window.persistedPhotos[adjustTarget.i]={id:up.id,url:up.url,isMain:old.isMain,originalUrl:old.originalUrl||originalPhotoSources.get(old.id)||old.url};originalPhotoSources.set(up.id,window.persistedPhotos[adjustTarget.i].originalUrl);renderPersistedPhotos();closePhotoAdjust()"
 if old2 in x:x=x.replace(old2,new2,1)
 p.write_text(x,encoding='utf-8')


# Fix zoom-out: allow the whole source photo to fit inside the square, including letterbox space.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 marker="// Reversible photo adjustment: always edit from the original source."
 patch=r'''// Allow zooming out below cover-size so the original full image can be restored.
const _drawAdjustCover=drawAdjust;
drawAdjust=function(){const im=document.getElementById('adjustImg');if(im)im.style.transform='translate('+adjustX+'px,'+adjustY+'px) scale('+adjustScale+')'};
'''
 if marker in x and "Allow zooming out below cover-size" not in x:x=x.replace(marker,patch+marker,1)
 # Start the editor at 1x but permit pinch down to 0.35x rather than hard-clamping at 1.
 x=x.replace("Math.max(1,Math.min(4,base.scale*dist/Math.max(1,base.dist)))","Math.max(.35,Math.min(4,base.scale*dist/Math.max(1,base.dist)))")
 # Old touch implementation may still be used in some builds.
 x=x.replace("Math.max(1,Math.min(4,ts.scale*dist/Math.max(1,ts.dist)))","Math.max(.35,Math.min(4,ts.scale*dist/Math.max(1,ts.dist)))")
 x=x.replace("Math.max(1,Math.min(4,adjustScale+(e.deltaY<0?.1:-.1)))","Math.max(.35,Math.min(4,adjustScale+(e.deltaY<0?.1:-.1)))")
 p.write_text(x,encoding='utf-8')


# Approved breeders publish puppies immediately; normalize any legacy pending puppies for approved breeders.
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 # Normalize legacy rows at startup so already-created listings become public.
 marker="def db():"
 # Add helper-independent startup SQL at init location by patching init_db's commit if available.
 init=x.find("def init_db(")
 if init>=0:
  end=x.find("\ndef ",init+1)
  if end<0:end=len(x)
  sec=x[init:end]
  if "legacy approved breeder puppies" not in sec:
   c=sec.rfind("con.commit()")
   if c>=0:
    pos=init+c
    code="""# legacy approved breeder puppies: approved breeders publish directly
    con.execute(\"UPDATE puppies SET review_status='approved' WHERE review_status!='approved' AND breeder_id IN (SELECT id FROM breeders WHERE review_status='approved')\")
    """
    x=x[:pos]+code+x[pos:]
 # On puppy creation, if the owning breeder is approved, force puppy approved.
 post=x.find("    def do_POST(self):")
 if post>=0 and "approved breeder direct publish" not in x[post:]:
  needle="con.commit(); con.close(); return self.send_json(puppy_json("
  a=x.find(needle,post)
  if a>=0:
   inject="""# approved breeder direct publish
            con.execute(\"UPDATE puppies SET review_status='approved' WHERE id=? AND breeder_id IN (SELECT id FROM breeders WHERE review_status='approved')\",(pid,))
            """
   x=x[:a]+inject+x[a:]
 p.write_text(x,encoding='utf-8')


# Public search: listings owned by an approved breeder are public even if an old puppy review flag stayed pending.
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 old="WHERE p.review_status='approved' AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
 new="WHERE (p.review_status='approved' OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
 x=x.replace(old,new)
 old2="WHERE p.id=? AND p.review_status='approved' AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
 new2="WHERE p.id=? AND (p.review_status='approved' OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
 x=x.replace(old2,new2)
 p.write_text(x,encoding='utf-8')


# Canonicalize breed keys for puppy create/edit so public breed picker matches stored listings.
p=Path('breeder-puppy-new.html')
if p.exists():
 x=p.read_text(encoding='utf-8')
 marker="async function savePuppy(e){"
 if marker in x and "function bigpawBreedKey" not in x:
  helper="""function bigpawBreedKey(name){const a=Array.isArray(window.BIGPAW_BREEDS)?window.BIGPAW_BREEDS:[];const b=a.find(v=>v.ja===name);return b?b.key:({'スタンダードプードル':'standard-poodle','ゴールデンレトリバー':'golden-retriever','ラブラドールレトリバー':'labrador-retriever'}[name]||name)}\n"""
  x=x.replace(marker,helper+marker,1)
 # Explicitly send breedKey in both update/create payloads.
 x=x.replace("status:status.value,breed:breed.value,gender:", "status:status.value,breed:breed.value,breedKey:bigpawBreedKey(breed.value),gender:")
 x=x.replace("name:color.value+'の'+gender.value,breed:breed.value,gender:", "name:color.value+'の'+gender.value,breed:breed.value,breedKey:bigpawBreedKey(breed.value),gender:")
 # Ensure breed data is available on editor.
 if '<script src="assets/breed-data.js"></script>' not in x:
  x=x.replace('<script src="assets/bridge.js"></script>','<script src="assets/bridge.js"></script><script src="assets/breed-data.js"></script>')
 p.write_text(x,encoding='utf-8')

# Server-side normalization also repairs existing listings saved with Japanese breed_key.
p=Path('backend/server.py')
if p.exists():
 x=p.read_text(encoding='utf-8')
 init=x.find("def init_db(")
 if init>=0:
  end=x.find("\ndef ",init+1)
  if end<0:end=len(x)
  sec=x[init:end]
  if "normalize legacy breed keys" not in sec:
   c=sec.rfind("con.commit()")
   if c>=0:
    pos=init+c
    code="""# normalize legacy breed keys used by public search
    con.execute(\"UPDATE puppies SET breed_key='standard-poodle' WHERE breed='スタンダードプードル' AND breed_key!='standard-poodle'\")
    """
    x=x[:pos]+code+x[pos:]
 p.write_text(x,encoding='utf-8')
