#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import re
import runpy
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / 'search.html'
PATCH = ROOT / 'backend' / 'search_result_list_patch.py'
FINAL_MARKER = 'id="bigpaw-search-final-layout-v3"'
FINAL_JS_MARKER = 'id="bigpaw-search-final-layout-v3-js"'
LEGACY_DIAG = '/__renderdiag'


def remove_legacy_search_diagnostics(html: str) -> str:
    # Remove any old diagnostic script that still posts layout snapshots to
    # /__renderdiag. These blocks came from an earlier search debugging phase
    # and can override/compete with the final search renderer on iPhone.
    blocks = re.findall(r'<script\b[^>]*>.*?</script>', html, flags=re.S | re.I)
    for block in blocks:
        if LEGACY_DIAG in block:
            html = html.replace(block, '', 1)
    return html


def heal_search(stage: str) -> None:
    runpy.run_path(str(PATCH), run_name='__main__')
    html = SEARCH.read_text(encoding='utf-8')
    cleaned = remove_legacy_search_diagnostics(html)
    if cleaned != html:
        SEARCH.write_text(cleaned, encoding='utf-8')
        html = cleaned
    checks = {
        'final_css': html.count(FINAL_MARKER) == 1,
        'final_js': html.count(FINAL_JS_MARKER) == 1,
        'legacy_diag_removed': LEGACY_DIAG not in html,
        'horizontal_css': 'grid-template-columns:minmax(0,49%) minmax(0,51%)' in html,
        'birth': '誕生：' in html,
        'color': '毛色：' in html,
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError('SEARCH_LIVE_GATE_FAIL|' + stage + '|missing=' + ','.join(failed))
    print(
        'SEARCH_LIVE_GATE_OK|stage=' + stage
        + '|final_css=1|final_js=1|legacy_renderdiag=0|horizontal=locked|version=20260926-final3',
        flush=True,
    )


def delayed_verify() -> None:
    # Re-apply after server module initialization as a guard against legacy
    # runtime/UI bootstrap code rewriting search.html during startup.
    time.sleep(1.0)
    heal_search('post_server_start')


def main() -> int:
    heal_search('pre_server_start')
    child = subprocess.Popen([sys.executable, str(ROOT / 'backend' / 'server.py')], cwd=str(ROOT), env=os.environ.copy())

    def forward(signum, _frame):
        if child.poll() is None:
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)

    verifier = threading.Thread(target=delayed_verify, daemon=True)
    verifier.start()
    return child.wait()


if __name__ == '__main__':
    raise SystemExit(main())
