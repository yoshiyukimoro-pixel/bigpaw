#!/usr/bin/env python3
"""Read-only check of Resend delivery events for BIG PAW operator breeder-application mail.

Prints only send time, provider id and delivery event. Never prints email
contents, other recipient addresses or API credentials. This does not send mail.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

OPERATOR_EMAIL = (os.environ.get("BIGPAW_APPLICATION_NOTIFY_EMAIL") or "info@bigpaw.site").strip().lower()
SUBJECT_FRAGMENT = "新しいブリーダー掲載申請"
BASE_URL = "https://api.resend.com/emails"


def operator_entries(rows, target=OPERATOR_EMAIL):
    """Return relevant Resend list entries; never inspect or print their message bodies."""
    out = []
    for entry in rows:
        recipients = entry.get("to") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        if target not in {str(address).strip().lower() for address in recipients}:
            continue
        if SUBJECT_FRAGMENT not in str(entry.get("subject") or ""):
            continue
        out.append({
            "id": str(entry.get("id") or "")[:100],
            "sent_at": str(entry.get("created_at") or "")[:50],
            "event": str(entry.get("last_event") or "unknown")[:40],
        })
    return out


def fetch_recent(key, opener=urlopen, limit_pages=3):
    """Read provider statuses without modifying the mailbox or sending mail."""
    found, cursor = [], None
    for _ in range(limit_pages):
        url = BASE_URL + "?limit=100"
        if cursor:
            url += "&after=" + quote(cursor, safe="")
        req = Request(url, headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
            "User-Agent": "BIGPAW-Operator-Mail-Diagnostics/1.0",
        })
        with opener(req, timeout=8) as response:
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise ValueError("unexpected response")
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            raise ValueError("unexpected email list")
        found.extend(operator_entries(rows))
        if not payload.get("has_more") or not rows:
            break
        cursor = str(rows[-1].get("id") or "")
        if not cursor:
            break
    return found


def main() -> int:
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not key:
        print("BREEDER_OPERATOR_MAIL_AUDIT|result=unavailable|reason=no_resend_key", flush=True)
        return 0
    try:
        entries = fetch_recent(key)
    except HTTPError as exc:
        print("BREEDER_OPERATOR_MAIL_AUDIT|result=unavailable|reason=resend_http_" + str(exc.code), flush=True)
        return 0
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        print("BREEDER_OPERATOR_MAIL_AUDIT|result=unavailable|reason=" + type(exc).__name__, flush=True)
        return 0
    print("BREEDER_OPERATOR_MAIL_AUDIT|result=ok|matching=" + str(len(entries)), flush=True)
    for item in entries[:15]:
        print("BREEDER_OPERATOR_MAIL_STATUS|event=" + item["event"] +
              "|sent_at=" + item["sent_at"] + "|provider_id=" + item["id"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
