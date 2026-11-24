"""Foreign-exchange conversion into a merchant's settlement currency."""

from __future__ import annotations

import bisect
import logging
from decimal import Decimal

from .money import exponent, round_half_up, to_minor

log = logging.getLogger(__name__)


class RateTable:
    """Daily rates per ordered currency pair."""

    def __init__(self, rows):
        self._dates, self._rates = {}, {}
        for r in rows:
            pair = (r["from_currency"], r["to_currency"])
            self._rates[(pair, r["date"])] = Decimal(r["rate"])
            self._dates.setdefault(pair, []).append(r["date"])
        for dates in self._dates.values():
            dates.sort()

    def lookup(self, from_ccy, to_ccy, on):
        """Return the rate to use for converting on date ``on``."""
        pair = (from_ccy, to_ccy)
        if pair not in self._dates:
            raise LookupError(f"no rates for {from_ccy}->{to_ccy}")
        dates = self._dates[pair]
        i = bisect.bisect_right(dates, on.isoformat()) - 1
        if i < 0:
            raise LookupError(f"no {from_ccy}->{to_ccy} rate usable on {on.isoformat()}")
        return self._rates[(pair, dates[i])]

    def pairs(self) -> list[tuple[str, str]]:
        """All currency pairs present in the table, sorted."""
        return sorted(self._dates)

    def __len__(self) -> int:
        return len(self._rates)


def convert(amount, currency, settle_ccy, rates, on):
    """Express ``amount`` of ``currency`` in minor units of ``settle_ccy``."""
    if currency == settle_ccy:
        return to_minor(amount, currency)
    rate = rates.lookup(currency, settle_ccy, on)
    return round_half_up(Decimal(amount) * rate * 10 ** exponent(settle_ccy))
