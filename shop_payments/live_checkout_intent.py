"""UNWIRED future live food-shop checkout preparation and recovery journal.

No HTTP routes import this module; it never sends a POST to Square, charges,
emails, refunds or ships. A future approved controller must enforce login/
public checkout controls, CSRF/origin or equivalent, rate limiting, final
legal disclosures, secret handling and the launch gate before calling it.

IMPORTANT: Persist an immutable cart and exact Square create-link payload
BEFORE any external API call. The 'begin_attempt' method marks an attempt
UNKNOWN before returning the one permitted POST payload, so a timeout/crash
cannot cause an automatic second call with a different order or key.
An unknown outcome requires manual Square lookup/reconciliation, never
auto-recreating a charge. Square API's idempotency key alone is not an
unbounded lifetime deduplication mechanism.

This is a preparation/verification library, NOT an enabled checkout feature.
"""
from __future__ import annotations

from contextlib import closing
import json
import re
import sqlite3
import time
from urllib.parse import urlsplit

from .live_order_ledger import LiveOrderBlocked, LiveOrderLedger, _ORDER, _valid_id
from .square_checkout import SaleItem, build_square_link_payload
from .square_live_readonly import _square_get

_LINK_ID = re.compile(r"^[A-Za-z0-9_-]{8,192}$")


