#!/usr/bin/env python3
"""One-time, safe Cloudflare Stream credentials probe.

This never uploads video bytes and never changes BIG PAW listing data.
A successful direct-upload ticket is deleted immediately. It runs at most once
per persistent volume for this diagnosis version.
"""
from __future__ import annotations
import io
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit

VERSION = "20261027-v2"
MARKER = ".bigpaw-cloudflare-stream-probe-" + VERSION + ".json"

def errors_from_body(raw):
    try: data = json.loads(raw or b"{}")
    except (ValueError, TypeError): return {"codes": [], "messages": ["non_json_response"]}
    errors = data.get("errors", []) if isinstance(data, dict) else []
    codes, messages = [], []
    for entry in errors[:3]:
        if not isinstance(entry, dict): continue
        code = entry.get("code")
        if isinstance(code, (str, int)) and re.fullmatch(r"[a-zA-Z0-9_-]{1,20}", str(code)):
            codes.append(str(code))
        message = str(entry.get("message") or "").strip()
        # Never emit arbitrary credentials or account identifiers from responses.
        low = message.lower()
        if "permission" in low or "unauthorized" in low or "forbidden" in low: label = "permission_denied"
        elif "authenticat" in low or "token" in low or "credential" in low: label = "authentication_failed"
        elif "billing" in low or "payment" in low or "subscription" in low: label = "billing_or_subscription"
        elif "storage" in low or "quota" in low or "capacity" in low or "minutes" in low: label = "storage_capacity"
        elif "not found" in low or "account" in low: label = "account_not_found_or_unavailable"
        elif "invalid" in low: label = "invalid_request"
        else: label = "other"
        messages.append(label)
    return {"codes": codes, "messages": messages}

def probe_once(env=None, fetch=urlopen, out=print):
    e = os.environ if env is None else env
    account = e.get("BIGPAW_CLOUDFLARE_STREAM_ACCOUNT_ID", "").strip()
    token = e.get("BIGPAW_CLOUDFLARE_STREAM_API_TOKEN", "").strip()
    if not (account and token):
        out("BIGPAW_STREAM_PROBE|result=not_configured")
        return {"result": "not_configured"}
    data_dir = e.get("BIGPAW_DATA_DIR", "").strip()
    if not data_dir:
        out("BIGPAW_STREAM_PROBE|result=skip_no_persistent_data_dir")
        return {"result": "skip_no_persistent_data_dir"}
    marker = Path(data_dir) / MARKER
    if marker.exists():
        out("BIGPAW_STREAM_PROBE|result=previously_checked")
        return {"result": "previously_checked"}
    base = e.get("BIGPAW_CLOUDFLARE_STREAM_API_BASE", "https://api.cloudflare.com/client/v4").rstrip("/")
    url = base + "/accounts/" + quote(account, safe="") + "/stream/direct_upload"
    payload = {"maxDurationSeconds": 60, "allowedOrigins": ["bigpaw.site", "www.bigpaw.site"],
               "requireSignedURLs": False, "creator": "bigpaw-stream-probe",
               "meta": {"puppyId": "bigpaw-connection-check", "name": "probe-no-video-upload"}}
    req = Request(url, data=json.dumps(payload).encode("utf-8"),
                  headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                           "Accept": "application/json"}, method="POST")
    result = {"result": "unknown"}
    try:
        with fetch(req, timeout=15) as response:
            raw = response.read(50000)
        doc = json.loads(raw or b"{}")
        if not doc.get("success", True):
            result = {"result": "api_rejected", **errors_from_body(raw)}
        else:
            uid = str((doc.get("result") or {}).get("uid") or "")
            result = {"result": "ticket_created"}
            # Log only the host/scheme, never the one-time credential-bearing URL.
            upload_url = str((doc.get("result") or {}).get("uploadURL") or "")
            parsed = urlsplit(upload_url)
            hostname = str(parsed.hostname or "").lower()
            result["upload_host"] = hostname if re.fullmatch(r"[a-z0-9.-]{1,253}", hostname) else "invalid_hostname"
            result["upload_scheme"] = parsed.scheme if parsed.scheme in ("http", "https") else "other"
            # Delete *only* the newly generated, unused ticket to release storage.
            if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", uid):
                del_req = Request(base + "/accounts/" + quote(account, safe="") +
                                  "/stream/" + quote(uid, safe=""),
                                  headers={"Authorization": "Bearer " + token}, method="DELETE")
                try:
                    with fetch(del_req, timeout=10): pass
                    result["ticket_deleted"] = True
                except Exception:
                    result["ticket_deleted"] = False
    except HTTPError as exc:
        result = {"result": "http_rejected", "http_status": exc.code,
                  **errors_from_body(exc.read(10000))}
    except Exception as exc:
        result = {"result": "network_or_other_error", "type": type(exc).__name__}
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    out("BIGPAW_STREAM_PROBE|" + "|".join(
        key + "=" + (",".join(str(i) for i in val) if isinstance(val, list) else str(val))
        for key, val in result.items()
    ))
    return result

if __name__ == "__main__":
    probe_once()
