"""Offline safety checks; no Google credentials or live database needed."""
from pathlib import Path
import os
import sqlite3
import tempfile
from unittest.mock import patch
from urllib.parse import parse_qs

from weekly_drive_backup import refresh_access_token, snapshot


class FakeTokenResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"access_token":"test-access-token","expires_in":3600,"token_type":"Bearer"}'


def run():
    with tempfile.TemporaryDirectory() as root:
        src = Path(root) / "source.sqlite3"
        dest = Path(root) / "backup.sqlite3"
        with sqlite3.connect(src) as conn:
            conn.execute("CREATE TABLE records(id INTEGER PRIMARY KEY, value TEXT)")
            conn.executemany("INSERT INTO records(value) VALUES (?)", [(str(i),) for i in range(100)])
            conn.commit()
        snapshot(src, dest)
        with sqlite3.connect(dest) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 100
        assert not dest.samefile(src)
        try:
            snapshot(Path(root) / "missing.sqlite3", dest)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Missing database must not silently succeed")

    captured = {}
    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = parse_qs(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeTokenResponse()

    env = {
        "BIGPAW_GOOGLE_CLIENT_ID": "intentionally-wrong-client-id",
        "BIGPAW_GOOGLE_CLIENT_SECRET": '{"web":{"client_secret":"GOCSPX-test_value"}}',
        "BIGPAW_GOOGLE_REFRESH_TOKEN": "test-refresh-token",
    }
    with patch.dict(os.environ, env, clear=False), patch("weekly_drive_backup.urlopen", fake_urlopen):
        assert refresh_access_token() == "test-access-token"
    assert captured["url"] == "https://oauth2.googleapis.com/token"
    assert captured["body"]["client_id"] == ["674803593362-qc4o2rs2qppvhn33h3ma01i93cfuamup.apps.googleusercontent.com"]
    assert captured["body"]["refresh_token"] == ["test-refresh-token"]
    assert captured["body"]["grant_type"] == ["refresh_token"]
    assert captured["body"]["client_secret"] == ["GOCSPX-test_value"]
    assert captured["timeout"] == 20

    print("PASS: SQLite snapshot and normalized OAuth client secret request")


if __name__ == "__main__":
    run()
