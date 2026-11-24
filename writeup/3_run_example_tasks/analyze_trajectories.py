"""Section 3.4: trajectory analysis figures for the three mini-SWE-agent runs.

Run from the repository root:

    uv run python writeup/3_run_example_tasks/analyze_trajectories.py

Produces, in writeup/3_run_example_tasks/:
  - bash-command-usage.png           which CLI programs each agent invoked
  - effort-distribution.png          share of actions per activity category
  - exploration-to-implementation.png  per-step activity timeline with the
                                     first edit of a deliverable file marked

Every agent action is one `execute_bash` command taken from the ATIF
trajectory at <job>/<trial>/agent/trajectory.json.
"""

from __future__ import annotations

import json
import re
import shlex
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"

# job folder -> (display name, regex matching the task's deliverable file(s))
TASKS = {
    "humaneval-agent": ("HumanEval/0", r"/app/humaneval_0\.py|humaneval_0\.py"),
    "swebench-django-11099": ("SWE-bench django-11099", r"django/contrib/auth/validators\.py"),
    "terminal-bench-model-extraction": ("Terminal-Bench model-extraction", r"/app/steal\.py|(?<![\w/])steal\.py"),
}

SUBMIT = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"

# ----------------------------------------------------------------- categories
# Each action (one bash command line) gets exactly one category. Rules are
# checked in the order below; the first rule that fires wins.
#   submit      the scaffold's completion sentinel
#   edit        writes/reverts a file: heredoc or > redirect into a file,
#               sed -i, patch, git apply/checkout/restore, Python open(..., "w")
#   run tests   runs a test runner (pytest, doctest, unittest, Django
#               runtests.py) or executes a script file (python foo.py)
#   experiment  an inline Python snippet (python -c "..."): ad-hoc probes,
#               reproductions, and one-off checks written on the fly
#   setup       installs packages (pip/apt/conda install)
#   inspect     only read-only programs (cat, ls, grep, find, sed -n, git
#               grep/diff/status, which, python --version, ...)
#   other       anything else (e.g. rm)
CATEGORIES = ["inspect", "experiment", "edit", "run tests", "setup", "submit", "other"]
COLORS = {
    "inspect": "#4C78A8",
    "experiment": "#72B7B2",
    "edit": "#F58518",
    "run tests": "#54A24B",
    "setup": "#B279A2",
    "submit": "#9D9D9D",
    "other": "#D8B5A5",
}

WRITE_PATTERNS = [
    r"<<-?\s*['\"]?\w+['\"]?\s*>\s*[^\s&|;]+",  # cat <<'EOF' > file
    r"cat\s*>\s*[^\s&|;]+",  # cat > file <<EOF
    r"(?<![0-9&>])>\s*(?!/dev/null|&)[^\s&|;]+\.(py|txt|json|diff|patch|sh|npy|cfg|toml)\b",
    r"open\([^)]*['\"][wa]b?['\"]",  # Python open(path, "w")
    r"\.write_text\(|np\.save\(",
]
EDIT_PROGRAMS = {"patch"}
EDIT_GIT_SUBCOMMANDS = {"apply", "checkout", "restore", "reset", "stash"}
TEST_PROGRAMS = {"pytest", "runtests.py", "tox", "nosetests"}
INSPECT_PROGRAMS = {
    "cat", "ls", "grep", "rg", "find", "head", "tail", "sed", "nl", "wc", "less",
    "tree", "awk", "diff", "git", "file", "stat", "pwd", "which", "echo", "du",
    "conda", "env", "printenv", "uname", "whoami", "id", "ps", "df", "type",
}
OPERATORS = {"|", "||", "&&", ";", "&", ";;"}
WRAPPERS = {"sudo", "time", "timeout", "env", "nohup", "exec"}


def strip_bodies(command: str) -> str:
    """Remove heredoc bodies and inline `-c` snippet bodies so their contents
    are not mistaken for shell commands."""
    command = re.sub(r"(<<-?\s*['\"]?(\w+)['\"]?[^\n]*)\n.*?\n\2\b", r"\1", command, flags=re.S)
    command = re.sub(r"(\s-c\s+)(\"(?:\\.|[^\"\\])*\"|'[^']*')", r"\1SNIPPET", command, flags=re.S)
    return command


