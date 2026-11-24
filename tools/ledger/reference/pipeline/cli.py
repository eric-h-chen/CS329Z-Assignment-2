"""Command-line entry point.

    python -m pipeline.cli --data DATA_DIR --month YYYY-MM --out OUT_DIR
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import __version__
from .dates import month_label, valid_month
from .events import effective_records, eligible, status_counts, warn_on_unexpected_values
from .fx import RateTable
from .ingest import InputError, load_inputs
from .merchants import merchant_table
from .money import format_minor
from .report import build, totals_by_merchant, write_rejects, write_report

log = logging.getLogger("pipeline")

REPORT_FILE = "report.csv"
REJECTS_FILE = "rejects.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.cli",
        description="Build the daily settlement report for one month.",
    )
    parser.add_argument("--data", required=True, type=Path,
                        help="directory holding events.csv, merchants.csv and fx_rates.csv")
    parser.add_argument("--month", required=True, help="report month as YYYY-MM")
    parser.add_argument("--out", required=True, type=Path,
                        help="directory to write report.csv and rejects.csv into")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print a run summary to stderr")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    if not valid_month(args.month):
        parser.error(f"--month must look like YYYY-MM, got {args.month!r}")
    if not args.data.is_dir():
        parser.error(f"--data {args.data} is not a directory")
    return args


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def print_summary(month: str, events: list, records: list, rows: dict,
                  rejects: list, merchants: dict, elapsed: float) -> None:
    """Log a short human-readable summary of the run."""
    if not log.isEnabledFor(logging.INFO):
        return
    effective = effective_records(events)
    log.info("settlement run for %s", month_label(month))
    log.info("  %d events, %d transactions, %d eligible",
             len(events), len(effective), len(records))
    for status, n in sorted(status_counts(effective).items()):
        log.info("    %-9s %d", status, n)
    log.info("  %d report rows, %d rejects", len(rows), len(rejects))
    for key, acc in sorted(totals_by_merchant(rows).items()):
        ccy = merchants[key]["settlement_currency"]
        net = acc["gross"] - acc["refunds"] - acc["fees"]
        log.info("    %-12s payments %-5d net %s", key, acc["count"], format_minor(net, ccy))
    log.info("  finished in %.2fs", elapsed)


def run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    try:
        events, merchant_rows, rate_rows = load_inputs(args.data)
    except InputError as exc:
        log.error("%s", exc)
        return 2

    warn_on_unexpected_values(events)
    merchants = merchant_table(merchant_rows)
    rates = RateTable(rate_rows)

    records = eligible(effective_records(events))
    rows, rejects = build(records, merchants, rates, args.month)

    args.out.mkdir(parents=True, exist_ok=True)
    write_report(args.out / REPORT_FILE, rows, merchants)
    write_rejects(args.out / REJECTS_FILE, rejects)

    print_summary(args.month, events, records, rows, rejects, merchants,
                  time.monotonic() - started)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
