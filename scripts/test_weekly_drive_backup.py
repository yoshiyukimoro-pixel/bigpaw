"""Offline safety checks; no Google credentials or live database needed."""
from pathlib import Path
import sqlite3
import tempfile
from weekly_drive_backup import snapshot


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
    print("PASS: SQLite backup copy, integrity and missing-source handling")


if __name__ == "__main__":
    run()