def _safe_link(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        return False
    try:
        u = urlsplit(value)
        return bool(
            u.scheme == "https"
            and u.hostname in {"square.link", "checkout.square.site"}
            and u.username is None and u.password is None
            and u.port in (None, 443)
            and not u.query and not u.fragment
            and u.path.startswith("/") and len(u.path) > 2
            and not any(x in u.path for x in ("\\", "//"))
        )
    except ValueError:
        return False


def _payload_from_lines(lines, *, location_id, order_id):
    """Rebuild exactly the original server-priced request, not today's prices."""
    if not isinstance(lines, list) or not 1 <= len(lines) <= 35:
        raise LiveOrderBlocked("Invalid saved checkout lines")
    catalog, cart = {}, {}
    for line in lines:
        if not isinstance(line, dict) or set(line) != {
            "sku", "qty", "unit_yen", "name", "size"
        }:
            raise LiveOrderBlocked("Malformed trusted checkout line")
        sku, qty, unit = line["sku"], line["qty"], line["unit_yen"]
        name, size = line["name"], line["size"]
        if (not isinstance(sku, str) or not re.fullmatch(r"[AOZC][0-9]{2}", sku)
                or sku in catalog or type(qty) is not int or not 1 <= qty <= 10
                or type(unit) is not int or not 1 <= unit <= 2_000_000
                or not isinstance(name, str) or not 1 <= len(name) <= 200
                or not isinstance(size, str) or not 1 <= len(size) <= 60
                or any(s in name + size for s in ("\r", "\n"))):
            raise LiveOrderBlocked("Saved checkout details invalid")
        catalog[sku] = SaleItem(product_id=sku, name=name, size=size,
                                sale_price_yen=unit)
        cart[sku] = qty
    try:
        return build_square_link_payload(
            cart=cart, verified_prices=catalog, shipping_yen=0,
            square_location_id=location_id, local_order_id=order_id,
            shipping_confirmed=True,
        )
    except (ValueError, TypeError, KeyError):
        raise LiveOrderBlocked("Square checkout payload cannot be restored") from None


class LiveCheckoutIntent:
    """PII-free SQLite intent; must share path with LiveOrderLedger."""

    def __init__(self, ledger: LiveOrderLedger):
        if not isinstance(ledger, LiveOrderLedger):
            raise LiveOrderBlocked("Existing private order ledger required")
        self.ledger = ledger

    def _open(self):
        return self.ledger._open()

    @staticmethod
    def _install(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS food_live_checkout_intent (
                order_id TEXT PRIMARY KEY,
                location_id TEXT NOT NULL,
                cart_json TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                request_json TEXT NOT NULL,
                amount_yen INTEGER NOT NULL CHECK(amount_yen > 0),
                state TEXT NOT NULL CHECK(state IN
                    ('planned','attempt_unknown','link_bound')),
                square_order_id TEXT UNIQUE,
                square_link_id TEXT UNIQUE,
                square_url TEXT,
                created_at INTEGER NOT NULL,
                attempt_at INTEGER,
                bound_at INTEGER
            )
        """)

    @staticmethod
    def _validate(order_id, location_id):
        if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
            raise LiveOrderBlocked("Server-created order ID required")
        if not _valid_id(location_id):
            raise LiveOrderBlocked("Square merchant location is invalid")

    def prepare(self, *, order_id, location_id, cart):
        """Persist one immutable approved-price request before external POST.

        Call ONLY after the future public server verifies the final legal
        disclosure and binds the customer checkout attempt to a session.
        An identical retry never resets a claimed/unknown intent.
        """
        self._validate(order_id, location_id)
        snapshot_json, total = self.ledger._snapshot(cart)
        lines = json.loads(snapshot_json)
        payload, rebuilt = _payload_from_lines(
            lines, location_id=location_id, order_id=order_id
        )
        if rebuilt != total:
            raise LiveOrderBlocked("Trusted cart sum differs from Square payload")
        cart_json = json.dumps(cart, sort_keys=True, separators=(",", ":"))
        request_json = json.dumps(payload, sort_keys=True,
                                  separators=(",", ":"), ensure_ascii=False)
        expected = (location_id, cart_json, snapshot_json, request_json, total)
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    "SELECT location_id,cart_json,snapshot_json,request_json,"
                    "amount_yen,state FROM food_live_checkout_intent "
                    "WHERE order_id=?", (order_id,)
                ).fetchone()
                if existing:
                    actual = tuple(existing[k] for k in (
                        "location_id", "cart_json", "snapshot_json",
                        "request_json", "amount_yen"
                    ))
                    if actual != expected:
                        raise LiveOrderBlocked("Checkout attempt cannot change")
                    state = existing["state"]
                    created = False
                else:
                    db.execute(
                        "INSERT INTO food_live_checkout_intent "
                        "(order_id,location_id,cart_json,snapshot_json,"
                        "request_json,amount_yen,state,created_at) "
                        "VALUES (?,?,?,?,?,?,'planned',?)",
                        (order_id, *expected, int(time.time())),
                    )
                    state = "planned"
                    created = True
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"state": state, "new_plan": created, "amount_yen": total}

    @staticmethod
    def _get(db, order_id):
        row = db.execute(
            "SELECT * FROM food_live_checkout_intent WHERE order_id=?",
            (order_id,),
        ).fetchone()
        if row is None:
            raise LiveOrderBlocked("No precommitted checkout intent")
        return row

    def begin_attempt(self, *, order_id):
        """One atomic planned->unknown transition BEFORE external Square call.

        Return server-only payload. Never give it to a browser or automatically
        reissue after an API timeout, worker crash, or uncertain provider result.
        """
        if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
            raise LiveOrderBlocked("Invalid order reference")
        with closing(self._open()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                if db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='food_live_checkout_intent'"
                ).fetchone() is None:
                    raise LiveOrderBlocked("No prepared order")
                row = self._get(db, order_id)
                if row["state"] != "planned":
                    raise LiveOrderBlocked("Square checkout might already exist; audit first")
                payload, total = _payload_from_lines(
                    json.loads(row["snapshot_json"]),
                    location_id=row["location_id"], order_id=order_id
                )
                restored = json.dumps(payload, sort_keys=True,
                                      separators=(",", ":"), ensure_ascii=False)
                if restored != row["request_json"] or total != row["amount_yen"]:
                    raise LiveOrderBlocked("Saved Square payload integrity failure")
                db.execute(
                    "UPDATE food_live_checkout_intent SET state='attempt_unknown',"
                    "attempt_at=? WHERE order_id=? AND state='planned'",
                    (int(time.time()), order_id),
                )
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"server_only_payload": payload, "state": "attempt_unknown"}

    def bind_square_result(self, *, order_id, link, api_key, opener=None):
        """Manual/controlled reconciliation of ONE previous Square response.

        Requires an independent read-only Square Production Order GET for
        currency, location and amount, then registers the existing journal.
        If code, storage or Square fails, DO NOT create a new link automatically.
        """
        if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
            raise LiveOrderBlocked("Invalid order reference")
        if not isinstance(link, dict):
            raise LiveOrderBlocked("Malformed Square link response")
        sid, lid, url = link.get("order_id"), link.get("id"), link.get("url")
        if (not _valid_id(sid) or not isinstance(lid, str)
                or not _LINK_ID.fullmatch(lid) or not _safe_link(url)):
            raise LiveOrderBlocked("Untrusted Square payment-link identity or URL")
        if not isinstance(api_key, str) or not api_key.strip():
            raise LiveOrderBlocked("Square GET credential required")

        with closing(self._open()) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_live_checkout_intent'"
            ).fetchone()
            if exists is None:
                raise LiveOrderBlocked("No prepared order")
            row = self._get(db, order_id)
            if row["state"] not in ("attempt_unknown", "link_bound"):
                raise LiveOrderBlocked("Checkout was never issued")
            if row["state"] == "link_bound":
                if any((row["square_order_id"] != sid,
                        row["square_link_id"] != lid,
                        row["square_url"] != url)):
                    raise LiveOrderBlocked("Bound Square link identity changed")
                return {"state": "link_bound", "new_binding": False}
            location, amount = row["location_id"], row["amount_yen"]
            cart = json.loads(row["cart_json"])
            # Payment link binding must not silently reprice after the attempt.
            snapshot = row["snapshot_json"]

        opts = {"api_key": api_key}
        if opener is not None:
            opts["opener"] = opener
        evidence = _square_get("orders", sid, **opts)
        order = evidence.get("order")
        money = order.get("total_money") if isinstance(order, dict) else None
        if (not isinstance(order, dict) or order.get("id") != sid
                or order.get("location_id") != location
                or order.get("state") not in ("OPEN", "COMPLETED")
                or not isinstance(money, dict)
                or money.get("currency") != "JPY"
                or type(money.get("amount")) is not int
                or money["amount"] != amount):
            raise LiveOrderBlocked("Square Order mismatch; manual reconciliation required")
        current_snapshot, current_amount = self.ledger._snapshot(cart)
        if current_snapshot != snapshot or current_amount != amount:
            raise LiveOrderBlocked(
                "Catalog changed after link attempt; manual reconciliation required"
            )
        # Legacy LiveOrderLedger writes to the same DB in its own transaction.
        # A crash between these two commits is recoverable by calling THIS
        # method with the SAME Square IDs, never by issuing another link.
        self.ledger.register_checkout(
            order_id=order_id, square_order_id=sid,
            location_id=location, cart=cart
        )
        with closing(self._open()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                current = self._get(db, order_id)
                if (current["location_id"] != location
                        or current["amount_yen"] != amount
                        or current["cart_json"] != row["cart_json"]
                        or current["snapshot_json"] != snapshot):
                    raise LiveOrderBlocked("Checkout changed during Square binding")
                if current["state"] == "link_bound":
                    if (current["square_order_id"], current["square_link_id"],
                            current["square_url"]) != (sid, lid, url):
                        raise LiveOrderBlocked("Different link already bound")
                    changed = False
                elif current["state"] == "attempt_unknown":
                    db.execute(
                        "UPDATE food_live_checkout_intent "
                        "SET state='link_bound',square_order_id=?,"
                        "square_link_id=?,square_url=?,bound_at=? "
                        "WHERE order_id=? AND state='attempt_unknown'",
                        (sid, lid, url, int(time.time()), order_id),
                    )
                    changed = True
                else:
                    raise LiveOrderBlocked("Unexpected checkout state")
                db.execute("COMMIT")
            except sqlite3.IntegrityError:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise LiveOrderBlocked("Square link already used") from None
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"state": "link_bound", "new_binding": changed}

    def status(self, order_id):
        """Private status only; intentionally no link URL or recipient."""
        if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
            raise LiveOrderBlocked("Invalid order reference")
        with closing(self._open()) as db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_live_checkout_intent'"
            ).fetchone() is None:
                return {"state": "not_found"}
            row = db.execute(
                "SELECT state,amount_yen FROM food_live_checkout_intent "
                "WHERE order_id=?", (order_id,)
            ).fetchone()
        return dict(row) if row else {"state": "not_found"}
