"""Private local-only operator console for BIG PAW *Sandbox* food orders.

No HTTP listener, production backend integration, email send, label creation,
actual shipment, refund initiation, or customer address display/storage.
All mutations require --confirm-sandbox and an existing SQLite test journal.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore, SquareSandboxError
from shop_payments.sandbox_fulfillment import SandboxFulfillmentOps

ORDER_ID = re.compile(r"^FOOD[0-9a-f]{32}$")


def _validated_db(value: str) -> Path:
    raw=Path(value).expanduser()
    if raw.is_symlink():
        raise ValueError("Refusing linked database file")
    full=raw.resolve(strict=True)
    if not full.is_file() or full.suffix not in (".db",".sqlite",".sqlite3"):
        raise ValueError("Expected existing isolated Sandbox SQLite file")
    # Do not accidentally target a production mounted database.
    forbidden={"/app/data/", "/app/production/", "/var/lib/postgresql/"}
    if any(str(full).startswith(part) for part in forbidden):
        raise ValueError("Production database paths are not accepted")
    return full


def _rows(db:Path) -> list[dict]:
    catalog=load_sale_catalog()
    connection=sqlite3.connect(f"file:{db}?mode=ro",uri=True,timeout=5)
    connection.row_factory=sqlite3.Row
    try:
        # Ops() creates fulfillment table in existing test journal. Safe.
        rows=connection.execute("""
            SELECT o.order_id,o.amount_yen,o.state AS payment_state,
                   o.created_at,o.paid_at,
                   COALESCE(f.state,'not_assessed') AS fulfillment_state,
                   COALESCE(f.stock_reserved,0) AS inventory_assigned
            FROM orders o LEFT JOIN food_fulfillment f ON f.order_id=o.order_id
            ORDER BY o.created_at DESC,o.order_id DESC
        """).fetchall()
        out=[]
        for r in rows:
            item_rows=connection.execute(
                "SELECT sku,quantity FROM order_items WHERE order_id=? ORDER BY sku",
                (r["order_id"],)).fetchall()
            items=[]
            for item in item_rows:
                sku=item["sku"]
                if sku not in catalog:raise ValueError("Unknown SKU stored in order")
                items.append({
                    "sku":sku,
                    "product":catalog[sku].name,
                    "size":catalog[sku].size,
                    "quantity":item["quantity"],
                })
            out.append({**dict(r),"shipping_yen":0,"currency":"JPY","items":items})
        return out
    finally:
        connection.close()


def _queue(db:Path) -> list[dict]:
    connection=sqlite3.connect(f"file:{db}?mode=ro",uri=True,timeout=5)
    connection.row_factory=sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(
            "SELECT order_id,event_type,created_at FROM food_operator_outbox "
            "ORDER BY created_at,order_id,event_type")]
    finally:
        connection.close()


def execute(args,*,env=None,opener=None):
    env=os.environ if env is None else env
    db=_validated_db(args.db)
    ops=SandboxFulfillmentOps(SandboxOrderStore(db))
    if args.action=="list":
        return {"sandbox":True,"orders":_rows(db)}
    if args.action=="events":
        return {"sandbox":True,"events":_queue(db)}
    if args.action=="stock":
        return {"sandbox":True,"sku":args.sku,"available":ops.stock(args.sku)}

    if args.confirm_sandbox is not True:
        raise ValueError("Explicit --confirm-sandbox required for any changes")
    if args.action=="stock-set":
        ops.set_stock(args.sku,args.qty)
        return {"sandbox":True,"action":"stock-set",
                "sku":args.sku,"available":ops.stock(args.sku)}
    if not ORDER_ID.fullmatch(args.order_id):
        raise ValueError("Invalid internal Sandbox order ID")
    if args.action=="check-paid":
        # Re-read only local verified journal. Does not trust redirect parameters.
        return {"sandbox":True,"order_id":args.order_id,
                "state":ops.state(args.order_id)}
    if args.action in ("assess","verify-refund"):
        token=str(env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","")).strip()
        if not token:
            raise ValueError("Sandbox Square test credential missing")
        kwargs={"token":token}
        if opener is not None:kwargs["opener"]=opener
        state=(ops.assess_paid_order(args.order_id,**kwargs)
               if args.action=="assess"
               else ops.reconcile_full_refund(args.order_id,**kwargs))
    elif args.action=="record-shipped":
        # ONLY updates a local journal, does not book/send any shipment.
        state=ops.mark_shipped(args.order_id)
    elif args.action=="refund-review":
        # Requires separately authorized real refund elsewhere. Here = local hold.
        state=ops.request_refund_review(args.order_id)
    else:
        raise ValueError("Unsupported operator action")
    return {"sandbox":True,"order_id":args.order_id,"action":args.action,
            "fulfillment_state":state,"shipping_executed":False,
            "refund_initiated":False}


def parser():
    p=argparse.ArgumentParser(description="Private BIG PAW Sandbox order journal CLI")
    p.add_argument("--db",required=True,help="Existing isolated Sandbox .sqlite3 journal")
    p.add_argument("--confirm-sandbox",action="store_true",help="Required for any changes")
    cmds=p.add_subparsers(dest="action",required=True)
    cmds.add_parser("list")
    cmds.add_parser("events")
    stock=cmds.add_parser("stock");stock.add_argument("sku")
    stock_set=cmds.add_parser("stock-set");stock_set.add_argument("sku")
    stock_set.add_argument("qty",type=int)
    for action in ("check-paid","assess","record-shipped","refund-review","verify-refund"):
        sub=cmds.add_parser(action);sub.add_argument("order_id")
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        value=execute(args)
    except (ValueError,sqlite3.Error,SquareSandboxError,OSError) as e:
        # Never print raw API/PII details or authorization secrets.
        print("SANDBOX_OPERATOR_ERROR: invalid state, credentials or test data",file=sys.stderr)
        return 1
    print(json.dumps(value,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
