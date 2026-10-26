"""Opt-in weekly Drive upload scheduler for the existing BIG PAW web process.

Called from a dedicated lightweight monitor thread inside the existing web service.
Never start a separate Railway service or attach the live volume elsewhere.
"""
import datetime as dt
import os
import threading
import json
from pathlib import Path
JST = dt.timezone(dt.timedelta(hours=9), name="JST")
_LOCK = threading.Lock()
_RUNNING = False
_LAST_ATTEMPT_WEEK = None
_LAST_SUCCESS_WEEK = None
_STATUS_PATH = Path(__file__).resolve().parents[1] / "weekly-drive-status.json"


def _write_status(status: str, detail: str = "", week: str = ""):
    payload = {
        "status": status,
        "detail": detail,
        "week": week,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    try:
        _STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def maybe_schedule_weekly_backup():
    """Start one upload thread on Mondays in Japan time, if explicitly enabled.

    Retries are allowed after restart; the uploader rejects duplicate weekly names.
    Failed attempts are retried on the next monitor tick, at most one per hour.
    """
    global _RUNNING, _LAST_ATTEMPT_WEEK
    if os.environ.get("BIGPAW_WEEKLY_DRIVE_BACKUP_ENABLED") != "1":
        _write_status("disabled")
        return False
    now = dt.datetime.now(dt.timezone.utc).astimezone(JST)
    if now.weekday() != 0:
        _write_status("off_day", week=now.strftime("%G-W%V"))
        return False
    week = now.strftime("%G-W%V")
    hour = now.strftime("%Y%m%d%H")
    with _LOCK:
        if _RUNNING or _LAST_SUCCESS_WEEK == week or _LAST_ATTEMPT_WEEK == (week, hour):
            return False
        _RUNNING = True
        _LAST_ATTEMPT_WEEK = (week, hour)

    def worker():
        global _RUNNING, _LAST_SUCCESS_WEEK
        try:
            from weekly_drive_backup import main
            _write_status("running", week=week)
            main()
            _write_status("success", week=week)
            with _LOCK:
                _LAST_SUCCESS_WEEK = week
        except Exception as exc:
            # Do not log tokens, credentials, response bodies, or arbitrary exception text.
            kind = type(exc).__name__
            detail = ""
            safe_code = getattr(exc, "safe_code", "")
            if kind == "OAuthRefreshFailed" and safe_code in {
                "invalid_grant", "invalid_client", "unauthorized_client", "invalid_scope",
                "http_error", "network_error", "invalid_response", "missing_access_token",
            }:
                detail = "|" + safe_code
            elif kind == "RefreshError":
                msg = str(exc).lower()
                for code in ("invalid_grant", "invalid_client", "unauthorized_client", "invalid_scope"):
                    if code in msg:
                        detail = "|" + code
                        break
            print("WEEKLY_DRIVE_BACKUP_FAILED|" + kind + detail, flush=True)
            _write_status("failed", (kind + detail), week)
        finally:
            with _LOCK:
                _RUNNING = False

    print("WEEKLY_DRIVE_BACKUP_SCHEDULED|" + week, flush=True)
    threading.Thread(target=worker, daemon=True, name="weekly-drive-backup").start()
    return True
