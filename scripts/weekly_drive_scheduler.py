"""Opt-in weekly Drive upload scheduler for the existing BIG PAW web process.

This module must be called from the already-running automation monitor loop.
Never start a separate process or attach the live Railway volume elsewhere.
"""
import datetime as dt
import os
import threading

_LOCK = threading.Lock()
_RUNNING = False
_LAST_ATTEMPT_WEEK = None


def maybe_schedule_weekly_backup():
    """Start one upload thread on Mondays, if explicitly enabled and configured.

    Retries are allowed after restart; the uploader rejects duplicate weekly names.
    Failed attempts are retried on the next automation tick, at most one per hour.
    """
    global _RUNNING, _LAST_ATTEMPT_WEEK
    if os.environ.get("BIGPAW_WEEKLY_DRIVE_BACKUP_ENABLED") != "1":
        return False
    now = dt.datetime.now(dt.timezone.utc)
    if now.weekday() != 0:
        return False
    week = now.strftime("%G-W%V")
    hour = now.strftime("%Y%m%d%H")
    with _LOCK:
        if _RUNNING or _LAST_ATTEMPT_WEEK == (week, hour):
            return False
        _RUNNING = True
        _LAST_ATTEMPT_WEEK = (week, hour)

    def worker():
        global _RUNNING
        try:
            from weekly_drive_backup import main
            main()
        except Exception as exc:
            # Do not log tokens, credentials, or response bodies.
            print("WEEKLY_DRIVE_BACKUP_FAILED|" + type(exc).__name__, flush=True)
        finally:
            with _LOCK:
                _RUNNING = False

    threading.Thread(target=worker, daemon=True, name="weekly-drive-backup").start()
    return True
