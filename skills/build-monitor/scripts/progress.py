#!/usr/bin/env python3
"""Build progress checklist: generated, never hand-maintained.

Reads a build's own record (scoreboard, gate ceilings, git, wave evidence, the
owner's list) and writes one self-contained HTML page. Two views share the data:

- checklist: road to done, the current wave lane by lane, the next queue, what
  waits on the owner, where the time went, and history.
- kanban: every register row as a card in one of six columns (backlog, next
  wave, this wave, rework, parked, done), with the run's spend, clock, wave
  count and projection above the board.

    python3 progress.py --config monitor.json                 # writes the page
    python3 progress.py --config monitor.json --view kanban   # the board
    python3 progress.py --config monitor.json --json          # prints the data only

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
TEMPLATES = {
    "checklist": os.path.join(HERE, "..", "assets", "progress-page.template.html"),
    "kanban": os.path.join(HERE, "..", "assets", "kanban-page.template.html"),
}


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


# ── the board (kanban view) ─────────────────────────────────────────────────
# Every scoreboard row goes to exactly one column, first match wins:
#   done     verdict in board.done_verdicts (PASS by default: only independent
#            verification moves a card here)
#   wave     named in the current wave's queue
#   next     named in the next wave's queue
#   rework   verdict starts with one of board.rework_prefixes, or the note says stuck
#   parked   any other terminal verdict, or a tag in board.parked_tags
#   backlog  everything else
BOARD_COLUMNS = ["backlog", "next", "wave", "rework", "parked", "done"]
ID_TOKEN = re.compile(r"(\.\.|–|,|&|\band\b)|\b([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*)-(\d+)\b|\b(\d+)\b|(\S)")


def expand_ids(text, known):
    """Row ids named in prose, in order, keeping only ids the scoreboard has.

    Understands "SES-05, 06, 07", "SES-05 and 06", "TRI-01..04" and "TRI-01–04".
    A bare number continues the last id's prefix only straight after a separator.
    """
    out, pre, prev, width, sep_seen = [], None, None, 2, None
    for m in ID_TOKEN.finditer(text):
        sep, prefix, num, bare, other = m.groups()
        if sep:
            sep_seen = sep
            continue
        if other:
            pre = prev = sep_seen = None
            continue
        if prefix:
            pre, width, n, rng = prefix, len(num), int(num), []
        elif bare and pre is not None and prev is not None and sep_seen:
            n = int(bare)
            rng = range(prev + 1, n) if sep_seen in ("..", "–") and n - prev < 100 else []
        else:
            pre = prev = sep_seen = None
            continue
        for k in [*rng, n]:
            rid = f"{pre}-{k:0{width}d}"
            if rid in known and rid not in out:
                out.append(rid)
        prev, sep_seen = n, None
    return out


def parse_queue_rows(path, known):
    """{lane: [row ids]} from a wave queue: a `| lane | rows |` table, or
    `**lane**` entries (bullets or prose sections). Ids no lane claims go to ""."""
    try:
        with open(path, errors="replace") as fh:
            text = fh.read()
    except OSError:
        return {}
    lanes = {}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        name = cells[0].strip("`* ")
        if len(cells) < 2 or not re.match(r"^[a-z][\w./-]*$", name):
            continue
        lanes[name] = expand_ids(" ".join(cells[1:]), known)
    if not lanes:
        parts = re.split(r"\*\*([a-z][\w./-]*)\*\*", text)
        for name, body in zip(parts[1::2], parts[2::2]):
            body = re.split(r"\n(?=#|\d+\. |- )", body)[0]
            lanes.setdefault(name, [])
            lanes[name] += [i for i in expand_ids(body, known) if i not in lanes[name]]
    claimed = {i for ids in lanes.values() for i in ids}
    rest = [i for i in expand_ids(text, known) if i not in claimed]
    if rest:
        lanes[""] = rest
    return lanes


def board_rows(text, sb, bcfg):
    """Scoreboard rows with the extra columns the board shows (1-based, optional)."""
    cols = bcfg.get("columns", {})
    vcol = sb.get("verdict_column", 3)
    rows = []
    for line in text.splitlines():
        if not line.startswith(sb.get("row_prefix", "| ")):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < vcol or not re.match(sb.get("id_regex", r"^[A-Z]+-[A-Z]+-\d+"), cells[0]):
            continue
        get = lambda k: cells[cols[k] - 1] if cols.get(k) and len(cells) >= cols[k] else ""
        rows.append({"id": cells[0], "verdict": cells[vcol - 1], "title": get("title"),
                     "note": get("note"), "tag": get("tag"), "wave": get("wave")})
    return rows


def carried_lanes(repo, pattern, n):
    """Lanes whose branch was carried to the next wave (refuted, kept for rework)."""
    if not pattern:
        return []
    head, _, tail = fmt(pattern, N=n).partition("{lane}")
    rx = re.compile("(?:^|/)" + re.escape(head) + "(.+)" + re.escape(tail) + "$")
    out = []
    for ref in git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes").split():
        m = rx.search(ref)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def board(repo, cfg, n, wave):
    sb, b, w = cfg["scoreboard"], cfg.get("board", {}), cfg["wave"]
    with open(rel(repo, sb["path"]), errors="replace") as fh:
        rows = board_rows(fh.read(), sb, b)
    known = {r["id"] for r in rows}
    qpattern = w.get("queue_file", "orchestrator/wave{N1}-queue.md")
    cur_q = parse_queue_rows(os.path.join(rel(repo, fmt(w["evidence_dir"], N=n - 1)),
                                          fmt(qpattern, N=n - 1, N1=n)), known) if n else {}
    nxt_q = parse_queue_rows(os.path.join(rel(repo, fmt(w["evidence_dir"], N=n)),
                                          fmt(qpattern, N=n, N1=n + 1)), known) if n else {}
    in_wave, in_next = {}, {}
    for lane, ids in cur_q.items():
        for i in ids:
            in_wave.setdefault(i, lane)
    for lane, ids in nxt_q.items():
        for i in ids:
            in_next.setdefault(i, lane)
    carried = carried_lanes(repo, b.get("carry_branch", ""), n) if n else []
    done_v = {v.upper() for v in b.get("done_verdicts", ["PASS"])}
    terminal = {v.upper() for v in sb.get("terminal", ["PASS"])}
    rework = tuple(p.upper() for p in b.get("rework_prefixes", ["WIP", "BLOCKED", "DISPUTED", "STUCK", "FAIL"]))
    parked_tags = set(b.get("parked_tags", []))
    area_rx = re.compile(b.get("area_regex", r"^(.*)-\d+$"))
    names = b.get("areas", {})
    for r in rows:
        v = r["verdict"].upper()
        m = area_rx.match(r["id"])
        r["area"] = m.group(1) if m else ""
        r["lane"] = in_wave.get(r["id"]) or in_next.get(r["id"]) or ""
        r["stuck"] = v.startswith("STUCK") or "stuck" in r["note"].lower()
        r["carried"] = r["id"] in in_wave and r["lane"] in carried
        r["parked"] = r["tag"] in parked_tags
        if v in done_v:
            r["column"] = "done"
        elif r["id"] in in_wave:
            r["column"] = "wave"
        elif r["id"] in in_next:
            r["column"] = "next"
        elif v.startswith(rework) or r["stuck"]:
            r["column"] = "rework"
        elif v in terminal or r["parked"]:
            r["column"] = "parked"
        else:
            r["column"] = "backlog"
    order = list(dict.fromkeys([*names, *(r["area"] for r in rows)]))
    areas = [{"code": a, "name": names.get(a, a),
              "total": sum(1 for r in rows if r["area"] == a),
              "done": sum(1 for r in rows if r["area"] == a and r["column"] == "done")}
             for a in order if any(r["area"] == a for r in rows)]
    lanes = list(cur_q) if not wave else [l["lane"] for l in wave["lanes"]] or list(cur_q)
    return {
        "columns": BOARD_COLUMNS,
        "parked_label": b.get("parked_label", "Parked"),
        "parked_hint": b.get("parked_hint", "Terminal without a PASS, or waiting on something the loop can't do alone"),
        "rows": rows,
        "areas": areas,
        "lanes": [{"lane": l, "rows": cur_q.get(l, []), "carried": l in carried} for l in lanes if l],
        "carried": carried,
    }


# ── the run: spend, clock, waves, projection (kanban view) ──────────────────
def dig(obj, dotted):
    for k in dotted.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def run_block(repo, cfg, rows_total, rows_done, now=None):
    """The run's budget and pace, from the checkpoint the build seat keeps.

    Per-wave figures come from the checkpoint's own git history when the
    checkpoint is committed: each commit that leaves a wave at the recorded
    phase gives that wave's spend, start, end and the scoreboard's PASS count
    then. Without that history, the journal's usage events give spend per wave.
    """
    rc = cfg.get("run")
    if not rc or not rc.get("checkpoint"):
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    k = {"spent": "budget.spent", "limit": "budget.total_limit", "unit": "budget.unit",
         "started_at": "budget.started_at", "deadline": "budget.deadline",
         "wave": "budget.wave.id", "wave_spent": "budget.wave.spent",
         "wave_started_at": "budget.wave.started_at", "phase": "wave_phase", **rc.get("keys", {})}
    path = rc["checkpoint"]
    try:
        with open(rel(repo, path)) as fh:
            ck = json.load(fh)
    except (OSError, ValueError):
        return {"error": f"checkpoint not readable: {path}"}
    spent = float(dig(ck, k["spent"]) or 0)
    limit = max(float(dig(ck, k["limit"]) or 0), float(rc.get("limit_override") or 0))
    started = parse_at(dig(ck, k["started_at"]))
    deadline = None if rc.get("no_time_limit") else parse_at(dig(ck, k["deadline"]))
    sbp, sb = cfg["scoreboard"]["path"], cfg["scoreboard"]
    done_v = {v.upper() for v in cfg.get("board", {}).get("done_verdicts", ["PASS"])}

    waves = {}
    if not os.path.isabs(path):
        for line in git(repo, "log", "--format=%H\t%cI", cfg["trunk"], "--", path).splitlines():
            sha, when = line.split("\t")
            try:
                c = json.loads(git(repo, "show", f"{sha}:{path}"))
            except ValueError:
                continue
            wv = dig(c, k["wave"])
            if dig(c, k["phase"]) != rc.get("recorded_phase", "recorded") or wv is None or wv in waves:
                continue
            board_then = parse_scoreboard(git(repo, "show", f"{sha}:{sbp}"), sb)
            ws, we = parse_at(dig(c, k["wave_started_at"])), parse_at(when)
            waves[wv] = {"wave": wv, "spent": float(dig(c, k["wave_spent"]) or 0),
                         "started": ws.isoformat() if ws else "", "recorded": when,
                         "hours": round((we - ws).total_seconds() / 3600, 2) if ws and we and we > ws else None,
                         "done": sum(1 for r in board_then if r["verdict"].upper() in done_v)}
    if not waves and cfg.get("timing", {}).get("journal"):
        try:
            with open(rel(repo, cfg["timing"]["journal"]), errors="replace") as fh:
                for line in fh:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(ev, dict) and ev.get("type") == "usage" and ev.get("wave") is not None:
                        w = waves.setdefault(ev["wave"], {"wave": ev["wave"], "spent": 0.0, "started": "",
                                                          "recorded": "", "hours": None, "done": None})
                        w["spent"] += float(ev.get("amount") or 0)
        except OSError:
            pass
    hist = [waves[w] for w in sorted(waves, key=lambda x: int(x))]
    prev = 0
    for h in hist:
        if h["done"] is not None:
            h["new"], prev = h["done"] - prev, h["done"]
    n = len(hist)
    elapsed_h = (now - started).total_seconds() / 3600 if started else None
    per_spent = spent / n if n else None
    hours = [h["hours"] for h in hist if h["hours"]]
    per_h = sum(hours) / len(hours) if hours else (elapsed_h / n if n and elapsed_h else None)
    per_done = rows_done / n if n else None
    left_spent = max(limit - spent, 0) if limit else None
    left_h = (deadline - now).total_seconds() / 3600 if deadline else None
    proj = None
    if n and per_done:
        by_spend = left_spent / per_spent if left_spent is not None and per_spent else float("inf")
        by_clock = max(left_h, 0) / per_h if left_h is not None and per_h else float("inf")
        more = min(by_spend, by_clock)
        if more != float("inf"):
            proj = {"done": min(rows_total, round(rows_done + more * per_done)),
                    "waves_more": round(more, 1),
                    "bound_by": "budget" if by_spend <= by_clock else "clock"}
    finish = None
    if per_done:
        wl = (rows_total - rows_done) / per_done
        finish = {"waves": round(wl, 1), "spent": round(wl * per_spent) if per_spent else None,
                  "hours": round(wl * per_h, 1) if per_h else None}
    return {
        "unit": dig(ck, k["unit"]) or rc.get("unit", "tokens"),
        "spent": spent, "limit": limit or None,
        "started_at": started.isoformat() if started else "",
        "deadline": deadline.isoformat() if deadline else "",
        "no_time_limit": bool(rc.get("no_time_limit")),
        "elapsed_hours": round(elapsed_h, 2) if elapsed_h is not None else None,
        "waves": hist,
        "per_wave": {"spent": per_spent, "hours": round(per_h, 2) if per_h else None,
                     "done": round(per_done, 1) if per_done else None},
        "projection": proj,
        "to_finish": finish,
        "note": rc.get("note", ""),
    }


def status_file(path):
    """The build seat's latest checklist, if the monitor saved one:
    {"text": "<header>\\n\\n✓ step\\n✱ step\\n○ step", "at": "<ISO time>"}."""
    try:
        with open(path) as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        return None
    lines = [l.strip().replace("**", "") for l in str(st.get("text", "")).splitlines() if l.strip()]
    if not lines:
        return None
    steps = [{"state": "done" if l[0] == "✓" else "now" if l[0] == "✱" else "todo",
              "text": l.lstrip("✓✱○ ").strip()} for l in lines[1:]]
    return {"head": lines[0], "steps": steps, "at": st.get("at", "")}


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


def build(cfg, cfg_dir, view="checklist"):
    repo = cfg["repo"]
    sb = cfg["scoreboard"]
    rows = parse_scoreboard(open(rel(repo, sb["path"]), errors="replace").read(), sb)
    rows_s = summarise_rows(rows, sb)
    gcfg = cfg.get("gates") or {}
    try:
        gates = read_gates(open(rel(repo, gcfg["path"])).read(), gcfg)
    except (KeyError, OSError):
        gates = []
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
    wave = wave_block(repo, cfg, n) if n else None
    data = {
        "view": view,
        "project": cfg.get("project", os.path.basename(repo)),
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "trunk": cfg["trunk"],
        "trunk_head": git(repo, "log", "-1", "--format=%h %s", cfg["trunk"])[:160],
        "rows": rows_s,
        "gates": gates,
        "done": done,
        "wave": wave,
        "owner": owner_list(rel(cfg_dir, cfg.get("owner_list", "owner-list.md"))),
        "owner_name": cfg.get("owner_name", "Owner"),
        "history": history(repo, cfg),
        "timing": timings(repo, cfg, n),
    }
    if view == "kanban":
        data["board"] = board(repo, cfg, n, wave)
        cards = data["board"]["rows"]
        data["run"] = run_block(repo, cfg, len(cards), sum(1 for r in cards if r["column"] == "done"))
        data["status"] = status_file(rel(cfg_dir, cfg["status_file"])) if cfg.get("status_file") else None
        data["last_push"] = git(repo, "log", "-1", "--format=%cI\t%s",
                                f'{cfg.get("remote", "origin")}/{cfg["trunk"]}')
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--view", choices=sorted(TEMPLATES), help="which page to write; overrides the config's view")
    ap.add_argument("--json", action="store_true", help="print the data and write nothing")
    a = ap.parse_args()
    cfg_path = os.path.abspath(a.config)
    cfg_dir = os.path.dirname(cfg_path)
    cfg = json.load(open(cfg_path))
    view = a.view or cfg.get("view", "checklist")
    data = build(cfg, cfg_dir, view)
    if a.json:
        json.dump(data, sys.stdout, indent=1)
        return
    tpl = open(rel(cfg_dir, cfg["template"]) if cfg.get("template") else TEMPLATES[view]).read()
    blob = json.dumps(data).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", blob).replace("__TITLE__", htmllib.escape(data["project"] + (" build board" if view == "kanban" else " progress")))
    out = rel(cfg_dir, cfg.get("out", "progress.html"))
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(html)
    os.replace(tmp, out)
    print(out)


if __name__ == "__main__":
    main()
