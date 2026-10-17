"""Free, human-in-the-loop registration certificate comparison, no external AI."""
from pathlib import Path
ROOT=Path('/app')
SERVER=ROOT/'backend/server.py'
s=SERVER.read_text(encoding='utf-8')
def once(src,a,b,label):
    assert src.count(a)==1,(label,src.count(a))
    return src.replace(a,b,1)
marker="""                if not all(mandatory):
                    con.close()
                    return self.send_json({'error':'incomplete_legal_disclosure',
                        'message':'第一種動物取扱業の法定表示情報が不足しています。申請者に再申請を依頼してください。'},409)"""
replacement=marker+"""
                checklist=body.get('legalDocumentChecklist') or {}
                items=('operatorName','officeName','officeAddress','businessType',
                       'registrationNo','registrationDate','expiresOn','animalManager')
                if not isinstance(checklist,dict) or any(checklist.get(x) is not True for x in items) or body.get('proofViewed') is not True:
                    con.close()
                    return self.send_json({'error':'document_check_required',
                        'message':'登録証の写しと8項目を照合し、すべてのチェックを完了してください。'},409)
                proof=re.search(r'\\[REGISTRATION_PROOF\\](/uploads/[^\\s]+)',str(a['profile'] or ''))
                if not proof:
                    con.close()
                    return self.send_json({'error':'registration_proof_required'},409)
                stored=Path(urlparse(proof.group(1)).path).name
                proof_row=con.execute("SELECT stored_name,mime FROM uploads WHERE user_id=? AND stored_name=? AND puppy_id IS NULL",
                                      (a['user_id'],stored)).fetchone()
                if not proof_row or not str(proof_row['mime'] or '').startswith('image/') or not (UPLOADS/stored).is_file():
                    con.close()
                    return self.send_json({'error':'registration_proof_missing'},409)
                audit(con,u['id'],'breeder_registration_proof_manually_checked','breeder_application',a['id'],
                      'eight_fields_confirmed_human_review')"""
s=once(s,marker,replacement,'backend_manual_approval_checklist')
SERVER.write_text(s,encoding='utf-8')

