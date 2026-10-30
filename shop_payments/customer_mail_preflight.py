"""Customer email delivery preflight -- NO REAL SEND, Sandbox only.

The checkout recipient email is fetched from Square Sandbox at the moment the
operator requests a preflight. It is not persisted, logged, or exposed to HTTP.
This module does not import Resend or make any email-provider calls.

Preflight requires a paid verified order, an existing notification draft,
the operator's current review of the SAME email and exact message, and the
same content/contact having passed the no-send simulation.
"""
from __future__ import annotations

import hashlib
import hmac

from .sandbox_connector import SquareSandboxError
from .sandbox_customer_review import (
    CUSTOMER_KINDS, EMAIL, ORDER_ID, SandboxCustomerReview,
    _draft_fingerprint,
)
from .sandbox_customer_dispatch import SandboxDryRunOutbox
from .sandbox_notifications import SandboxNotificationDrafts
from .sandbox_reconcile import _fetch_square_sandbox_resource
from .sandbox_tracking import SandboxTrackingJournal


def _square_checkout_email(order: dict) -> str:
    if not isinstance(order, dict):
        raise ValueError("Square order missing")
    fulfillments = order.get("fulfillments")
    if not isinstance(fulfillments, list):
        raise ValueError("Square shipment contact missing")
    unique = set()
    for item in fulfillments:
        if not isinstance(item, dict) or item.get("type") != "SHIPMENT":
            continue
        details = item.get("shipment_details")
        recipient = details.get("recipient") if isinstance(details, dict) else None
        email = recipient.get("email_address") if isinstance(recipient, dict) else None
        if (isinstance(email, str) and len(email) <= 254
                and EMAIL.fullmatch(email) and ".." not in email
                and not email.startswith(".")):
            unique.add(email.lower())
    if len(unique) != 1:
        raise ValueError("One unambiguous Square shipment email is required")
    return unique.pop()


def prepare_customer_email(
    store, order_id: str, kind: str, *, sandbox_token: str, opener=None
) -> dict:
    """Prepare ephemeral delivery data for a future separately approved sender.

    Caller must never serialize/log the result or expose it to a browser.
    The result is not an authorization to send, even if 'prepared' is true.
    """
    if (not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id)
            or kind not in CUSTOMER_KINDS):
        raise ValueError("Unsupported notification preflight")
    if not isinstance(sandbox_token, str) or not sandbox_token.strip():
        raise ValueError("No Sandbox verification token")
    review = SandboxCustomerReview(store)
    opts = {"token": sandbox_token}
    if opener is not None:
        opts["opener"] = opener
    # This re-reads the Square Sandbox order and checks human-reviewed hashes.
    status = review.readiness(order_id, kind, **opts)
    if not status.get("ready") or not status.get("reviewed"):
        raise ValueError("Fresh operator approval required")
    dryrun = SandboxDryRunOutbox(store)
    if not dryrun.inspected(order_id, kind):
        raise ValueError("No no-send simulation recorded")

    snapshot = store.paid_order_snapshot(order_id)
    if not snapshot or not snapshot.get("square_order_id"):
        raise ValueError("Verified Square paid order required")
    url = "/orders/" + snapshot["square_order_id"]
    value = _fetch_square_sandbox_resource(url, **opts)
    order = value.get("order")
    if not isinstance(order, dict) or order.get("id") != snapshot["square_order_id"]:
        raise SquareSandboxError("Square order mismatch")
    email = _square_checkout_email(order)  # transient, must not be stored
    actual_contact_hash = hmac.new(
        sandbox_token.encode("utf-8"), email.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    approved_contact_hash, approved_message_hash = status["_fingerprints"]
    if not hmac.compare_digest(actual_contact_hash, approved_contact_hash):
        raise ValueError("Square recipient changed during preflight")
    if not hmac.compare_digest(
        _draft_fingerprint(store, order_id, kind), approved_message_hash
    ):
        raise ValueError("Message content changed during preflight")
    delivery_id = hashlib.sha256(
        (order_id + ":" + kind + ":" + approved_contact_hash +
         ":" + approved_message_hash).encode("ascii")
    ).hexdigest()
    with dryrun._open() as db:
        row = db.execute(
            "SELECT snapshot_digest FROM food_sandbox_customer_dryrun "
            "WHERE order_id=? AND kind=?", (order_id, kind)
        ).fetchone()
    if row is None or not hmac.compare_digest(row["snapshot_digest"], delivery_id):
        raise ValueError("No matching no-send simulation")
    draft = SandboxNotificationDrafts(store).preview(order_id, kind)
    message = draft["body"]
    if kind == "customer_shipment_notice":
        tracking = SandboxTrackingJournal(store).read(order_id)
        if not tracking:
            raise ValueError("Shipping confirmation missing")
        message = message.replace(
            "配送会社：【運営が確認して入力】",
            "配送会社：" + tracking["carrier_label"]
        ).replace(
            "追跡番号：【運営が確認して入力】",
            "追跡番号：" + tracking["tracking_number"]
        )
    return {
        "to": email,  # IN MEMORY ONLY -- never expose through an HTTP response
        "subject": draft["subject"],
        "body": message,
        "idempotency_key": "bigpaw-shop-customer/v1/" + order_id + "/" + kind,
        "snapshot_digest": delivery_id,
        "prepared_only": True,
    }
