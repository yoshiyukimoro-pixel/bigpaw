"""Breeder self-service statutory-disclosure alerts from persisted server state.

Warn only the signed-in breeder if any statutory fields are missing, the legal
office name is still a legacy fallback, consent is pending or the registration
expired. Clear automatically after successful publish/confirmation. No operator
manual action or alteration to old listings/public privacy gates.
"""
from pathlib import Path
ROOT=Path('/app')
SERVER=ROOT/'backend/server.py'
s=SERVER.read_text(encoding='utf-8')

def once(src,old,new,tag):
    assert src.count(old)==1,(tag,src.count(old))
    return src.replace(old,new,1)

get_marker="        if path=='/api/breeder/legal-display':\n"
addition="""        if path=='/api/breeder/legal-status':
            u=self.require(['breeder'])
            if not u:return
            con=db()
            row=con.execute('''SELECT b.visit_address,b.registration_no,
                       l.office_name,l.operator_name,l.registration_date,
                       l.expires_on,l.animal_manager,l.business_type,l.confirmed
                       FROM breeders b LEFT JOIN breeder_legal_disclosures l
                         ON l.breeder_id=b.id WHERE b.user_id=?''',(u['id'],)).fetchone()
            con.close()
            if not row:
                return self.send_json({'error':'breeder_profile_not_found'},404)
            needed=(
                ('事業者の氏名・法人名','operator_name'),
                ('事業所の正式名称（登録証どおり）','office_name'),
                ('登録事業所の所在地','visit_address'),
                ('第一種動物取扱業の種別','business_type'),
                ('登録番号','registration_no'),
                ('登録年月日','registration_date'),
                ('有効期間の末日','expires_on'),
                ('動物取扱責任者の氏名','animal_manager'),
            )
            missing=[label for label,key in needed if not str(row[key] or '').strip()]
            if str(row['business_type'] or '').strip() and '販売' not in str(row['business_type']):
                missing.append('第一種動物取扱業の種別（販売）')
            import datetime as _status_date
            for key,label in (('registration_date','登録年月日'),('expires_on','有効期間の末日')):
                value=str(row[key] or '').strip()
                if not value:continue
                try:
                    checked=_status_date.date.fromisoformat(value)
                    if key=='expires_on' and checked < _status_date.date.today():
                        missing.append('登録有効期限が切れています')
                except ValueError:
                    missing.append(label+'（日付形式を確認）')
            if not bool(row['confirmed']):
                missing.append('法定情報の一般公開確認')
            return self.send_json({
                'complete':not missing,
                'confirmed':bool(row['confirmed']),
                'missing':missing,
                'missingCount':len(missing)
            })
"""
# Patch GET route only; PATCH remains unchanged.
first=s.index('    def do_GET(self):')
last=s.index('    def do_POST(self):')
get=s[first:last]
get=once(get,get_marker,addition+get_marker,'GET_OWN_LEGAL_STATUS')
s=s[:first]+get+s[last:]
compile(s,str(SERVER),'exec')
SERVER.write_text(s,encoding='utf-8')

admin=ROOT/'admin.html'
h=admin.read_text(encoding='utf-8')
banner="""<div id="breederLegalAlert" class="notice" role="alert" style="display:none;margin-bottom:18px;background:#fff6e7;border:1px solid #e7bd70;color:#704c14">
<b id="breederLegalAlertTitle">⚠ 第一種動物取扱業の法定表示を確認してください</b>
<div id="breederLegalAlertDetails" style="margin-top:7px"></div>
<a class="btn btn-main" style="display:inline-flex;margin-top:12px;background:#497eaf;color:#fff" href="breeder-profile-edit.html#legalDisplayForm">不足項目を入力・公開確認する →</a>
</div>"""
h=once(h,
      '<div id="billingSuspend" class="notice"',
      banner+'<div id="billingSuspend" class="notice"',
      'dashboard_alert_before_billing')
