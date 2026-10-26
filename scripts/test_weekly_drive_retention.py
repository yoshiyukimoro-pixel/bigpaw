"""Offline retention tests with a fake Drive API; no files are deleted remotely."""
from weekly_drive_backup import prune_old_weekly_backups


class Request:
    def __init__(self, result):
        self.result = result
    def execute(self):
        return self.result


class Files:
    def __init__(self, names):
        self.names = names
        self.trashed = []
        self.list_calls = 0
    def list(self, **kwargs):
        self.list_calls += 1
        assert kwargs["q"].endswith("in parents and trashed = false")
        assert kwargs["pageSize"] == 1000
        if kwargs.get("pageToken") is None:
            return Request({"files": self.names[:3], "nextPageToken": "next"})
        return Request({"files": self.names[3:]})
    def update(self, **kwargs):
        assert kwargs["body"] == {"trashed": True}
        self.trashed.append(kwargs["fileId"])
        return Request({})


class Drive:
    def __init__(self, names):
        self.api = Files(names)
    def files(self):
        return self.api


def run():
    names = [
        {"id": "manual", "name": "bigpaw-auto-20261025.sqlite3"},
        {"id": "w1", "name": "bigpaw-weekly-2026-W40.sqlite3"},
        {"id": "other", "name": "notes.txt"},
        {"id": "w2", "name": "bigpaw-weekly-2026-W41.sqlite3"},
        {"id": "w3", "name": "bigpaw-weekly-2026-W42.sqlite3"},
        {"id": "w4", "name": "bigpaw-weekly-2026-W43.sqlite3"},
        {"id": "w5", "name": "bigpaw-weekly-2026-W44.sqlite3"},
    ]
    drive = Drive(names)
    assert prune_old_weekly_backups(drive, "folder", keep=4) == 1
    assert drive.api.trashed == ["w1"]
    assert drive.api.list_calls == 2
    drive = Drive(names[:6])
    assert prune_old_weekly_backups(drive, "folder", keep=4) == 0
    assert drive.api.trashed == []
    print("PASS: four-week retention, pagination, and manual file protection")


if __name__ == "__main__":
    run()
