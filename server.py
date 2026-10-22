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

from shop_preview_install import install_private_shop_preview

# Build a private preview without exposing it in the public site navigation.
# This is idempotent and applies to the extracted ZIP application only.
os.environ["BIGPAW_PRIVATE_SHOP_PREVIEW_FILE"] = str(ROOT / "private_shop_preview.html")
install_private_shop_preview(ROOT, APP, SERVER)

os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.execv(sys.executable, [sys.executable, str(SERVER)])
