"""Hand-specified probe inputs, one per SPEC.md rule group.

Writes tools/ledger/data/probes/Pnn/{month.txt,input/*.csv}. Expected outputs
are produced later by build_tasks.py from the reference pipeline.
Run: python gen_probes.py
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

from gen_data import write_merchants

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "probes"

EVENT_COLS = ["event_seq", "txn_id", "type", "merchant_id", "amount", "currency",
              "occurred_at", "status", "original_txn_id", "memo"]
IRIS = ("MRC-IRIS09", "Iris Florist", "America/Chicago", "USD", 125)


def ev(seq, txn, kind, mid, amount, ccy, at, status="settled", original="", memo=""):
    return [seq, txn, kind, mid, amount, ccy, at, status, original, memo]


PROBES = {
    "P01": dict(month="2026-03", bom=True, events=[
        ev(101, "T-P01-1", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-10T18:00:00Z",
           memo="Invoice 42, March"),
        ev(102, "T-P01-2", "payment", "MRC-ACME01", "20.00", "USD", "2026-03-10T19:00:00Z",
           memo='Line one\nHe said "fine"'),
        ev(103, "T-P01-3", "payment", "MRC-ACME01", "30.00", "USD", "2026-03-11T18:00:00Z",
           memo="plain note"),
    ]),
    "P02": dict(month="2026-03", events=[
        ev(201, "T-P02-1", "payment", "mrc-acme01", "10.00", "USD", "2026-03-10T18:00:00Z"),
        ev(202, "T-P02-2", "payment", " MRC-BOLT02 ", "20.00", "USD", "2026-03-10T18:00:00Z"),
        ev(203, "T-P02-3", "payment", "\tMRC-CEDR03", "10.00", "USD", "2026-03-11T20:00:00Z"),
        ev(220, "T-P02-4", "payment", "MRC-GHOST99", "15.00", "USD", "2026-03-12T18:00:00Z"),
        ev(210, "T-P02-5", "refund", "MRC-ZETA00", "5.00", "USD", "2026-04-01T12:00:00Z",
           original="T-PRIOR-00017"),
        ev(230, "T-P02-6", "payment", "MRC-GHOST99", "9.00", "USD", "2026-03-12T19:00:00Z",
           status="pending"),
        ev(204, "T-P02-7", "payment", "MRC-ACME01\u00a0", "10.00", "USD", "2026-03-11T18:00:00Z"),
    ]),
    "P03": dict(month="2026-03", events=[
        ev(102, "T-P03-1", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-10T18:00:00Z"),
        ev(1001, "T-P03-1", "payment", "MRC-ACME01", "30.00", "USD", "2026-03-10T18:00:00Z"),
        ev(98, "T-P03-1", "payment", "MRC-ACME01", "20.00", "USD", "2026-03-10T18:00:00Z"),
    ]),
    "P04": dict(month="2026-03", events=[
        ev(401, "T-P04-1", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-10T18:00:00Z"),
        ev(402, "T-P04-1", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-10T18:00:00Z",
           status="reversed"),
        ev(403, "T-P04-2", "payment", "MRC-ACME01", "40.00", "USD", "2026-03-10T19:00:00Z",
           status="pending"),
        ev(404, "T-P04-2", "payment", "MRC-ACME01", "40.00", "USD", "2026-03-10T19:00:00Z",
           status="failed"),
        ev(405, "T-P04-3", "payment", "MRC-ACME01", "20.00", "USD", "2026-03-11T18:00:00Z"),
        ev(406, "T-P04-3", "payment", "MRC-ACME01", "20.00", "USD", "2026-03-11T18:00:00Z",
           status="reversed"),
        ev(407, "T-P04-3", "payment", "MRC-ACME01", "20.00", "USD", "2026-03-11T18:00:00Z"),
        ev(408, "T-P04-4", "payment", "MRC-ACME01", "30.00", "USD", "2026-03-10T20:00:00Z"),
        ev(409, "T-P04-5", "payment", "MRC-ACME01", "50.00", "USD", "2026-03-12T18:00:00Z"),
        ev(410, "T-P04-5", "payment", "MRC-ACME01", "50.00", "USD", "2026-03-12T18:00:00Z",
           status="pending"),
    ]),
    "P05": dict(month="2026-11", events=[
        ev(501, "T-P05-1", "payment", "MRC-ACME01", "10.00", "USD", "2026-11-01T04:30:00Z"),
        ev(502, "T-P05-2", "payment", "MRC-ACME01", "20.00", "USD", "2026-11-01T05:30:00Z"),
        ev(503, "T-P05-3", "payment", "MRC-ACME01", "30.00", "USD", "2026-12-01T05:30:00Z"),
        ev(504, "T-P05-4", "payment", "MRC-ACME01", "40.00", "USD", "2026-12-01T06:30:00Z"),
        ev(505, "T-P05-5", "payment", "MRC-HANA08", "20.00", "USD", "2026-10-31T15:30:00Z"),
    ]),
    "P06": dict(month="2026-03", events=[
        ev(601, "T-P06-1", "payment", "MRC-FUJI06", "1200", "JPY", "2026-03-10T03:00:00Z"),
        ev(602, "T-P06-2", "payment", "MRC-GULF07", "1.500", "KWD", "2026-03-10T09:00:00Z"),
    ]),
    "P07": dict(month="2026-03", events=[
        ev(701, "T-P07-1", "payment", "MRC-ACME01", "0.29", "USD", "2026-03-10T18:00:00Z"),
        ev(702, "T-P07-2", "payment", "MRC-ACME01", "19.99", "USD", "2026-03-11T18:00:00Z"),
    ]),
    "P08": dict(month="2026-03", rates=[
        ("2026-03-12", "EUR", "USD", "1.080000"),
        ("2026-03-13", "EUR", "USD", "1.090000"),
        ("2026-03-16", "EUR", "USD", "1.100000"),
        ("2026-03-17", "EUR", "USD", "1.110000"),
        ("2026-03-13", "USD", "EUR", "0.917000"),
        ("2026-03-16", "USD", "EUR", "0.909000"),
        ("2026-03-02", "JPY", "USD", "0.006500"),
        ("2026-03-16", "USD", "JPY", "148.000000"),
    ], events=[
        ev(801, "T-P08-1", "payment", "MRC-ACME01", "10.00", "EUR", "2026-03-14T18:00:00Z"),
        ev(802, "T-P08-2", "payment", "MRC-ACME01", "20.00", "EUR", "2026-03-15T18:00:00Z"),
        ev(803, "T-P08-3", "payment", "MRC-ACME01", "10.00", "EUR", "2026-03-12T18:00:00Z"),
        ev(804, "T-P08-4", "payment", "MRC-ACME01", "1000", "JPY", "2026-03-16T18:00:00Z"),
        ev(805, "T-P08-5", "payment", "MRC-HANA08", "10.00", "EUR", "2026-03-16T16:00:00Z"),
    ]),
    "P09": dict(month="2026-03", extra_merchants=[IRIS], rates=[
        ("2026-03-09", "EUR", "USD", "1.079000"),
        ("2026-03-10", "EUR", "USD", "1.082000"),
        ("2026-03-11", "EUR", "USD", "1.086000"),
        ("2026-03-12", "EUR", "USD", "1.084000"),
    ], events=[
        ev(901, "T-P09-1", "payment", "MRC-ACME01", "2.50", "EUR", "2026-03-10T18:00:00Z"),
        ev(902, "T-P09-2", "payment", "MRC-ACME01", "2.50", "EUR", "2026-03-11T18:00:00Z"),
        ev(903, "T-P09-3", "payment", "MRC-IRIS09", "10.00", "USD", "2026-03-12T18:00:00Z"),
    ]),
    "P10": dict(month="2026-03", rates=[
        ("2026-03-16", "EUR", "USD", "1.080000"),
        ("2026-03-17", "EUR", "USD", "1.100000"),
    ], events=[
        ev(111, "T-P10-1", "payment", "MRC-ACME01", "50.00", "USD", "2026-03-10T18:00:00Z"),
        ev(112, "T-P10-2", "refund", "MRC-ACME01", "20.00", "USD", "2026-03-12T18:00:00Z",
           original="T-P10-1"),
        ev(113, "T-P10-3", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-12T19:00:00Z"),
        ev(114, "T-P10-4", "refund", "MRC-ACME01", "5.00", "USD", "2026-03-13T18:00:00Z",
           original="T-PRIOR-00042"),
        ev(115, "T-P10-5", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-13T19:00:00Z"),
        ev(116, "T-P10-6", "payment", "MRC-ACME01", "30.00", "USD", "2026-03-09T18:00:00Z"),
        ev(117, "T-P10-6", "payment", "MRC-ACME01", "30.00", "USD", "2026-03-09T18:00:00Z",
           status="reversed"),
        ev(118, "T-P10-7", "refund", "MRC-ACME01", "3.00", "USD", "2026-03-14T18:00:00Z",
           original="T-P10-6"),
        ev(119, "T-P10-8", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-14T19:00:00Z"),
        ev(141, "T-P10-9", "payment", "MRC-ACME01", "20.00", "EUR", "2026-03-16T18:00:00Z"),
        ev(142, "T-P10-10", "refund", "MRC-ACME01", "10.00", "EUR", "2026-03-17T18:00:00Z",
           original="T-P10-9"),
        ev(143, "T-P10-11", "payment", "MRC-ACME01", "10.00", "USD", "2026-03-17T19:00:00Z"),
    ]),
    "P11": dict(month="2026-03", events=[
        ev(121, "T-P11-1", "payment", "MRC-ACME01", "0.17", "USD", "2026-03-10T17:00:00Z"),
        ev(122, "T-P11-2", "payment", "MRC-ACME01", "0.17", "USD", "2026-03-10T18:00:00Z"),
        ev(123, "T-P11-3", "payment", "MRC-ACME01", "0.17", "USD", "2026-03-10T19:00:00Z"),
        ev(124, "T-P11-4", "refund", "MRC-ACME01", "0.10", "USD", "2026-03-10T20:00:00Z",
           original="T-P11-1"),
    ]),
    "P12": dict(month="2026-03", extra_merchants=[
        ("MRC-JADE10", "Jade Kitchen 10", "America/Chicago", "USD", 300),
        ("MRC-JADE9", "Jade Kitchen 9", "America/Chicago", "USD", 300),
    ], events=[
        ev(131, "T-P12-1", "payment", "MRC-ACME01", "50.00", "USD", "2026-03-18T17:00:00Z"),
        ev(132, "T-P12-2", "payment", "MRC-ACME01", "20.00", "USD", "2026-03-18T18:00:00Z"),
        ev(133, "T-P12-3", "refund", "MRC-ACME01", "5.00", "USD", "2026-03-18T19:00:00Z",
           original="T-P12-1"),
        ev(134, "T-P12-4", "refund", "MRC-ACME01", "30.00", "USD", "2026-03-20T18:00:00Z",
           original="T-P12-1"),
        ev(135, "T-P12-5", "payment", "MRC-ACME01", "0.00", "USD", "2026-03-18T20:00:00Z",
           memo="card verification"),
        ev(136, "T-P12-6", "payment", "MRC-JADE9", "10.00", "USD", "2026-03-19T18:00:00Z"),
        ev(137, "T-P12-7", "payment", "MRC-JADE10", "10.00", "USD", "2026-03-19T18:00:00Z"),
    ]),
}

DEFAULT_RATES = [
    ("2026-03-02", "EUR", "USD", "1.081500"),
    ("2026-03-02", "USD", "EUR", "0.924100"),
]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for pid, spec in PROBES.items():
        assert len(spec["events"]) <= 12
        d = OUT / pid / "input"
        d.mkdir(parents=True)
        (OUT / pid / "month.txt").write_text(spec["month"] + "\n")
        bom = spec.get("bom", False)
        with open(d / "events.csv", "w", encoding="utf-8", newline="") as f:
            if bom:
                f.write("﻿")
            w = csv.writer(f, lineterminator="\n")
            w.writerow(EVENT_COLS)
            w.writerows(spec["events"])
        write_merchants(d / "merchants.csv", False, spec.get("extra_merchants", ()))
        with open(d / "fx_rates.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["date", "from_currency", "to_currency", "rate"])
            w.writerows(spec.get("rates", DEFAULT_RATES))
    print(f"wrote {len(PROBES)} probes")


if __name__ == "__main__":
    main()
