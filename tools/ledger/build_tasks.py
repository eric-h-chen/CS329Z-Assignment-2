"""Derive baseline and mutants from the reference, compute expected outputs,
and write both task directories.

Run (Python 3.12 with tzdata==2025.2, PYTHONTZPATH=""):
    python gen_data.py && python gen_probes.py && python build_tasks.py
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from defects import DEFECTS

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
REF = HERE / "reference" / "pipeline"
OUT = HERE / "out"
DATA = HERE / "data"
TASK_FILES = HERE / "task_files"
VISIBLE = HERE / "visible_tests"
# Task A is not submitted; it is built outside tasks/ so check_submission.py sees one task.
TASKS = {"reconcile": REPO / "backup_tasks" / "ledger-reconcile",
         "conflicts": REPO / "tasks" / "ledger-conflicts"}
HIDDEN_MONTHS = ["2026-07", "2026-11"]
VISIBLE_MONTH = "2026-03"
BASE_IMAGE = ("python:3.12.16-slim-bookworm"
              "@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337")

ENV = {**os.environ, "PYTHONTZPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}


def read_ref() -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(REF.glob("*.py"))}


def apply(files: dict[str, str], ids: list[str]) -> dict[str, str]:
    files = dict(files)
    for did in ids:
        for fname, old, new in DEFECTS[did]:
            n = files[fname].count(old)
            assert n == 1, f"{did}: old string occurs {n} times in {fname}: {old!r}"
            files[fname] = files[fname].replace(old, new)
    return files


def write_pkg(dest: Path, files: dict[str, str]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name, text in files.items():
        (dest / name).write_text(text)


def datasets() -> dict[str, tuple[Path, str]]:
    """name -> (input dir, month)"""
    out = {}
    for m in ["2026-03", "2026-07", "2026-11"]:
        out[f"month-{m}"] = (DATA / "months" / m, m)
    for p in sorted((DATA / "probes").iterdir()):
        out[p.name] = (p / "input", (p / "month.txt").read_text().strip())
    return out


def run_pipeline(app: Path, inp: Path, month: str, out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    proc = subprocess.run(
        [sys.executable, "-m", "pipeline.cli", "--data", str(inp), "--month", month, "--out", str(out)],
        cwd=app, env=ENV, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"{app} on {inp} exited {proc.returncode}: {proc.stderr}"


def build_variants() -> dict[str, Path]:
    ref = read_ref()
    variants = {"reference": ref, "baseline": apply(ref, sorted(DEFECTS))}
    for did in sorted(DEFECTS):
        variants[f"mutants/{did}"] = apply(ref, [did])
    apps = {}
    for name, files in variants.items():
        app = OUT / "apps" / name
        write_pkg(app / "pipeline", files)
        apps[name] = app
    return apps


def run_all(apps: dict[str, Path]) -> None:
    for name, app in apps.items():
        for ds, (inp, month) in datasets().items():
            run_pipeline(app, inp, month, OUT / "runs" / name / ds)


def controls(report: Path, dest: Path) -> None:
    totals: dict[tuple[str, str], list[int]] = {}
    with open(report, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            acc = totals.setdefault((row["merchant_id"], row["currency"]), [0, 0])
            acc[0] += int(row["net_minor"])
            acc[1] += int(row["payment_count"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["merchant_id", "currency", "net_minor", "payment_count"])
        for (mid, ccy), (net, count) in sorted(totals.items()):
            w.writerow([mid, ccy, net, count])


DOCKERFILE = """FROM {image}
ENV PYTHONTZPATH="" PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir {pins}
WORKDIR /app
COPY app/ /app/
"""

TASK_TOML = """schema_version = "1.3"
artifacts = []

[task]
name = "cs329z/{name}"
description = "{description}"
keywords = {keywords}

[metadata]
difficulty = "hard"
category = "debugging"
tags = {tags}

[verifier]
timeout_sec = 300.0
collect = []

[verifier.env]

[agent]
timeout_sec = 1800.0

