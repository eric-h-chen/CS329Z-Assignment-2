"""The 12 planted defects, as exact (file, old, new) replacements against the reference.

Applied one at a time they give the mutants; applied together, the baseline.
Every `old` string must occur exactly once in its file (asserted by build_tasks.py).
"""

DEFECTS: dict[str, list[tuple[str, str, str]]] = {
    # R1: naive comma split, silently skipping lines without 10 fields.
    "D01": [(
        "ingest.py",
        '''def read_events(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
''',
        '''EVENT_COLUMNS = ["event_seq", "txn_id", "type", "merchant_id", "amount",
                 "currency", "occurred_at", "status", "original_txn_id", "memo"]


def read_events(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        next(f)
        for line in f:
            fields = line.rstrip("\\n").split(",")
            if len(fields) != len(EVENT_COLUMNS):
                continue
            rows.append(dict(zip(EVENT_COLUMNS, fields)))
    return rows
''',
    )],
    # R4, R12: raw merchant id lookup, misses dropped silently, no rejects.
    "D02": [
        ("report.py", 'from .merchants import canonical_id\n', ''),
        ("report.py", '        key = canonical_id(rec["merchant_id"])\n', '        key = rec["merchant_id"]\n'),
        ("report.py", '            rejects.append((int(rec["event_seq"]), rec["txn_id"], "UNKNOWN_MERCHANT"))\n', ''),
    ],
    # R2: event_seq compared as text.
    "D03": [(
        "events.py",
        'if cur is None or int(ev["event_seq"]) > int(cur["event_seq"]):',
        'if cur is None or ev["event_seq"] > cur["event_seq"]:',
    )],
    # R2, R3: eligibility filter applied before choosing the effective record.
    "D04": [(
        "cli.py",
        "records = eligible(effective_records(events))",
        "records = effective_records(eligible(events))",
    )],
    # R5: UTC calendar date.
    "D05": [
        ("dates.py", "from zoneinfo import ZoneInfo\n", ""),
        ("dates.py", "    return utc.astimezone(ZoneInfo(tz_name)).date()\n", "    return utc.date()\n"),
    ],
    # R6: only USD and EUR exponents known; default 2.
    "D06": [
        ("money.py", 'EXPONENT = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}', 'EXPONENT = {"USD": 2, "EUR": 2}'),
        ("money.py", "    return EXPONENT[currency]\n", "    return EXPONENT.get(currency, 2)\n"),
    ],
    # R6: binary floating point and truncation.
    "D07": [(
        "money.py",
        "    return int(Decimal(amount).scaleb(exponent(currency)))\n",
        "    return int(float(amount) * 10 ** exponent(currency))\n",
    )],
    # R7: next later rate date when the settlement date has none.
    "D08": [(
        "fx.py",
        "        i = bisect.bisect_right(dates, on.isoformat()) - 1\n",
        "        i = min(bisect.bisect_left(dates, on.isoformat()), len(dates) - 1)\n",
    )],
    # R8: ties to even.
    "D09": [
        ("money.py", "from decimal import ROUND_HALF_UP, Decimal\n", "from decimal import Decimal\n"),
        ("money.py", "    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))\n", "    return int(round(x))\n"),
    ],
    # R9: refund dated by its original payment, dropped when that payment is absent.
    "D10": [
        ("report.py", "    rows, rejects = {}, []\n",
         '    rows, rejects = {}, []\n    originals = {r["txn_id"]: r for r in records}\n'),
        ("report.py",
         '        day = settlement_date(rec["occurred_at"], merchant["timezone"])\n',
         '''        source = rec
        if rec["type"] == "refund":
            source = originals.get(rec["original_txn_id"])
            if source is None:
                continue
        day = settlement_date(source["occurred_at"], merchant["timezone"])
'''),
    ],
    # R10: one fee on each row's gross total.
    "D11": [
        ("report.py",
         '            row["fees"] += round_half_up(Decimal(settled) * int(merchant["fee_bps"]) / 10000)\n',
         ''),
        ("report.py",
         "            row[\"refunds\"] += settled\n    return rows, rejects\n",
         '''            row["refunds"] += settled
    for (key, _day), row in rows.items():
        row["fees"] = round_half_up(Decimal(row["gross"]) * int(merchants[key]["fee_bps"]) / 10000)
    return rows, rejects
'''),
    ],
    # R11: rows without payments omitted.
    "D12": [(
        "report.py",
        '            row = rows[(key, day)]\n',
        '''            row = rows[(key, day)]
            if row["count"] == 0:
                continue
'''),
    ],
}
