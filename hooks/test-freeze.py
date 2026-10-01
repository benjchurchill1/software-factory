#!/usr/bin/env python3
"""PreToolUse hook: refuse an edit to a committed test. Does nothing until configured.

WHY THIS EXISTS. With nobody reviewing every wave, a weakened test is the one
change no one else will notice: the barrier goes green, the verifier reads a
passing suite, and the record afterwards looks like diligence. The loop's rule
is that a committed test is superseded, never edited. This hook makes breaking
that rule fail at the moment it is tried, not at the barrier.

CONTRACT
  configured  the edited file sits inside a checkout (a repo or a lane
              worktree) whose root holds `.claude/test-freeze.json`, committed
              by software-factory at gate 12:
                {"tests": ["tests/**", "**/*.spec.ts", "scripts/checks/**"],
                 "frozen": ["scripts/guards.py", "scripts/pre-barrier.sh",
                            "scripts/preflight.sh"],
                 "base": "<the trunk branch>",
                 "supersessions": "docs/build/supersessions.jsonl"}
              No config, no effect: every other project is untouched.
  frozen      a path matching one of `tests` that already exists on `base`.
              A test file the lane created itself is not frozen, so a builder
              can write and rework its own new tests freely. Check scripts
              belong in `tests` too: a weakened check is a weakened test. The
              `frozen` paths (by default the ratchet's own scripts) are frozen
              the same way, and are never superseded either.
  refused     Edit, Write, MultiEdit or NotebookEdit on a frozen path, or on
              the config file itself. The refusal says how to supersede.
  not a lock  a shell command can still change a file. The guarantee is the
              `tests` line of pre-barrier.sh, which fails any merge that edits
              a committed test or deletes one without a supersession record.
              This hook is the early warning that saves the lane a stage.

Any error inside the hook allows the edit: the pre-barrier line still holds,
and a broken hook must not stop every edit in the project.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONFIG = Path(".claude") / "test-freeze.json"
DEFAULT_FROZEN = ["scripts/guards.py", "scripts/pre-barrier.sh", "scripts/preflight.sh"]


def allow():
    sys.exit(0)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    sys.exit(0)


def glob_regex(pattern):
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


def find_root(path):
    for d in [path.parent, *path.parent.parents]:
        if (d / CONFIG).is_file():
            return d
    return None


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        allow()
    if payload.get("tool_name") not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        allow()
    ti = payload.get("tool_input") or {}
    raw = ti.get("file_path") or ti.get("notebook_path")
    if not raw:
        allow()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(payload.get("cwd") or os.getcwd()) / path
    path = Path(os.path.realpath(path))
    root = find_root(path)
    if root is None:
        allow()
    rel = path.relative_to(root).as_posix()
    if rel == CONFIG.as_posix():
        deny(f"{rel} defines the test freeze and is not edited by a build seat. "
             "A change to it is the owner's, and pre-barrier.sh fails any merge that makes one.")
    try:
        cfg = json.loads((root / CONFIG).read_text())
        globs = [str(g) for g in cfg["tests"]]
        base = str(cfg["base"])
    except (OSError, ValueError, KeyError, TypeError):
        allow()
    register = str(cfg.get("supersessions") or "docs/build/supersessions.jsonl")
    frozen = [str(g) for g in cfg.get("frozen", DEFAULT_FROZEN)]
    is_frozen = any(glob_regex(g).match(rel) for g in frozen)
    if not is_frozen and not any(glob_regex(g).match(rel) for g in globs):
        allow()
    committed = subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"{base}:{rel}"],
                               capture_output=True, timeout=5).returncode == 0
    if not committed:
        allow()
    if is_frozen:
        deny(f"{rel} is part of the ratchet that keeps tests and checks from getting looser, "
             "and no build seat edits it. A change to it is the owner's; pre-barrier.sh fails "
             "any merge that makes one.")
    deny(f"{rel} is a committed test (it exists on {base}). Committed tests are superseded, "
         "never edited. If it is genuinely wrong, write a successor that names "
         f"{Path(rel).name} in its header with an assertion map, and append "
         '{"predecessor": "' + rel + '", "successor": "<new path>", "why": "...", "wave": N} '
         f"to {register}. The trunk owner deletes the predecessor at the barrier. If the test "
         "is right, fix the implementation instead. A red test under contention is not a "
         "refutation: check for contention and re-run it alone first.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # fail open: the pre-barrier line is the guarantee
        sys.exit(0)
