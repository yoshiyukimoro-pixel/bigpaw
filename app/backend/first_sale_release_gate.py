"""Abort the image build if workflow or existing API regressions fail.
Tests use a scratch app copy, scratch DB and local capture transport only.
No production credentials, DB, uploads or outgoing customer emails are used.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='bigpaw-release-gate-') as tmp:
    work=Path(tmp); app=work/'app'
    shutil.copytree(ROOT,app,ignore=shutil.ignore_patterns('*.sqlite3','*.sqlite3-*','__pycache__','backups'))
    for p in (app/'backend').glob('*.py'):
        p.write_text(p.read_text().replace("'/app'",repr(str(app))).replace('"/app"',repr(str(app))).replace("'/app/", "'"+str(app)+"/").replace('"/app/', '"'+str(app)+'/'))
    runtime=('auth_cookie_hardening_patch.py','safari_gallery_runtime_patch.py','support_contact_runtime_patch.py','offsite_backup_runtime_patch.py','login_prompt_runtime_patch.py','direct_payment_runtime_patch.py','breeder_mobile_menu_runtime_patch.py')
    for script in runtime:
        subprocess.run([sys.executable,'backend/'+script],cwd=app,check=True)
    subprocess.run([sys.executable,'-c',"import runpy; g=runpy.run_path('backend/start_live.py'); g['heal_search']('release-gate')"],cwd=app,check=True)
    # Deterministic build-time tests do not inherit any deployment or mail credentials.
    env={k:v for k,v in os.environ.items() if not k.startswith(('BIGPAW_','SMTP_','RESEND_'))}
    env['BIGPAW_TEST_CONTEXT_PATH']=str(work/'context.json')
    subprocess.run([sys.executable,str(ROOT/'backend/first_sale_workflow_test.py'),str(app)],env=env,cwd=work,check=True,timeout=120)
print('FIRST_SALE_RELEASE_GATE_OK|production_cookie_csrf|workflow|billing|cancel|suspension|photos|favorites|search|existing_management')
