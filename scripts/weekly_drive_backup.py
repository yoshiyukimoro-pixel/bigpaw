#!/usr/bin/env python3
"""Optional weekly offsite SQLite snapshot upload. Run from a scheduled Railway job.

Required environment:
 BIGPAW_DRIVE_FOLDER_ID: destination Google Drive folder ID
 GOOGLE_APPLICATION_CREDENTIALS: path to a Google service-account JSON file
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
    from google.auth import default
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials, _ = default(scopes=["https://www.googleapis.com/auth/drive.file"])
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    safe_name = destination.name.replace("'", "\\'")
    query = f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"
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
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        raise RuntimeError("Set GOOGLE_APPLICATION_CREDENTIALS to a secure credentials file")
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
