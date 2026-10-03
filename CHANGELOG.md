# Changelog

## 0.6.0

- **New optional plugin: `factory-live`** (`mods/factory-live/`), a Claude Code mod built on the early-access function-hooks API. It runs inside the build seat's session, scoped to a repo `arm.py` has armed, and writes only its own files in the arming's state directory.
- **It wakes a paused seat.** A minute after the `pause` file's `until`, it submits a resume prompt that follows §Pausing on a usage limit. It wakes once per pause and at most 24 times per arming, and never after the `stop` file, past the arming's 72 hours, or in any session other than the seat. The seat is the session whose prompt carried the marker, recorded in `seat.json`; `--exclude` sessions never qualify. This fills `<RESUME_MECHANISM>`, which had been `/loop`, a scheduled resume, or a line on the owner's list.
- **It writes the windows.** On each measurement it writes `usage-window.json` (every rate-limit window and the session cost) and `usage-window` (`<percent left> <resets at>` for the tightest window). The latter works as `<USAGE_WINDOW_COMMAND>` only when the run's spend figures are in window percent.
- **It records turns.** It appends each seat turn (subagents included) to `turns.jsonl`: duration, end reason, model, token counts and running cost. The loop can cite it as its usage source.
- **It shows the state.** A band above the prompt and a `/factory` command show the keep-alive's counts, the pause, the tightest window and the cost.
- Nine tests under `claude plugin test`. It has not yet woken a real seat after a real usage limit, or run in a cloud session.
- The rig doc, gate 11 and the loop interview name it as a resume mechanism.
- **Enabled per project.** If the owner picks `factory-live` to wake the seat, gate 11 fills the new `assets/settings.factory-live.template.json`. Its `enabledPlugins` and `extraKnownMarketplaces` entries go into the project's gitignored settings file beside gate 2's allowlist, so the mod loads in that repo's seats and nowhere else. The owner merges it by hand, as with the allowlist, and step 9 checks that `/factory` answers in a new session in the repo.
- Self-test: 52 tests (from 51). The new test checks that the entry enables only the mod and grants no permission or hook.

## 0.5.0