fn="""async function refreshBreederLegalAlert(){
 const panel=document.getElementById('breederLegalAlert');
 const details=document.getElementById('breederLegalAlertDetails');
 try{
   const state=await BigPawAPI.request('/breeder/legal-status');
   if(state.complete){panel.style.display='none';details.textContent='';return}
   details.textContent=(state.missing||[]).length
      ?'不足・要確認：'+state.missing.join('、')
      :'法定表示を確認してください。';
   panel.style.display='block';
 }catch(err){
   // Network failures must not be confused with a fully completed disclosure.
   details.textContent='確認状況を取得できません。犬舎プロフィールから法定表示をご確認ください。';
   panel.style.display='block';
 }
}
"""
h=once(h,
      "function badge(s){return s==='募集中'?",
      fn+"function badge(s){return s==='募集中'?",
      'dashboard_status_loader')
h=once(h,
      "   operatorScope.style.display='none';kennelModeLabel.textContent='ブリーダー管理';",
      "   operatorScope.style.display='none';kennelModeLabel.textContent='ブリーダー管理';\n"
      "   await refreshBreederLegalAlert();",
      'status_after_authenticated_breeder_login')
# Even if switching the authenticated account in the browser, never show another
# breeder's previous alert when operator or anonymous.
h=once(h,
      "  if(BigPawBridge.isServerMode()&&me?.role!=='breeder'&&me?.role!=='operator'){loginNotice.style.display='block';",
      "  if(me?.role!=='breeder')document.getElementById('breederLegalAlert').style.display='none';\n"
      "  if(BigPawBridge.isServerMode()&&me?.role!=='breeder'&&me?.role!=='operator'){loginNotice.style.display='block';",
      'clear_old_alert_outside_breeder')
admin.write_text(h,encoding='utf-8')

page=ROOT/'breeder-profile-edit.html'
h=page.read_text(encoding='utf-8')
edit_banner="""<div id="legalCompletionAlert" class="notice" role="status" style="display:none;margin:12px 0;background:#fff6e7;border:1px solid #e7bd70;color:#704c14">
<b>⚠ 法定表示の不足情報があります</b>
<div id="legalCompletionDetails" style="margin-top:6px"></div>
<a href="#legalDisplayForm" style="color:#235b88;text-decoration:underline;font-weight:800">法定表示の入力欄へ移動 ↓</a>
</div>"""
h=once(h,
       '<div class="breadcrumb"><a href="admin.html">管理画面</a> ＞ 犬舎プロフィール</div>',
       '<div class="breadcrumb"><a href="admin.html">管理画面</a> ＞ 犬舎プロフィール</div>'+edit_banner,
       'profile_alert')
h=once(h,
       "        note.textContent='✓ 法定情報を保存・公開しました。';",
       "        note.textContent='✓ 法定情報を保存・公開しました。';\n"
       "        await window.refreshBreederLegalAlert?.();",
       'refresh_on_success_only')
refresh="""<script id="legal-completion-alert-script">
window.refreshBreederLegalAlert=async function(){
 const panel=document.getElementById('legalCompletionAlert');
 const details=document.getElementById('legalCompletionDetails');
 try{
   const state=await BigPawAPI.request('/breeder/legal-status');
   if(state.complete){panel.style.display='none';details.textContent='';return}
   details.textContent='不足・要確認：'+(state.missing||[]).join('、');
   panel.style.display='block';
 }catch(e){
   details.textContent='確認状態を取得できません。再読み込みしてご確認ください。';
   panel.style.display='block';
 }
};
window.refreshBreederLegalAlert();
</script>"""
h=once(h,'</body></html>',refresh+'</body></html>','profile_alert_status_script')
page.write_text(h,encoding='utf-8')
print('BREEDER_LEGAL_MISSING_ALERT_OK|own_login_only|persisted_eight_fields|explicit_consent|expired_detected|auto_clear_after_success|no_manual_dismiss|listing_untouched',flush=True)
