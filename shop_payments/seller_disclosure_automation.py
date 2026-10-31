"""Email-verified on-request seller-contact disclosure. DORMANT unless explicitly
enabled in the live service with privately supplied merchant details and Resend.
No private merchant contact data is persisted, exposed in source, or logged.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
from urllib.request import Request, urlopen

CATEGORY = "ドッグフードショップ販売者情報の開示請求"
FROM = "BIG PAW <noreply@bigpaw.site>"
REPLY_TO = "info@bigpaw.site"
ENDPOINT = "https://api.resend.com/emails"
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_\x60{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{30,200}$")
PROVIDER_ID = re.compile(r"^[A-Za-z0-9_-]{6,100}$")
TTL = 24 * 60 * 60


def ready(env):
    """Fail closed: publishing a legal draft is never permission to send PII."""
    if not isinstance(env, dict):
        return False
    required = ("BIGPAW_SHOP_SELLER_NAME", "BIGPAW_SHOP_SELLER_POSTAL",
                "BIGPAW_SHOP_SELLER_ADDRESS", "BIGPAW_SHOP_SELLER_PHONE")
    return (env.get("BIGPAW_ENV") == "production"
            and env.get("BIGPAW_SHOP_SELLER_DISCLOSURE_AUTO_ENABLED") == "1"
            and isinstance(env.get("RESEND_API_KEY"), str)
            and len(env["RESEND_API_KEY"].strip()) >= 20
            and all(isinstance(env.get(x), str) and env[x].strip() for x in required)
            and re.fullmatch(r"\d{3}-\d{4}", env["BIGPAW_SHOP_SELLER_POSTAL"]) is not None
            and re.fullmatch(r"0\d{9,10}", re.sub(r"[-\s]", "", env["BIGPAW_SHOP_SELLER_PHONE"])) is not None
            and len(env["BIGPAW_SHOP_SELLER_ADDRESS"]) <= 300)


def install(db):
    db.execute("""CREATE TABLE IF NOT EXISTS food_seller_disclosure (
       ticket_id TEXT PRIMARY KEY,
       token_hash TEXT UNIQUE NOT NULL,
       status TEXT NOT NULL CHECK (status IN (
           'verification_prepared','challenge_accepted','challenge_unknown',
           'sending','provider_accepted','delivery_unknown')),
       created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
       accepted_at INTEGER, updated_at INTEGER NOT NULL,
       provider_id TEXT
    )""")


def _digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _record(db, ticket_id, state, at, provider_id=None):
    db.execute(
        "UPDATE food_seller_disclosure SET status=?,updated_at=?,provider_id=? WHERE ticket_id=?",
        (state, at, provider_id, ticket_id),
    )


def send_resend(api_key, recipient, subject, body, idempotency_key, opener=urlopen):
    """Single Resend call, never fallback to SMTP after an ambiguous outcome."""
    if not EMAIL.fullmatch(recipient) or ".." in recipient or "\r" in recipient or "\n" in recipient:
        raise ValueError("invalid recipient")
    payload = json.dumps({"from": FROM, "to": [recipient],
                          "reply_to": REPLY_TO, "subject": subject, "text": body},
                         ensure_ascii=False).encode("utf-8")
    request = Request(ENDPOINT, data=payload, method="POST", headers={
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Idempotency-Key": idempotency_key,
        "User-Agent": "BIGPAW-Seller-Disclosure/1.0",
    })
    # An error may mean that the provider received the mail. The journal forbids
    # automatic retries. Never print an exception containing mail payload or PII.
    with opener(request, timeout=12) as response:
        if response.status not in (200, 201):
            raise RuntimeError("provider_unconfirmed")
        data = json.loads(response.read(4096))
    ident = data.get("id") if isinstance(data, dict) else None
    if not isinstance(ident, str) or not PROVIDER_ID.fullmatch(ident):
        raise RuntimeError("provider_receipt_invalid")
    return ident


def request_for_ticket(db, ticket_id, recipient, *, env=None, clock=time.time,
                       sender=send_resend, token_factory=secrets.token_urlsafe):
    """Called after an ordinary support ticket is committed.
    Only emails a challenge. NEVER sends seller contact data at this step.
    """
    env = os.environ if env is None else env
    if not ready(env):
        return "disabled"
    if not isinstance(recipient, str) or len(recipient) > 254 or not EMAIL.fullmatch(recipient):
        return "invalid_recipient"
    now = int(clock())
    install(db)
    # Block repeated challenges to the same recipient even with distinct IPs.
    count = db.execute("""SELECT COUNT(*) FROM food_seller_disclosure d
         JOIN support_tickets t ON t.id=d.ticket_id
         WHERE LOWER(t.email)=? AND d.created_at>=?""",
                       (recipient.lower(), now-3600)).fetchone()[0]
    if count >= 3:
        return "too_many_requests"
    token = token_factory(32)
    if not TOKEN.fullmatch(token):
        raise ValueError("invalid token generator")
    try:
        db.execute("""INSERT INTO food_seller_disclosure
            (ticket_id,token_hash,status,created_at,expires_at,updated_at)
            VALUES(?,?,?,?,?,?)""",
                   (ticket_id, _digest(token), "verification_prepared",now,now+TTL,now))
        db.commit()
    except sqlite3.IntegrityError:
        return "already_requested"
    url = "https://bigpaw.site/shop-disclosure-confirm.html#token=" + token
    subject = "【BIG PAW】販売者情報の開示請求：メールアドレス確認"
    body = ("BIG PAWフードショップの販売者住所・電話番号の開示をご希望いただきありがとうございます。\n\n"
            "以下のページでメールアドレスを確認すると、登録されたこのアドレスへ販売者情報を自動送信します。\n"
            + url + "\n\n確認期限：24時間\n"
            "この請求に心当たりがない場合は、操作せずに削除してください。\n"
            "このメールには事業者住所・電話番号は記載していません。")
    try:
        receipt = sender(env["RESEND_API_KEY"], recipient, subject, body,
                         "seller-challenge-" + ticket_id)
    except Exception:
        _record(db,ticket_id,"challenge_unknown",int(clock()))
        db.commit()
        return "delivery_unknown"
    _record(db,ticket_id,"challenge_accepted",int(clock()),receipt)
    db.commit()
    return "verification_sent"


def confirm_request(db, token, *, env=None, clock=time.time,
                    sender=send_resend):
    """POST-only after email token possession; reserve BEFORE network send."""
    env = os.environ if env is None else env
    if not ready(env):
        return "disabled"
    if not isinstance(token,str) or not TOKEN.fullmatch(token):
        return "invalid_or_expired"
    now = int(clock())
    install(db)
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("""SELECT d.ticket_id,d.status,d.expires_at,t.email
        FROM food_seller_disclosure d JOIN support_tickets t ON t.id=d.ticket_id
        WHERE d.token_hash=?""",(_digest(token),)).fetchone()
    if row is None or row[1] != "challenge_accepted" or row[2] <= now:
        db.rollback()
        return "invalid_or_expired"
    ticket_id,_,_,recipient = row
    db.execute("""UPDATE food_seller_disclosure SET status='sending',updated_at=?
        WHERE ticket_id=?""",(now,ticket_id))
    db.commit()
    subject = "【BIG PAW】特定商取引法に基づく販売者情報の開示"
    body = ("BIG PAWフードショップの販売者情報を開示いたします。\n\n"
            "販売業者：" + env["BIGPAW_SHOP_SELLER_NAME"].strip() + "\n"
            "郵便番号：" + env["BIGPAW_SHOP_SELLER_POSTAL"].strip() + "\n"
            "所在地：" + env["BIGPAW_SHOP_SELLER_ADDRESS"].strip() + "\n"
            "電話番号：" + env["BIGPAW_SHOP_SELLER_PHONE"].strip() + "\n\n"
            "お問い合わせ：info@bigpaw.site\n"
            "この情報は特定商取引法に基づく開示請求への回答です。")
    try:
        receipt = sender(env["RESEND_API_KEY"], recipient, subject, body,
                         "seller-disclosure-" + ticket_id)
    except Exception:
        _record(db,ticket_id,"delivery_unknown",int(clock()))
        db.commit()
        return "delivery_unknown"
    _record(db,ticket_id,"provider_accepted",int(clock()),receipt)
    # No private street address/phone in operator reply history or audit logs.
    db.execute("""UPDATE support_tickets SET status='resolved',
         operator_note=?,updated_at=? WHERE id=?""",
         ("メールアドレス確認済み・販売者情報の自動回答を送信サービスが受け付けました（到達未確認）。",
          int(clock()),ticket_id))
    db.execute("""INSERT INTO audit_logs
        (id,user_id,action,target_type,target_id,detail,created_at)
        VALUES(?,?,?,?,?,?,?)""",
        ("a_"+secrets.token_hex(6),None,"shop_seller_disclosure_provider_accepted",
         "support_ticket",ticket_id,"email_verified;no_private_content",int(clock())))
    db.commit()
    return "provider_accepted"