- **New skill: `environment-check`.** Before the build seat starts, it lists everything the build needs from outside the repo in `docs/build/environment.json` (secrets by exact name, CLIs, hosts, probes that prove each token against its real target, the hosted database's migration path, logins, machine size) and the owner's standing word in `docs/build/standing-decisions.md`. `scripts/env-check.py` (standard library) checks them from the session the build will run in and writes a READY or BLOCKED report whose failing lines are one list of owner actions. Exit 0 ready, 1 blocked, 2 manifest unreadable or unfilled; `--dry-run` prints the checks and runs none.
- It catches what the Keystone build found mid-build: a database token missing from the cloud environment, so 23 of 26 migrations never reached the hosted database; a deploy script that did not apply migrations; a token saved as `NETLIFY_AUT_TOKEN` (a set variable that nearly matches a missing one is reported as a misspelling, with the rename); logins only the owner can create; five planned lanes on a 4-core machine that lost its worker three times (lanes at two cores and 3 GB each, review lenses one after another under eight cores); and budget and deploy approvals the build seat refused because they were relayed.
- Secret values are never printed or written; any that appears in a probe's output is redacted.
- `software-factory` runs it at step 8, before `build-loop`, and verifies it at step 9. The loop prompt runs `<ENV_CHECK_COMMAND>` before wave zero and on every resume, takes its lane count as the ceiling, and stops with an `environment-blocked` handoff on failure. It reads `<STANDING_DECISIONS_PATH>` and takes a change only when the owner types it in its own session.
- Trigger evals now cover four skills; five task evals for the new skill.
- Self-test: 51 tests (from 47).

## 0.4.0

- **The Kanban board.** `progress.py` gains a second view of the same data, `--view kanban` (or `"view": "kanban"` in `monitor.json`, now the example's default). Every register row is a card in one of six columns: Backlog, Next wave, This wave, Rework, Parked, Done. Only `done_verdicts` (PASS by default) reach Done. Queue files are read as a lane table or as `**lane**` entries, with "SES-05, 06" and "TRI-01..04" expanded and only ids on the scoreboard counted. A module filter narrows the board; lanes carried after a refutation are marked.
- **The run.** Above the board: spent against the cap, time against the deadline (or "runs until finished"), waves recorded, spend and rows per wave, a projection bound by whichever of budget or clock runs out first, and what finishing every row would take at the current pace, with a per-wave table. Figures come from the build seat's `checkpoint.json` and, when it is committed, its git history; otherwise from the journal's `usage` events. `run.limit_override` and `run.no_time_limit` hold the owner's later word until the checkpoint catches up.
- Optional `status_file`: the build seat's latest status checklist, shown on the board and used to judge health.
- A missing gates file no longer stops the page.
- First used on the Keystone build, where the owner asked for the board in place of the checklist.
- Self-test: 47 tests (from 43).

## 0.3.0

Five additions for a build nobody reviews wave by wave. None was measured on the source build; each extends a rule that held there only while someone watched.

- **Lessons become checks.** Every refutation that stands (contention ruled out) is appended to a checks ledger as a failure class, its lens, its evidence and, where it can be mechanical, a script under `scripts/checks/`. Panels read their lens's checks before the claim and run the scripts; the barrier runs them all. The ledger is append-only, and a check is retired only by a ruling that names it, never the loop's (ruling policy §Retiring a check). Lanes that collided at a barrier go in a never-together ledger under the same rules, and pre-flight keeps them out of one wave.
- **Clean rounds.** A lane is finished when `<CLEAN_ROUNDS>` (default 2) fresh panel rounds in a row come back clean at the same lane commit. Any commit resets the count; a refuted round ends the stage; rounds don't use up the three stages. Each verifier writes a `## Prediction` before it reads the builder's self-report.
- **Test-freeze hook.** A new PreToolUse hook (`hooks/test-freeze.py`) refuses an edit to a committed test, inert until the repo commits `.claude/test-freeze.json`. The pre-barrier `tests` line is the guarantee: it fails a merge that edits a committed test, or deletes one without a supersession record whose successor names it.
- **Pre-flight.** New `preflight.sh`, run at wave open and before every barrier attempt: generated files free of slots, disk, reboot since last seen, pending reboot, login time left, usage window and budget, never-together. Exits 0 go, 1 fail, 10 pause, 20 stop, 30 recover. An expiring login stops the loop cleanly with an `auth-expiring` handoff, never mid-barrier. A spent usage window **pauses** until the reset: the seat writes the keep-alive hook's new `pause` file, which lets it stop uncounted, and is woken by the rig's resume mechanism.
- **Usage ledger.** The journal's `usage` and `rate_limit` events are the pacing source: the next wave or barrier is estimated as the largest of the last three.
- New `guards.py` (standard library) behind the pre-barrier ratchet lines and pre-flight: `ledger`, `checks`, `tests`, `panels`, `together`, `pace`, `auth`.
- The ratchet guards itself: check scripts under `scripts/checks/` are frozen like tests; the freeze config's `frozen` list (by default `guards.py`, `pre-barrier.sh`, `preflight.sh`) may not change at all; and `pre-barrier.sh` judges each merge with the trunk's committed `guards.py`, not the candidate's.
- `pre-barrier.sh` gains five lines: tests, checks-ledger, together-ledger, panels, checks.
- The factory has thirteen gates: 11 (pre-flight) and 12 (the ratchet). The rig template gains §Disk and reboots and §Login and usage; recovery gains three drills (reboot, usage limit, login expiry); the allowlist gains the new scripts and denies edits to the freeze config.
- The progress page shows `paused` time in "Where the time went"; the monitor checks clean rounds, predictions and proposed checks at review.
- One new task eval each for `build-loop` and `software-factory`.
- Self-test: 43 tests (from 26).

## 0.2.1

- **Where the time went.** The loop prompt now has the build seat journal a start and end `phase` event for each step (`cut`, `build`, `verify`, `review_wait`, `barrier`, `record`, `owner_wait`). `progress.py` gives each minute of a wave to the highest-priority active phase (work outranks waiting) and reports gaps as unaccounted, so each wave's split adds up to its real span. The progress page shows the current wave as a stacked bar with the largest cost named, and the last twelve waves for comparison. Enabled by `timing.journal` in `monitor.json`.
- `build-monitor` reads the new section on each pass and answers "why is it slow?" from it; one new task eval and one trigger query.
- Fixed a layout bug present since 0.1.0: at phone width the progress page scrolled sideways because the wave table's minimum width stretched the whole column. It now scrolls inside its own panel.
- Self-test: 26 tests (from 22).

## 0.2.0

### Keep-alive hook
- Rewritten in Python (`hooks/build-loop-continue.py`); the bash version is removed.
- `max` now caps consecutive continuations **without progress**. A new commit on any branch, or a change to a `progress_paths` file, resets it. Previously it counted every continuation per arming, so a long healthy build disarmed itself.
- New `max_total` (default 500) caps continuations per arming regardless of progress.
- State is per repo (`~/.claude/state/build-loop/<repo-key>/`), so builds on one machine no longer share a counter or stop file. The old single `armed.json` is still honoured.
- The loop prompt's path is configurable (`prompt_path`).
- Errors inside the hook allow a normal stop.
- New `hooks/arm.py` (`nonce`, `arm`, `status`, `disarm`) replaces hand-writing `armed.json`.

### Portability
- README lists every tool dependency with its fallback.
- `build-monitor` adds a file channel for sessions without `ListAgents`/`SendMessage`, and a local-HTML fallback when the Artifact tool is absent.
- The rig template covers sleep checks on macOS, Linux and Windows.

### Structure
- `software-factory/SKILL.md` steps 4 to 6 slimmed to instruction plus exit condition; rationale and script contracts moved to `references/harness-gates.md`.
- `references/recovery.md` rewritten: defined terms, enforced versus prompt-only rules, the usage-source requirement, and explicit met / waived / blocked rules for gate 9.
- Skill descriptions no longer overlap.

### Evidence and evals
- README states the evidence's limits.
- Task evals and trigger evals for each skill (`skills/<name>/evals/`), generated trigger sets from `evals/triggers.json`.

### House style and templates
- UK spelling throughout, no em dashes in prose; enforced by a new style test.
- Hinted slots use `<NAME: hint>`, which the documented slot grep matches; the old em-dash form did not.
- `monitor.example.json` placeholders renamed so the slot grep catches them.
- `progress.py` accepts `: ` as well as the older em-dash separator in queue, owner-list and merge-subject lines, so older records still parse.

### Self-test
- 22 tests (from 11): hook and arming helper, and house style, added.
