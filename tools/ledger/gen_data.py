"""Deterministic month generator for the ledger tasks.

Writes tools/ledger/data/months/<YYYY-MM>/{events,merchants,fx_rates}.csv.
Run: python gen_data.py
"""

from __future__ import annotations

import calendar
import csv
import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from math import gcd
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "months"

MERCHANTS = [
    # id, name, tz, ccy, bps, weight
    ("MRC-ACME01", "Acme Outfitters", "America/Chicago", "USD", 290, 22.0),
    ("MRC-BOLT02", "Bolt Hardware", "America/New_York", "USD", 275, 18.0),
    ("MRC-CEDR03", "Cedar & Pine Market", "America/Los_Angeles", "USD", 310, 16.0),
    ("MRC-DELT04", "Delta Kaffeehaus", "Europe/Berlin", "EUR", 180, 14.0),
    ("MRC-ECHO05", "Echo Books", "Europe/Dublin", "EUR", 195, 12.0),
    ("MRC-FUJI06", "Fuji Stationery", "Asia/Tokyo", "JPY", 360, 9.0),
    ("MRC-GULF07", "Gulf Pearl Trading", "Asia/Kuwait", "KWD", 250, 7.5),
    ("MRC-HANA08", "Hana Studio", "Asia/Tokyo", "USD", 325, 1.5),
]
MERCHANT = {m[0]: m for m in MERCHANTS}
UNKNOWN_IDS = ["MRC-GHOST99", "MRC-ZETA00"]
CURRENCIES = ["USD", "EUR", "JPY", "KWD"]
EXP = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
AMOUNT_RANGE = {"USD": (10, 90000), "EUR": (10, 90000), "JPY": (50, 90000), "KWD": (100, 300000)}
BASE_RATES = {
    ("USD", "EUR"): 0.92, ("USD", "JPY"): 150.0, ("USD", "KWD"): 0.307,
    ("EUR", "USD"): 1.085, ("EUR", "JPY"): 162.5, ("EUR", "KWD"): 0.333,
    ("JPY", "USD"): 0.00665, ("JPY", "EUR"): 0.00614, ("JPY", "KWD"): 0.002048,
    ("KWD", "USD"): 3.255, ("KWD", "EUR"): 3.0, ("KWD", "JPY"): 488.0,
}

MONTHS = [
    # month, seed, first event_seq, bom
    ("2026-03", 303, 9200, True),
    ("2026-07", 707, 97000, False),
    ("2026-11", 1111, 998000, True),
]

LIFECYCLES = [
    (["settled"], 45),
    (["pending", "settled"], 30),
    (["pending", "settled", "settled*"], 8),
    (["pending", "settled", "reversed"], 6),
    (["pending", "failed"], 6),
    (["pending"], 3),
    (["settled", "reversed", "settled"], 2),
]

PLAIN_MEMOS = ["online order", "in-store purchase", "subscription renewal", "gift card",
               "invoice payment", "deposit", "monthly plan", "repeat customer",
               "phone order", "partial shipment", "replacement item", "event tickets"]
COMMA_MEMOS = ["Order 4471, gift wrap", "Invoice 2026-118, net 30", "Smith, J.",
               "2 items, 1 backordered", "pickup Tues, 3pm", "returns desk, aisle 4"]
QUOTE_MEMOS = ['customer said "thanks"', 'item "Blue Mug" large', '"rush" delivery',
               'size "M" exchange']
NEWLINE_MEMOS = ["first line\nsecond line", "Ship to back door\nRing twice",
                 "note from cashier\nverified ID", 'see "attached"\nreceipt 88']
UNICODE_MEMOS = ["Café Zürich order", "東京店 注文", "Größe M Rückgabe", "naïve façade décor",
                 "Señora Muñoz", "Kuwait — دينار"]


