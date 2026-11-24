# Authoring code for `tasks/ledger-conflicts`

Nothing in this folder is copied into the agent's environment. It produces the task.

| Path | Purpose |
| --- | --- |
| `reference/pipeline/` | Correct pipeline (becomes the oracle in `solution/pipeline/`) |
| `SPEC.md` | Shipped verbatim as `/app/SPEC.md` |
| `defects.py` | The 12 planted defects as exact string edits; all applied = the agent's starting code |
| `gen_data.py`, `gen_probes.py` | Deterministic month datasets and the 12 single-rule probes (output in `data/`) |
| `visible_tests/` | The visible pytest suite, the list of wrong tests, and `CONFLICTS.md` (the SPEC.md sentence each wrong test contradicts) |
| `task_files/` | `verify.py` (shared verifier) and the instruction files |
| `build_tasks.py` | Builds baseline, mutants and expected outputs, then writes the task directories |
| `validate.py` | Probe matrix, coverage, shortcut and near-miss checks, suite outcomes, per-temptation checks |

`build_tasks.py` also writes the unsubmitted sibling task (`ledger-reconcile`, controls instead of
tests) to `backup_tasks/`, which is git-ignored.

## Rebuild and validate

Python 3.12 with `tzdata==2025.2` and `pytest==8.3.4`, and `PYTHONTZPATH=""`:

    python gen_data.py && python gen_probes.py && python build_tasks.py && python validate.py

The build is deterministic: rerunning it leaves `tasks/ledger-conflicts/` byte-for-byte unchanged.
