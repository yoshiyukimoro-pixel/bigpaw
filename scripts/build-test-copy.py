#!/usr/bin/env python3
"""Replay Docker's Python build steps into an isolated scratch copy without Docker.
Dependency install is omitted: Pillow is supplied by the test runtime.
"""
import json, shutil, subprocess, sys
from pathlib import Path
repo=Path(__file__).resolve().parents[1]
target=Path(sys.argv[1]).resolve()
assert target!=repo and repo not in target.parents
if target.exists(): shutil.rmtree(target)
shutil.copytree(repo/'app',target)
# Only staging copies: production still uses Docker's /app root.
for p in (target/'backend').glob('*.py'):
    p.write_text(p.read_text().replace("'/app'",repr(str(target))).replace('"/app"',json.dumps(str(target))).replace("'/app/", "'"+str(target)+"/").replace('"/app/', '"'+str(target)+'/'))
# Nested release gates must rebase the already translated root onto their own
# disposable copy, rather than letting their hardcoded patches touch this tree.
for p in (target/'backend').glob('*release_gate.py'):
    s=p.read_text()
    if 'shutil.copytree' in s and 'p.read_text().replace(' in s:
        p.write_text(s.replace('p.read_text().replace(', 'p.read_text().replace(str(ROOT),str(app)).replace('))
for line in (repo/'Dockerfile').read_text().splitlines():
    if not line.startswith('RUN ['): continue
    args=json.loads(line[4:])
    if args[:2]==['python3','-c']: args[2]=args[2].replace('/app/',str(target)+'/')
    subprocess.run(args,cwd=target,check=True)
# Mirror the live Railway start command as well as Docker build instructions.
for script in ('auth_cookie_hardening_patch.py','safari_gallery_runtime_patch.py','support_contact_runtime_patch.py','offsite_backup_runtime_patch.py','login_prompt_runtime_patch.py','direct_payment_runtime_patch.py','breeder_mobile_menu_runtime_patch.py'):
    subprocess.run(['python3','backend/'+script],cwd=target,check=True)
subprocess.run(['python3','-c',"import runpy; g=runpy.run_path('backend/start_live.py'); g['heal_search']('isolated-pre-start')"],cwd=target,check=True)
print('ISOLATED_DOCKER_AND_START_STEPS_OK',target)
