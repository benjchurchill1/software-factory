#!/usr/bin/env python3
"""The mechanical guards the pre-barrier and pre-flight scripts run.

    guards.py ledger   <path> --kind checks|together --trunk <branch>
    guards.py checks   <path>
    guards.py tests    --trunk <branch> [--head <ref>] [--config .claude/test-freeze.json]
                       (also fails any change to the config's "frozen" paths)
    guards.py panels   --journal <file> --wave <n> --rounds <k> [--max-stages 3] <lane>=<commit>...
    guards.py together <path> --queue <file>
    guards.py pace     --journal <file> --wave <n> --mode wave|barrier [--limit x]
                       [--reserve x] [--default-estimate x] [--remaining x --resets-at <iso>]
    guards.py auth     --need-minutes <m> [--remaining-seconds <s>|unknown]
                       [--since <file> --lifetime-hours <h>]

Copied into the project as scripts/guards.py by software-factory (gates 11 and
12). Standard library only. Run from the repository root, or pass --root.

Each command prints ONE line, `VERDICT name: detail`, and exits with the
verdict's code, so the calling script can print it as one of its own lines:

    PASS 0 · FAIL 1 · PAUSE 10 · STOP 20

WHY THESE ARE MECHANICAL. With nobody reviewing every wave, three things only
hold if a script refuses to let them slip: the checks get stricter and never
quietly looser (the ledgers), a committed test is superseded and never edited
(the test freeze), and a lane is finished only when fresh panels agree at the
same commit (clean rounds). The other two, pace and auth, exist so the build
sees an expired login or a spent usage window coming, and stops or pauses at a
clean point instead of dying in the middle of a barrier.

The ledgers are append-only JSON lines:

    {"op": "add", "id": "C-7", "source": "<evidence path>", ...}
    {"op": "retire", "id": "C-7", "ruling": "<decision file that names C-7>"}

A `checks` entry also has "class" (the failure class, in one sentence) and may
have "run": a script under scripts/checks/ that exits non-zero when the class
recurs. A `together` entry has "rows": the two row IDs that must not share a
wave. Nothing is ever edited or deleted; a retirement is its own line, and it
must cite a ruling file that exists and names the entry.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CODES = {"PASS": 0, "FAIL": 1, "PAUSE": 10, "STOP": 20}
RUN_PATH = re.compile(r"^scripts/checks/[a-z0-9][a-z0-9_-]*\.sh$")
# Files no merge may change at all: the ratchet's own machinery. Without this a
# lane could edit guards.py to print PASS, or pre-barrier.sh to skip a line.
DEFAULT_FROZEN = ["scripts/guards.py", "scripts/pre-barrier.sh", "scripts/preflight.sh"]


def verdict(kind, name, detail, extra=None):
    print(f"{kind} {name}: {detail}")
    if extra:
        print(extra)
    sys.exit(CODES[kind])


def git(root, *args):
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return out.returncode, out.stdout


def lines_of(text):
    return [l for l in text.splitlines() if l.strip()]


def glob_regex(pattern):
    """A path glob with `**` (any depth), `*` and `?`, matched against a repo-relative path."""
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif c == "*":
            out, i = out + "[^/]*", i + 1
        elif c == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(c), i + 1
    return re.compile("^" + out + "$")


def matches(path, globs):
    return any(glob_regex(g).match(path) for g in globs)


def parse_at(value):
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def now_from(a):
    return parse_at(a.now) if getattr(a, "now", None) else dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def journal(path):
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return None
    events = []
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    return events


# ── the ledgers ─────────────────────────────────────────────────────────────
def read_ledger(root, rel, kind):
    """Parse a ledger. Returns (entries, active ids, problems)."""
    problems, added, retired, entries = [], {}, set(), []
    try:
        text = (Path(root) / rel).read_text()
    except OSError:
        return [], {}, []
    for n, line in enumerate(lines_of(text), 1):
        try:
            e = json.loads(line)
        except ValueError:
            problems.append(f"line {n} is not JSON")
            continue
        if not isinstance(e, dict) or e.get("op") not in ("add", "retire") or not e.get("id"):
            problems.append(f"line {n} needs op add|retire and an id")
            continue
        eid = str(e["id"])
        if e["op"] == "add":
            if eid in added:
                problems.append(f"{eid} added twice")
            if not e.get("source"):
                problems.append(f"{eid} has no source (the evidence that taught it)")
            if kind == "checks":
                if not e.get("class"):
                    problems.append(f"{eid} has no class")
                if e.get("run") and not RUN_PATH.match(str(e["run"])):
                    problems.append(f"{eid} run must be a script under scripts/checks/")
                elif e.get("run") and not (Path(root) / e["run"]).is_file():
                    problems.append(f"{eid} run {e['run']} does not exist")
            if kind == "together":
                rows = e.get("rows")
                if not (isinstance(rows, list) and len(rows) == 2 and all(isinstance(r, str) and r for r in rows)):
                    problems.append(f"{eid} rows must be two row IDs")
            added[eid] = e
        else:
            ruling = str(e.get("ruling") or "")
            if eid not in added:
                problems.append(f"{eid} retired before it was added")
            elif eid in retired:
                problems.append(f"{eid} retired twice")
            if not ruling:
                problems.append(f"{eid} retired with no ruling")
            else:
                try:
                    body = (Path(root) / ruling).read_text(errors="replace")
                except OSError:
                    problems.append(f"{eid} retired by {ruling}, which does not exist")
                else:
                    if not re.search(r"(?<![\w-])" + re.escape(eid) + r"(?![\w-])", body):
                        problems.append(f"{eid} retired by {ruling}, which does not name it")
            retired.add(eid)
        entries.append(e)
    active = {k: v for k, v in added.items() if k not in retired}
    return entries, active, problems


def cmd_ledger(a):
    name = f"{a.kind}-ledger"
    root = Path(a.root)
    current_path = root / a.path
    rc, base_text = git(root, "show", f"{a.trunk}:{a.path}")
    base = lines_of(base_text) if rc == 0 else []
    if not current_path.exists():
        if base:
            verdict("FAIL", name, f"{a.path} was deleted; it is append-only")
        verdict("PASS", name, f"{a.path} not started yet")
    current = lines_of(current_path.read_text())
    if current[:len(base)] != base:
        verdict("FAIL", name, f"{a.path} was edited, not appended to: its first {len(base)} "
                              f"lines must equal {a.trunk}'s")
    _, active, problems = read_ledger(root, a.path, a.kind)
    if problems:
        verdict("FAIL", name, "; ".join(problems))
    verdict("PASS", name, f"{len(active)} active, {len(current) - len(base)} new lines, append-only")


def cmd_checks(a):
    root = Path(a.root)
    _, active, problems = read_ledger(root, a.path, "checks")
    if problems:
        verdict("FAIL", "checks", "ledger invalid: " + "; ".join(problems))
    runnable = {k: v for k, v in active.items() if v.get("run")}
    failed = []
    for eid, e in runnable.items():
        try:
            out = subprocess.run(["bash", str(root / e["run"])], cwd=root, capture_output=True,
                                 text=True, timeout=int(e.get("timeout_s", 600)))
            sys.stderr.write(out.stdout + out.stderr)
            if out.returncode != 0:
                failed.append(eid)
        except subprocess.TimeoutExpired:
            failed.append(eid + " (timeout)")
    if failed:
        verdict("FAIL", "checks", "recurred: " + ", ".join(failed))
    verdict("PASS", "checks", f"{len(runnable)} run, {len(active) - len(runnable)} by lens only")


# ── the test freeze ─────────────────────────────────────────────────────────
def cmd_tests(a):
    root = Path(a.root)
    rc, cfg_text = git(root, "show", f"{a.trunk}:{a.config}")
    if rc != 0:
        verdict("FAIL", "tests", f"{a.config} is not on {a.trunk}; the freeze is not configured")
    try:
        cfg = json.loads(cfg_text)
        globs = [str(g) for g in cfg["tests"]]
    except (ValueError, KeyError, TypeError):
        verdict("FAIL", "tests", f"{a.config} on {a.trunk} needs a \"tests\" list of globs")
    register = str(cfg.get("supersessions") or "docs/build/supersessions.jsonl")
    frozen = [str(g) for g in cfg.get("frozen", DEFAULT_FROZEN)]
    rc, diff = git(root, "diff", "--name-status", "--no-renames", f"{a.trunk}...{a.head}")
    if rc != 0:
        verdict("FAIL", "tests", f"cannot diff {a.trunk}...{a.head}")
    problems, deleted, edited, touched = [], [], [], []
    for line in diff.splitlines():
        status, _, path = line.partition("\t")
        if path in (a.config,):
            problems.append(f"{a.config} changed")
        elif matches(path, frozen):
            touched.append(path)
        elif matches(path, globs) and status[:1] in ("M", "T"):
            edited.append(path)
        elif matches(path, globs) and status[:1] == "D":
            deleted.append(path)
    if touched:
        problems.append("frozen files changed: " + ", ".join(touched))
    if edited:
        problems.append("committed tests edited: " + ", ".join(edited))
    rc, base_reg = git(root, "show", f"{a.trunk}:{register}")
    base_lines = lines_of(base_reg) if rc == 0 else []
    try:
        reg_lines = lines_of((root / register).read_text())
    except OSError:
        reg_lines = []
    if reg_lines[:len(base_lines)] != base_lines:
        problems.append(f"{register} was edited, not appended to")
    records = {}
    for line in reg_lines:
        try:
            r = json.loads(line)
            records[str(r["predecessor"])] = str(r["successor"])
        except (ValueError, KeyError, TypeError):
            problems.append(f"{register} has a line without predecessor and successor")
    for path in deleted:
        succ = records.get(path)
        if not succ:
            problems.append(f"{path} deleted with no supersession record")
        elif not (root / succ).is_file():
            problems.append(f"{path} superseded by {succ}, which does not exist")
        elif Path(path).name not in (root / succ).read_text(errors="replace"):
            problems.append(f"{succ} does not name its predecessor {Path(path).name}")
    if problems:
        verdict("FAIL", "tests", "; ".join(problems))
    verdict("PASS", "tests", f"no committed test edited; {len(deleted)} superseded with records")


# ── clean rounds ────────────────────────────────────────────────────────────
def cmd_panels(a):
    events = journal(a.journal)
    if events is None:
        verdict("FAIL", "panels", f"journal not readable: {a.journal}")
    short = []
    for spec in a.lanes:
        lane, _, commit = spec.partition("=")
        rounds = [e for e in events if e.get("type") == "panel" and str(e.get("wave")) == str(a.wave)
                  and str(e.get("lane")) == lane]
        stages = [int(e.get("stage") or 1) for e in rounds if str(e.get("stage") or "1").isdigit()]
        if stages and max(stages) > a.max_stages:
            short.append(f"{lane} ran stage {max(stages)} (cap {a.max_stages})")
            continue
        clean = 0
        for e in reversed(rounds):
            if e.get("verdict") != "clean" or str(e.get("commit")) != commit:
                break
            clean += 1
        if clean < a.rounds:
            last = rounds[-1] if rounds else None
            why = ("no panel rounds" if not last else
                   "tip moved after its last panel" if str(last.get("commit")) != commit else
                   f"{clean} clean in a row at its tip")
            short.append(f"{lane}: {why}, needs {a.rounds}")
    if short:
        verdict("FAIL", "panels", "; ".join(short))
    verdict("PASS", "panels", f"{len(a.lanes)} lanes, each {a.rounds} clean rounds at its tip")


# ── never together ──────────────────────────────────────────────────────────
def cmd_together(a):
    root = Path(a.root)
    _, active, problems = read_ledger(root, a.path, "together")
    if problems:
        verdict("FAIL", "together", "ledger invalid: " + "; ".join(problems))
    try:
        queue = Path(a.queue).read_text(errors="replace")
    except OSError:
        verdict("FAIL", "together", f"queue not readable: {a.queue}")

    def listed(row):
        return re.search(r"(?<![\w-])" + re.escape(row) + r"(?![\w-])", queue)

    clash = [f"{eid} ({' + '.join(e['rows'])})" for eid, e in active.items()
             if all(listed(r) for r in e["rows"])]
    if clash:
        verdict("FAIL", "together", "queue holds rows that must not share a wave: " + ", ".join(clash))
    verdict("PASS", "together", f"{len(active)} pairs kept apart")


# ── pace: the usage ledger ──────────────────────────────────────────────────
def cmd_pace(a):
    events = journal(a.journal)
    if events is None:
        verdict("STOP", "usage", f"journal not readable: {a.journal}; usage is unknown")
    now = now_from(a)
    per_wave, barrier, spent = {}, {}, 0.0
    for e in events:
        if e.get("type") != "usage":
            continue
        try:
            amount, wave = float(e.get("amount")), int(e.get("wave"))
        except (TypeError, ValueError):
            continue
        spent += amount
        per_wave[wave] = per_wave.get(wave, 0.0) + amount
        if e.get("phase") == "barrier":
            barrier[wave] = barrier.get(wave, 0.0) + amount
    source = per_wave if a.mode == "wave" else barrier
    history = [source[w] for w in sorted(source) if w < a.wave][-3:]
    estimate = max(history) if history else a.default_estimate
    if estimate is None:
        verdict("STOP", "usage", "no usage recorded yet and no default estimate")
    reserve = a.reserve or 0.0
    detail = f"next {a.mode} about {estimate:g} (largest of last {len(history)}), spent {spent:g}"
    if a.limit is not None and spent + estimate + reserve > a.limit:
        verdict("STOP", "usage", f"budget-exhausted: {detail}, limit {a.limit:g}, reserve {reserve:g}")
    limits = [parse_at(e.get("resets_at")) for e in events if e.get("type") == "rate_limit"]
    limits = [t for t in limits if t and t > now]
    if limits:
        until = max(limits)
        verdict("PAUSE", "usage", f"a usage limit was hit; it resets at {iso(until)}",
                f"resume_at {iso(until)}")
    if a.remaining is not None:
        if a.remaining < estimate + reserve:
            until = parse_at(a.resets_at) if a.resets_at else None
            if not until:
                verdict("STOP", "usage", f"window has {a.remaining:g} left, {detail}, and no reset time")
            verdict("PAUSE", "usage", f"window has {a.remaining:g} left, {detail}; resets {iso(until)}",
                     f"resume_at {iso(until)}")
        detail += f", window {a.remaining:g} left"
    verdict("PASS", "usage", detail)


# ── auth: the login ─────────────────────────────────────────────────────────
def cmd_auth(a):
    now = now_from(a)
    left = None
    if a.remaining_seconds not in (None, "", "unknown"):
        try:
            left = float(a.remaining_seconds) / 60
        except ValueError:
            left = None
    if left is None and a.since and a.lifetime_hours:
        try:
            since = parse_at(Path(a.since).read_text().strip())
        except OSError:
            since = None
        if since:
            left = (since + dt.timedelta(hours=a.lifetime_hours) - now).total_seconds() / 60
    if left is None:
        verdict("STOP", "auth", "cannot tell when the login expires: record the login time "
                                "with `date -u +%FT%TZ > <run state>/auth-at` after logging in")
    if left < a.need_minutes:
        verdict("STOP", "auth", f"auth-expiring: about {max(left, 0):.0f} min left, "
                                f"the next step needs {a.need_minutes:g}")
    verdict("PASS", "auth", f"about {left:.0f} min left, the next step needs {a.need_minutes:g}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=os.getcwd())
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ledger")
    s.add_argument("path")
    s.add_argument("--kind", choices=["checks", "together"], required=True)
    s.add_argument("--trunk", required=True)
    s = sub.add_parser("checks")
    s.add_argument("path")
    s = sub.add_parser("tests")
    s.add_argument("--trunk", required=True)
    s.add_argument("--head", default="HEAD")
    s.add_argument("--config", default=".claude/test-freeze.json")
    s = sub.add_parser("panels")
    s.add_argument("--journal", required=True)
    s.add_argument("--wave", required=True)
    s.add_argument("--rounds", type=int, required=True)
    s.add_argument("--max-stages", type=int, default=3)
    s.add_argument("lanes", nargs="+")
    s = sub.add_parser("together")
    s.add_argument("path")
    s.add_argument("--queue", required=True)
    s = sub.add_parser("pace")
    s.add_argument("--journal", required=True)
    s.add_argument("--wave", type=int, required=True)
    s.add_argument("--mode", choices=["wave", "barrier"], required=True)
    s.add_argument("--limit", type=float)
    s.add_argument("--reserve", type=float)
    s.add_argument("--default-estimate", type=float)
    s.add_argument("--remaining", type=float)
    s.add_argument("--resets-at")
    s.add_argument("--now")
    s = sub.add_parser("auth")
    s.add_argument("--need-minutes", type=float, required=True)
    s.add_argument("--remaining-seconds")
    s.add_argument("--since")
    s.add_argument("--lifetime-hours", type=float)
    s.add_argument("--now")
    a = p.parse_args()
    {"ledger": cmd_ledger, "checks": cmd_checks, "tests": cmd_tests, "panels": cmd_panels,
     "together": cmd_together, "pace": cmd_pace, "auth": cmd_auth}[a.cmd](a)


if __name__ == "__main__":
    main()
