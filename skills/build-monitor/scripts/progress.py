#!/usr/bin/env python3
"""Build progress checklist: generated, never hand-maintained.

Reads a build's own record (scoreboard, gate ceilings, git, wave evidence, the
owner's list) and writes one self-contained HTML page: road to done, the
current wave lane by lane, the next queue, what waits on the owner, and history.

    python3 progress.py --config monitor.json            # writes the page
    python3 progress.py --config monitor.json --json     # prints the data only

Read-only against the repo: it runs `git` read commands and reads files. It is
safe while a barrier runs. Every path in the config is relative to `repo`
unless absolute; `owner_list`, `out` and `template` are relative to the config.
Standard library only.
"""
import argparse
import html as htmllib
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "..", "assets", "progress-page.template.html")


def git(repo, *args, default=""):
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=60)
        return out.stdout.strip() if out.returncode == 0 else default
    except Exception:
        return default


def is_ancestor(repo, a, b):
    try:
        return subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", a, b],
                              capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False


def fmt(s, **kw):
    for k, v in kw.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def rel(base, p):
    return p if os.path.isabs(p) else os.path.join(base, p)


# ── scoreboard ──────────────────────────────────────────────────────────────
def parse_scoreboard(text, sb):
    rows = []
    col = sb.get("verdict_column", 3)
    for line in text.splitlines():
        if not line.startswith(sb.get("row_prefix", "| ")):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < col or not re.match(sb.get("id_regex", r"^[A-Z]+-[A-Z]+-\d+"), cols[0]):
            continue
        rows.append({"id": cols[0], "verdict": cols[col - 1]})
    return rows


def summarise_rows(rows, sb):
    terminal = set(sb.get("terminal", ["PASS"]))
    derived = set(sb.get("derived_rows", []))
    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    open_rows = [r for r in rows if r["verdict"] not in terminal and r["id"] not in derived]
    return {
        "total": len(rows),
        "pass": counts.get("PASS", 0),
        "terminal": sum(1 for r in rows if r["verdict"] in terminal),
        "derived": sorted(r["id"] for r in rows if r["id"] in derived),
        "by_verdict": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "open": [f'{r["id"]} ({r["verdict"]})' for r in open_rows][:40],
        "open_count": len(open_rows),
    }


# ── gates ───────────────────────────────────────────────────────────────────
def read_gates(text, gcfg):
    try:
        gates = json.loads(text).get("gates", {})
    except Exception:
        return []
    labels = gcfg.get("labels", {})
    zero = set(gcfg.get("done_at_zero", []))
    out = []
    for name, g in gates.items():
        out.append({"name": name, "label": labels.get(name, name), "ceiling": g.get("ceiling"),
                    "wave": g.get("wave"), "done_at_zero": name in zero})
    return out


# ── the current wave ────────────────────────────────────────────────────────
def current_wave(repo, cfg):
    w = cfg["wave"]
    conf = rel(repo, w["conf"])
    try:
        m = re.search(w.get("wave_regex", r"^WAVE=(\d+)"), open(conf).read(), re.M)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def verdict_of(path, regex):
    """The panel's verdict: a line naming it wins; else the file's head."""
    try:
        text = open(path, errors="replace").read()
    except Exception:
        return "unknown"
    for line in text.splitlines():
        if re.search(r"verdict", line, re.I):
            m = re.search(regex, line)
            if m:
                return m.group(0)
    m = re.search(regex, "\n".join(text.splitlines()[:6]))
    return m.group(0) if m else "unknown"


def lane_status(repo, cfg, n, lane, merges, evidence):
    w = cfg["wave"]
    lane_dir = os.path.join(evidence, lane)
    branch = fmt(w["lane_branch"], N=n, lane=lane)
    integ = fmt(w["integration_branch"], N=n)
    stage_re = re.compile(w.get("stage_prefix_regex", r"^stage(\d+)-"))
    vglob = w.get("verify_glob", "*verify-*.md")
    stages = {}
    for p in sorted(glob.glob(os.path.join(lane_dir, vglob))):
        name = os.path.basename(p)
        m = stage_re.match(name)
        k = int(m.group(1)) if m else 1
        v = verdict_of(p, w.get("verdict_regex", r"NO LENS REFUTES|REFUTED"))
        stages.setdefault(k, []).append(v)
    review = []
    for k in sorted(stages):
        vs = stages[k]
        refuted = any("REFUT" in v and "NO LENS" not in v for v in vs)
        review.append({"stage": k, "verdict": "refuted" if refuted else ("held" if all("NO LENS" in v for v in vs) else "unknown")})
    subj = next((s for s in merges if re.search(fmt(w.get("merge_subject_regex", r"merge {lane}\b"), lane=re.escape(lane)), s)), "")
    merged = bool(subj) or (git(repo, "rev-parse", "--verify", "-q", branch) != "" and is_ancestor(repo, branch, integ))
    approved = bool(subj and re.search(w.get("approval_regex", "reviewing seat"), subj, re.I))
    built = os.path.exists(os.path.join(lane_dir, w.get("build_marker", "build.md"))) or bool(review)
    return {"lane": lane, "cut": True, "built": built, "review": review, "approved": approved,
            "merged": merged, "note": note_of(subj)}


