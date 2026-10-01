#!/usr/bin/env python3
"""env-check.py: prove the build's environment is ready before the loop starts.

Reads the environment manifest (what the build needs from the world) and checks
it from the session the build will run in. Standard library only.

    python3 env-check.py --manifest docs/build/environment.json --repo .
    python3 env-check.py --manifest ... --dry-run      # print the checks, run none
    python3 env-check.py --manifest ... --report docs/build/environment-check.md

Exit codes: 0 ready, 1 blocked (the report lists the owner's actions),
2 the manifest itself is unreadable or incomplete.

Secret values are never printed, logged or written: only their names, and
whether they are present.
"""
import argparse
import datetime
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
CHECK_TIMEOUT = 120
DECISION_LINE = re.compile(r"^\s*[-*]\s+\**([a-z0-9][a-z0-9-]*)\**\s*:\s*(.+?)\s*$")
SLOT = re.compile(r"<[A-Z][A-Z0-9_]*(?::[^>]*)?>")


class Check:
    def __init__(self, area, name, status, detail, fix=None):
        self.area, self.name, self.status, self.detail, self.fix = area, name, status, detail, fix


class Run:
    def __init__(self, manifest, repo, dry_run):
        self.m, self.repo, self.dry = manifest, repo, dry_run
        self.checks = []
        self.cloud = manifest.get("where_the_build_runs", "local") == "cloud"
        env_name = manifest.get("cloud_environment") or "the build's cloud environment"
        self.where_settings_live = (
            f"on the cloud environment \"{env_name}\" (claude.ai/code, the environment's "
            "settings), not in project settings; then start a fresh session, because a running "
            "session never sees the change"
            if self.cloud else "in the shell profile the build seat starts from, then restart that seat")

    def add(self, *args, **kw):
        self.checks.append(Check(*args, **kw))

    def plan(self, area, text):
        print(f"PLAN  {area}: {text}")

    # ------------------------------------------------------------- secrets
    def secrets(self):
        for item in self.m.get("secrets", []):
            name, purpose = item["name"], item.get("for", "")
            optional = item.get("optional", False)
            if self.dry:
                self.plan("secrets", f"{name} is set ({purpose})")
                continue
            value = os.environ.get(name)
            if value is None or value == "":
                near = [k for k in difflib.get_close_matches(name, list(os.environ), n=3, cutoff=0.8)
                        if k != name]
                if near:
                    fix = (f"Rename {near[0]} to {name} {self.where_settings_live}.")
                    detail = f"missing; {near[0]} is set instead, which looks like a misspelling"
                else:
                    fix = f"Add {name} ({purpose}) {self.where_settings_live}."
                    detail = "missing"
                self.add("secrets", name, WARN if optional else FAIL, detail, None if optional else fix)
            elif value != value.strip() or value[:1] in "\"'" or SLOT.search(value):
                self.add("secrets", name, FAIL, "set, but has surrounding spaces, quotes or a placeholder",
                         f"Re-enter {name} as the bare value {self.where_settings_live}.")
            else:
                self.add("secrets", name, PASS, f"set ({purpose})")

    # --------------------------------------------------------------- tools
    def tools(self):
        for item in self.m.get("tools", []):
            name = item["name"]
            if self.dry:
                self.plan("tools", f"{name} on PATH" + (f", `{item['version_command']}`" if item.get("version_command") else ""))
                continue
            path = shutil.which(name)
            if not path:
                hint = item.get("install")
                fix = (f"Install {name} ({hint}) in the environment's setup script so every fresh session has it."
                       if self.cloud else f"Install {name}" + (f": {hint}." if hint else "."))
                self.add("tools", name, FAIL, "not on PATH", fix)
                continue
            if item.get("version_command"):
                code, out = self.shell(item["version_command"], 30)
                line = (out.strip().splitlines() or [""])[0][:80]
                self.add("tools", name, PASS if code == 0 else FAIL, line or f"exit {code}",
                         None if code == 0 else f"`{item['version_command']}` fails; reinstall {name}.")
            else:
                self.add("tools", name, PASS, path)

    # --------------------------------------------------------------- hosts
    def hosts(self):
        for host in self.m.get("hosts", []):
            url = host if "://" in host else f"https://{host}/"
            if self.dry:
                self.plan("network", f"{url} answers")
                continue
            try:
                urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=10)
                ok, detail = True, "answers"
            except urllib.error.HTTPError as e:
                # Any HTTP answer from the host itself means the route is open.
                ok, detail = e.code != 407, f"answers (HTTP {e.code})"
            except Exception as e:  # noqa: BLE001 - every other failure is "unreachable"
                ok, detail = False, f"unreachable: {str(e)[:100]}"
            fix = None if ok else (
                f"Allow {host} in the network access {self.where_settings_live}." if self.cloud
                else f"Open outbound HTTPS to {host}.")
            self.add("network", host, PASS if ok else FAIL, detail, fix)

    # -------------------------------------------------------------- probes
    def probes(self):
        for p in self.m.get("probes", []):
            self.probe(p, "probes")

    def probe(self, p, area):
        name = p["name"]
        if self.dry:
            self.plan(area, f"{name}: `{p['command']}`")
            return
        missing = [n for n in p.get("needs", []) if not os.environ.get(n)]
        if missing:
            self.add(area, name, FAIL, f"not run: needs {', '.join(missing)}",
                     p.get("owner_fix") or f"Set {', '.join(missing)} first (see secrets).")
            return
        code, out = self.shell(p["command"], p.get("timeout", CHECK_TIMEOUT))
        expect = p.get("expect_stdout")
        ok = code == 0 and (not expect or expect in out)
        tail = " | ".join(out.strip().splitlines()[-2:])[:160]
        detail = (f"exit {code}" + (f", expected `{expect}` in output" if code == 0 and not ok else "")
                  + (f": {tail}" if tail and not ok else ""))
        self.add(area, name, PASS if ok else FAIL, "works" if ok else detail,
                 None if ok else p.get("owner_fix") or f"`{p['command']}` must succeed from this session.")

    # ---------------------------------------------------------- migrations
    def migrations(self):
        mg = self.m.get("migrations")
        if not mg:
            return
        directory = self.repo / mg.get("dir", "")
        script = mg.get("deploy_script")
        if self.dry:
            self.plan("migrations", f"count files in {mg.get('dir')}")
            if script:
                self.plan("migrations", f"{script} applies them (`{mg.get('apply_command')}`)")
            for p in mg.get("probes", []):
                self.plan("migrations", f"{p['name']}: `{p['command']}`")
            return
        files = sorted(directory.glob("*.sql")) if directory.is_dir() else []
        self.add("migrations", "files in the repo", PASS if directory.is_dir() else WARN,
                 f"{len(files)} in {mg.get('dir')}" if directory.is_dir() else f"{mg.get('dir')} not found yet")
        if script:
            path = self.repo / script
            text = path.read_text(errors="replace") if path.is_file() else ""
            apply = mg.get("apply_command", "")
            ok = bool(text) and apply and apply in text
            self.add("migrations", "deploy applies migrations", PASS if ok else FAIL,
                     f"{script} runs `{apply}`" if ok else
                     (f"{script} does not run `{apply}`" if text else f"{script} not found"),
                     None if ok else f"Make {script} run `{apply}` before it ships the app, so every "
                     "deploy brings the hosted database up to the code.")
        for p in mg.get("probes", []):
            self.probe(p, "migrations")

    # -------------------------------------------------------------- logins
    def logins(self):
        lg = self.m.get("logins")
        if not lg:
            return
        accounts = lg.get("accounts", [])
        if self.dry:
            self.plan("logins", f"{len(accounts)} account(s) by {lg.get('how')}; owner has confirmed")
            return
        how = lg.get("how")
        if how == "seed":
            self.add("logins", "accounts", PASS, f"{len(accounts)} seeded by the build with no password")
            return
        confirmed = bool(lg.get("owner_confirmed"))
        who = "; ".join(f"{a.get('email', '?')} ({a.get('role', 'user')})" for a in accounts) or "none listed"
        verb = "accept the invitation for" if how == "invite" else "create"
        self.add("logins", "accounts", PASS if confirmed else FAIL,
                 f"{how}: {who}" + ("; owner confirmed" if confirmed else "; owner has not confirmed"),
                 None if confirmed else
                 f"The owner must {verb} these logins (Claude never invents passwords): {who}. "
                 "Then set logins.owner_confirmed to true in the manifest.")

    # --------------------------------------------------------- concurrency
    def concurrency(self):
        c = self.m.get("concurrency", {})
        if self.dry:
            self.plan("machine", "cores and memory; safe lanes against the planned lanes")
            return
        cores = os.cpu_count() or 1
        mem = memory_gb()
        per_lane_cores = c.get("cores_per_lane", 2)
        per_lane_gb = c.get("gb_per_lane", 3)
        safe = max(1, min(cores // per_lane_cores, int(mem // per_lane_gb) if mem else cores))
        serial = cores < c.get("parallel_review_min_cores", 8)
        detail = (f"{cores} cores, {mem:.0f} GB" if mem else f"{cores} cores, memory unknown") + \
                 f": at most {safe} lane(s) at once; review lenses {'one after another' if serial else 'in parallel'}"
        planned = c.get("planned_lanes")
        if planned and planned > safe:
            self.add("machine", "lane concurrency", FAIL, detail + f"; planned {planned}",
                     f"Plan {safe} lane(s) at once, not {planned} (the loop prompt's wave shape), "
                     "or run the build on a bigger machine.")
        else:
            self.add("machine", "lane concurrency", PASS, detail)
        self.safe_lanes, self.serial_review = safe, serial

    # ----------------------------------------------------------- decisions
    def decisions(self):
        rel = self.m.get("decisions_file")
        required = self.m.get("decisions_required", [])
        if not rel:
            return
        if self.dry:
            self.plan("decisions", f"{rel} records: {', '.join(required)}")
            return
        path = self.repo / rel
        found = {}
        if path.is_file():
            for line in path.read_text(errors="replace").splitlines():
                m = DECISION_LINE.match(line)
                if m:
                    found[m.group(1)] = m.group(2)
        for key in required:
            value = found.get(key, "")
            if value and not SLOT.search(value):
                self.add("decisions", key, PASS, value[:100])
            else:
                self.add("decisions", key, FAIL, "not recorded" if not value else "still a placeholder",
                         f"The owner states the {key} decision in their own words; record it in {rel} "
                         "and commit it before the build starts. A build seat will not take it relayed "
                         "from another session.")

    # ------------------------------------------------------------- helpers
    def shell(self, command, timeout):
        try:
            r = subprocess.run(command, shell=True, cwd=self.repo, capture_output=True, text=True,
                               timeout=timeout)
            return r.returncode, redact(r.stdout + r.stderr, self.m)
        except subprocess.TimeoutExpired:
            return 124, f"timed out after {timeout}s"

    def report(self):
        fails = [c for c in self.checks if c.status == FAIL]
        ready = not fails
        lines = [f"# Environment check: {self.m.get('project', 'the build')}", "",
                 f"Run {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC on "
                 f"{'the cloud environment ' + repr(self.m.get('cloud_environment', '')) if self.cloud else 'this machine'}.",
                 "", f"**{'READY' if ready else 'BLOCKED'}**: {len(self.checks) - len(fails)} of "
                 f"{len(self.checks)} checks pass.", ""]
        if fails:
            lines += ["## What the owner needs to do", ""]
            for i, c in enumerate(fails, 1):
                lines.append(f"{i}. {c.fix}")
            lines.append("")
        lines += ["## Checks", "", "| Area | Check | Result | Detail |", "| --- | --- | --- | --- |"]
        for c in self.checks:
            lines.append(f"| {c.area} | {c.name} | {c.status} | {c.detail.replace('|', '/')} |")
        if hasattr(self, "safe_lanes"):
            lines += ["", "## For the loop prompt", "",
                      f"- Lanes at once: **{self.safe_lanes}**.",
                      f"- Review lenses: **{'one after another' if self.serial_review else 'in parallel'}**."]
        return "\n".join(lines) + "\n", ready


def memory_gb():
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    try:
        out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
        return int(out.stdout.strip()) / 1024 ** 3
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def redact(text, manifest):
    for item in manifest.get("secrets", []):
        value = os.environ.get(item["name"])
        if value and len(value) >= 4:
            text = text.replace(value, f"<{item['name']} redacted>")
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default="docs/build/environment.json")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--report", help="write the markdown report here as well as printing it")
    ap.add_argument("--dry-run", action="store_true", help="print every check, run none")
    ap.add_argument("--skip-network", action="store_true", help="skip the host checks (tests only)")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    mpath = Path(args.manifest)
    mpath = mpath if mpath.is_absolute() else repo / mpath
    try:
        manifest = json.loads(mpath.read_text())
    except (OSError, ValueError) as e:
        print(f"MANIFEST {mpath}: {e}", file=sys.stderr)
        return 2
    slots = sorted(set(SLOT.findall(json.dumps(manifest))))
    if slots:
        print(f"MANIFEST {mpath} still has unfilled slots: {', '.join(slots)}", file=sys.stderr)
        return 2

    run = Run(manifest, repo, args.dry_run)
    run.secrets()
    run.tools()
    if not args.skip_network:
        run.hosts()
    run.probes()
    run.migrations()
    run.logins()
    run.concurrency()
    run.decisions()
    if args.dry_run:
        return 0
    text, ready = run.report()
    print(text)
    if args.report:
        out = Path(args.report)
        out = out if out.is_absolute() else repo / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
