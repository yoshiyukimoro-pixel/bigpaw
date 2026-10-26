"""Offline scheduler checks. Never contacts Google or Railway."""
import datetime as dt
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_drive_scheduler as scheduler


def run():
    with patch.dict(os.environ, {"BIGPAW_WEEKLY_DRIVE_BACKUP_ENABLED": "0"}):
        assert scheduler.maybe_schedule_weekly_backup() is False
    with patch.dict(os.environ, {"BIGPAW_WEEKLY_DRIVE_BACKUP_ENABLED": "1"}):
        # Sunday never schedules even when enabled.
        sunday = dt.datetime(2026, 10, 25, 12, tzinfo=dt.timezone.utc)
        with patch.object(scheduler.dt, "datetime") as clock:
            clock.now.return_value = sunday
            assert scheduler.maybe_schedule_weekly_backup() is False
    print("PASS: weekly scheduler disabled and off-day checks")


if __name__ == "__main__":
    run()