p=ROOT/'operator-breeders.html'
h=p.read_text(encoding='utf-8')
style="""<style id="manual-document-review-css">
#documentReview{position:fixed;inset:0;z-index:500;background:rgba(35,28,11,.72);display:none;align-items:center;justify-content:center;padding:14px}
#documentReview.open{display:flex}
#documentReview .review-window{background:#fffbea;border:2px solid #ebd48c;border-radius:16px;width:min(1200px,100%);max-height:94dvh;overflow:auto;padding:20px}
#documentReview .review-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px}
#documentReview .review-proof{min-height:300px;max-height:65vh;width:100%;object-fit:contain;background:#fff;border:1px solid #d8c688;border-radius:12px}
#documentReview .review-field{display:flex;align-items:flex-start;gap:12px;padding:11px 6px;border-bottom:1px solid #e9e0bc;cursor:pointer}
#documentReview .review-field input{width:20px;height:20px;flex:none;accent-color:#b58125}
#documentReview .review-field b{display:block;overflow-wrap:anywhere}
#documentReview .review-field small{display:block;color:#746849}
#documentReview .review-actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:16px}
#documentReview .review-actions button:disabled{opacity:.45;cursor:not-allowed}
@media(max-width:760px){#documentReview .review-grid{grid-template-columns:1fr}#documentReview .review-proof{max-height:42vh}#documentReview .review-window{padding:12px}}
</style>"""
assert h.count('</head>')==1
h=h.replace('</head>',style+'</head>',1)
dialog="""<div id="documentReview" role="dialog" aria-modal="true" aria-label="登録証と申請内容の目視照合">
<div class="review-window">
<div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
<h2 style="margin:0">第一種動物取扱業 登録証の照合</h2>
<button class="btn btn-sub" type="button" onclick="closeDocumentReview()">閉じる ✕</button>
</div>
<p class="muted" style="margin:7px 0 14px">無料の目視確認です。AIは利用しません。左の登録証を見ながら、右の申請情報と一致する項目にチェックしてください。書類の真正性は別途確認が必要です。</p>
<div class="review-grid">
<section><h3>① 登録証の写し（運営専用）</h3>
<div id="reviewImageStatus" class="notice">画像を読み込み中…</div>
<img id="reviewProofImage" class="review-proof" alt="ブリーダーが提出した第一種動物取扱業登録証" hidden>
<p class="muted">拡大が必要な場合は画像をタップしてください。外部AIへ画像を送信しません。</p>
</section>
<section><h3>② 申請された法定表示情報</h3>
<div id="reviewFieldList"></div>
<p id="reviewProgress" class="notice" aria-live="polite">0 / 8項目 照合済み</p>
<div class="review-actions">
<button class="btn btn-main" id="reviewApproveButton" type="button" disabled onclick="approveManually()">8項目確認して承認</button>
<button class="btn btn-sub" type="button" onclick="rejectManually()">差し戻し</button>
</div><p id="reviewResult" role="alert" class="muted"></p>
</section>
</div></div></div>"""
assert h.count('</main>')==1
h=h.replace('</main>','</main>'+dialog,1)
button="""<button class="btn btn-main" onclick="review('${a.id}','approved')">承認</button>"""
h=once(h,button,"""<button class="btn btn-main" onclick="openDocumentReview('${a.id}')">登録証と申請を照合</button>""",'approval_entry_button')
js="""
<script id="manual-document-review-js">
let currentReview=null,proofBlobUrl='';
const LEGAL_KEYS=[
 ['operatorName','事業者の氏名・法人名','representative'],
 ['officeName','事業所の正式名称','legal_office_name'],
 ['officeAddress','登録事業所の所在地','visit_address'],
 ['businessType','第一種動物取扱業の種別','__sales'],
 ['registrationNo','登録番号','registration_no'],
 ['registrationDate','登録年月日','legal_registration_date'],
 ['expiresOn','有効期間の末日','expires_on'],
 ['animalManager','動物取扱責任者の氏名','legal_animal_manager']
];
function updateReviewProgress(){
 const boxes=[...document.querySelectorAll('#reviewFieldList input[data-key]')];
 const checked=boxes.filter(b=>b.checked).length;
 document.getElementById('reviewProgress').textContent=checked+' / 8項目 照合済み';
 document.getElementById('reviewApproveButton').disabled=!(currentReview&&currentReview.proofViewed&&checked===8&&boxes.length===8);
}
function closeDocumentReview(){
 document.getElementById('documentReview').classList.remove('open');
 document.getElementById('reviewProofImage').removeAttribute('src');
 if(proofBlobUrl)URL.revokeObjectURL(proofBlobUrl);
 proofBlobUrl='';currentReview=null;updateReviewProgress();
}
async function openDocumentReview(id){
 closeDocumentReview();
 const rows=await BigPawAPI.breederApplications();
 const a=(rows||[]).find(x=>String(x.id)===String(id));
 if(!a||a.status!=='pending'){alert('審査待ちの申請を選択してください。');return}
 currentReview={id:a.id,proofViewed:false};
 document.getElementById('documentReview').classList.add('open');
 document.getElementById('reviewResult').textContent='';
 const list=document.getElementById('reviewFieldList');list.replaceChildren();
 for(const [key,label,field] of LEGAL_KEYS){
  const v=field==='__sales'?'販売':a[field]||'';
  const row=document.createElement('label');row.className='review-field';
  const check=document.createElement('input');check.type='checkbox';check.dataset.key=key;
  check.disabled=!String(v).trim();check.addEventListener('change',updateReviewProgress);
  const stack=document.createElement('span');
  const name=document.createElement('small');name.textContent=label;
  const value=document.createElement('b');value.textContent=v||'未入力（要差し戻し）';
  stack.append(name,value);row.append(check,stack);list.append(row);
 }
 updateReviewProgress();
 const st=document.getElementById('reviewImageStatus'),img=document.getElementById('reviewProofImage');
 st.style.display='block';st.textContent='登録証の写しを読み込み中…';img.hidden=true;
 try{
  if(!a.registration_proof_url)throw new Error('登録証の写しがありません。');
  const headers={};if(BigPawAPI.token())headers.Authorization='Bearer '+BigPawAPI.token();
  const res=await fetch(a.registration_proof_url,{credentials:'same-origin',headers,cache:'no-store'});
  if(!res.ok)throw new Error('登録証を表示できません（HTTP '+res.status+'）');
  const blob=await res.blob();
  if(!blob.type.startsWith('image/'))throw new Error('画像形式を確認できません。');
  if(!currentReview||currentReview.id!==id)return;
  proofBlobUrl=URL.createObjectURL(blob);
  img.onload=()=>{if(currentReview&&currentReview.id===id){currentReview.proofViewed=true;updateReviewProgress()}};
  img.onerror=()=>{st.textContent='登録証を表示できません。承認はできません。';img.hidden=true};
  img.src=proofBlobUrl;img.hidden=false;st.style.display='none';
  img.onclick=()=>{if(proofBlobUrl)window.open(proofBlobUrl,'_blank','noopener')};
 }catch(error){st.textContent=error.message||'登録証を取得できません';img.hidden=true;updateReviewProgress()}
}
async function approveManually(){
 if(!currentReview||!currentReview.proofViewed)return;
 const checks=[...document.querySelectorAll('#reviewFieldList input[data-key]')];
 if(checks.length!==8||!checks.every(x=>x.checked))return;
 const id=currentReview.id, btn=document.getElementById('reviewApproveButton');
 if(!confirm('登録証の写しと8項目を目視で照合し、登録申請を承認しますか？'))return;
 btn.disabled=true;
 try{
  const legalDocumentChecklist=Object.fromEntries(checks.map(x=>[x.dataset.key,true]));
  await BigPawAPI.updateBreederApplication(id,{status:'approved',legalDocumentChecklist,proofViewed:true});
  closeDocumentReview();await load();
 }catch(e){document.getElementById('reviewResult').textContent='承認できませんでした：'+(e.message||'内容を再確認してください');updateReviewProgress()}
}
async function rejectManually(){
 if(!currentReview)return;
 const reason=prompt('差し戻す理由を入力してください。');
 if(reason===null)return;
 if(!reason.trim()){alert('差し戻し理由を入力してください。');return}
 try{
  await BigPawAPI.updateBreederApplication(currentReview.id,{status:'rejected',reviewNote:reason.trim()});
  closeDocumentReview();await load();
 }catch(e){document.getElementById('reviewResult').textContent='差し戻しできませんでした：'+(e.message||'通信エラー')}
}
</script>"""
assert h.count('</body>')==1
h=h.replace('</body>',js+'</body>',1)
p.write_text(h,encoding='utf-8')
print('FREE_BREEDER_DOCUMENT_REVIEW_OK|operator_only|no_external_ai|eight_manual_checks|image_side_by_side|approval_server_enforced|no_cost',flush=True)
