"""Offline scheduler checks. Never contacts Google or Railway."""
import datetime as dt
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_drive_scheduler as scheduler


def reset_state():
    scheduler._RUNNING = False
    scheduler._LAST_ATTEMPT_WEEK = None
    scheduler._LAST_SUCCESS_WEEK = None


def run():
    reset_state()
    with patch.dict(os.environ, {"BIGPAW_WEEKLY_DRIVE_BACKUP_ENABLED": "0"}):
        assert scheduler.maybe_schedule_weekly_backup() is False

    reset_state()
    with patch.dict(os.environ, {"BIGPAW_WEEKLY_DRIVE_BACKUP_ENABLED": "1"}):
        # Sunday 23:59 JST must not schedule.
        sunday_utc = dt.datetime(2026, 10, 25, 14, 59, tzinfo=dt.timezone.utc)
        with patch.object(scheduler.dt, "datetime") as clock:
            clock.now.return_value = sunday_utc
            assert scheduler.maybe_schedule_weekly_backup() is False

    reset_state()
    with patch.dict(os.environ, {"BIGPAW_WEEKLY_DRIVE_BACKUP_ENABLED": "1"}):
        # Monday 00:01 JST must schedule immediately.
        monday_utc = dt.datetime(2026, 10, 25, 15, 1, tzinfo=dt.timezone.utc)
        with patch.object(scheduler.dt, "datetime") as clock, patch.object(scheduler.threading, "Thread") as thread_cls:
            clock.now.return_value = monday_utc
            assert scheduler.maybe_schedule_weekly_backup() is True
            thread_cls.assert_called_once()
            thread_cls.return_value.start.assert_called_once()

    print("PASS: weekly scheduler enable gate and Japan-time Monday boundary")


if __name__ == "__main__":
    run()
