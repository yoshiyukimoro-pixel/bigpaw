#!/usr/bin/env python3
"""Optional weekly offsite SQLite snapshot upload. Run from a scheduled Railway job.

Required environment:
 BIGPAW_DRIVE_FOLDER_ID: destination Google Drive folder ID
 BIGPAW_GOOGLE_CLIENT_ID / BIGPAW_GOOGLE_CLIENT_SECRET / BIGPAW_GOOGLE_REFRESH_TOKEN: OAuth secrets
 BIGPAW_DB_PATH: absolute path to the persistent SQLite database

This script does not run from the web server or alter local retention.
"""
import datetime as dt
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


def snapshot(source: Path, destination: Path):
    if not source.is_file():
        raise FileNotFoundError("BIGPAW_DB_PATH does not point to an existing database")
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30) as original:
        with sqlite3.connect(destination) as copy:
            original.backup(copy, pages=128, sleep=0.25)
            result = copy.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError("SQLite snapshot integrity check failed")


def upload(destination: Path, folder_id: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials = Credentials(
        token=None,
        refresh_token=os.environ["BIGPAW_GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["BIGPAW_GOOGLE_CLIENT_ID"],
        client_secret=os.environ["BIGPAW_GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    def quote_query(value):
        return value.replace(chr(92), chr(92) * 2).replace("'", chr(92) + "'")

    query = (
        f"name = '{quote_query(destination.name)}' and "
        f"'{quote_query(folder_id)}' in parents and trashed = false"
    )
    existing = service.files().list(q=query, fields="files(id,name,size),nextPageToken",page_size=100,
                                    supportsAllDrives=True,includeItemsFromAllDrives=True).execute()
    if existing.get("files"):
        raise RuntimeError("Backup filename already exists; refusing to overwrite")
    metadata = {"name": destination.name, "parents": [folder_id]}
    media = MediaFileUpload(str(destination), mimetype="application/x-sqlite3", resumable=True)
    created = service.files().create(body=metadata, media_body=media, fields="id,name,size",
                                     supportsAllDrives=True).execute()
    if int(created.get("size", -1)) != destination.stat().st_size:
        raise RuntimeError("Uploaded size mismatch; investigate Drive file before relying on backup")
    return created["id"]


def main():
    db_path = os.environ.get("BIGPAW_DB_PATH", "").strip()
    folder = os.environ.get("BIGPAW_DRIVE_FOLDER_ID", "").strip()
    if not db_path or not folder:
        raise RuntimeError("Set BIGPAW_DB_PATH and BIGPAW_DRIVE_FOLDER_ID")
    required = ("BIGPAW_GOOGLE_CLIENT_ID", "BIGPAW_GOOGLE_CLIENT_SECRET", "BIGPAW_GOOGLE_REFRESH_TOKEN")
    if not all(os.environ.get(key) for key in required):
        raise RuntimeError("Google OAuth credentials missing; configure Railway secrets")
    # ISO week gives one unique backup name per week, regardless of retry date.
    now = dt.datetime.now(dt.timezone.utc)
    year, week, _ = now.isocalendar()
    filename = f"bigpaw-weekly-{year}-W{week:02d}.sqlite3"
    with tempfile.TemporaryDirectory(prefix="bigpaw-offsite-") as tmp:
        path = Path(tmp) / filename
        snapshot(Path(db_path).resolve(), path)
        upload(path, folder)
    print(f"Weekly Drive backup uploaded and size verified: {filename}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Weekly Drive backup FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
