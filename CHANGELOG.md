# Changelog

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
