# software-factory

Four Claude Code skills for running an autonomous software build: a
requirements register in, a build proved row by row against it, with
verification you can inspect and no one watching the terminal.

The loop itself is the easy part. Whether an unattended build finishes depends
on the factory around it (an oracle worth building against, a machine that
doesn't swap or sleep, permissions the loop already holds, tests that clean up
after themselves) and on a second pair of eyes that reviews what the gates
can't see.

| Skill | When | What it does |
| --- | --- | --- |
| `software-factory` | Once, before the build; again if a running build stalls on its environment | Quality-tests the requirements register and the definition of done, has the interface defined and the owner approve mockups of the key screens before the register freezes (design system, design rows, a screenshot-vs-mockup check), then primes thirteen gates: rig memory and sleep, standing permissions, a ruling policy, test-data lifecycle, lane provisioning, per-lane databases, reachable done conditions, generated state, a guarded deploy, named seats, a pre-flight for login, usage, disk and reboots, and a ratchet so tests and checks only get stricter. Then invokes `build-loop`. |
| `environment-check` | Once, at the end of priming, from the session the build will run in; again when a running build hits a missing token, host, migration or login | Lists everything the build needs from outside the repo (secrets, CLIs, hosts, the hosted database's migration path, the deploy target, logins, the owner's standing decisions) and proves each from the build's own session. Catches misspelt secret names, a deploy that does not apply migrations, logins only the owner can create, and a wave plan wider than the machine. Gives the owner one list of what to fix, and the loop reruns it before wave zero. |
| `build-loop` | Once, at the end of priming; again to fix the loop prompt's logic | Interviews you and writes the loop prompt, the shared-resource conventions, a status readout and the scoreboard. Waves run parallel lanes in worktrees, each built and then attacked by adversarial verify panels until two rounds in a row come back clean at the same commit (up to three build stages inside the wave), and then one serial barrier. Every refutation that stands becomes a check later waves apply. Five gate counts ratchet: none may rise. |
| `build-monitor` | For the life of the build, in a second session | Reviews every lane before merge (screenshots at phone and desktop width), rules within your delegation, shapes the next wave's queue, runs staging checks, keeps your to-do list short, and publishes a generated progress page: a **Kanban board** of every register row with the run's spend, clock and projection, or a **checklist** of road to done, the current wave lane by lane, the next queue, what waits on you, where each wave's time went, and history. |

The plugin also registers two hooks, each inert until you set it up for a repo:
a **keep-alive Stop hook** for the build seat, and a **test-freeze hook** that
refuses edits to committed tests (see below).

## Where this came from, and what that does and doesn't show

All three skills were extracted from one real build: a UK accountancy
practice-management product, built by this loop over 113 waves between August
and September 2026. Every rule cites what it cost when it was missing
(`skills/*/references/evidence.md`).

Read the figures with three limits in mind. They come from **one build**. The
artefacts they cite live in a private repository and are not published, so the
citations can't be checked from here. And that build **had not finished**: at
wave 113, 132 of 152 requirement rows were PASS (the rest out of scope, or
derived at the end), and the done sequence had not been run. What it does show:

- In the early waves, about two thirds of the calendar was lost to stalls on
  the machine, on permissions, and on questions queued for a person. The
  factory's gates exist to remove those.
- Most rows passed in the first ~30 waves could be proved with nothing
  rendered. Gate 0, the oracle review, exists to catch that before building
  starts.
- Over waves 101 to 112, with the monitor seat and multi-stage lanes in place,
  12 waves went green in about 74 hours, 7 of them at the first barrier
  attempt. Several changes landed together, so no single one can claim that.

## Where the time goes

The build seat journals a start and end event for each step of a wave: cutting
lanes, building, verify panels, waiting for review, barrier attempts, the record,
and waiting on you. The progress page splits each wave's wall-clock across those
steps, giving every minute to the busiest step active in it, so parallel lanes
aren't double-counted. Minutes where nothing was recorded show as
**unaccounted**. Every bar adds up to the wave's real length, so the largest
segment is the thing to fix. Point `timing.journal` in the monitor's config at
the journal to turn it on.

## Checks that only get stricter

Nobody reviews every wave of an unattended build, so the verification has to
tighten by itself and be unable to loosen quietly:

- **Lessons become checks.** Every refutation that stands (contention ruled
  out) is written to an append-only checks ledger as a failure class, with a
  script where one fits. Later panels apply it and the barrier runs it. A check
  leaves only by a ruling that names it, never the loop's own.
- **Clean rounds.** A lane is finished when two fresh panels in a row find
  nothing at the same commit. Each verifier writes its prediction before it
  reads the builder's claim.
- **Tests are superseded, never edited.** The test-freeze hook refuses an edit
  to a committed test; the pre-barrier script fails a merge that makes one
  anyway.
- **Pre-flight.** Before each wave and each barrier, one script checks the
  login, the usage window, the budget, disk, reboots and the generated config.
  An expiring login stops the build cleanly, never mid-barrier. A spent usage
  window pauses it until the reset.

These are new in 0.3.0 and, unlike the rest, were not measured on the source
build.

## Before the build starts: the environment check

The factory primes the machine and the repo. The environment check proves the
world outside them: every token the build needs is set under its exact name and
works against the real target, every host is reachable, the deploy script
applies migrations with the database's CLI, every login someone will use has
someone responsible for creating it, the owner's standing decisions are written
in the repo, and the wave plan fits the machine. It runs from the session the
build will run in, because a cloud session never sees environment changes made
after it started, and the loop runs it again before wave zero.

