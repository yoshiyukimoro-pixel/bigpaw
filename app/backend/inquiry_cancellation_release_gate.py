"""Run cancellation integration suite on a disposable copy of the built image."""
from pathlib import Path
import os,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='bigpaw-cancellation-gate-') as tmp:
    work=Path(tmp);app=work/'app'
    shutil.copytree(ROOT,app,ignore=shutil.ignore_patterns('*.sqlite3','*.sqlite3-*','__pycache__','backups'))
    for p in (app/'backend').glob('*.py'):
        p.write_text(p.read_text().replace("'/app'",repr(str(app))).replace('"/app"',repr(str(app))).replace("'/app/", "'"+str(app)+"/").replace('"/app/', '"'+str(app)+'/'))
    for script in ('auth_cookie_hardening_patch.py','safari_gallery_runtime_patch.py','support_contact_runtime_patch.py','offsite_backup_runtime_patch.py','login_prompt_runtime_patch.py','direct_payment_runtime_patch.py','breeder_mobile_menu_runtime_patch.py'):
        subprocess.run([sys.executable,'backend/'+script],cwd=app,check=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('BIGPAW_','SMTP_','RESEND_'))}
    subprocess.run([sys.executable,str(ROOT/'backend/inquiry_cancellation_test.py'),str(app)],env=env,cwd=work,check=True,timeout=120)
print('INQUIRY_CANCELLATION_RELEASE_GATE_OK|bilateral_reasons|mismatch|unanswered|operator_review|mail_retry|retained_history|transaction_guard')
