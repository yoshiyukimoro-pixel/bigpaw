"""UNWIRED, PII-free live order-management read model (operator-side ONLY).

This is NOT a public route, not a live payment assertion, and not an email
or shipping API. Never expose its output to a shopper without an independent
owner-authentication/authorization layer. Views only a bounded, consistent,
read-only SQLite snapshot. No Square GET is performed when listing orders.

A durable paid_verified state means 'Square paid was verified in the past'.
The current refund/chargeback status is UNKNOWN unless checked AGAIN with
the independent Square live GET verifier during a later authorized action.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

from .live_order_ledger import LiveOrderLedger, LiveOrderBlocked

SKU = re.compile(r"^[AOZC][0-9]{2}$")


def read_order_management_snapshot(*, ledger: LiveOrderLedger, limit=100):
    """Return a bounded status ledger for a FUTURE authenticated admin UI.

    Does not mutate data, reveal recipients, send mail, create a Square link,
    or claim that a historical paid state reflects the current Square state.
    """
    if not isinstance(ledger, LiveOrderLedger):
        raise LiveOrderBlocked("Private live ledger is required")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise LiveOrderBlocked("Invalid private order list limit")
    # SQLite mode=ro makes it impossible for a read-only listing to create
    # an empty DB accidentally or write to the order journal.
    file_path = Path(ledger.db_file)
    if not file_path.is_file():
        return {"orders": [], "count": 0, "read_only": True}
    uri = "file:" + quote(str(file_path.resolve())) + "?mode=ro"
    with closing(sqlite3.connect(uri, timeout=5, uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        try:
            tables = {
                row["name"] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "food_live_order_ledger" not in tables:
                db.execute("COMMIT")
                return {"orders": [], "count": 0, "read_only": True}
            rows = db.execute(
                "SELECT order_id,cart_snapshot,amount_yen,state,created_at,"
                "paid_at FROM food_live_order_ledger "
                "ORDER BY created_at DESC,order_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            event_count = {}
            if "food_live_signed_payment_events" in tables and rows:
                ids = [row["order_id"] for row in rows]
                placeholders = ",".join("?" for _ in ids)
                for event in db.execute(
                    "SELECT order_id,COUNT(*) AS n "
                    "FROM food_live_signed_payment_events "
                    "WHERE order_id IN (" + placeholders + ") "
                    "GROUP BY order_id", ids,
                ).fetchall():
                    event_count[event["order_id"]] = event["n"]
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise

    entries = []
    for row in rows:
        if (not isinstance(row["order_id"], str)
                or not re.fullmatch(r"FOOD[0-9a-f]{32}", row["order_id"])
                or row["state"] not in ("checkout_recorded", "paid_verified")
                or type(row["amount_yen"]) is not int
                or not 1 <= row["amount_yen"] <= 2_000_000):
            raise LiveOrderBlocked("Corrupt private order record")
        try:
            lines = json.loads(row["cart_snapshot"])
            if not isinstance(lines, list) or not 1 <= len(lines) <= 35:
                raise ValueError()
            items, total, seen = [], 0, set()
            for line in lines:
                if not isinstance(line, dict) or set(line) != {
                    "sku", "qty", "unit_yen", "name", "size"
                }:
                    raise ValueError()
                sku = line["sku"]
                qty = line["qty"]
                unit = line["unit_yen"]
                if (not isinstance(sku, str) or not SKU.fullmatch(sku)
                        or sku in seen or type(qty) is not int
                        or not 1 <= qty <= 10
                        or type(unit) is not int or not 1 <= unit <= 2_000_000
                        or not isinstance(line["name"], str)
                        or not 1 <= len(line["name"]) <= 200
                        or not isinstance(line["size"], str)
                        or not 1 <= len(line["size"]) <= 60
                        or any(x in line["name"]+line["size"]
                               for x in ("\r", "\n"))):
                    raise ValueError()
                seen.add(sku)
                total += qty * unit
                items.append({
                    "sku": sku, "name": line["name"], "size": line["size"],
                    "qty": qty, "unit_yen": unit,
                })
            if total != row["amount_yen"]:
                raise ValueError()
        except (TypeError, ValueError, KeyError):
            raise LiveOrderBlocked("Corrupt private order items") from None
        historic = row["state"] == "paid_verified"
        entries.append({
            "order_id": row["order_id"],
            "items": items,
            "amount_yen": total,
            "created_at": row["created_at"],
            "paid_at": row["paid_at"] if historic else None,
            "payment_recorded_historically": historic,
            "current_payment_status": "not_checked",
            "manual_square_check_required": historic,
            "verified_signed_event_count": event_count.get(row["order_id"], 0),
        })
    return {"orders": entries, "count": len(entries), "read_only": True}
