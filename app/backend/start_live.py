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
REBUILT_SEARCH = ROOT / 'search-list-rebuild.html'
PATCH = ROOT / 'backend' / 'search_result_list_patch.py'
FINAL_MARKER = 'id="bigpaw-search-final-layout-v3"'
FINAL_JS_MARKER = 'id="bigpaw-search-final-layout-v3-js"'
LEGACY_DIAG = '/__renderdiag'
NATIVE_MARKER = 'data-bp-native-layout="20260926-native1"'
REBUILT_MARKERS = (
    'class="bp-puppy-layout"',
    'grid-template-columns:minmax(0,49%) minmax(0,51%)',
    'class="bp-puppy-photo"',
    'class="bp-puppy-info"',
    'puppy-detail.html?id=',
    'window.BIGPAW_SELECTED_BREEDS',
    'id="bpAge"',
    'id="bpColor"',
    'id="bpMin"',
    'id="bpMax"',
    'data-prefecture-count="47"',
    '誕生：',
    '毛色：',
)
REBUILT_PREFECTURES = (
    '北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県',
    '茨城県','栃木県','群馬県','埼玉県','千葉県','東京都','神奈川県',
    '新潟県','富山県','石川県','福井県','山梨県','長野県',
    '岐阜県','静岡県','愛知県','三重県',
    '滋賀県','京都府','大阪府','兵庫県','奈良県','和歌山県',
    '鳥取県','島根県','岡山県','広島県','山口県',
    '徳島県','香川県','愛媛県','高知県',
    '福岡県','佐賀県','長崎県','熊本県','大分県','宮崎県','鹿児島県','沖縄県',
)


def rebuilt_missing(html: str) -> list[str]:
    missing = [marker for marker in REBUILT_MARKERS if marker not in html]
    for name in REBUILT_PREFECTURES:
        marker = f'<option value="{name}">{name}</option>'
        if marker not in html:
            missing.append('prefecture:' + name)
    return missing


def install_rebuilt_search(stage: str) -> bool:
    if not REBUILT_SEARCH.exists():
        return False
    html = REBUILT_SEARCH.read_text(encoding='utf-8')
    missing = rebuilt_missing(html)
    if missing:
        raise RuntimeError('SEARCH_REBUILD_GATE_FAIL|' + stage + '|missing=' + ','.join(missing))
    if LEGACY_DIAG in html:
        raise RuntimeError('SEARCH_REBUILD_GATE_FAIL|' + stage + '|legacy_renderdiag_present')
    SEARCH.write_text(html, encoding='utf-8')
    verify = SEARCH.read_text(encoding='utf-8')
    missing_after = rebuilt_missing(verify)
    if missing_after:
        raise RuntimeError('SEARCH_REBUILD_GATE_FAIL|' + stage + '|postwrite_missing=' + ','.join(missing_after))
    print(
        'SEARCH_REBUILD_LIVE_OK|stage=' + stage
        + '|source=search-list-rebuild.html|layout=photo_left_info_right|ratio=49_51'
        + '|prefectures=47|multi_breed=enabled|age_color_price_filters=enabled|detail_page=linked_not_modified',
        flush=True,
    )
    return True


def remove_legacy_search_diagnostics(html: str) -> str:
    blocks = re.findall(r'<script\b[^>]*>.*?</script>', html, flags=re.S | re.I)
    for block in blocks:
        if LEGACY_DIAG in block:
            html = html.replace(block, '', 1)
    return html


def force_native_horizontal_renderer(html: str) -> str:
    if NATIVE_MARKER in html:
        return html
    pat = re.compile(
        r'list\.map\(p=>`<a class="card result-card" href="puppy-detail\.html\?id=\$\{encodeURIComponent\(p\.id\)\}">.*?</a>`\)\.join\(\'\'\)',
        flags=re.S,
    )
    replacement = r'''list.map(p=>`<a class="result-card" data-bp-native-layout="20260926-native1" href="puppy-detail.html?id=${encodeURIComponent(p.id)}"><div class="result-title">${BigPaw.esc(p.breed||'子犬')}</div><div class="result-row"><div class="result-pic-wrap"><div class="result-pic">${p.imageUrl?`<img src="${BigPaw.esc(p.imageUrl)}" alt="${BigPaw.esc(p.breed||'子犬')}" loading="eager" decoding="async">`:'🐾'}</div>${p.gender?`<span class="result-gender">${BigPaw.esc(p.gender)}</span>`:''}</div><div class="result-info"><div class="result-meta"><span class="result-status">${BigPaw.esc(p.status||'募集中')}</span><span>${BigPaw.esc(p.area||'')}</span></div><div class="result-line">誕生：${BigPaw.esc(String(p.birth||'未登録').replace(/-/g,'/'))}</div><div class="result-line">毛色：${BigPaw.esc(p.color||'未登録')}</div><div class="price">${BigPaw.currency(p.price)} <span style="font-size:12px;color:#5c5357;font-weight:700">(税込)</span></div>${p.desc?`<div class="result-appeal">${BigPaw.esc(p.desc)}</div>`:''}<div class="result-more">この子の詳細を見る ›</div></div></div></a>`).join('')'''
    html, n = pat.subn(lambda _m: replacement, html, count=1)
    if n != 1:
        raise RuntimeError('SEARCH_NATIVE_RENDER_FAIL|legacy_card_template_count=' + str(n))
    return html


def heal_legacy_search(stage: str) -> None:
    runpy.run_path(str(PATCH), run_name='__main__')
    html = SEARCH.read_text(encoding='utf-8')
    html = remove_legacy_search_diagnostics(html)
    html = force_native_horizontal_renderer(html)
    SEARCH.write_text(html, encoding='utf-8')
    html = SEARCH.read_text(encoding='utf-8')
    checks = {
        'final_css': html.count(FINAL_MARKER) == 1,
        'final_js': html.count(FINAL_JS_MARKER) == 1,
        'legacy_diag_removed': LEGACY_DIAG not in html,
        'horizontal_css': 'grid-template-columns:minmax(0,49%) minmax(0,51%)' in html,
        'native_horizontal_renderer': html.count(NATIVE_MARKER) == 1,
        'legacy_vertical_renderer_removed': 'class="card result-card"' not in html,
        'birth': '誕生：' in html,
        'color': '毛色：' in html,
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError('SEARCH_LIVE_GATE_FAIL|' + stage + '|missing=' + ','.join(failed))
    print(
        'SEARCH_LIVE_GATE_OK|stage=' + stage
        + '|native_renderer=horizontal|legacy_vertical_renderer=0|final_css=1|final_js=1|legacy_renderdiag=0|version=20260926-native1',
        flush=True,
    )


def heal_search(stage: str) -> None:
    if install_rebuilt_search(stage):
        return
    heal_legacy_search(stage)


def delayed_verify() -> None:
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
