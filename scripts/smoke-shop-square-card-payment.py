"""Retired Square Sandbox Payment Links direct-card probe (no network).

A Square-hosted Payment Link starts with a DRAFT Order. The supported
simulation is the official Sandbox Testing Panel, not Payments.CreatePayment
directly against the linked Order. Two 2026-10-31 attempts failed with
HTTP 400 BAD_REQUEST; no Payment was created by either attempt.

Standalone fake-card Payments API and hosted-panel tests remain separate
explicitly opted-in workflow jobs. This deprecated entry point never
contacts Square, regardless of environment or injected dependencies.
"""
from __future__ import annotations
import sys


def main(*, env=None, link_creator=None, payment_creator=None, payment_reader=None) -> int:
    """Always fail closed before generating a payment link or card charge."""
    print("SQUARE_LINKED_CARD_PROBE_DISABLED: Payment Links orders start as DRAFT; "
          "use the separately opted-in Square Sandbox Testing Panel. "
          "No Square request, charge, or customer-data operation was made.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
