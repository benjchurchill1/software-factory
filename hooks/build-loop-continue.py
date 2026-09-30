#!/usr/bin/env python3
"""Stop hook: keep an autonomous build-loop seat running. Does nothing until armed.

WHY THIS EXISTS. The loop seat ends its turn after a wave or a barrier and
nothing re-invokes it, so an autonomous run stops whenever the model decides it
has said enough. This hook blocks that stop, scoped to one repo, bounded, and
released by one file.

CONTRACT
  armed       an arming file exists for a repo whose `cwd_prefix` contains the
              stopping session's cwd, and it is under MAX_AGE_H old. Armings
              live in STATE_ROOT/<key>/armed.json, one directory per repo, so
              two builds on one machine never share a counter or a stop file.
              Write them with `arm.py`. A legacy STATE_ROOT/armed.json is still
              honoured. When several armings match, the longest prefix wins.
  identified  only a session whose transcript contains `marker` (a nonce from
              the loop's opening prompt), and which is not in
              `exclude_sessions`, is held. No marker, no hold.
  bounded     `max` (default 60) is a cap on CONSECUTIVE continuations without
              progress. Progress is any change to a branch tip in the repo (a
              lane commit, a barrier merge, a record commit) or to the mtime of
              a path listed in `progress_paths`. Progress resets the
              consecutive count. `max_total` (default 500) caps continuations
              per arming regardless of progress. Re-arming resets both.
  released    the seat (or a person) creates the arming's `stop` file, a cap is
              reached, the arming is older than MAX_AGE_H, or the arming file
              is deleted. A released stop is a real stop.

The block reason tells the seat to create its `stop` file when it halts on
purpose (done, stalled, or waiting on a person). That keeps a deliberate halt
distinguishable from drifting to a halt, which is the whole point.

Any error inside the hook allows the stop. A broken keep-alive must fail open
to a normal stop, never to an unbounded hold.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

STATE_ROOT = Path(os.environ.get("BUILD_LOOP_STATE_ROOT",
                                 Path.home() / ".claude" / "state" / "build-loop"))
MAX_AGE_H = 72
DEFAULT_MAX = 60
DEFAULT_MAX_TOTAL = 500
DEFAULT_PROMPT = "docs/prompts/build-loop.md"


def allow():
    sys.exit(0)  # exit 0 with no stdout: the session stops normally


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def real(p):
    return os.path.realpath(os.path.expanduser(str(p)))


def inside(child, parent):
    child, parent = real(child), real(parent)
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def armings():
    legacy = STATE_ROOT / "armed.json"
    found = [legacy] if legacy.is_file() else []
    if STATE_ROOT.is_dir():
        found += sorted(p for p in STATE_ROOT.glob("*/armed.json") if p.is_file())
    return found


def load(path):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def as_int(value, default, ceiling=100000):
    try:
        n = int(value)
        return n if 1 <= n <= ceiling else default
    except (TypeError, ValueError):
        return default


def fingerprint(repo, extra_paths):
    """What moves when the build makes progress. Unreadable parts hash as empty."""
    parts = []
    try:
        out = subprocess.run(["git", "-C", repo, "for-each-ref", "--format=%(objectname) %(refname)",
                              "refs/heads"], capture_output=True, text=True, timeout=5)
        parts.append(out.stdout if out.returncode == 0 else "")
    except (OSError, subprocess.SubprocessError):
        parts.append("")
    for rel in extra_paths:
        p = Path(repo) / rel
        try:
            parts.append(f"{rel}:{p.stat().st_mtime_ns}")
        except OSError:
            parts.append(f"{rel}:-")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def transcript_has(path, marker):
    needle = marker.encode()
    try:
        with open(path, "rb") as fh:
            tail = b""
            while chunk := fh.read(1 << 20):
                if needle in tail + chunk:
                    return True
                tail = chunk[-len(needle):]
    except OSError:
        return False
    return False


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        allow()
    session = str(payload.get("session_id") or "")
    cwd = str(payload.get("cwd") or "")
    transcript = str(payload.get("transcript_path") or "")
    if not cwd:
        allow()

    # Pick the arming for this repo: the longest cwd_prefix that contains cwd.
    best = None
    for path in armings():
        cfg = load(path)
        prefix = cfg and cfg.get("cwd_prefix")
        if not prefix or not inside(cwd, prefix):
            continue
        if best is None or len(real(prefix)) > len(real(best[1]["cwd_prefix"])):
            best = (path, cfg)
    if best is None:
        allow()
    armed, cfg = best
    state = armed.parent
    stopfile = state / "stop"
    countfile = state / "count.json"

    if stopfile.exists():
        allow()
    # Stale arming is not arming. A machine left overnight must not wake up
    # holding a seat open against a prompt nobody remembers writing.
    armed_mtime = armed.stat().st_mtime
    if time.time() - armed_mtime > MAX_AGE_H * 3600:
        allow()

    excluded = cfg.get("exclude_sessions") or []
    if session and session in [str(x) for x in excluded]:
        allow()

    # The seat identifies itself. Use a unique nonce that appears only in the
    # pasted opening prompt, not in the prompt FILE, which a monitor seat reads.
    marker = str(cfg.get("marker") or "")
    if not marker or not transcript or not transcript_has(transcript, marker):
        allow()

    repo = cfg["cwd_prefix"]
    cap = as_int(cfg.get("max"), DEFAULT_MAX, 9999)
    cap_total = as_int(cfg.get("max_total"), DEFAULT_MAX_TOTAL)
    prompt = str(cfg.get("prompt_path") or DEFAULT_PROMPT)
    progress_paths = [str(p) for p in (cfg.get("progress_paths") or [])]

    # The counter belongs to this arming, not to all time.
    arming = f"{cfg.get('arming_id', '')}:{armed.stat().st_mtime_ns}"
    count = load(countfile) or {}
    if count.get("arming") != arming:
        count = {"arming": arming, "consecutive": 0, "total": 0, "fingerprint": ""}
    fp = fingerprint(repo, progress_paths)
    if fp != count.get("fingerprint"):
        count["consecutive"] = 0
        count["fingerprint"] = fp
    count["consecutive"] = int(count.get("consecutive", 0)) + 1
    count["total"] = int(count.get("total", 0)) + 1
    tmp = countfile.with_suffix(".tmp")
    tmp.write_text(json.dumps(count))
    tmp.replace(countfile)

    n, total = count["consecutive"], count["total"]
    if n > cap or total > cap_total:
        which = (f"{cap} consecutive continuations with no new commit or progress-file change"
                 if n > cap else f"{cap_total} continuations in this arming")
        try:
            armed.unlink()
        except OSError:
            pass
        block(f"BUILD-LOOP KEEP-ALIVE SPENT: {which}. The hook has disarmed itself so this "
              "cannot run away. Write one paragraph for the owner saying where the wave got to "
              "and what it needs, then stop.")

    block(f"BUILD-LOOP CONTINUATION ({n} of {cap} without progress; {total} of {cap_total} "
          "this arming). You are the autonomous build-loop seat and the run is not finished. "
          f"Do not summarise and stop: pick the loop back up where it is. Re-read {prompt} if "
          "you have lost the thread, work out from git log and the scoreboard and wave records "
          "the loop prompt names which wave and which step you are on, and take the NEXT step "
          "of that step list: a lane, a barrier attempt, the record, or opening the next wave. "
          "If you are genuinely finished or genuinely blocked (the definition of done is met, "
          "§Stop conditions has fired, or a decision only the owner can take is in the way), "
          f"create {stopfile} with one line saying which of those it is, and stop. That file is "
          "how a deliberate halt is told apart from drifting to a halt.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # fail open to a normal stop
        sys.exit(0)
