"""Isolated future LIVE checkout order ledger. NOT connected to BIG PAW routes.

Trust boundary: only an authenticated server may call register_checkout after it
itself generated the cart, price and Square checkout IDs. Never pass a browser
payload directly to this object. This module creates NO payment links, sends NO
mail, and does NOT use a live Square key on its own.

Keep an immutable, PII-free checkout snapshot before accepting a paid event.
A webhook payment ID is only a hint: independent Square production GETs must
confirm the exact order/location/JPY amount and shipment before marking paid.
SQLite commits are idempotent and fail closed on conflicts or unknown outcomes.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import time

_ORDER = re.compile(r"^FOOD[0-9a-f]{32}$")
_SQUARE_ID = re.compile(r"^[A-Za-z0-9_-]{8,192}$")
_MAX_TOTAL = 2_000_000


class LiveOrderBlocked(ValueError):
    """Never interpret this as permission to retry or create a new charge."""


def _valid_id(value):
    return isinstance(value, str) and _SQUARE_ID.fullmatch(value) is not None


class LiveOrderLedger:
    def __init__(self, db_file: str | Path):
        self.db_file = str(db_file)

    def _open(self):
        conn = sqlite3.connect(self.db_file, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @staticmethod
    def _install(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS food_live_order_ledger (
                order_id TEXT PRIMARY KEY,
                square_order_id TEXT NOT NULL UNIQUE,
                square_location_id TEXT NOT NULL,
                cart_snapshot TEXT NOT NULL,
                amount_yen INTEGER NOT NULL CHECK(amount_yen > 0),
                state TEXT NOT NULL CHECK(state IN ('checkout_recorded','paid_verified')),
                payment_id TEXT UNIQUE,
                created_at INTEGER NOT NULL,
                paid_at INTEGER
            )
        """)

    @staticmethod
    def _snapshot(cart):
        # The server's approved retail pricebook is the *only* price source.
        from .retail_catalog import load_sale_catalog
        catalog = load_sale_catalog()
        if not isinstance(cart, dict) or not 1 <= len(cart) <= 35:
            raise LiveOrderBlocked("Invalid trusted checkout cart")
        lines = []
        total = 0
        count = 0
        for sku, qty in sorted(cart.items()):
            if (not isinstance(sku, str) or sku not in catalog
                    or type(qty) is not int or not 1 <= qty <= 10):
                raise LiveOrderBlocked("Unrecognized SKU or quantity")
            count += qty
            if count > 50:
                raise LiveOrderBlocked("Item limit exceeded")
            unit = catalog[sku].sale_price_yen
            if type(unit) is not int or unit <= 0:
                raise LiveOrderBlocked("Invalid approved unit price")
            total += unit * qty
            lines.append({"sku": sku, "qty": qty, "unit_yen": unit})
        if total < 1 or total > _MAX_TOTAL:
            raise LiveOrderBlocked("Checkout total outside safety limit")
        return json.dumps(lines, sort_keys=True, separators=(",", ":")), total

    def register_checkout(self, *, order_id, square_order_id, location_id, cart):
        """Call only from trusted LIVE server immediately after Square link creation.

        Identical retry is safe; any changed ID, price or cart is rejected.
        Does not receive an email/address/name or perform a Square request.
        """
        if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
            raise LiveOrderBlocked("Invalid server-generated order ID")
        if not _valid_id(square_order_id) or not _valid_id(location_id):
            raise LiveOrderBlocked("Invalid Square checkout references")
        cart_json, amount = self._snapshot(cart)
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute(
                    "SELECT square_order_id,square_location_id,cart_snapshot,amount_yen "
                    "FROM food_live_order_ledger WHERE order_id=?", (order_id,)
                ).fetchone()
                expected = (square_order_id, location_id, cart_json, amount)
                if old is not None:
                    actual = tuple(old[k] for k in (
                        "square_order_id", "square_location_id", "cart_snapshot",
                        "amount_yen"))
                    if actual != expected:
                        raise LiveOrderBlocked("Checkout identity or amount changed")
                    inserted = False
                else:
                    db.execute(
                        "INSERT INTO food_live_order_ledger "
                        "(order_id,square_order_id,square_location_id,cart_snapshot,"
                        "amount_yen,state,created_at) "
                        "VALUES (?,?,?,?,?,'checkout_recorded',?)",
                        (order_id, square_order_id, location_id, cart_json,
                         amount, int(time.time())),
                    )
                    inserted = True
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"order_id": order_id, "amount_yen": amount,
                "new_record": inserted}

    def status(self, order_id):
        if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
            raise LiveOrderBlocked("Invalid order reference")
        with closing(self._open()) as db:
            try:
                row = db.execute(
                    "SELECT state,amount_yen FROM food_live_order_ledger "
                    "WHERE order_id=?", (order_id,)
                ).fetchone()
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc):
                    return {"state": "not_found"}
                raise
        return dict(row) if row else {"state": "not_found"}

    def reconcile_payment(self, *, order_id, payment_id, api_key, opener=None,
                          verifier=None):
        """Verify with Square GET before a durable, once-only paid transition.

        A future authenticated webhook/controller supplies payment_id, but the
        stored order, location and price always come from this private journal.
        The verifier is called OUTSIDE the SQLite write transaction. Neither
        the fresh recipient nor any payment token is stored or returned.
        """
        if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
            raise LiveOrderBlocked("Invalid order reference")
        if not _valid_id(payment_id):
            raise LiveOrderBlocked("Invalid Square payment reference")
        if not isinstance(api_key, str) or not api_key.strip():
            raise LiveOrderBlocked("Missing live Square credential")
        with closing(self._open()) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_live_order_ledger'"
            ).fetchone()
            if not exists:
                raise LiveOrderBlocked("No trusted checkout snapshot")
            row = db.execute(
                "SELECT * FROM food_live_order_ledger WHERE order_id=?",
                (order_id,)
            ).fetchone()
        if row is None:
            raise LiveOrderBlocked("No trusted checkout snapshot")
        if row["state"] == "paid_verified":
            if row["payment_id"] != payment_id:
                raise LiveOrderBlocked("Different payment for a paid order")
            return {"state": "paid_verified", "new_transition": False}
        if row["state"] != "checkout_recorded":
            raise LiveOrderBlocked("Unrecognized order state")

        if verifier is None:
            from .square_live_readonly import verify_paid_live_shipment
            verifier = verify_paid_live_shipment
        args = dict(payment_id=payment_id, square_order_id=row["square_order_id"],
                    location_id=row["square_location_id"],
                    amount_yen=row["amount_yen"], api_key=api_key)
        if opener is not None:
            args["opener"] = opener
        # Fail closed. Never mark paid if the independent production GET fails.
        evidence = verifier(**args)
        if (not isinstance(evidence, dict)
                or evidence.get("live_square_verified") is not True
                or any(evidence.get(key) != expected for key, expected in (
                    ("payment_id", payment_id),
                    ("square_order_id", row["square_order_id"]),
                    ("location_id", row["square_location_id"]),
                    ("amount_yen", row["amount_yen"])))):
            raise LiveOrderBlocked("Independent Square payment evidence mismatch")

        with closing(self._open()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute(
                    "SELECT * FROM food_live_order_ledger WHERE order_id=?",
                    (order_id,)
                ).fetchone()
                if current is None or any(current[k] != row[k] for k in (
                        "square_order_id", "square_location_id", "cart_snapshot",
                        "amount_yen")):
                    raise LiveOrderBlocked("Trusted checkout changed during verification")
                if current["state"] == "paid_verified":
                    if current["payment_id"] != payment_id:
                        raise LiveOrderBlocked("Conflicting verified payment")
                    new = False
                elif current["state"] == "checkout_recorded":
                    db.execute(
                        "UPDATE food_live_order_ledger SET state='paid_verified',"
                        "payment_id=?,paid_at=? WHERE order_id=? AND "
                        "state='checkout_recorded'",
                        (payment_id, int(time.time()), order_id),
                    )
                    new = True
                else:
                    raise LiveOrderBlocked("Invalid payment transition")
                db.execute("COMMIT")
            except sqlite3.IntegrityError:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise LiveOrderBlocked("Payment already belongs to another order") from None
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"state": "paid_verified", "new_transition": new}
