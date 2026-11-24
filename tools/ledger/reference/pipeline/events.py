"""Collapsing of processor events into transactions.

The processor emits one event per state change. Several events can therefore
describe the same transaction; this module reduces them to one record each and
keeps the records that should be settled.
"""

from __future__ import annotations

import logging
from collections import Counter

log = logging.getLogger(__name__)

KNOWN_TYPES = frozenset({"payment", "refund"})
KNOWN_STATUSES = frozenset({"pending", "settled", "failed", "reversed"})


def effective_records(events):
    """Return one record per txn_id, chosen by event sequence number."""
    by_txn = {}
    for ev in events:
        cur = by_txn.get(ev["txn_id"])
        if cur is None or int(ev["event_seq"]) > int(cur["event_seq"]):
            by_txn[ev["txn_id"]] = ev
    return list(by_txn.values())


def eligible(records):
    """Keep the records that take part in settlement."""
    return [r for r in records if r["status"] == "settled"]


def status_counts(records: list[dict]) -> Counter:
    """Count records by status, for the run summary."""
    return Counter(r["status"] for r in records)


def warn_on_unexpected_values(events: list[dict]) -> None:
    """Log, without failing, any type or status value we do not recognise."""
    odd_types = {e["type"] for e in events} - KNOWN_TYPES
    odd_status = {e["status"] for e in events} - KNOWN_STATUSES
    if odd_types:
        log.warning("unrecognised event type(s): %s", ", ".join(sorted(odd_types)))
    if odd_status:
        log.warning("unrecognised status value(s): %s", ", ".join(sorted(odd_status)))
