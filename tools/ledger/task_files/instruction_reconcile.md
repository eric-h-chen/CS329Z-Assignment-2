# Fix the settlement pipeline

`/app/pipeline` turns payment-processor events into a daily settlement
report. Finance says the March 2026 report does not reconcile with the
bank's control totals in `/app/controls/2026-03.csv`. The control totals
are correct.

`/app/SPEC.md` is the authoritative definition of correct behavior. The
pipeline deviates from it in several places. Fix the pipeline so that it
conforms to SPEC.md in full.

Run the pipeline from `/app` with:

    python -m pipeline.cli --data data/2026-03 --month 2026-03 --out out

## How your work is graded

Your pipeline will be run through that same command line on input
directories you have not seen: other months, and small datasets that each
exercise one rule of SPEC.md. For every one of them, `report.csv` and
`rejects.csv` must match the specification exactly.

Matching the March control totals is necessary but not sufficient. The
controls are monthly totals per merchant, so they cannot confirm every
rule, and a change that only fits the March data will fail on other inputs.

## Constraints

- Keep the command line and the two output file names unchanged.
- You may restructure or rewrite the code behind the command line.
- Use only the Python standard library and the installed `tzdata` package.
