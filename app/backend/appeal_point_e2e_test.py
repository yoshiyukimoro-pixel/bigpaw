#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'backend' / 'server.py'


def free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def request(base: str, path: str, method: str = 'GET', body=None, token: str = ''):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
    headers = {}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(base + path, data=data, headers=headers, method=method)
    with urlopen(req, timeout=5) as r:
        raw = r.read()
        return json.loads(raw.decode('utf-8')) if raw else None


def wait_ready(base: str, proc: subprocess.Popen) -> None:
    deadline = time.time() + 15
    last = None
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ''
            raise RuntimeError(f'server exited early rc={proc.returncode}: {out}')
        try:
            request(base, '/api/health')
            return
        except Exception as e:
            last = e
            time.sleep(0.15)
    raise RuntimeError(f'server did not become ready: {last}')


def main() -> int:
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='bigpaw-appeal-e2e-') as td:
        env = os.environ.copy()
        env.update({
            'BIGPAW_ENV': 'development',
            'BIGPAW_DEV_LINKS': '1',
            'BIGPAW_DATA_DIR': td,
            'PORT': str(port),
            'PYTHONUNBUFFERED': '1',
        })
        proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_ready(base, proc)
            login = request(base, '/api/login', 'POST', {'email': 'dog44@bigpaw.jp', 'password': 'demo1234'})
            token = (login or {}).get('token', '')
            if not token:
                raise AssertionError('breeder login did not return a token')

            puppies = request(base, '/api/breeder/puppies', token=token)
            target = next((p for p in puppies if str(p.get('id')) == 'p1'), None)
            if not target:
                raise AssertionError('seed puppy p1 not found')

            first = '🐾保存テストA✨'
            second = '🐾保存テストB✨'
            request(base, '/api/puppies/p1', 'PATCH', {'appealPoint': first}, token)
            puppies = request(base, '/api/breeder/puppies', token=token)
            saved = next(p for p in puppies if str(p.get('id')) == 'p1')
            if saved.get('appealPoint') != first:
                raise AssertionError(f'breeder readback mismatch after first save: {saved.get("appealPoint")!r}')

            request(base, '/api/puppies/p1', 'PATCH', {'appealPoint': second}, token)
            puppies = request(base, '/api/breeder/puppies', token=token)
            saved = next(p for p in puppies if str(p.get('id')) == 'p1')
            if saved.get('appealPoint') != second:
                raise AssertionError(f'breeder readback mismatch after second save: {saved.get("appealPoint")!r}')

            public = request(base, '/api/puppies/p1')
            if public.get('appealPoint') != second:
                raise AssertionError(f'public readback mismatch: {public.get("appealPoint")!r}')

            form = (ROOT / 'breeder-puppy-new.html').read_text(encoding='utf-8')
            if form.count('appealPoint:appealPoint.value') < 2:
                raise AssertionError('appealPoint missing from create/edit UI payload')
            if 'appealPoint:d.appealPoint' not in form:
                raise AssertionError('appealPoint missing from edit-page hydration')
            if 'verifyAppealPointPersistence' not in form:
                raise AssertionError('UI persistence verification guard is missing')

            print('APPEAL_POINT_E2E_OK|login=breeder|patch=2x|breeder_readback=ok|public_readback=ok|edit_hydration=ok|ui_verify=ok', flush=True)
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
