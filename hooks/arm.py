#!/usr/bin/env python3
"""Arm, inspect or disarm the build-loop keep-alive hook for one repo.

    arm.py arm    <repo> --marker <nonce> [--max 60] [--max-total 500]
                         [--prompt-path docs/prompts/build-loop.md]
                         [--progress-path <file>]... [--exclude <session id>]...
    arm.py status [<repo>]
    arm.py disarm <repo>
    arm.py nonce

Each repo gets its own state directory under ~/.claude/state/build-loop/, so
two builds on one machine never share a counter or a stop file. `arm` prints
the stop-file path the build seat will be told to write when it halts on
purpose, and the pause-file path it writes when a usage window is spent.
Arming is the owner's action, as gate 2 of the factory is: the build seat
never arms itself.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

STATE_ROOT = Path(os.environ.get("BUILD_LOOP_STATE_ROOT",
                                 Path.home() / ".claude" / "state" / "build-loop"))
MAX_AGE_H = 72


def key_for(repo):
    real = os.path.realpath(os.path.expanduser(repo))
    slug = re.sub(r"[^a-z0-9]+", "-", Path(real).name.lower()).strip("-")[:32] or "repo"
    return real, f"{slug}-{hashlib.sha256(real.encode()).hexdigest()[:10]}"


def cmd_arm(a):
    real, key = key_for(a.repo)
    if not Path(real).is_dir():
        sys.exit(f"arm: {real} is not a directory")
    if len(a.marker) < 12:
        sys.exit("arm: the marker must be at least 12 characters; use `arm.py nonce`")
    state = STATE_ROOT / key
    state.mkdir(parents=True, exist_ok=True)
    stop = state / "stop"
    if stop.exists():
        print(f"cleared a previous stop file: {stop.read_text().strip() or '(empty)'}")
        stop.unlink()
    pause = state / "pause"
    if pause.exists():
        print(f"cleared a previous pause file: {pause.read_text().strip() or '(empty)'}")
        pause.unlink()
    cfg = {"cwd_prefix": real, "marker": a.marker, "max": a.max, "max_total": a.max_total,
           "prompt_path": a.prompt_path, "progress_paths": a.progress_path,
           "exclude_sessions": a.exclude,
           "arming_id": secrets.token_hex(8)}
    tmp = state / "armed.json.tmp"
    tmp.write_text(json.dumps(cfg, indent=2) + "\n")
    tmp.replace(state / "armed.json")
    print(f"armed {real}\n  state  {state}\n  stop   {stop}\n  pause  {pause}\n"
          f"  expires in {MAX_AGE_H} h")
    print("Put the marker in the prompt you PASTE to start the build seat, not in the prompt file.")


def describe(state):
    armed = state / "armed.json"
    try:
        cfg = json.loads(armed.read_text())
    except (OSError, ValueError):
        return None
    age_h = (time.time() - armed.stat().st_mtime) / 3600
    count = {}
    try:
        count = json.loads((state / "count.json").read_text())
    except (OSError, ValueError):
        pass
    stop = state / "stop"
    until = None
    try:
        pause = json.loads((state / "pause").read_text())
        until = pause.get("until") if isinstance(pause, dict) else None
        when = dt.datetime.fromisoformat(str(until).replace("Z", "+00:00"))
        when = when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)
        until = until if when > dt.datetime.now(dt.timezone.utc) else None
    except (OSError, ValueError, TypeError):
        until = None
    status = ("released (stop file)" if stop.exists()
              else "expired" if age_h > MAX_AGE_H
              else f"paused until {until}" if until else "armed")
    return (f"{cfg.get('cwd_prefix')}\n  {status}, {age_h:.1f} h old, "
            f"{count.get('consecutive', 0)}/{cfg.get('max', 60)} without progress, "
            f"{count.get('total', 0)}/{cfg.get('max_total', 500)} total\n  state {state}")


def cmd_status(a):
    dirs = [STATE_ROOT / key_for(a.repo)[1]] if a.repo else sorted(
        p.parent for p in STATE_ROOT.glob("*/armed.json"))
    if (STATE_ROOT / "armed.json").exists() and not a.repo:
        dirs.insert(0, STATE_ROOT)
    lines = [d for d in (describe(s) for s in dirs) if d]
    print("\n".join(lines) if lines else "nothing armed")


def cmd_disarm(a):
    real, key = key_for(a.repo)
    armed = STATE_ROOT / key / "armed.json"
    if armed.exists():
        armed.unlink()
        print(f"disarmed {real}")
    else:
        print(f"{real} was not armed")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    arm = sub.add_parser("arm")
    arm.add_argument("repo")
    arm.add_argument("--marker", required=True)
    arm.add_argument("--max", type=int, default=60)
    arm.add_argument("--max-total", type=int, default=500)
    arm.add_argument("--prompt-path", default="docs/prompts/build-loop.md")
    arm.add_argument("--progress-path", action="append", default=[])
    arm.add_argument("--exclude", action="append", default=[])
    st = sub.add_parser("status")
    st.add_argument("repo", nargs="?")
    dis = sub.add_parser("disarm")
    dis.add_argument("repo")
    sub.add_parser("nonce")
    a = p.parse_args()
    if a.cmd == "nonce":
        print("build-loop-" + secrets.token_hex(8))
    else:
        {"arm": cmd_arm, "status": cmd_status, "disarm": cmd_disarm}[a.cmd](a)


if __name__ == "__main__":
    main()
