#!/usr/bin/env python3
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ZIP = ROOT / "bigpaw-app.zip"
RUNTIME = ROOT / ".bigpaw-runtime"
APP = RUNTIME / "BIG_PAW_v1.0_FINAL3_domain_ready_package"
SERVER = APP / "backend" / "server.py"

if not ZIP.exists():
    raise SystemExit("bigpaw-app.zip not found")

if not SERVER.exists():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP) as zf:
        zf.extractall(RUNTIME)

os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.execv(sys.executable, [sys.executable, str(SERVER)])
