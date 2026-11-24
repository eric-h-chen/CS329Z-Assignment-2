"""Loading of the three input files.

Each reader returns a list of dictionaries keyed by the header row. Values are
kept as strings; conversion happens in the stage that needs it.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

EVENTS_FILE = "events.csv"
MERCHANTS_FILE = "merchants.csv"
RATES_FILE = "fx_rates.csv"

REQUIRED_COLUMNS = {
    EVENTS_FILE: ("event_seq", "txn_id", "type", "merchant_id", "amount",
                  "currency", "occurred_at", "status", "original_txn_id"),
    MERCHANTS_FILE: ("merchant_id", "timezone", "settlement_currency", "fee_bps"),
    RATES_FILE: ("date", "from_currency", "to_currency", "rate"),
}


class InputError(Exception):
    """Raised when an input file is missing or structurally unusable."""


EVENT_COLUMNS = ["event_seq", "txn_id", "type", "merchant_id", "amount",
                 "currency", "occurred_at", "status", "original_txn_id", "memo"]


def read_events(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        next(f)
        for line in f:
            fields = line.rstrip("\n").split(",")
            if len(fields) != len(EVENT_COLUMNS):
                continue
            rows.append(dict(zip(EVENT_COLUMNS, fields)))
    return rows


def read_merchants(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_rates(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def check_columns(rows: list[dict], required: Iterable[str], name: str) -> None:
    """Fail early if a non-empty file lacks one of the columns we rely on."""
    if not rows:
        return
    missing = [c for c in required if c not in rows[0]]
    if missing:
        raise InputError(f"{name}: missing column(s) {', '.join(missing)}")


def load_inputs(data_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Read events, merchants and rates from ``data_dir``.

    Returns the three row lists in that order. Raises :class:`InputError` when
    a file is absent or lacks a required column.
    """
    paths = {name: data_dir / name for name in (EVENTS_FILE, MERCHANTS_FILE, RATES_FILE)}
    for name, path in paths.items():
        if not path.is_file():
            raise InputError(f"{name} not found in {data_dir}")

    events = read_events(paths[EVENTS_FILE])
    merchants = read_merchants(paths[MERCHANTS_FILE])
    rates = read_rates(paths[RATES_FILE])

    for name, rows in ((EVENTS_FILE, events), (MERCHANTS_FILE, merchants), (RATES_FILE, rates)):
        check_columns(rows, REQUIRED_COLUMNS[name], name)
        log.debug("loaded %d rows from %s", len(rows), name)
    return events, merchants, rates
