"""Aggregation of settled transactions into report rows, and CSV output."""

from __future__ import annotations

import csv
import logging
from decimal import Decimal
from pathlib import Path

from .dates import settlement_date
from .fx import convert
from .money import round_half_up

log = logging.getLogger(__name__)

REPORT_HEADER = ["merchant_id", "settlement_date", "currency", "gross_minor",
                 "refunds_minor", "fees_minor", "net_minor", "payment_count"]
REJECTS_HEADER = ["event_seq", "txn_id", "reason"]


def build(records, merchants, rates, month):
    """Aggregate records into ``{(merchant_id, date): totals}`` plus rejects."""
    rows, rejects = {}, []
    originals = {r["txn_id"]: r for r in records}
    for rec in records:
        key = rec["merchant_id"]
        merchant = merchants.get(key)
        if merchant is None:
            continue
        source = rec
        if rec["type"] == "refund":
            source = originals.get(rec["original_txn_id"])
            if source is None:
                continue
        day = settlement_date(source["occurred_at"], merchant["timezone"])
        if day.strftime("%Y-%m") != month:
            continue
        settled = convert(rec["amount"], rec["currency"],
                          merchant["settlement_currency"], rates, day)
        row = rows.setdefault((key, day), {"gross": 0, "refunds": 0, "fees": 0, "count": 0})
        if rec["type"] == "payment":
            row["gross"] += settled
            row["count"] += 1
        else:
            row["refunds"] += settled
    for (key, _day), row in rows.items():
        row["fees"] = round_half_up(Decimal(row["gross"]) * int(merchants[key]["fee_bps"]) / 10000)
    return rows, rejects


def write_report(path: Path, rows: dict, merchants: dict) -> int:
    """Write report.csv and return the number of data rows written."""
    written = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow(REPORT_HEADER)
        for (key, day) in sorted(rows):
            row = rows[(key, day)]
            if row["count"] == 0:
                continue
            net = row["gross"] - row["refunds"] - row["fees"]
            out.writerow([key, day.isoformat(), merchants[key]["settlement_currency"],
                          row["gross"], row["refunds"], row["fees"], net, row["count"]])
            written += 1
    return written


def write_rejects(path: Path, rejects: list[tuple[int, str, str]]) -> int:
    """Write rejects.csv and return the number of data rows written."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow(REJECTS_HEADER)
        for seq, txn, reason in sorted(rejects, key=lambda r: r[0]):
            out.writerow([seq, txn, reason])
    return len(rejects)


def totals_by_merchant(rows: dict) -> dict[str, dict[str, int]]:
    """Roll report rows up to one total per merchant, for the run summary."""
    out: dict[str, dict[str, int]] = {}
    for (key, _day), row in rows.items():
        acc = out.setdefault(key, {"gross": 0, "refunds": 0, "fees": 0, "count": 0})
        for field in acc:
            acc[field] += row[field]
    return out
