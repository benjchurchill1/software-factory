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
