"""Verifier for the ledger tasks.

    python verify.py --app /app --tests <dir of this file> --task reconcile|conflicts

Exits 0 only if every check passes. Never imports code from the app; the
pipeline is exercised only through its command line.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

INT_COLUMNS = {
    "report.csv": {"gross_minor", "refunds_minor", "fees_minor", "net_minor", "payment_count"},
    "rejects.csv": {"event_seq"},
}


def read_csv(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def compare_csv(actual: Path, expected: Path, name: str) -> str | None:
    """Return None if equal under the comparison rules, else a description of the first difference."""
    exp = read_csv(expected)
    if not actual.is_file():
        return f"{name}: missing"
    try:
        act = read_csv(actual)
    except Exception as exc:  # unparsable or not UTF-8
        return f"{name}: unreadable ({exc.__class__.__name__}: {exc})"
    if not act:
        return f"{name}: empty file"
    if act[0] != exp[0]:
        return f"{name}: header {act[0]} != {exp[0]}"
    header = exp[0]
    ints = INT_COLUMNS[name]
    if len(act) != len(exp):
        first = None
        for i in range(1, min(len(act), len(exp))):
            if act[i] != exp[i]:
                first = i
                break
        hint = f"; first differing row {first}: got {act[first]} want {exp[first]}" if first else ""
        return f"{name}: {len(act) - 1} data rows, expected {len(exp) - 1}{hint}"
    for i in range(1, len(exp)):
        a, e = act[i], exp[i]
        if len(a) != len(header):
            return f"{name} row {i}: {len(a)} fields: {a}"
        for col, av, ev in zip(header, a, e):
            if col in ints:
                try:
                    ok = int(av) == int(ev)
                except ValueError:
                    ok = False
            else:
                ok = av == ev
            if not ok:
                return f"{name} row {i}: got {a} want {e}"
    return None


def run_check(app: Path, inp: Path, month: str, expected: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pipeline.cli", "--data", str(inp), "--month", month,
                 "--out", str(out)],
                cwd=app, capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            return False, "timeout after 60s"
        if proc.returncode != 0:
            return False, f"exit {proc.returncode}: {proc.stderr.strip()[-300:]}"
        for name in ("report.csv", "rejects.csv"):
            diff = compare_csv(out / name, expected / name, name)
            if diff:
                return False, diff
    return True, "ok"


def hidden_checks(app: Path, tests: Path) -> dict:
    results = {}
    for probe in sorted((tests / "probes").iterdir()):
        month = (probe / "month.txt").read_text().strip()
        results[f"probe {probe.name}"] = run_check(app, probe / "input", month, probe / "expected")
    for month_dir in sorted((tests / "months").iterdir()):
        results[f"month {month_dir.name}"] = run_check(
            app, month_dir / "input", month_dir.name, month_dir / "expected")
    return results


def suite_outcome(app: Path, tests: Path) -> tuple[bool, str]:
    expected_wrong = set(json.loads((tests / "expected_conflicts.json").read_text()))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(tests / "visible_original", root / "tests")
        (root / "pytest.ini").write_text("[pytest]\naddopts =\n")
        junit = root / "junit.xml"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST", "PYTHON"))}
        env["LEDGER_APP"] = str(app)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONTZPATH"] = os.environ.get("PYTHONTZPATH", "")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                 f"--junitxml={junit}", "tests"],
                cwd=root, env=env, capture_output=True, text=True, timeout=200,
            )
        except subprocess.TimeoutExpired:
            return False, "suite timed out"
        if not junit.is_file():
            return False, f"pytest produced no report: {proc.stdout[-500:]} {proc.stderr[-500:]}"
        outcomes = {}
        for case in ET.parse(junit).getroot().iter("testcase"):
            name = case.get("name")
            if case.find("failure") is not None:
                outcomes[name] = "failed"
            elif case.find("error") is not None:
                outcomes[name] = "error"
            elif case.find("skipped") is not None:
                outcomes[name] = "skipped"
            else:
                outcomes[name] = "passed"
    problems = []
    for name, outcome in sorted(outcomes.items()):
        want = "failed" if name in expected_wrong else "passed"
        if outcome != want:
            problems.append(f"{name}: {outcome}, expected {want}")
    missing = expected_wrong - set(outcomes)
    if missing:
        problems.append(f"not collected: {sorted(missing)}")
    if len(outcomes) < 23:
        problems.append(f"only {len(outcomes)} tests collected")
    return (not problems), ("; ".join(problems) or f"ok ({len(outcomes)} tests)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=Path("/app"))
    parser.add_argument("--tests", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--task", choices=["reconcile", "conflicts"], required=True)
    args = parser.parse_args()
    app, tests = args.app.resolve(), args.tests.resolve()

    checks = hidden_checks(app, tests)
    summary: dict = {"hidden_checks": {k: ok for k, (ok, _) in checks.items()}}
    print("== hidden checks (unseen inputs) ==")
    for name, (ok, detail) in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -- {detail}"))
    passed = all(ok for ok, _ in checks.values())
    print(f"hidden checks: {sum(ok for ok, _ in checks.values())}/{len(checks)} passed")

    if args.task == "conflicts":
        # The agent is never told that some visible tests are wrong. The original suite is
        # run against its pipeline: tests that agree with SPEC.md must pass, and tests that
        # contradict SPEC.md must fail (a pipeline that satisfies them does not conform).
        # Edits to /app/tests are allowed and irrelevant, since the pristine copy is used.
        print("== original visible suite against the pipeline ==")
        for label, fn in (("suite_outcome", suite_outcome),):
            try:
                ok, detail = fn(app, tests)
            except Exception as exc:
                ok, detail = False, f"verifier error: {exc!r}"
            summary[label] = ok
            print(f"{'PASS' if ok else 'FAIL'}  {label}  -- {detail}")
            passed = passed and ok

    summary["reward"] = 1 if passed else 0
    print("SUMMARY " + json.dumps(summary))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"verifier error: {exc!r}")
        sys.exit(1)