def month_days(month: str) -> tuple[date, date]:
    y, m = (int(p) for p in month.split("-"))
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def fmt_ts(dt: datetime) -> str:
    return utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_amount(minor: int, ccy: str, short: bool) -> str:
    e = EXP[ccy]
    if e == 0:
        return str(minor)
    s = f"{minor // 10 ** e}.{minor % 10 ** e:0{e}d}"
    if short:
        s = s.rstrip("0").rstrip(".")
    return s


def weighted(rng: random.Random, items):
    vals, weights = zip(*items)
    return rng.choices(vals, weights=weights, k=1)[0]


def make_rates(rng: random.Random, month: str):
    first, last = month_days(month)
    days = []
    d = first - timedelta(days=10)
    while d <= last + timedelta(days=1):
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    in_month = [d for d in days if first < d < last]
    for d in rng.sample(in_month, 2):
        days.remove(d)
    rates: dict[tuple[tuple[str, str], date], Decimal] = {}
    for pair, base in BASE_RATES.items():
        r = base * (1 + rng.uniform(-0.01, 0.01))
        for d in days:
            r *= 1 + rng.uniform(-0.004, 0.004)
            rates[(pair, d)] = Decimal(f"{r:.6f}")
    return rates, days


def tie_solutions(rate: Decimal, src: str, dst: str):
    """Minor amounts m of src such that m/10^e * rate * 10^s ends in exactly .5 with even integer part."""
    r_micro = int(rate * 1000000)
    e, s = EXP[src], EXP[dst]
    K = r_micro * 10 ** s
    D = 10 ** (e + 6)
    half = D // 2
    g = gcd(K, D)
    if half % g:
        return []
    Dg = D // g
    m0 = (half // g) * pow(K // g, -1, Dg) % Dg if Dg > 1 else 0
    lo, hi = AMOUNT_RANGE[src]
    out = []
    m = m0 + ((lo - m0 + Dg - 1) // Dg) * Dg if m0 < lo else m0
    while m <= hi:
        if ((m * K) // D) % 2 == 0:
            out.append(m)
        m += Dg
    return out


def find_ties(rng, rates, days, month):
    first, last = month_days(month)
    slots = [(pair, d) for (pair, d) in rates if first < d < last and d in days]
    found = []
    for pair, d in slots:
        for m in tie_solutions(rates[(pair, d)], *pair):
            found.append((pair, d, m))
    return found


def inject_tie_rates(rng, rates, days, month, n=4):
    """Set a few rates to three significant decimals so that ties become common."""
    first, last = month_days(month)
    cands = [d for d in days if first < d < last]
    pairs = [("EUR", "USD"), ("USD", "EUR"), ("KWD", "USD"), ("EUR", "JPY")]
    for pair, d in zip(pairs[:n], rng.sample(cands, n)):
        rates[(pair, d)] = Decimal(f"{float(rates[(pair, d)]):.3f}").quantize(Decimal("0.000001"))


def pick_memo(rng):
    return weighted(rng, [
        ("", 60), ("plain", 25), ("comma", 8), ("quote", 3), ("newline", 2), ("unicode", 2),
    ])


def memo_text(rng, kind):
    pool = {"plain": PLAIN_MEMOS, "comma": COMMA_MEMOS, "quote": QUOTE_MEMOS,
            "newline": NEWLINE_MEMOS, "unicode": UNICODE_MEMOS}.get(kind)
    return rng.choice(pool) if pool else ""


def noisy_id(rng, mid):
    roll = rng.random()
    if roll < 0.01:
        return rng.choice(UNKNOWN_IDS)
    if roll < 0.07:
        return mid.lower()
    if roll < 0.11:
        pad = rng.choice([" ", "  ", "\t"])
        where = rng.choice(["left", "right", "both"])
        return (pad if where != "right" else "") + mid + (pad if where != "left" else "")
    return mid


def random_amount(rng, ccy):
    lo, hi = AMOUNT_RANGE[ccy]
    short = EXP[ccy] > 0 and rng.random() < 0.05
    m = rng.randint(lo, hi)
    if short:
        m = max(lo, m - m % 10 ** EXP[ccy] if rng.random() < 0.5 else m - m % 10)
    return m, short


def generate(month: str, seed: int, first_seq: int, bom: bool):
    rng = random.Random(seed)
    first, last = month_days(month)
    w_start = datetime.combine(first - timedelta(days=1), time(0), timezone.utc)
    w_end = datetime.combine(last + timedelta(days=2), time(0), timezone.utc)
    span = int((w_end - w_start).total_seconds())

    rates, rate_days = make_rates(rng, month)
    ties = find_ties(rng, rates, rate_days, month)
    if len(ties) < 6:
        inject_tie_rates(rng, rates, rate_days, month)
        ties = find_ties(rng, rates, rate_days, month)
    assert len(ties) >= 6, f"{month}: only {len(ties)} rounding ties"

    txns = []  # dicts: txn_id, type, mid (canonical), raw_mid, ccy, at, amounts/status list, original
    n_txn = 2400
    for i in range(n_txn):
        mid = weighted(rng, [(m[0], m[5]) for m in MERCHANTS])
        if rng.random() < 0.85:
            at = w_start + timedelta(seconds=rng.randrange(span))
        else:
            boundary = rng.choice([w_start + timedelta(days=1), w_end - timedelta(days=1)])
            at = boundary + timedelta(seconds=rng.randint(-36000, 36000))
        kind = "payment" if rng.random() < 0.88 else "refund"
        txns.append({"txn_id": f"T{seed}-{i:05d}", "type": kind, "mid": mid, "at": at})

    txns.sort(key=lambda t: t["at"])
    payments_by_mid: dict[str, list[dict]] = {}
    for t in txns:
        settle = MERCHANT[t["mid"]][3]
        t["raw_mid"] = noisy_id(rng, t["mid"])
        if t["type"] == "payment":
            t["ccy"] = settle if rng.random() < 0.7 else rng.choice([c for c in CURRENCIES if c != settle])
            t["minor"], t["short"] = random_amount(rng, t["ccy"])
            t["original"] = ""
            payments_by_mid.setdefault(t["mid"], []).append(t)
        else:
            prior = [p for p in payments_by_mid.get(t["mid"], [])
                     if p["at"] < t["at"] - timedelta(days=1)]
            if prior and rng.random() < 0.7:
                p = rng.choice(prior)
                t["original"] = p["txn_id"]
                t["ccy"] = p["ccy"]
                t["minor"] = max(AMOUNT_RANGE[p["ccy"]][0], rng.randint(1, p["minor"]))
                t["short"] = False
            else:
                t["original"] = f"T-PRIOR-{rng.randint(0, 99999):05d}"
                t["ccy"] = settle if rng.random() < 0.7 else rng.choice([c for c in CURRENCIES if c != settle])
                t["minor"], t["short"] = random_amount(rng, t["ccy"])
        t["life"] = weighted(rng, LIFECYCLES)

    # Rounding ties: single-event settled payments on the rate's own date.
    rng.shuffle(ties)
    used_slots = set()
    injected = 0
    for (src, dst), d, m in ties:
        if (src, dst, d) in used_slots or injected >= 8:
            continue
        cands = [x for x in MERCHANTS if x[3] == dst]
        mer = rng.choice(cands)
        local = datetime.combine(d, time(12, rng.randint(0, 59)), ZoneInfo(mer[2]))
        txns.append({"txn_id": f"T{seed}-X{injected:03d}", "type": "payment", "mid": mer[0],
                     "raw_mid": mer[0], "at": utc(local), "ccy": src, "minor": m,
                     "short": False, "original": "", "life": ["settled"]})
        used_slots.add((src, dst, d))
        injected += 1

    # Refund-only days: settled refunds on local days with no payment for that merchant.
    def local_day(t):
        return utc(t["at"]).astimezone(ZoneInfo(MERCHANT[t["mid"]][2])).date()
    busy = {(t["mid"], local_day(t)) for t in txns if t["type"] == "payment"}
    empty = []
    for mid in ("MRC-HANA08", "MRC-GULF07", "MRC-FUJI06"):
        d = first
        while d <= last:
            if (mid, d) not in busy:
                empty.append((mid, d))
            d += timedelta(days=1)
    rng.shuffle(empty)
    for j, (mid, d) in enumerate(empty[:5]):
        mer = MERCHANT[mid]
        local = datetime.combine(d, time(rng.randint(9, 20), rng.randint(0, 59)), ZoneInfo(mer[2]))
        minor, short = random_amount(rng, mer[3])
        txns.append({"txn_id": f"T{seed}-R{j:03d}", "type": "refund", "mid": mid, "raw_mid": mid,
                     "at": utc(local), "ccy": mer[3], "minor": minor, "short": short,
                     "original": f"T-PRIOR-{rng.randint(0, 99999):05d}", "life": ["settled"]})

    # Opaque transaction ids, so injected cases do not stand out.
    new_ids = rng.sample(range(100000, 999999), len(txns))
    rename = {t["txn_id"]: f"TX{n}" for t, n in zip(txns, new_ids)}
    for t in txns:
        t["txn_id"] = rename[t["txn_id"]]
        t["original"] = rename.get(t["original"], t["original"])

    # Events.
    events = []
    for t in txns:
        emit = t["at"]
        amount = fmt_amount(t["minor"], t["ccy"], t["short"])
        for k, status in enumerate(t["life"]):
            if k:
                emit = emit + timedelta(seconds=rng.randint(60, 36 * 3600))
            if status == "settled*":
                status = "settled"
                lo, hi = AMOUNT_RANGE[t["ccy"]]
                amount = fmt_amount(min(hi, max(lo, t["minor"] + rng.randint(-500, 500))), t["ccy"], False)
            events.append({
                "emit": emit, "txn_id": t["txn_id"], "type": t["type"], "merchant_id": t["raw_mid"],
                "amount": amount, "currency": t["ccy"], "occurred_at": fmt_ts(t["at"]),
                "status": status, "original_txn_id": t["original"],
                "memo": memo_text(rng, pick_memo(rng)),
            })
    events.sort(key=lambda e: (e["emit"], e["txn_id"]))
    seq = first_seq
    for e in events:
        e["event_seq"] = seq
        seq += rng.randint(1, 3)
    shuffled = []
    for i in range(0, len(events), 50):
        block = events[i:i + 50]
        rng.shuffle(block)
        shuffled.extend(block)
    return shuffled, rates


def write_month(month: str, events, rates, bom: bool) -> None:
    d = OUT / month
    d.mkdir(parents=True, exist_ok=True)
    prefix = "﻿" if bom else ""
    cols = ["event_seq", "txn_id", "type", "merchant_id", "amount", "currency",
            "occurred_at", "status", "original_txn_id", "memo"]
    with open(d / "events.csv", "w", encoding="utf-8", newline="") as f:
        f.write(prefix)
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for e in events:
            w.writerow([e[c] for c in cols])
    write_merchants(d / "merchants.csv", bom)
    with open(d / "fx_rates.csv", "w", encoding="utf-8", newline="") as f:
        f.write(prefix)
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "from_currency", "to_currency", "rate"])
        for (pair, day) in sorted(rates, key=lambda k: (k[1], k[0])):
            w.writerow([day.isoformat(), pair[0], pair[1], f"{rates[(pair, day)]:.6f}"])


def write_merchants(path: Path, bom: bool, extra=()) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        if bom:
            f.write("﻿")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["merchant_id", "name", "timezone", "settlement_currency", "fee_bps"])
        for m in list(MERCHANTS) + list(extra):
            w.writerow(m[:5])


def main() -> None:
    for month, seed, first_seq, bom in MONTHS:
        events, rates = generate(month, seed, first_seq, bom)
        # D01 note: a continuation line must never itself contain exactly 9 commas.
        for e in events:
            if "\n" in e["memo"]:
                assert all(part.count(",") != 9 for part in e["memo"].split("\n")[1:])
        write_month(month, events, rates, bom)
        print(f"{month}: {len(events)} events, {len(rates)} rate rows")


if __name__ == "__main__":
    main()
