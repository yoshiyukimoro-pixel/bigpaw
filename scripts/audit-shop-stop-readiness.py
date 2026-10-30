"""Read-only, aggregate emergency-stop exposure audit for BIG PAW food shop.

This NEVER contacts Square, invalidates a link, reads customer PII, or writes
a production SQLite database. Counts are local evidence only: independently
verify all live payment links in the Square dashboard during a real incident.
Run only with an explicitly supplied DB file (no implicit default path).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

_INTENT_COLUMNS = {"state", "square_link_id", "square_order_id", "order_id"}
_LEDGER_COLUMNS = {"state", "order_id"}


class AuditBlocked(ValueError):
    pass


def _columns(conn, table):
    return {row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")}


def inspect(database: str | Path) -> dict:
    path = Path(database)
    if not path.is_file() or path.is_symlink():
        raise AuditBlocked("Existing regular private database file required")
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=3) as db:
            db.execute("PRAGMA query_only=ON")
            if not _INTENT_COLUMNS.issubset(
                _columns(db, "food_live_checkout_intent")
            ):
                raise AuditBlocked("Checkout intent journal schema unavailable")
            if not _LEDGER_COLUMNS.issubset(
                _columns(db, "food_live_order_ledger")
            ):
                raise AuditBlocked("Private order ledger schema unavailable")
            row = db.execute("""
                SELECT
                  COALESCE(SUM(CASE WHEN i.state='planned' THEN 1 ELSE 0 END),0),
                  COALESCE(SUM(CASE WHEN i.state='attempt_unknown' THEN 1 ELSE 0 END),0),
                  COALESCE(SUM(CASE WHEN i.state='link_bound' THEN 1 ELSE 0 END),0),
                  COALESCE(SUM(CASE WHEN i.state='link_bound' AND
                               l.state='paid_verified' THEN 1 ELSE 0 END),0),
                  COALESCE(SUM(CASE WHEN i.state='link_bound' AND
                               (l.state IS NULL OR
                                l.state!='paid_verified') THEN 1 ELSE 0 END),0)
                FROM food_live_checkout_intent AS i
                LEFT JOIN food_live_order_ledger AS l
                  ON l.order_id=i.order_id
            """).fetchone()
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        raise AuditBlocked("Private order journal could not be read safely") from None

    planned, uncertain, bound, paid_bound, awaiting = (int(x) for x in row)
    return {
        "scope": "local_readonly_aggregate_only",
        "planned_no_link": planned,
        "attempt_unknown_requires_square_review": uncertain,
        "link_bound_total_requires_square_link_review": bound,
        "link_bound_payment_verified": paid_bound,
        "link_bound_not_payment_verified": awaiting,
        "needs_external_square_dashboard_review": (uncertain + bound) > 0,
        "existing_links_automatically_cancelled": False,
        "square_contacted": False,
        "database_mutated": False,
        "live_release_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True,
                        help="Explicit existing private SQLite database path")
    args = parser.parse_args(argv)
    try:
        result = inspect(args.db)
    except AuditBlocked:
        print("SHOP_STOP_AUDIT_BLOCKED: source missing or unsuitable")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