def note_of(subject):
    """The free-text note in a merge subject: after " — " (older records) or the first ": "."""
    for sep in (" — ", ": "):
        if sep in subject:
            return subject.split(sep, 1)[1][:220]
    return ""


def barrier_attempts(evidence, w):
    out = []
    for d in sorted(glob.glob(os.path.join(evidence, w.get("barrier_glob", "barrier*"))),
                    key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0)):
        launch = os.path.join(d, w.get("barrier_launch", "launch.txt"))
        if not os.path.isfile(launch):
            continue
        text = open(launch, errors="replace").read()
        m = re.search(w.get("barrier_exit_regex", r"BARRIER EXIT=(\d+)"), text)
        started = re.search(r"launched (\S+)", text)
        state = "running" if not m else ("green" if m.group(1) == "0" else "red")
        out.append({"attempt": len(out) + 1, "state": state, "launched": started.group(1) if started else "",
                    "dir": os.path.basename(d)})
    return out


def queue_items(path):
    items = []
    try:
        for line in open(path, errors="replace"):
            m = re.match(r"^- \*\*([^*]+)\*\*(.*)", line)
            if m and not m.group(1).lower().startswith(("amendment", "wave ", "housekeeping", "for ")):
                items.append({"name": re.split(r"\s+—\s+", m.group(1).strip())[0], "why": re.sub(r"^[\s,;:—()-]+|[\s,;:—-]+$", "", re.sub(r"[`*]", "", m.group(2)))[:200]})
    except Exception:
        pass
    return items


def wave_block(repo, cfg, n):
    w = cfg["wave"]
    evidence = rel(repo, fmt(w["evidence_dir"], N=n))
    trunk = cfg["trunk"]
    integ = fmt(w["integration_branch"], N=n)
    merges = git(repo, "log", "--format=%s", f"{trunk}..{integ}").splitlines()
    lanes = []
    try:
        ledger = json.load(open(os.path.join(evidence, w.get("lane_ledger", "lane-ranges.json"))))
        lanes = [l["lane"] for l in (ledger if isinstance(ledger, list) else ledger.get("lanes", []))]
    except Exception:
        pass
    attempts = barrier_attempts(evidence, w)
    ver = sorted(glob.glob(rel(repo, fmt(w["verification_glob"], N=n))))
    record_re = fmt(cfg["history"]["record_regex"], N=n).replace("(\\d+)", str(n))
    recorded = any(re.search(record_re, s) for s in git(repo, "log", "-20", "--format=%s", trunk).splitlines())
    remote = f'{cfg.get("remote", "origin")}/{trunk}'
    pushed = git(repo, "rev-parse", "-q", "--verify", remote) == git(repo, "rev-parse", trunk)
    qfile = os.path.join(evidence, fmt(w.get("queue_file", "orchestrator/wave{N1}-queue.md"), N=n, N1=n + 1))
    return {
        "n": n,
        "integration": integ,
        "integration_head": git(repo, "log", "-1", "--format=%h %s", integ)[:160],
        "lanes": [lane_status(repo, cfg, n, l, merges, evidence) for l in lanes],
        "barrier": attempts,
        "verification_files": [os.path.basename(v) for v in ver],
        "recorded": recorded,
        "pushed": pushed,
        "remote_ref": remote,
        "queue_next": queue_items(qfile),
    }


