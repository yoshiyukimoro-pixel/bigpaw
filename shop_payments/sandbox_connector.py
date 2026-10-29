"""Isolated Square *Sandbox-only* adapter for BIG PAW food shop.

This module is NOT imported by the production BIG PAW backend, Dockerfile or
public shop page. It is intentionally never able to call Square Production.
No Square credentials or customer data are stored in this source code.
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .square_checkout import (
    SaleItem, build_square_link_payload, completed_payment_matches,
    verify_square_webhook,
)

SANDBOX_ENDPOINT = "https://connect.squareupsandbox.com/v2/online-checkout/payment-links"
SQUARE_VERSION = "2026-09-16"
_ALLOWED_LINK_HOSTS = frozenset(("sandbox.square.link",))
_ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


class SquareSandboxError(RuntimeError):
    pass


def _safe_checkout_url(value: str) -> bool:
    """Never give a browser an attacker-controlled URL from malformed responses."""
    if not isinstance(value, str):
        return False
    p = urlsplit(value)
    return p.scheme == "https" and p.hostname in _ALLOWED_LINK_HOSTS and not p.username and not p.password


def create_square_sandbox_payment_link(payload: dict, *, token: str, opener=urlopen) -> dict:
    """Make an isolated server-side CreatePaymentLink request to Square Sandbox.

    No production hostname, configurable API host, or client-side token allowed.
    Callable only after shop prices and shipping have been independently approved.
    A network error must NOT imply payment failure or authorize a different order
    ID: retry the SAME stored payload and idempotency_key.
    """
    if not isinstance(token, str) or not token.strip():
        raise SquareSandboxError("Sandbox credential is missing")
    if not isinstance(payload, dict) or not payload.get("order") or not payload.get("idempotency_key"):
        raise SquareSandboxError("Square order payload is invalid")
    request = Request(
        SANDBOX_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + token.strip(),
            "Content-Type": "application/json",
            "Square-Version": SQUARE_VERSION,
        },
        method="POST",
    )
    try:
        with opener(request, timeout=12) as response:
            if getattr(response, "status", 200) not in (200, 201):
                raise SquareSandboxError("Square Sandbox returned an unexpected status")
            data = json.loads(response.read(512_000))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        # Do not log or show bearer token, HTTP response data, or customer data.
        raise SquareSandboxError("Square Sandbox connection failed; check server logs safely") from None
    if not isinstance(data, dict) or not isinstance(data.get("payment_link"), dict):
        raise SquareSandboxError("Square Sandbox response has no payment link")
    link = data["payment_link"]
    url = link.get("url") or link.get("long_url")
    if not _safe_checkout_url(url) or not isinstance(link.get("order_id"), str) or not link["order_id"]:
        raise SquareSandboxError("Square Sandbox returned an invalid checkout link")
    if not isinstance(link.get("id"), str) or not link["id"]:
        raise SquareSandboxError("Square Sandbox returned no link ID")
    return {"url": url, "square_order_id": link["order_id"], "square_link_id": link["id"]}


class SandboxOrderStore:
    """Small durable sandbox order journal; no names, addresses or card data.

    Use a separate SQLite database on a staging volume. A public endpoint still
    needs rate limits, CORS policy, CSRF controls and approved shipping pricing.
    """

    def __init__(self, db_file: str | Path):
        self.db_file = str(db_file)
        self._init_db()

    def _open(self):
        conn = sqlite3.connect(self.db_file, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_db(self):
        with closing(self._open()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS orders (
                  order_id TEXT PRIMARY KEY,
                  cart_json TEXT NOT NULL,
                  amount_yen INTEGER NOT NULL CHECK(amount_yen > 0),
                  square_location_id TEXT NOT NULL,
                  square_order_id TEXT UNIQUE,
                  square_link_id TEXT,
                  checkout_url TEXT,
                  state TEXT NOT NULL CHECK(state IN ('created','payment_pending','paid')),
                  created_at INTEGER NOT NULL,
                  paid_at INTEGER,
                  square_payment_id TEXT
                );
                CREATE TABLE IF NOT EXISTS order_items (
                  order_id TEXT NOT NULL,
                  sku TEXT NOT NULL,
                  quantity INTEGER NOT NULL CHECK(quantity > 0),
                  PRIMARY KEY (order_id, sku)
                );
                CREATE TABLE IF NOT EXISTS square_events (
                  event_id TEXT PRIMARY KEY,
                  received_at INTEGER NOT NULL
                );
            """)
            # Older Sandbox journals predate the payment-reference column.
            # Keep them readable, but never assume a historical payment ID.
            names = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
            if "square_payment_id" not in names:
                conn.execute("ALTER TABLE orders ADD COLUMN square_payment_id TEXT")

    def add_pending_order(
        self, *, order_id: str, cart: dict[str, int],
        verified_prices: dict[str, SaleItem], shipping_yen: int, location_id: str
    ) -> tuple[dict, int]:
        """Store validated order before asking Square for a payment link."""
        payload, total = build_square_link_payload(
            cart=cart, verified_prices=verified_prices,
            shipping_yen=shipping_yen, square_location_id=location_id,
            local_order_id=order_id, shipping_confirmed=True,
        )
        line_snapshot = json.dumps(payload["order"]["line_items"], ensure_ascii=False, sort_keys=True)
        with closing(self._open()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                existing = conn.execute(
                    "SELECT cart_json, amount_yen, square_location_id FROM orders WHERE order_id=?",
                    (order_id,),
                ).fetchone()
                if existing:
                    if (existing["cart_json"] != line_snapshot
                            or existing["amount_yen"] != total
                            or existing["square_location_id"] != location_id):
                        raise ValueError("cannot reuse checkout ID with different cart or pricing")
                else:
                    conn.execute("""
                        INSERT INTO orders(order_id,cart_json,amount_yen,square_location_id,state,created_at)
                        VALUES (?,?,?,?,?,?)
                    """, (order_id, line_snapshot, total, location_id, "created", int(time.time())))
                # Capture immutable SKU/quantity data for the fulfillment ledger.
                # Square line-item names alone are not unique inventory keys.
                old_items = {
                    row["sku"]: row["quantity"]
                    for row in conn.execute(
                        "SELECT sku, quantity FROM order_items WHERE order_id=?", (order_id,)
                    )
                }
                if old_items and old_items != dict(cart):
                    raise ValueError("cannot change saved SKU quantities")
                if not old_items:
                    conn.executemany(
                        "INSERT INTO order_items(order_id,sku,quantity) VALUES (?,?,?)",
                        [(order_id, sku, qty) for sku, qty in sorted(cart.items())],
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return payload, total

    def checkout_link_if_exists(self, order_id: str) -> dict | None:
        """Return the same existing sandbox link for a retry; never create another."""
        if not _ORDER_ID.fullmatch(order_id):
            raise ValueError("Invalid order ID")
        with closing(self._open()) as conn:
            row = conn.execute(
                "SELECT state,checkout_url,square_order_id,square_link_id,amount_yen "
                "FROM orders WHERE order_id=?", (order_id,),
            ).fetchone()
        if row is None:
            return None
        if row["state"] == "paid":
            raise ValueError("Already paid; do not create new checkout link")
        if row["state"] == "created":
            return None
        if row["state"] != "payment_pending" or not _safe_checkout_url(row["checkout_url"]):
            raise ValueError("Invalid saved checkout")
        return {
            "url": row["checkout_url"], "square_order_id": row["square_order_id"],
            "square_link_id": row["square_link_id"], "amount_yen": row["amount_yen"],
        }

    def save_link(self, order_id: str, link: dict):
        if not _ORDER_ID.fullmatch(order_id) or not isinstance(link, dict):
            raise ValueError("invalid checkout order")
        if not _safe_checkout_url(link.get("url")):
            raise ValueError("unsafe checkout URL")
        if not all(isinstance(link.get(k), str) and link[k] for k in ("square_order_id", "square_link_id")):
            raise ValueError("invalid Square reference")
        with closing(self._open()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
                if not row:
                    raise ValueError("unknown order")
                if row["state"] == "payment_pending":
                    if (row["square_order_id"], row["square_link_id"], row["checkout_url"]) == (
                        link["square_order_id"], link["square_link_id"], link["url"]
                    ):
                        conn.execute("COMMIT")
                        return
                    raise ValueError("cannot change saved Square link")
                if row["state"] != "created":
                    raise ValueError("order is not awaiting checkout")
                conn.execute("""
                    UPDATE orders
                    SET square_order_id=?, square_link_id=?, checkout_url=?, state='payment_pending'
                    WHERE order_id=? AND state='created'
                """, (link["square_order_id"], link["square_link_id"], link["url"], order_id))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def accept_webhook(
        self, *, raw_body: bytes, signature_header: str,
        signature_key: str, notification_url: str, payment_lookup=None
    ) -> str:
        """A signed event is only a hint; verify current Square payment via API.

        payment_lookup is a server-side callback to GET /v2/payments/{id}.
        Without an API confirmation the order MUST remain unpaid. Never call
        Square over the network while holding a SQLite transaction lock.

        Results: 'paid', 'duplicate', 'ignored', 'unmatched', 'unverified'.
        """
        event = verify_square_webhook(
            raw_body=raw_body, signature_header=signature_header,
            signature_key=signature_key, notification_url=notification_url,
        )
        event_id = event["event_id"]
        if not event_id or len(event_id) > 200:
            raise ValueError("Invalid Square event ID")
        pay = event.get("data", {}).get("object", {}).get("payment", {})
        if not isinstance(pay, dict) or not isinstance(pay.get("order_id"), str):
            return "ignored"
        with closing(self._open()) as conn:
            if conn.execute(
                "SELECT 1 FROM square_events WHERE event_id=?", (event_id,)
            ).fetchone():
                return "duplicate"
            row = conn.execute(
                "SELECT * FROM orders WHERE square_order_id=?", (pay["order_id"],)
            ).fetchone()
        if not row:
            # Link persistence and the incoming event can race. Ask Square to retry.
            return "unmatched"
        if not completed_payment_matches(
            event, square_order_id=row["square_order_id"],
            amount_yen=row["amount_yen"], location_id=row["square_location_id"],
        ):
            return "ignored"
        payment_id = pay.get("id")
        if payment_lookup is None or not isinstance(payment_id, str):
            return "unverified"
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,192}", payment_id):
            return "unverified"
        # Never trust a webhook alone; a fresh API read must confirm the same
        # payment, amount, currency, location, order and COMPLETED status.
        current = payment_lookup(payment_id)
        if not isinstance(current, dict) or current.get("id") != payment_id:
            return "unverified"
        fresh = {"type": "payment.updated", "data": {"object": {"payment": current}}}
        if not completed_payment_matches(
            fresh, square_order_id=row["square_order_id"],
            amount_yen=row["amount_yen"], location_id=row["square_location_id"],
        ):
            return "unverified"
        # Do not mark paid when Square reports a fully/partially refunded payment.
        refund = current.get("refunded_money", {})
        if isinstance(refund, dict) and isinstance(refund.get("amount"), int) and refund["amount"] > 0:
            return "unverified"
        # Import only after independent Square API verification, to avoid
        # circular module initialization and any pre-payment notice.
        from .sandbox_notifications import (
            install_notification_tables, enqueue_notification_group, PAID_DRAFTS,
        )
        with closing(self._open()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                if conn.execute(
                    "SELECT 1 FROM square_events WHERE event_id=?", (event_id,)
                ).fetchone():
                    conn.execute("COMMIT")
                    return "duplicate"
                latest = conn.execute(
                    "SELECT * FROM orders WHERE square_order_id=?", (pay["order_id"],)
                ).fetchone()
                if not latest or (
                    latest["amount_yen"] != row["amount_yen"]
                    or latest["square_location_id"] != row["square_location_id"]
                    or latest["square_order_id"] != row["square_order_id"]
                ):
                    conn.execute("COMMIT")
                    return "unverified"
                if latest["state"] not in ("payment_pending", "paid"):
                    conn.execute("COMMIT")
                    return "unverified"
                if latest["state"] == "paid" and latest["square_payment_id"] != payment_id:
                    # A different payment against the same Square order needs
                    # manual review; never silently overwrite the original.
                    conn.execute("COMMIT")
                    return "unverified"
                conn.execute(
                    "INSERT INTO square_events(event_id,received_at) VALUES (?,?)",
                    (event_id, int(time.time())),
                )
                if latest["state"] == "payment_pending":
                    conn.execute(
                        "UPDATE orders SET state='paid',paid_at=?,square_payment_id=? "
                        "WHERE order_id=? AND state='payment_pending'",
                        (int(time.time()), payment_id, latest["order_id"]),
                    )
                # Transactional draft creation, *not* sending. A crash cannot
                # mark an order paid while losing its operator action reminder.
                install_notification_tables(conn)
                enqueue_notification_group(conn,latest["order_id"],PAID_DRAFTS)
                conn.execute("COMMIT")
                return "paid" if latest["state"] == "payment_pending" else "duplicate"
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def status(self, order_id: str) -> str:
        """Internal use only; do not expose public order status without authorization."""
        with closing(self._open()) as conn:
            row = conn.execute("SELECT state FROM orders WHERE order_id=?", (order_id,)).fetchone()
        return row["state"] if row else "not_found"

    def paid_order_snapshot(self, order_id: str) -> dict | None:
        """Operator-only non-PII snapshot; never expose via a public endpoint."""
        if not isinstance(order_id, str) or not _ORDER_ID.fullmatch(order_id):
            raise ValueError("Invalid order ID")
        with closing(self._open()) as conn:
            row = conn.execute(
                "SELECT order_id,amount_yen,square_order_id,square_location_id,"
                "square_payment_id FROM orders WHERE order_id=? AND state='paid'",
                (order_id,),
            ).fetchone()
            if not row:
                return None
            items = conn.execute(
                "SELECT sku,quantity FROM order_items WHERE order_id=? ORDER BY sku",
                (order_id,),
            ).fetchall()
            if not items or not row["square_payment_id"]:
                return None  # Old incomplete journal requires manual recovery.
            return {**dict(row), "cart": {r["sku"]: r["quantity"] for r in items}}
