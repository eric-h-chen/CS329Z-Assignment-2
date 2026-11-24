"""Merchant directory lookups."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def canonical_id(raw):
    """Normalise a merchant id as received from the processor."""
    return raw.strip(" \t\r\n\f\v").upper()


def merchant_table(rows: list[dict]) -> dict[str, dict]:
    """Index the merchant directory by merchant_id.

    The directory is maintained by hand, so duplicate ids are reported. The
    last row for an id wins.
    """
    table: dict[str, dict] = {}
    for row in rows:
        mid = row["merchant_id"]
        if mid in table:
            log.warning("duplicate merchant_id %s in merchant directory", mid)
        table[mid] = row
    return table


def describe(merchant: dict) -> str:
    """Short human-readable label used in log lines."""
    return f"{merchant['merchant_id']} ({merchant['settlement_currency']}, {merchant['timezone']})"
