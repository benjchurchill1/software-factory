#!/usr/bin/env python3
"""Split evals/triggers.json into skill-creator's per-skill trigger-eval format.

Each query names the one skill that should fire on it, or null for none. For a
given skill, its own queries are should_trigger true and every other query
(including the other skills' queries, which are the near-misses that
matter most) is should_trigger false.

    python3 evals/split_triggers.py      # writes skills/<name>/evals/trigger-evals.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
queries = json.loads((ROOT / "evals" / "triggers.json").read_text())
for skill in ("software-factory", "environment-check", "build-loop", "build-monitor"):
    out = [{"query": q["query"], "should_trigger": q["skill"] == skill} for q in queries]
    path = ROOT / "skills" / skill / "evals" / "trigger-evals.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"{path.relative_to(ROOT)}: {sum(o['should_trigger'] for o in out)} of {len(out)} should trigger")
