"""Separate, private Sandbox journal for BUY-TO-ORDER dog food.

BIG PAW orders from the Kyushu supplier only after Square-verified payment,
receives stock at the Saitama store, inspects it and ships to the buyer.
The journal records *manual* steps only. It never contacts the supplier,
sends emails, ships items, creates refunds or uses production credentials.

There is deliberately NO stock-on-hand requirement before checkout.
A backorder/shortage is recorded for proactive contact and an optional
full refund; a fake refund cannot silently turn an order into refunded.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from urllib.request import urlopen

from .sandbox_connector import SandboxOrderStore
from .sandbox_notifications import (install_notification_tables, enqueue_notification_group, STAGE_DRAFTS)
from .sandbox_reconcile import (
    retrieve_sandbox_shipment_status,
    retrieve_verified_sandbox_payment,
    verify_current_sandbox_payment,
)

INITIAL = "awaiting_supplier_order"
STATES = frozenset((
    INITIAL, "supplier_ordered", "supplier_backorder",
    "received_at_shop", "shipped", "refund_review", "refunded",
))
TRANSITIONS = {
    INITIAL: frozenset(("supplier_ordered", "supplier_backorder", "refund_review")),
    "supplier_ordered": frozenset(("supplier_backorder", "received_at_shop", "refund_review")),
    "supplier_backorder": frozenset(("supplier_ordered", "refund_review")),
    "received_at_shop": frozenset(("shipped", "refund_review")),
    "shipped": frozenset(),
    "refund_review": frozenset(),
    "refunded": frozenset(),
}

class SandboxProcurementOps:
    def __init__(self, order_store: SandboxOrderStore):
        self.order_store = order_store
        with closing(self._open()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS food_procurement (
                    order_id TEXT PRIMARY KEY,
                    stage TEXT NOT NULL CHECK(stage IN (
                      'awaiting_supplier_order','supplier_ordered','supplier_backorder',
                      'received_at_shop','shipped','refund_review','refunded'
                    )),
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS food_procurement_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    recorded_at INTEGER NOT NULL
                );
            """)
            install_notification_tables(db)

    def _open(self):
        connection=sqlite3.connect(self.order_store.db_file, timeout=10, isolation_level=None)
        connection.row_factory=sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _paid(self, order_id: str) -> dict:
        verified=self.order_store.paid_order_snapshot(order_id)
        if not verified or not verified.get("square_payment_id") or not verified.get("cart"):
            raise ValueError("Square-verified paid order required")
        return verified

    def state(self, order_id: str) -> str:
        if self.order_store.status(order_id)!="paid":
            return "payment_not_verified"
        with closing(self._open()) as db:
            row=db.execute(
                "SELECT stage FROM food_procurement WHERE order_id=?",(order_id,)
            ).fetchone()
        return row["stage"] if row else INITIAL

    def events(self, order_id: str | None = None) -> list[dict]:
        with closing(self._open()) as db:
            if order_id is None:
                rows=db.execute(
                    "SELECT order_id,stage,recorded_at FROM food_procurement_events "
                    "ORDER BY id").fetchall()
            else:
                rows=db.execute(
                    "SELECT order_id,stage,recorded_at FROM food_procurement_events "
                    "WHERE order_id=? ORDER BY id",(order_id,)).fetchall()
        return [dict(row) for row in rows]

    def transition(self, order_id: str, next_stage: str, *,
                   token: str = "", opener=urlopen) -> str:
        """Manual record, NOT an actual order, arrival, dispatch or refund.

        Shipment requires independently confirmed shipping details in Square.
        Payment/refund finality cannot be entered through this method.
        """
        if next_stage not in STATES or next_stage == "refunded":
            raise ValueError("Unsupported procurement stage")
        paid=self._paid(order_id)
        if next_stage=="shipped":
            if not token:
                raise ValueError("Sandbox token required to verify shipment")
            verify_current_sandbox_payment(
                snapshot=paid, token=token, opener=opener,
            )
            result=retrieve_sandbox_shipment_status(
                paid["square_order_id"], token=token, opener=opener,
            )
            if (result.get("square_order_id")!=paid["square_order_id"] or
                    result.get("shipment_details_complete") is not True):
                raise ValueError("Square shipping recipient/address incomplete")
        with closing(self._open()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row=db.execute(
                    "SELECT stage FROM food_procurement WHERE order_id=?",(order_id,)
                ).fetchone()
                current=row["stage"] if row else INITIAL
                if current==next_stage:
                    db.execute("COMMIT")
                    return current  # retry never duplicates an event
                if next_stage not in TRANSITIONS[current]:
                    raise ValueError("Forbidden procurement transition")
                now=int(time.time())
                db.execute(
                    "INSERT INTO food_procurement(order_id,stage,updated_at) "
                    "VALUES (?,?,?) ON CONFLICT(order_id) DO UPDATE SET "
                    "stage=excluded.stage,updated_at=excluded.updated_at",
                    (order_id,next_stage,now),
                )
                db.execute(
                    "INSERT INTO food_procurement_events(order_id,stage,recorded_at) "
                    "VALUES (?,?,?)",(order_id,next_stage,now),
                )
                enqueue_notification_group(db,order_id,STAGE_DRAFTS.get(next_stage,()))
                db.execute("COMMIT")
                return next_stage
            except Exception:
                db.execute("ROLLBACK")
                raise

    def confirm_full_refund(self, order_id: str, *, token: str, opener=urlopen) -> str:
        """Read actual Square Sandbox Payment; no refund is initiated here."""
        paid=self._paid(order_id)
        current=retrieve_verified_sandbox_payment(
            paid["square_payment_id"],token=token,opener=opener,
        )
        money=current.get("amount_money",{})
        returned=current.get("refunded_money",{})
        if not (
            current.get("status")=="COMPLETED"
            and current.get("id")==paid["square_payment_id"]
            and current.get("order_id")==paid["square_order_id"]
            and current.get("location_id")==paid["square_location_id"]
            and isinstance(money,dict)
            and type(money.get("amount")) is int
            and money["amount"]==paid["amount_yen"]
            and money.get("currency")=="JPY"
            and isinstance(returned,dict)
            and type(returned.get("amount")) is int
            and returned["amount"]==paid["amount_yen"]
            and returned.get("currency")=="JPY"
        ):
            raise ValueError("Square has not confirmed a full refund")
        with closing(self._open()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row=db.execute(
                    "SELECT stage FROM food_procurement WHERE order_id=?",(order_id,)
                ).fetchone()
                stage=row["stage"] if row else INITIAL
                if stage=="refunded":
                    db.execute("COMMIT")
                    return "refunded"
                if stage!="refund_review":
                    raise ValueError("Refund must be under review; shipped orders not refundable here")
                now=int(time.time())
                db.execute(
                    "UPDATE food_procurement SET stage='refunded',updated_at=? WHERE order_id=?",
                    (now,order_id),
                )
                db.execute(
                    "INSERT INTO food_procurement_events(order_id,stage,recorded_at) "
                    "VALUES (?,'refunded',?)",(order_id,now),
                )
                enqueue_notification_group(db,order_id,STAGE_DRAFTS["refunded"])
                db.execute("COMMIT")
                return "refunded"
            except Exception:
                db.execute("ROLLBACK")
                raise