def simple_commands(command: str) -> list[list[str]]:
    """Quote-aware split of a bash line into simple commands (token lists),
    breaking on | || && ; & and on newlines outside quotes."""
    out: list[list[str]] = []
    for line in strip_bodies(command).split("\n"):
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:  # unbalanced quotes: fall back to a naive split
            tokens = re.split(r"\s+", line.strip())
        current: list[str] = []
        for tok in tokens:
            if tok in OPERATORS:
                if current:
                    out.append(current)
                current = []
            else:
                current.append(tok)
        if current:
            out.append(current)
    return out


def program_and_args(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Skip VAR=value prefixes, `cd`-less wrappers like sudo/timeout, and
    return (program basename, remaining args)."""
    i = 0
    while i < len(tokens) and (
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[i]) or tokens[i] in WRAPPERS
    ):
        i += 1
    if i >= len(tokens):
        return None, []
    name = tokens[i].rsplit("/", 1)[-1]
    if re.fullmatch(r"python[0-9.]*", name):
        name = "python"
    return name, tokens[i + 1 :]


def program_label(tokens: list[str]) -> str | None:
    """Label used in the command-usage figure; python is split by usage mode."""
    name, args = program_and_args(tokens)
    if name is None or name == "cd":
        return None
    if name == "python":
        if "-c" in args:
            return "python -c (inline)"
        if "-m" in args:
            return f"python -m {args[args.index('-m') + 1]}" if args.index("-m") + 1 < len(args) else "python -m"
        scripts = [a for a in args if a.endswith(".py")]
        if scripts:
            return f"python {scripts[0].rsplit('/', 1)[-1]}"
        return "python (other)"
    if name == "git" and args:
        return f"git {args[0]}"
    return name


def categorize(command: str) -> str:
    if SUBMIT in command:
        return "submit"
    cmds = [program_and_args(t) for t in simple_commands(command)]
    cmds = [(n, a) for n, a in cmds if n and n != "cd"]
    if any(re.search(p, command) for p in WRITE_PATTERNS):
        return "edit"
    for name, args in cmds:
        if name in EDIT_PROGRAMS or (name == "sed" and any(a.startswith("-i") for a in args)):
            return "edit"
        if name == "git" and args and args[0] in EDIT_GIT_SUBCOMMANDS:
            return "edit"
    for name, args in cmds:
        if name in TEST_PROGRAMS or name.endswith(".py"):
            return "run tests"
        if name == "python":
            if "-m" in args and args[args.index("-m") + 1 : args.index("-m") + 2] in (["pytest"], ["doctest"], ["unittest"]):
                return "run tests"
            if "-c" not in args and any(a.endswith(".py") for a in args):
                return "run tests"
    if any(name == "python" and "-c" in args for name, args in cmds):
        return "experiment"
    for name, args in cmds:
        if name in {"pip", "pip3", "apt", "apt-get", "conda", "uv"} and "install" in args:
            return "setup"
    if cmds and all(
        n in INSPECT_PROGRAMS or (n == "python" and set(a) <= {"--version", "-V"})
        for n, a in cmds
    ):
        return "inspect"
    return "other"


def edits_deliverable(command: str, deliverable_re: str) -> bool:
    """True if this command writes to the task's deliverable file."""
    if categorize(command) != "edit":
        return False
    return re.search(deliverable_re, command) is not None


# --------------------------------------------------------------------- loading
def load_actions(job: str) -> list[str]:
    trials = [p for p in (ARTIFACTS / job).iterdir() if p.is_dir() and "__" in p.name]
    if len(trials) != 1:
        raise SystemExit(f"{job}: expected one trial folder, found {len(trials)}")
    traj = json.loads((trials[0] / "agent" / "trajectory.json").read_text())
    actions = []
    for step in traj["steps"]:
        for call in step.get("tool_calls") or []:
            cmd = (call.get("arguments") or {}).get("command")
            if cmd is not None:
                actions.append(cmd)
    return actions


def main() -> None:
    data = {}
    for job, (label, deliverable) in TASKS.items():
        actions = load_actions(job)
        cats = [categorize(a) for a in actions]
        first_impl = next(
            (i for i, a in enumerate(actions) if edits_deliverable(a, deliverable)), None
        )
        programs = Counter(
            p
            for a in actions
            if SUBMIT not in a
            for p in (program_label(t) for t in simple_commands(a))
            if p
        )
        data[job] = dict(label=label, actions=actions, cats=cats, first_impl=first_impl, programs=programs)
        print(f"{label}: {len(actions)} actions, first deliverable edit at action "
              f"{None if first_impl is None else first_impl + 1}; {Counter(cats)}")

    labels = [d["label"] for d in data.values()]
    used = [c for c in CATEGORIES if any(c in d["cats"] for d in data.values())]

    # ------------------------------------------------ 1. bash-command-usage
    total = Counter()
    for d in data.values():
        total.update(d["programs"])
    top = [p for p, _ in total.most_common(14)]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    width = 0.27
    for k, d in enumerate(data.values()):
        xs = [i + (k - 1) * width for i in range(len(top))]
        ax.bar(xs, [d["programs"][p] for p in top], width, label=f'{d["label"]} ({len(d["actions"])} actions)')
    ax.set_xticks(range(len(top)))
    ax.set_xticklabels(top, rotation=30, ha="right", family="monospace")
    ax.set_ylabel("Invocations (count)")
    ax.set_title("Command-line programs invoked by mini-SWE-agent (Gemini 3.8 Flash), per task\n"
                 "each bash action is split on | && || ; into simple commands and each command's program is counted\n"
                 "(python is broken out by mode: inline -c snippet, -m module, or script file)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "bash-command-usage.png", dpi=160)
    plt.close(fig)

    # ----------------------------------------------- 2. effort-distribution
    fig, ax = plt.subplots(figsize=(10.5, 3.8))
    for row, d in enumerate(data.values()):
        n = len(d["cats"])
        counts = Counter(d["cats"])
        left = 0.0
        for cat in CATEGORIES:
            share = counts[cat] / n if n else 0
            if share:
                ax.barh(row, share, left=left, color=COLORS[cat], edgecolor="white")
                if share >= 0.06:
                    ax.text(left + share / 2, row, f"{counts[cat]}", ha="center", va="center",
                            color="white", fontsize=9, fontweight="bold")
                left += share
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels([f'{d["label"]}\n(n={len(d["cats"])} actions)' for d in data.values()])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("Share of agent actions (bar labels = action counts)")
    ax.set_title("How the agent distributed its effort, by activity category")
    ax.legend(handles=[Patch(color=COLORS[c], label=c) for c in used],
              ncol=len(used), loc="upper center", bbox_to_anchor=(0.4, -0.28), frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "effort-distribution.png", dpi=160)
    plt.close(fig)

    # ------------------------------------ 3. exploration-to-implementation
    fig, axes = plt.subplots(len(data), 1, figsize=(11, 1.35 * len(data) + 1.2), squeeze=False)
    for ax, d in zip(axes[:, 0], data.values()):
        n = len(d["cats"])
        for i, cat in enumerate(d["cats"]):
            ax.barh(0, 1, left=i + 0.5, color=COLORS[cat], edgecolor="white", linewidth=0.6)
        if d["first_impl"] is not None:
            x = d["first_impl"] + 0.5
            ax.axvline(x, color="black", lw=2)
            pct = d["first_impl"] / n
            right_half = pct > 0.5
            ax.annotate(f'first deliverable edit: action {d["first_impl"] + 1} of {n} '
                        f'({d["first_impl"]} actions = {pct:.0%} before it)',
                        xy=(x, 0.45), xytext=(-4 if right_half else 4, 0), textcoords="offset points",
                        fontsize=8.5, va="bottom", ha="right" if right_half else "left")
        else:
            ax.text(0.5, 0.45, "deliverable never edited", fontsize=8.5, va="bottom")
        ax.set_xlim(0.5, n + 0.5)
        ax.set_ylim(-0.5, 0.9)
        ax.set_yticks([])
        ax.set_title(d["label"], loc="left", fontsize=10)
        ax.spines[["top", "right", "left"]].set_visible(False)
    axes[-1, 0].set_xlabel("Agent action index (1 = first command)")
    fig.suptitle("Exploration → implementation: activity of every action; black line = first write to the task's deliverable file",
                 fontsize=10.5)
    fig.legend(handles=[Patch(color=COLORS[c], label=c) for c in used],
               ncol=len(used), loc="lower center", frameon=False)
    fig.tight_layout(rect=(0, 0.07, 1, 0.97))
    fig.savefig(HERE / "exploration-to-implementation.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