[environment]
network_mode = "public"
build_timeout_sec = 600.0
os = "linux"
mcp_servers = []

[environment.env]

[solution.env]
"""

TEST_SH = """#!/bin/bash
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /logs/verifier
if python "$HERE/verify.py" --app /app --tests "$HERE" --task {task}; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
"""

SOLVE_SH = """#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
rm -rf /app/pipeline
cp -r "$HERE/pipeline" /app/pipeline
"""

META = {
    "reconcile": dict(
        name="ledger-reconcile",
        description="Find and fix every deviation from a written specification in a payments-settlement pipeline, using only coarse monthly control totals as a signal.",
        keywords='["debugging", "specification", "finance", "python"]',
        tags='["root-cause-analysis", "spec-conformance", "hidden-tests"]',
    ),
    "conflicts": dict(
        name="ledger-conflicts",
        description="Fix a payments-settlement pipeline to conform to its specification when some tests in the legacy suite (unannounced) contradict that specification.",
        keywords='["debugging", "specification", "testing", "python"]',
        tags='["spec-conformance", "test-audit", "hidden-tests"]',
    ),
}


def write_task(kind: str, apps: dict[str, Path]) -> None:
    task = TASKS[kind]
    for sub in ("environment", "tests", "solution"):
        if (task / sub).exists():
            shutil.rmtree(task / sub)
    meta = META[kind]
    task.mkdir(parents=True, exist_ok=True)
    (task / "task.toml").write_text(TASK_TOML.format(**meta))
    shutil.copy(TASK_FILES / f"instruction_{kind}.md", task / "instruction.md")

    env = task / "environment"
    app = env / "app"
    app.mkdir(parents=True)
    pins = "tzdata==2025.2" + (" pytest==8.3.4" if kind == "conflicts" else "")
    (env / "Dockerfile").write_text(DOCKERFILE.format(image=BASE_IMAGE, pins=pins))
    shutil.copy(HERE / "SPEC.md", app / "SPEC.md")
    shutil.copytree(apps["baseline"] / "pipeline", app / "pipeline")
    shutil.copytree(DATA / "months" / VISIBLE_MONTH, app / "data" / VISIBLE_MONTH)
    if kind == "reconcile":
        controls(OUT / "runs" / "reference" / f"month-{VISIBLE_MONTH}" / "report.csv",
                 app / "controls" / f"{VISIBLE_MONTH}.csv")
    else:
        shutil.copytree(VISIBLE / "tests", app / "tests")

    tests = task / "tests"
    tests.mkdir()
    (tests / "test.sh").write_text(TEST_SH.format(task=kind))
    (tests / "test.sh").chmod(0o755)
    shutil.copy(TASK_FILES / "verify.py", tests / "verify.py")
    for m in HIDDEN_MONTHS:
        shutil.copytree(DATA / "months" / m, tests / "months" / m / "input")
        shutil.copytree(OUT / "runs" / "reference" / f"month-{m}", tests / "months" / m / "expected")
    for p in sorted((DATA / "probes").iterdir()):
        shutil.copytree(p / "input", tests / "probes" / p.name / "input")
        shutil.copy(p / "month.txt", tests / "probes" / p.name / "month.txt")
        shutil.copytree(OUT / "runs" / "reference" / p.name, tests / "probes" / p.name / "expected")
    if kind == "conflicts":
        shutil.copytree(VISIBLE / "tests", tests / "visible_original")
        shutil.copy(VISIBLE / "expected_conflicts.json", tests / "expected_conflicts.json")

    sol = task / "solution"
    sol.mkdir()
    solve = SOLVE_SH
    (sol / "solve.sh").write_text(solve)
    (sol / "solve.sh").chmod(0o755)
    shutil.copytree(apps["reference"] / "pipeline", sol / "pipeline")


def main() -> None:
    apps = build_variants()
    run_all(apps)
    for kind in TASKS:
        write_task(kind, apps)
    print("built:", ", ".join(str(t.relative_to(REPO)) for t in TASKS.values()))


if __name__ == "__main__":
    main()
