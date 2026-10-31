"""Approved BIG PAW retail pricebook (Sandbox only).

MSRP is the tax-inclusive *selling price* approved by the merchant.
No procurement prices are part of this module. Shipping is included,
and never added at checkout. No actual orders or Square calls here.
"""
from __future__ import annotations

import json
from pathlib import Path

from .square_checkout import SaleItem, build_square_link_payload

PRICEBOOK_FILE = Path(__file__).with_name("retail_pricebook.json")


def load_sale_catalog(path: Path = PRICEBOOK_FILE) -> dict[str, SaleItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not (data.get("currency") == "JPY"
            and data.get("tax_included") is True
            and data.get("shipping_included") is True
            and data.get("shipping_yen") == 0):
        raise ValueError("Retail pricebook must be JPY, tax and shipping included")
    rows = data.get("products")
    if not isinstance(rows, list) or len(rows) != 35:
        raise ValueError("Expected exactly 35 approved sale products")
    catalog: dict[str, SaleItem] = {}
    for row in rows:
        pid = row["id"]
        if pid in catalog:
            raise ValueError("Duplicate sale product ID")
        if not isinstance(row.get("sale_price_yen"), int) or isinstance(row.get("sale_price_yen"), bool):
            raise ValueError("Invalid retail price")
        catalog[pid] = SaleItem(
            product_id=pid, name=row["name"], size=row["size"], sale_price_yen=row["sale_price_yen"]
        )
    return catalog


def build_shipping_included_square_order(
    *, cart: dict[str, int], square_location_id: str, local_order_id: str
) -> tuple[dict, int]:
    """Only accept product IDs/quantities, never a browser-supplied price.

    Caller must have validated/persisted this exact cart and its selling price
    snapshot; a future public checkout endpoint must enforce request limits.
    """
    return build_square_link_payload(
        cart=cart,
        verified_prices=load_sale_catalog(),
        shipping_yen=0,
        square_location_id=square_location_id,
        local_order_id=local_order_id,
        shipping_confirmed=True,
    )
