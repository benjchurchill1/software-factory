# The progress checklist

`scripts/progress.py` turns a build's own record into one self-contained HTML
page. It reads files and runs read-only `git`; it never writes into the repo.
It uses the standard library only.

    python3 scripts/progress.py --config monitor.json          # writes `out`
    python3 scripts/progress.py --config monitor.json --json   # data only

## Config fields

Paths are relative to `repo` unless absolute. `owner_list`, `out` and
`template` are relative to the config file. `{N}` is the current wave and
`{N1}` the next one. `{lane}` is a lane name.

| Field | Meaning |
| --- | --- |
| `project`, `owner_name` | Page heading; whose list the owner's list is |
| `repo`, `trunk`, `remote` | The checkout, the trunk branch (not necessarily `main`), the push remote |
| `artifact_url` | The published page, so any session republishes to the same URL |
| `scoreboard.path` | The progress file, one markdown table row per requirement |
| `scoreboard.row_prefix`, `id_regex`, `verdict_column` | How to find rows and which column (1-based) holds the verdict |
| `scoreboard.terminal` | Verdicts that count as terminal |
| `scoreboard.derived_rows` | Rows that are aggregates derived at the done sequence, not work |
| `gates.path` | The ratchet file: `{"gates": {name: {"ceiling": n, "wave": w}}}` |
| `gates.done_at_zero` | Gates whose zero is a done condition; the others are ratchets only |
| `gates.labels` | Plain-words names for the page |
| `done_extra` | Done conditions the record can't measure: `{label, done, detail}`, maintained by the monitor |
| `wave.conf`, `wave_regex` | Where the current wave number lives (the lane-cut conf) |
| `wave.evidence_dir` | The wave's evidence directory |
| `wave.lane_ledger` | The lane ledger lane-cut writes: a JSON array of `{lane, …}`, or an object with `lanes: [{lane, …}]` |
| `wave.integration_branch`, `lane_branch` | Branch name patterns |
| `wave.barrier_glob`, `barrier_launch`, `barrier_exit_regex` | Barrier attempt directories, their launch file, and the exit line (no exit line means running) |
| `wave.verification_glob` | Green-barrier records; also drives History |
| `wave.queue_file` | The next wave's queue. Entries are `- **name**: why` bullets |
| `wave.verify_glob`, `stage_prefix_regex`, `verdict_regex` | Panel records per lane, their stage prefix, and the verdict words |
| `wave.build_marker` | A file whose presence means the lane built |
| `wave.merge_subject_regex`, `approval_regex` | How a merge commit names the lane, and how it records the monitor's approval |
| `history.verification_regex`, `max` | Wave and attempt from a verification filename; how many waves to chart |
| `history.record_regex` | How the trunk's record commit names a wave (`{N}`); marks the current wave recorded |
| `timing.journal` | The build seat's `journal.jsonl`. Optional: without it, the page has no "Where the time went" section |
| `timing.max` | How many waves to show there; defaults to `history.max` |

## How each section is derived

| Section | Source |
| --- | --- |
| Road to done | Scoreboard terminal count; each `done_at_zero` gate's ceiling; `done_extra` |
| Wave | Lane ledger; `build_marker`; panel records per stage; merge commits on `trunk..integration`; barrier launch files; `trunk` against `remote/trunk` |
| Next queue | The queue file's bullets |
| Waiting on the owner | `owner-list.md` |
| History | The add commit of each wave's highest-numbered verification file gives the date and attempt count, and the scoreboard at that commit gives PASS |

"Pushed" compares against the local remote-tracking ref, so it is as fresh as
the last fetch or push.

## Adapting to another build

The page expects the shapes build-loop emits. If a build names things
differently, change the config patterns, not the script. If a fact isn't
written anywhere (for example, the monitor's approvals aren't quoted in merge
commits), fix the build's convention so it is. A page that needs a person to
type its facts has become a status report.

## Why generated

A hand-kept checklist drifts at exactly the moment it matters: mid-barrier,
with two seats busy. This build's own rule (factory gate 8) is that state the
loop reads is generated. The progress page is read by the owner, so the same
rule applies.

## Where the time went

Derived from the `phase` events the build seat writes to its journal (the loop
prompt's §Persistent budgets and recovery says when). Lanes run in parallel, so
adding up phases would overcount. Instead every minute of a wave is given to
the highest-priority phase active in that minute, in this order: `barrier`,
`record`, `cut`, `build`, `verify`, `review_wait`, `owner_wait`, `paused`. Work outranks
waiting: a minute counts as waiting for review, or waiting on the owner, only
if nothing was being built or verified at the time; `paused` (a usage-window
pause) ranks last of all. A minute with nothing
active at all is **unaccounted**. That is usually host sleep, a stopped seat,
or a stall nobody recorded, and it is often the largest thing to fix.

Each wave's segments add up to its real wall-clock span. The current wave runs
up to now; a past wave's unclosed phase (a crashed lane) is cut off at the
wave's last recorded moment and listed as open. The section also names the
slowest lane's build time and anything still open.
