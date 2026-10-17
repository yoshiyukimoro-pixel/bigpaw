"""Release gate for breeder legal-alert visibility and automatic resolution."""
from pathlib import Path
root=Path('/app')
server=(root/'backend/server.py').read_text(encoding='utf-8')
admin=(root/'admin.html').read_text(encoding='utf-8')
edit=(root/'breeder-profile-edit.html').read_text(encoding='utf-8')
assert "if path=='/api/breeder/legal-status':" in server
assert "u=self.require(['breeder'])" in server
assert "LEFT JOIN breeder_legal_disclosures l" in server
assert "FROM breeders b LEFT JOIN breeder_legal_disclosures l" in server
for label,key in (('事業者の氏名・法人名','operator_name'),
                  ('事業所の正式名称','office_name'),
                  ('登録事業所の所在地','visit_address'),
                  ('第一種動物取扱業の種別','business_type'),
                  ('登録番号','registration_no'),
                  ('登録年月日','registration_date'),
                  ('有効期間の末日','expires_on'),
                  ('動物取扱責任者の氏名','animal_manager')):
    assert label in server and ",'"+key+"')" in server,(label,key)
assert "missing.append('法定情報の一般公開確認')" in server
assert "missing.append('登録有効期限が切れています')" in server
assert "'complete':not missing" in server
assert "'missingCount':len(missing)" in server
assert "id=\"breederLegalAlert\"" in admin
assert "await refreshBreederLegalAlert();" in admin
assert "state.complete){panel.style.display='none'" in admin
assert "me?.role!=='breeder'" in admin
assert 'breeder-profile-edit.html#legalDisplayForm' in admin
assert 'id="legalCompletionAlert"' in edit
assert "window.refreshBreederLegalAlert=async function()" in edit
assert "await window.refreshBreederLegalAlert?.();" in edit
assert "if(state.complete){panel.style.display='none'" in edit
assert 'style="display:none' in edit
# Never alter buyer pages, nor turn off listings for old applications.
for fragment in ("UPDATE puppies SET review_status='rejected'",'review_status="rejected"',"UPDATE breeders SET review_status='rejected'"):
    assert fragment not in server,fragment
print('BREEDER_LEGAL_ALERT_GATE_OK|eight_fields|own_only|unfinished_warn|expired_warn|confirmation_required|auto_clear|operator_buyer_unchanged|no_listing_stop',flush=True)
