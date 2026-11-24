# Settlement report specification

This document is the authoritative definition of the settlement pipeline.

## 1. Invocation

    python -m pipeline.cli --data DATA_DIR --month YYYY-MM --out OUT_DIR

Reads `events.csv`, `merchants.csv` and `fx_rates.csv` from DATA_DIR.
Writes `report.csv` and `rejects.csv` to OUT_DIR, creating it if needed.
Both files are always written, even when they have no data rows.
Exits with status 0 on success.

## 2. Input files

All input files are UTF-8 CSV as defined by RFC 4180, with a header row.
A file may begin with a byte-order mark. Fields may be quoted, and a quoted
field may contain commas, doubled quotes, and line breaks.

### merchants.csv

| Column | Meaning |
| --- | --- |
| merchant_id | Canonical merchant id (see R4) |
| name | Display name, not used |
| timezone | IANA time zone name, for example `America/Chicago` |
| settlement_currency | Currency the merchant is paid in |
| fee_bps | Processing fee in basis points, a non-negative integer |

### events.csv

| Column | Meaning |
| --- | --- |
| event_seq | Positive integer, unique across the file |
| txn_id | Transaction identifier |
| type | `payment` or `refund` |
| merchant_id | Merchant id as sent by the processor, not necessarily canonical |
| amount | Non-negative decimal number in major units of `currency` |
| currency | `USD`, `EUR`, `JPY` or `KWD` |
| occurred_at | UTC instant, formatted `YYYY-MM-DDTHH:MM:SSZ` |
| status | `pending`, `settled`, `failed` or `reversed` |
| original_txn_id | For refunds, the txn_id of the refunded payment. Empty for payments |
| memo | Free text |

### fx_rates.csv

| Column | Meaning |
| --- | --- |
| date | Calendar date `YYYY-MM-DD` |
| from_currency | Currency converted from |
| to_currency | Currency converted to |
| rate | Decimal number: one major unit of from_currency equals `rate` major units of to_currency |

Not every date has a row for every currency pair.

### Input guarantees

- G1. All events of one transaction have the same type, merchant_id,
  currency and occurred_at. Their amount and status may differ.
- G2. An amount never has more decimal places than its currency's
  exponent (see R6).
- G3. Merchant ids in merchants.csv are canonical and unique.
- G4. For every conversion R7 requires, fx_rates.csv contains at least one
  usable row.
- G5. For a given month, events.csv contains every event of every
  transaction whose occurred_at falls between 00:00 UTC on the day before
  the month's first day and 24:00 UTC on the day after its last day.

## 3. Rules

R1. Parsing. Every record of events.csv is one event. No record is skipped.

R2. Effective record. Events that share a txn_id describe one transaction.
Its effective record is the event with the numerically greatest event_seq.
Every other event of that transaction is ignored for all purposes.

R3. Eligibility. A transaction is eligible if and only if the status of its
effective record is `settled`. An ineligible transaction appears in neither
output file.

R4. Merchant resolution. The canonical form of a merchant id is the raw
value with leading and trailing ASCII whitespace removed, converted to
upper case. An eligible transaction whose canonical merchant id is not in
merchants.csv is rejected: it gets one row in rejects.csv with reason
`UNKNOWN_MERCHANT`, whatever its date, and it is excluded from the report.

R5. Settlement date. A transaction's settlement date is the calendar date
of occurred_at in its merchant's time zone, using IANA time zone rules
including daylight saving time. A transaction is in the report if and only
if it is eligible, its merchant is known, and its settlement date falls in
the month given by `--month`. Other transactions are excluded silently.

R6. Minor units. Money is computed in integer minor units.
`amount_minor = amount x 10^e`, computed exactly, where e is the currency
exponent: USD 2, EUR 2, JPY 0, KWD 3.

R7. Conversion. Each transaction is converted to its merchant's settlement
currency on its own, before any summing.
- If currency equals the settlement currency, `settled_minor = amount_minor`.
- Otherwise `settled_minor = round_half_up(amount x rate x 10^s)`, where s
  is the exponent of the settlement currency and `rate` comes from the
  fx_rates.csv row with from_currency = currency, to_currency = settlement
  currency, and the latest date that is on or before the settlement date.
- Only such direct rows are used. Inverse and cross rates are never derived.

R8. Rounding. `round_half_up(x) = floor(x + 1/2)` for x >= 0, computed in
exact decimal arithmetic. Examples: 270.5 becomes 271, 271.5 becomes 272,
270.4999 becomes 270.

R9. Refunds. A refund is reported under its own merchant, its own
settlement date (from its own occurred_at), and its own amount and
currency, converted by R7. original_txn_id is informational and is not
used in any computation. A refund is reported whether or not the payment
it refers to is present in the input.

R10. Fees. Each payment in the report carries a fee of
`round_half_up(settled_minor x fee_bps / 10000)`, computed per payment.
Refunds carry no fee and do not reduce any fee.

R11. Report rows. report.csv has one row for each pair of merchant and
settlement date that has at least one payment or refund in the report.

| Column | Value |
| --- | --- |
| merchant_id | Canonical merchant id |
| settlement_date | `YYYY-MM-DD` |
| currency | The merchant's settlement currency |
| gross_minor | Sum of settled_minor over the row's payments |
| refunds_minor | Sum of settled_minor over the row's refunds, as a positive number |
| fees_minor | Sum of the row's fees |
| net_minor | gross_minor - refunds_minor - fees_minor, which may be negative |
| payment_count | Number of payments in the row. Refunds are not counted |

Rows are sorted by merchant_id ascending by code point, then by
settlement_date ascending.

R12. Rejects. rejects.csv has the columns `event_seq,txn_id,reason`, taken
from the effective record, sorted by event_seq ascending numerically.

R13. Output format. Both output files are UTF-8 CSV without a byte-order
mark, with the header row first and columns in the order given above.
Integers are written in base 10 without separators or padding.

## 4. Worked example

A merchant settles in USD with fee_bps 290. A settled payment of 2.50 EUR
has a settlement date for which the applicable EUR to USD rate is 1.082000.

- amount x rate x 10^2 = 2.50 x 1.082 x 100 = 270.5
- settled_minor = round_half_up(270.5) = 271
- fee = round_half_up(271 x 290 / 10000) = round_half_up(7.859) = 8

If this is the merchant's only transaction that day, the row reads
gross_minor 271, refunds_minor 0, fees_minor 8, net_minor 263,
payment_count 1.
