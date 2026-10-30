"""Operator-only, isolated Sandbox journal for customer service case rehearsals.

Records a controlled issue category and workflow status against an already
verified paid Square Sandbox order. It NEVER contacts customers or suppliers,
starts a Square refund, creates a shipment, or stores free-form personal data.
No part of the production BIG PAW app imports this module.
"""
from __future__ import annotations

from contextlib import closing
import re
import sqlite3
import time

ORDER = re.compile(r"^FOOD[0-9a-f]{32}$")
CASE_TYPES = {
    "out_of_stock": "仕入先欠品の対応",
    "pre_ship_cancel": "発送前キャンセルの相談",
    "return_request": "返品の相談",
    "damaged_or_wrong": "不良品・破損・誤配送",
    "delivery_delay": "配送遅延の相談",
}
CASE_STATUSES = {
    "open": "対応待ち（テスト）",
    "awaiting_customer": "お客様への確認待ち（連絡はしていません）",
    "resolved": "対応完了（テスト記録）",
}
NEXT = {
    "none": frozenset(("open",)),
    "open": frozenset(("awaiting_customer", "resolved")),
    "awaiting_customer": frozenset(("open", "resolved")),
    "resolved": frozenset(),
}


class SandboxServiceCases:
    def __init__(self, store):
        self.store = store

    def _open(self):
        db = sqlite3.connect(self.store.db_file, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _install(db):
        db.executescript("""
            CREATE TABLE IF NOT EXISTS food_sandbox_service_cases (
                order_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(order_id,kind)
            );
            CREATE TABLE IF NOT EXISTS food_sandbox_service_case_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                recorded_at INTEGER NOT NULL
            );
        """)

    def snapshot(self, order_id: str) -> list[dict]:
        if not isinstance(order_id, str) or not ORDER.fullmatch(order_id):
            raise ValueError("Unsupported Sandbox order")
        with closing(self._open()) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_sandbox_service_cases'"
            ).fetchone()
            if not exists:
                return []
            rows = db.execute(
                "SELECT kind,status,created_at,updated_at "
                "FROM food_sandbox_service_cases WHERE order_id=? ORDER BY created_at,kind",
                (order_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def record(self, order_id: str, kind: str, expected: str, status: str) -> str:
        if (not isinstance(order_id, str) or not ORDER.fullmatch(order_id) or
            kind not in CASE_TYPES or expected not in NEXT or
            status not in CASE_STATUSES or status not in NEXT[expected]):
            raise ValueError("Invalid Sandbox case transition")
        # Paid is an immutable Square-verified order record; never mark
        # unverified pending checkouts as requests or allow fulfillment.
        verified = self.store.paid_order_snapshot(order_id)
        if not verified or not verified.get("square_payment_id"):
            raise ValueError("Square-verified paid test order required")

        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                current_row = db.execute(
                    "SELECT status FROM food_sandbox_service_cases "
                    "WHERE order_id=? AND kind=?", (order_id,kind)
                ).fetchone()
                current = current_row["status"] if current_row else "none"
                if current != expected:
                    raise ValueError("Stale Sandbox case form; reload")
                # Cross-check payment status again within the transaction.
                if not db.execute(
                    "SELECT 1 FROM orders WHERE order_id=? "
                    "AND state='paid' AND square_payment_id IS NOT NULL",
                    (order_id,)
                ).fetchone():
                    raise ValueError("Payment is not verified")
                now = int(time.time())
                if current == "none":
                    db.execute(
                        "INSERT INTO food_sandbox_service_cases "
                        "(order_id,kind,status,created_at,updated_at) "
                        "VALUES (?,?,?,?,?)", (order_id,kind,status,now,now)
                    )
                else:
                    db.execute(
                        "UPDATE food_sandbox_service_cases "
                        "SET status=?,updated_at=? WHERE order_id=? AND kind=?",
                        (status,now,order_id,kind)
                    )
                db.execute(
                    "INSERT INTO food_sandbox_service_case_events "
                    "(order_id,kind,status,recorded_at) VALUES (?,?,?,?)",
                    (order_id,kind,status,now)
                )
                db.execute("COMMIT")
                return status
            except Exception:
                db.execute("ROLLBACK")
                raise
