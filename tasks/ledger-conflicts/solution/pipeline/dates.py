"""Date handling for settlement."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def settlement_date(occurred_at, tz_name):
    """Return the settlement date of an event timestamp for a merchant."""
    utc = datetime.strptime(occurred_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return utc.astimezone(ZoneInfo(tz_name)).date()


def valid_month(value: str) -> bool:
    """True if ``value`` looks like ``YYYY-MM``."""
    return bool(MONTH_PATTERN.match(value))


def month_label(value: str) -> str:
    """Human-readable month name for log output, e.g. ``March 2026``."""
    year, month = (int(p) for p in value.split("-"))
    return date(year, month, 1).strftime("%B %Y")