# ── history ─────────────────────────────────────────────────────────────────
def history(repo, cfg):
    """One point per wave that recorded a green barrier: the verification file's
    add commit gives the date, its attempt number, and the scoreboard then."""
    h = cfg["history"]
    vglob = cfg["wave"]["verification_glob"]
    vdir = os.path.dirname(vglob)
    vre = re.compile(h.get("verification_regex", r"wave(\d+)-barrier-(\d+)\.txt$"))
    log = git(repo, "log", "--diff-filter=A", "--format=@%H\t%aI", "--name-only", cfg["trunk"], "--", vdir)
    best = {}
    sha = when = None
    for line in log.splitlines():
        if line.startswith("@"):
            sha, when = line[1:].split("\t")
            continue
        m = vre.search(line.strip())
        if not m:
            continue
        w, k = int(m.group(1)), int(m.group(2))
        if w not in best or k > best[w]["attempts"]:
            best[w] = {"wave": w, "attempts": k, "at": when, "sha": sha}
    recs = sorted(best.values(), key=lambda r: r["wave"])[-h.get("max", 30):]
    for r in recs:
        rows = parse_scoreboard(git(repo, "show", f'{r["sha"]}:{cfg["scoreboard"]["path"]}'), cfg["scoreboard"])
        r["pass"] = sum(1 for x in rows if x["verdict"] == "PASS")
        r["total"] = len(rows)
        r["sha"] = r["sha"][:8]
    return recs


# ── where the time went ─────────────────────────────────────────────────────
# The build seat journals {"type": "phase", "wave": N, "phase": P, "lane": L,
# "event": "start"|"end", "at": ISO-8601 UTC}. Lanes overlap, so phase totals
# would overcount. Instead every minute of a wave goes to the highest-priority
# phase active in that minute: work outranks waiting. A minute with nothing
# active is "unaccounted": sleep, a stopped seat, a stall nobody recorded.
# "paused" is a usage-window pause the seat recorded; it ranks last, so a
# minute counts as paused only if nothing else was happening.
PHASES = ["barrier", "record", "cut", "build", "verify", "review_wait", "owner_wait", "paused"]
UNACCOUNTED = "unaccounted"


def parse_at(value):
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def phase_intervals(lines):
    """Journal lines to {wave: [(phase, lane, start, end_or_None)]}. Tolerates junk."""
    open_, done = {}, {}
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict) or ev.get("type") != "phase" or ev.get("phase") not in PHASES:
            continue
        at = parse_at(ev.get("at"))
        try:
            wave = int(ev.get("wave"))
        except (TypeError, ValueError):
            continue
        if at is None:
            continue
        key = (wave, ev["phase"], str(ev.get("lane") or ""), str(ev.get("attempt") or ""))
        if ev.get("event") == "start":
            open_.setdefault(key, at)            # a repeated start keeps the first
        elif ev.get("event") == "end" and key in open_:
            start = open_.pop(key)
            if at >= start:
                done.setdefault(wave, []).append((key[1], key[2], start, at))
    for (wave, phase, lane, _), start in open_.items():
        done.setdefault(wave, []).append((phase, lane, start, None))
    return done


def attribute(intervals, until):
    """Split a wave's span into minutes per phase, by priority. Returns (span_min, {phase: min})."""
    spans = [(p, s, e or until) for p, _, s, e in intervals if (e or until) > s]
    if not spans:
        return 0.0, {}
    points = sorted({t for _, s, e in spans for t in (s, e)})
    rank = {p: i for i, p in enumerate(PHASES)}
    out = {}
    for a, b in zip(points, points[1:]):
        active = [p for p, s, e in spans if s <= a and e >= b]
        who = min(active, key=rank.get) if active else UNACCOUNTED
        out[who] = out.get(who, 0.0) + (b - a).total_seconds() / 60
    return (points[-1] - points[0]).total_seconds() / 60, out


