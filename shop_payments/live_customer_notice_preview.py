"""Private, review-only draft for a future REAL Square-paid food-shop order.

No HTTP route imports this module. No Resend imports, no messages sent, no
shipping/return activity, no seller-policy approval and no production switches.
This preview must NOT be passed directly to customer_email_transport.send_once:
it deliberately has neither 'prepared_only' nor the sendable field 'to'.
The future live controller still needs explicit proprietor/recipient approvals,
immutable final checkout terms, authorization and delivery-state checks.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from .live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from .square_live_readonly import verify_paid_live_shipment

KIND = "customer_order_confirmed"


def preview_paid_order_confirmation(
    *, ledger: LiveOrderLedger, order_id: str, api_key: str,
    review_secret: str, opener=None, verifier=None
) -> dict:
    """Fresh Square production READS only; return non-sendable masked preview.

    The caller's order_id is only a lookup key. Amount, Square order/location/
    payment IDs MUST come from the immutable paid journal. A prior paid event
    is insufficient if Square has since refunded/reversed or changed shipping.
    The recipient lives only in function memory. No emailing or SQL write.
    """
    if not isinstance(ledger, LiveOrderLedger):
        raise LiveOrderBlocked("Private live order ledger required")
    if not isinstance(api_key, str) or not api_key.strip():
        raise LiveOrderBlocked("No approved Square read key")
    if not isinstance(review_secret, str) or len(review_secret) < 24:
        raise LiveOrderBlocked("Missing private notice-review signing secret")
    snapshot = ledger.paid_notice_snapshot(order_id)

    fn = verifier or verify_paid_live_shipment
    args = {
        "payment_id": snapshot["payment_id"],
        "square_order_id": snapshot["square_order_id"],
        "location_id": snapshot["location_id"],
        "amount_yen": snapshot["amount_yen"],
        "api_key": api_key,
    }
    if opener is not None:
        args["opener"] = opener
    fresh = fn(**args)
    if (not isinstance(fresh, dict)
            or fresh.get("live_square_verified") is not True
            or any(fresh.get(field) != snapshot[stored] for field, stored in (
                ("payment_id", "payment_id"),
                ("square_order_id", "square_order_id"),
                ("location_id", "location_id"),
                ("amount_yen", "amount_yen")))):
        raise LiveOrderBlocked("Fresh Square paid-shipment evidence does not match")

    email = fresh.get("recipient_email")
    # The full email must never be exposed in the preview or written to SQL.
    if (not isinstance(email, str) or len(email) > 254
            or email.count("@") != 1 or email != email.strip()):
        raise LiveOrderBlocked("Unambiguous Square shipping contact required")
    local, domain = email.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise LiveOrderBlocked("Invalid Square shipping contact")
    masked = local[0] + "***@" + domain[0] + "***"

    details = []
    for line in snapshot["lines"]:
        details.append(
            f"・{line['sku']} {line['name']} {line['size']} ×{line['qty']} "
            f"（税込単価 {line['unit_yen']:,}円）"
        )
    subject = "【BIG PAW】ドッグフードご注文・決済確認（送信前確認）"
    body = (
        "このたびはご注文ありがとうございます。\\n"
        f"ご注文番号：{snapshot['order_id']}\\n"
        + "\\n".join(details)
        + f"\\n合計（税込・送料込み）：{snapshot['amount_yen']:,}円"
        + "\\n追加送料：0円\\n"
        "商品は決済後、九州の仕入先から埼玉の当店へ取り寄せ、"
        "検品後に当店から発送します。"
        "通常、ご注文・決済完了から4〜7日程度がお届けの目安です。"
        "休業日・欠品・配送事情等により前後する場合があります。"
        "\\n※これは送信内容の社内確認用プレビューであり、メールは送信されていません。"
    )

    # The fingerprint binds the *exact* contact, paid payment and draft.
    # Key is a separate server secret; never persist even this draft to SQL.
    signed = json.dumps({
        "order_id": snapshot["order_id"], "kind": KIND,
        "payment_id": snapshot["payment_id"],
        "square_order_id": snapshot["square_order_id"],
        "amount_yen": snapshot["amount_yen"],
        "recipient": email, "subject": subject, "body": body,
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hmac.new(review_secret.encode("utf-8"),
                      signed.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "order_id": snapshot["order_id"],
        "kind": KIND,
        "subject": subject,
        "body": body,
        "masked_recipient": masked,
        "review_fingerprint": digest,
        "review_only": True,
        "send_enabled": False,
        "sent": False,
        "requires_owner_approval": True,
    }
