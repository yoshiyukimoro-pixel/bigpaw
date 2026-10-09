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


def fetch_sender_domain_status(key, opener=urlopen):
    """Read sending-domain SPF/DKIM verification, never its DNS values."""
    headers = {
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
        "User-Agent": "BIGPAW-Operator-Mail-Diagnostics/1.0",
    }
    with opener(Request("https://api.resend.com/domains", headers=headers), timeout=8) as response:
        domain_list = json.load(response)
    rows = domain_list.get("data") or []
    if not isinstance(rows, list):
        raise ValueError("unexpected domain list")
    domain = next((d for d in rows if isinstance(d, dict)
                   and str(d.get("name", "")).strip().lower() == "bigpaw.site"), None)
    if not domain:
        return {"status": "missing", "sending": "unknown", "records": {}}
    identifier = str(domain.get("id") or "")
    if not identifier or not all(c.isalnum() or c == "-" for c in identifier):
        raise ValueError("invalid domain identifier")
    with opener(Request("https://api.resend.com/domains/" + identifier,
                        headers=headers), timeout=8) as response:
        details = json.load(response)
    records = {}
    for item in details.get("records") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("record") or "").upper()
        if kind not in {"SPF", "DKIM", "DMARC"}:
            continue
        status = str(item.get("status") or "unknown").lower()
        if status not in {"verified", "pending", "not_started", "failed", "temporarily_failed"}:
            status = "unknown"
        if kind not in records:
            records[kind] = []
        records[kind].append(status)
    capabilities = details.get("capabilities") or domain.get("capabilities") or {}
    raw_domain_status = str(details.get("status") or domain.get("status") or "unknown").lower()
    raw_sending_status = str(capabilities.get("sending") or "unknown").lower()
    return {
        "status": raw_domain_status if raw_domain_status in
        {"verified", "partially_verified", "pending", "not_started", "failed", "temporarily_failed"}
        else "unknown",
        "sending": raw_sending_status if raw_sending_status in {"enabled", "disabled"} else "unknown",
        "records": records,
    }


def audit_sender_domain(key):
    try:
        domain = fetch_sender_domain_status(key)
    except HTTPError as exc:
        print("BIGPAW_RESEND_DOMAIN_AUDIT|result=unavailable|reason=http_" + str(exc.code), flush=True)
        return
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        print("BIGPAW_RESEND_DOMAIN_AUDIT|result=unavailable|reason=" + type(exc).__name__, flush=True)
        return
    print("BIGPAW_RESEND_DOMAIN_AUDIT|result=ok|status=" + domain["status"] +
          "|sending=" + domain["sending"], flush=True)
    for kind in ("SPF", "DKIM", "DMARC"):
        statuses = domain["records"].get(kind) or []
        print("BIGPAW_RESEND_DOMAIN_RECORD|type=" + kind +
              "|status=" + (",".join(statuses) if statuses else "unreported"), flush=True)


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
    audit_sender_domain(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
