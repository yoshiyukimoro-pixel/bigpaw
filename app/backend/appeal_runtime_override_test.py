#!/usr/bin/env python3
from pathlib import Path

ROOT=Path('/app')
JS=(ROOT/'breeder-editor-safety-fix.js').read_text(encoding='utf-8')
HTML=(ROOT/'breeder-puppy-new.html').read_text(encoding='utf-8')

checks={
  'override_payload_includes_appeal': "appealPoint:value('appealPoint')" in JS,
  'override_has_persistence_verify': 'verifyAppealPointPersistence' in JS,
  'override_verifies_before_success': JS.find('await verifyAppealPointPersistence')!=-1 and JS.find('await verifyAppealPointPersistence') < JS.find("alert(pid?'変更を保存しました。':'子犬情報を掲載しました。')"),
  'editor_field_present': 'id="appealPoint"' in HTML,
  'inline_payload_includes_appeal': 'appealPoint:appealPoint.value' in HTML,
  'override_script_loaded': 'breeder-editor-safety-fix.js' in HTML,
}
failed=[k for k,v in checks.items() if not v]
if failed:
    raise SystemExit('APPEAL_RUNTIME_OVERRIDE_FAIL|'+'|'.join(failed))
print('APPEAL_RUNTIME_OVERRIDE_OK|payload=appealPoint|readback=required|success_after_verify|editor_field=present|override_loaded', flush=True)
