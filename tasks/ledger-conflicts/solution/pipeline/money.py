"""Currency amounts.

All report arithmetic is done on integers counted in a currency's minor unit
(cents for USD). Amounts arrive as decimal strings in major units.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

EXPONENT = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}


def exponent(currency):
    """Number of minor-unit digits for ``currency``."""
    return EXPONENT[currency]


def to_minor(amount, currency):
    """Convert a major-unit amount string to an integer of minor units."""
    return int(Decimal(amount).scaleb(exponent(currency)))


def round_half_up(x):
    """Round a Decimal to an integer."""
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def format_minor(value: int, currency: str) -> str:
    """Render minor units as a major-unit string, for log output only."""
    e = EXPONENT.get(currency, 2)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if e == 0:
        return f"{sign}{value} {currency}"
    whole, frac = divmod(value, 10 ** e)
    return f"{sign}{whole}.{frac:0{e}d} {currency}"
