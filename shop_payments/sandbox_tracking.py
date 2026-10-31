"""Sandbox-only manual carrier and tracking reference journal.

This module NEVER books shipping, contacts carriers, sends customer emails,
or performs Square actions. An operator may record a reference only after a
Square-verified Sandbox payment and the 'shipped' test stage.
"""
from __future__ import annotations

from contextlib import closing
import re
import sqlite3
import time

ORDER = re.compile(r"^FOOD[0-9a-f]{32}$")
TRACKING = re.compile(r"^[A-Za-z0-9-]{8,35}$")
CARRIERS = {
    "yamato": "ヤマト運輸",
    "sagawa": "佐川急便",
    "japan_post": "日本郵便",
}


class SandboxTrackingJournal:
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
            CREATE TABLE IF NOT EXISTS food_sandbox_tracking (
                order_id TEXT PRIMARY KEY,
                carrier_code TEXT NOT NULL,
                tracking_number TEXT NOT NULL,
                recorded_at INTEGER NOT NULL
            );
        """)

    def read(self, order_id: str):
        if not isinstance(order_id, str) or not ORDER.fullmatch(order_id):
            raise ValueError("Invalid Sandbox order ID")
        with closing(self._open()) as db:
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='food_sandbox_tracking'"
            ).fetchone()
            if not table:
                return None
            row = db.execute(
                "SELECT carrier_code, tracking_number, recorded_at "
                "FROM food_sandbox_tracking WHERE order_id=?", (order_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "carrier_code": row["carrier_code"],
            "carrier_label": CARRIERS.get(row["carrier_code"], "配送会社未確認"),
            "tracking_number": row["tracking_number"],
            "recorded_at": row["recorded_at"],
        }

    def record_once(self, order_id: str, carrier_code: str, tracking_number: str):
        if not isinstance(order_id, str) or not ORDER.fullmatch(order_id):
            raise ValueError("Invalid Sandbox order ID")
        if carrier_code not in CARRIERS:
            raise ValueError("Unsupported carrier")
        if not isinstance(tracking_number, str) or not TRACKING.fullmatch(tracking_number):
            raise ValueError("Invalid tracking reference")
        # A lowercase conversion would alter case-sensitive references.
        # Keep the exact original and explicitly forbid leading/trailing hyphens.
        if tracking_number.startswith("-") or tracking_number.endswith("-"):
            raise ValueError("Invalid tracking reference")
        # Don't use a state flag as proof that a live shipment happened.
        if not self.store.paid_order_snapshot(order_id):
            raise ValueError("Verified Square Sandbox payment required")
        from .sandbox_procurement import SandboxProcurementOps
        ops = SandboxProcurementOps(self.store)
        if ops.state(order_id) != "shipped":
            raise ValueError("Shipped Sandbox stage required")
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                state = db.execute(
                    "SELECT p.stage FROM orders o JOIN food_procurement p "
                    "ON o.order_id=p.order_id "
                    "WHERE o.order_id=? AND o.state='paid'", (order_id,)
                ).fetchone()
                if not state or state["stage"] != "shipped":
                    raise ValueError("Paid shipped Sandbox order required")
                existing = db.execute(
                    "SELECT carrier_code, tracking_number FROM food_sandbox_tracking "
                    "WHERE order_id=?", (order_id,)
                ).fetchone()
                if existing:
                    if existing["carrier_code"] != carrier_code or existing["tracking_number"] != tracking_number:
                        raise ValueError("Tracking already recorded; no silent overwrite")
                    db.execute("COMMIT")
                    return False  # idempotent retry, not a second record
                db.execute(
                    "INSERT INTO food_sandbox_tracking "
                    "(order_id,carrier_code,tracking_number,recorded_at) "
                    "VALUES (?,?,?,?)",
                    (order_id, carrier_code, tracking_number, int(time.time()))
                )
                db.execute("COMMIT")
                return True
            except Exception:
                db.execute("ROLLBACK")
                raise