It was added after the Keystone build found each of these mid-build
(`skills/environment-check/references/evidence.md`); like the 0.3.0 additions,
it has not yet been measured on a build from the start.

## Install

```
/plugin marketplace add benjchurchill1/software-factory
/plugin install software-factory@software-factory
```

## Use

1. In the project, run `/software-factory`. It works through the gates in
   order and tells you which ones need your hands. Two always do: pasting the
   permission allowlist, and granting the ruling delegation.
2. It finishes by running `build-loop`, which writes the loop prompt.
3. Arm the keep-alive hook (below), then start the build seat with that prompt.
4. In a second session, run `/build-monitor`. It finds the build seat, writes a
   progress config beside the repo, and generates the progress page after
   every wave.

### The keep-alive hook

A loop seat ends its turn after each wave and nothing re-invokes it. The hook
blocks that stop, within bounds. Arming is your action, never the build seat's.

```
python3 hooks/arm.py nonce                          # prints a unique marker
python3 hooks/arm.py arm /path/to/repo --marker <nonce> --exclude <monitor session id>
python3 hooks/arm.py status                         # what is armed, and its counts
python3 hooks/arm.py disarm /path/to/repo
```

(`hooks/` is inside the installed plugin; run the script from there, or copy it.)

- **Holds** only a session whose transcript contains the marker, inside the
  repo, and not in `--exclude`. Put the marker in the prompt you **paste** to
  start the build seat, not in the prompt file on disk, which the monitor seat
  reads.
- **`--max`** (default 60) caps consecutive continuations **without progress**.
  Progress is any new commit on any branch in the repo, or a change to a file
  named with `--progress-path`. **`--max-total`** (default 500) caps
  continuations per arming regardless.
- **Stops holding** when the seat writes its stop file (`arm` prints the path,
  and the hook tells the seat), when a cap is reached, or 72 hours after
  arming.
- **Lets a paused seat stop** while its pause file names a time still to come.
  The seat writes it when pre-flight says a usage window is spent; nothing is
  counted, and the file is ignored once the time has passed.
- **`--prompt-path`** tells the hook where the loop prompt lives if it isn't
  `docs/prompts/build-loop.md`.
- Each repo has its own state directory under `~/.claude/state/build-loop/`, so
  builds on the same machine don't share counters or stop files. Re-arming
  clears a previous stop file and resets the counts. An arming written by an
  earlier version at `~/.claude/state/build-loop/armed.json` is still honoured.

### The test-freeze hook

Inert until the repo commits `.claude/test-freeze.json` (the factory drafts it
at gate 12; you place and commit it):

```json
{"tests": ["tests/**", "**/*.spec.ts", "scripts/checks/**"],
 "frozen": ["scripts/guards.py", "scripts/pre-barrier.sh", "scripts/preflight.sh"],
 "base": "your-trunk-branch",
 "supersessions": "docs/build/supersessions.jsonl"}
```

In that repo and its lane worktrees, an Edit or Write to a file matching
`tests` that already exists on `base` is refused, with instructions to write a
successor instead. Tests a lane creates are not frozen until merged. Check
scripts belong in `tests`, because a weakened check is a weakened test. The
`frozen` paths are the ratchet's own scripts (these three by default): no
merge may change them at all, and the pre-barrier script judges each merge
with the trunk's copy of `guards.py`, not the candidate's. A shell
command can still change a file, so the pre-barrier script's `tests` line is
the guarantee and the hook is the early warning.

## Requirements

- `git`, `bash` and `python3`. Everything the plugin runs uses the standard
  library only.
- A requirements register (one row per requirement, with a pass criterion) and
  a single command that means "green". `software-factory` helps you get both
  into shape.
- Claude Code, plus the capabilities below. Each has a fallback, and the skills
  say which they are using.

| Capability | Used for | If it isn't available |
| --- | --- | --- |
| The Workflow tool | Parallel lanes and verify panels in one wave | Serial iterations with subagents for verification. Slower, same contract. |
| Ultracode | The intended single-session mode for the loop | `/loop` with one wave per firing, as the loop prompt describes |
| `ListAgents` and `SendMessage` | The monitor seat finding and talking to the build seat | A file channel: `inbox/to-build.md` and `inbox/to-monitor.md` in the orchestrator directory |
| The Artifact tool (claude.ai) | Publishing the progress page at a stable link | Open the generated HTML file locally, or serve it with `python3 -m http.server` |
| macOS | The rig and sleep checks were exercised here | The rig template has Linux and Windows equivalents; check them once on your machine |

The templates assume a database-backed web app (per-lane databases, a
Playwright e2e suite). Gates that don't apply, such as lane databases for a
project with no shared service, are waived with the reason written down.

## Checking the plugin

```
python3 skills/software-factory/scripts/verify-factory.py
```

This renders the factory's shell templates into temporary git repos (including
one at a path with a space) and exercises them; tests `guards.py` (the ledgers,
the test freeze, clean rounds, pacing and the login check) and the pre-flight
script's exit codes; tests both hooks and the arming helper against real git,
including a lane worktree; and checks the house style: UK spelling and no em
dashes in the prose.

That shows the scripts behave. Whether Claude follows the skills is a separate
question, and each skill has evals for it in `skills/<name>/evals/`:
`evals.json` holds task prompts with assertions, and `trigger-evals.json` holds
twenty-one queries per skill for testing that the right skill fires. The trigger
sets are generated from one list, `evals/triggers.json`, so each skill is
tested against the others' near-misses:

```
python3 evals/split_triggers.py
```

Run both with the skill-creator skill's eval and description-optimisation
workflows.

## Licence

MIT