def timings(repo, cfg, current, now=None):
    t = cfg.get("timing")
    if not t or not t.get("journal"):
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        with open(rel(repo, t["journal"]), errors="replace") as fh:
            by_wave = phase_intervals(fh)
    except OSError:
        return {"error": f'journal not readable: {t["journal"]}', "order": [], "waves": []}
    keep = int(t.get("max", cfg.get("history", {}).get("max", 30)))
    waves = []
    for wave in sorted(by_wave)[-keep:]:
        iv = by_wave[wave]
        is_current = wave == current
        closed_ends = [e for _, _, _, e in iv if e]
        # A past wave's unclosed phase is clipped at the wave's last recorded
        # moment, not stretched to now; only the current wave runs to the present.
        until = now if is_current else max(closed_ends + [s for _, _, s, _ in iv])
        span, mins = attribute(iv, until)
        lanes = {}
        for p, lane, s, e in iv:
            if p == "build" and lane:
                lanes[lane] = lanes.get(lane, 0.0) + ((e or until) - s).total_seconds() / 60
        slowest = max(lanes.items(), key=lambda kv: kv[1]) if lanes else None
        open_now = sorted({p + ("/" + lane if lane else "") for p, lane, _, e in iv if e is None})
        waves.append({"wave": wave, "current": is_current, "span_min": round(span, 1),
                      "phases": {k: round(v, 1) for k, v in mins.items()},
                      "top": max(mins.items(), key=lambda kv: kv[1])[0] if mins else None,
                      "slowest_build": ({"lane": slowest[0], "min": round(slowest[1], 1)}
                                        if slowest else None),
                      "open": open_now})
    return {"order": PHASES + [UNACCOUNTED], "waves": waves}


# ── the owner's list ────────────────────────────────────────────────────────
def owner_list(path):
    items = []
    try:
        for line in open(path, errors="replace"):
            m = re.match(r"^\s*- \[( |x|X)\]\s+(.*)", line)
            if m:
                text = m.group(2).strip()
                # `what: why` (current) or `what — why` (older lists).
                parts = re.split(r"\s+—\s+", text, maxsplit=1)
                if len(parts) == 1:
                    parts = re.split(r":\s+", text, maxsplit=1)
                items.append({"done": m.group(1).lower() == "x", "item": parts[0],
                              "detail": parts[1] if len(parts) > 1 else ""})
    except Exception:
        pass
    return items


def build(cfg, cfg_dir):
    repo = cfg["repo"]
    sb = cfg["scoreboard"]
    rows = parse_scoreboard(open(rel(repo, sb["path"]), errors="replace").read(), sb)
    rows_s = summarise_rows(rows, sb)
    gates = read_gates(open(rel(repo, cfg["gates"]["path"])).read(), cfg["gates"])
    n = current_wave(repo, cfg)
    done = [{"label": sb.get("done_label", "Every row has a terminal verdict"),
             "value": rows_s["terminal"] + len(rows_s["derived"]), "target": rows_s["total"],
             "done": rows_s["open_count"] == 0,
             "detail": (f'{rows_s["pass"]} PASS; derived at the done sequence: {", ".join(rows_s["derived"])}'
                        if rows_s["derived"] else f'{rows_s["pass"]} PASS')}]
    for g in gates:
        if g["done_at_zero"]:
            done.append({"label": f'{g["label"]} at zero', "value": g["ceiling"], "target": 0,
                         "done": g["ceiling"] == 0, "detail": f'ceiling set at wave {g["wave"]}'})
    for extra in cfg.get("done_extra", []):
        done.append({"label": extra["label"], "value": None, "target": None,
                     "done": bool(extra.get("done")), "detail": extra.get("detail", "")})
    return {
        "project": cfg.get("project", os.path.basename(repo)),
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "trunk": cfg["trunk"],
        "trunk_head": git(repo, "log", "-1", "--format=%h %s", cfg["trunk"])[:160],
        "rows": rows_s,
        "gates": gates,
        "done": done,
        "wave": wave_block(repo, cfg, n) if n else None,
        "owner": owner_list(rel(cfg_dir, cfg.get("owner_list", "owner-list.md"))),
        "owner_name": cfg.get("owner_name", "Owner"),
        "history": history(repo, cfg),
        "timing": timings(repo, cfg, n),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--json", action="store_true", help="print the data and write nothing")
    a = ap.parse_args()
    cfg_path = os.path.abspath(a.config)
    cfg_dir = os.path.dirname(cfg_path)
    cfg = json.load(open(cfg_path))
    data = build(cfg, cfg_dir)
    if a.json:
        json.dump(data, sys.stdout, indent=1)
        return
    tpl = open(rel(cfg_dir, cfg["template"]) if cfg.get("template") else DEFAULT_TEMPLATE).read()
    blob = json.dumps(data).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", blob).replace("__TITLE__", htmllib.escape(data["project"] + " progress"))
    out = rel(cfg_dir, cfg.get("out", "progress.html"))
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(html)
    os.replace(tmp, out)
    print(out)


if __name__ == "__main__":
    main()
