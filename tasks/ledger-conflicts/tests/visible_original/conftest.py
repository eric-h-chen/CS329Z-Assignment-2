import csv
import os
import subprocess
import sys

import pytest

APP_DIR = os.environ.get("LEDGER_APP", "/app")

EVENT_COLUMNS = ["event_seq", "txn_id", "type", "merchant_id", "amount", "currency",
                 "occurred_at", "status", "original_txn_id", "memo"]
MERCHANT_COLUMNS = ["merchant_id", "name", "timezone", "settlement_currency", "fee_bps"]
RATE_COLUMNS = ["date", "from_currency", "to_currency", "rate"]


def merchant(mid, tz="America/Chicago", ccy="USD", bps=300):
    return {"merchant_id": mid, "name": f"Merchant {mid}", "timezone": tz,
            "settlement_currency": ccy, "fee_bps": str(bps)}


def event(seq, txn, kind, mid, amount, ccy, at, status="settled", original="", memo=""):
    return {"event_seq": str(seq), "txn_id": txn, "type": kind, "merchant_id": mid,
            "amount": amount, "currency": ccy, "occurred_at": at, "status": status,
            "original_txn_id": original, "memo": memo}


def _write(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def run(tmp_path):
    def _run(month, merchants, events, rates=()):
        data = tmp_path / "data"
        data.mkdir(exist_ok=True)
        out = tmp_path / "out" / month
        _write(data / "events.csv", EVENT_COLUMNS, events)
        _write(data / "merchants.csv", MERCHANT_COLUMNS, merchants)
        _write(data / "fx_rates.csv", RATE_COLUMNS, [dict(zip(RATE_COLUMNS, r)) for r in rates])
        proc = subprocess.run(
            [sys.executable, "-m", "pipeline.cli", "--data", str(data),
             "--month", month, "--out", str(out)],
            cwd=APP_DIR, capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return _read(out / "report.csv"), _read(out / "rejects.csv")
    return _run
