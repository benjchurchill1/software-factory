---
name: build-loop
description: Interview the user about a register-driven product build, then emit a bespoke autonomous build-and-test loop for Claude Code — the loop prompt itself, a shared-resource conventions doc, a status readout, and a seeded scoreboard. Use when someone wants to set up an autonomous or unattended build loop, a "run until every requirement passes" agent, a wave-based build with adversarial verification, or wants to adapt an existing build-loop prompt to another project. Also use when an existing loop stalls, mistakes a busy machine for a failing feature, marks its own work PASS, or has no closed definition of done.
---

# Build loop

Produce a loop that a competent stranger could run unattended, against a
project it has never seen, and trust the result of.

The loop being generated is a **register-driven product build**: a file of
requirement rows is the work queue, the test oracle and the definition of done.
Work proceeds in waves — parallel builders in worktrees, one serial barrier
where shared state is mutated, parallel adversarial verifiers afterwards.

## What gets written

Four artefacts, all inside the target repo. Paths follow the project's existing
layout; the ones below are the defaults when there is nothing to follow.

| File | From | Purpose |
| --- | --- | --- |
| `docs/prompts/build-loop.md` | `assets/build-loop.template.md` | the prompt the user pastes to run a wave |
| `docs/engineering/build-conventions.md` | `assets/build-conventions.template.md` | the rules builders and verifiers read at wave start |
| `scripts/loop-status.sh` | `assets/loop-status.template.sh` | read-only readout: live runs, contention, orphans, scoreboard |
| the progress scoreboard | derived from the register | one row per requirement, all `TODO` |

Never emit a loop prompt alone. The conventions doc is where the shared-resource
rules live, and a loop with no status readout is one whose failures are invisible
until a human notices the wall-clock.

## Before this: the factory

The loop is only half of what an unattended build needs. The **software-factory**
skill primes the other half — the rig's memory budget, the permission allowlist
so the loop can run its own maintenance, a ruling policy so judgement calls do
not queue on a person, the test-data lifecycle, per-lane databases, and
regenerated state. Those are what decide whether a loop finishes; measured over
waves 31 to 52 of one build (seven days), roughly two thirds of the calendar was lost to
them and almost none to the loop's own design.

If this skill was invoked directly on a new build, say so and offer to run
`software-factory` first. If the factory is already primed, carry on here.

## Workflow

### 1. Orient before asking

Read the repo first and turn as many interview questions as possible into
confirmations. Look for: a requirements/register file; `package.json` scripts or
equivalent for the check command; a migrations directory; existing agent
instructions (`CLAUDE.md`, `AGENTS.md`); hooks in `.claude/`; a git branch that
looks like previous loop work.

Say what was found and what is being assumed. Ask only what the repo cannot
answer.

### 2. Interview

Follow **[references/interview.md](references/interview.md)** — the full question
set in order, with the specific answers that must be pushed back on.

Three answers are load-bearing and get challenged rather than recorded:

- **The oracle.** If the user names the tests, or the loop's own judgement, the
  loop has no oracle. Tests are written by the loop; an oracle the loop can edit
  is not one. Ask again for something the loop may never change.
- **Green.** If no single command means green, or the named command does not yet
  exist, that is wave zero's first job — not something to discover mid-build.
- **The blocked list.** It must be closed and enumerated. An open-ended "some
  rows can't be done locally" is how a loop stops working while looking busy.

Everything else is taken at face value.

### 3. Emit

Fill the templates in `assets/`. Every `<SLOT>` must be replaced or deliberately
removed — a slot left in a generated file is a defect, so grep for `<` before
finishing.

Read **[references/loop-anatomy.md](references/loop-anatomy.md)** while filling
them: it says what each section of the loop prompt is defending against, which
is what decides whether a section can be trimmed for a given project.

Seed the scoreboard from the register: one line per in-scope row, verdict
`TODO`, plus an empty `## Log` section. The loop derives its state from this
file, so it must exist before the first wave.
Seed a separate checkpoint with `bootstrap_complete: false`; scoreboard
existence must never bypass wave zero. Fill the persistent budget/recovery slots
from the factory handover or interview, and preserve them when resuming.

### 4. Verify before handing over

Do not hand over an unrun loop.

- Run the generated `loop-status.sh`. It must execute and print, with the shared
  resource up and down.
- Run the project's check command. It must exist and terminate. If it is red,
  say so — the loop's first wave will inherit that.
- Confirm the scoreboard's row count matches the register's in-scope row count.
- Grep the generated files for unreplaced slots.
- Check ownerless WIP retry, empty-frontier dependency stalls and bootstrap
  completion against the template contract. Record the factory recovery drills
  from `software-factory/references/recovery.md`; do not claim that a prose
  protocol alone proves restart safety.

Report what was verified and what was not.

### 5. Hand over

State how to start it (paste the prompt in an ultracode session, or `/loop` for
one wave per firing), how to watch it (`loop-status.sh`, and the four signals in
the conventions doc), and what it will produce when it finishes.

Three things start with it, and each cost the source build at least one lane or
barrier when missing:

- **The keep-alive Stop hook.** A loop seat ends its turn after a wave or a
  barrier and nothing re-invokes it. The hook blocks that stop, bounded: armed
  by a file naming a marker phrase from the loop prompt (so only the seat
  running the loop is held, never a peer), a stop file the seat writes with one
  line when it halts on purpose, a cap on consecutive continuations, and an
  arming expiry. This plugin ships it as `hooks/build-loop-continue.sh` and
  registers it as a Stop hook; it does nothing until armed. Arm it by writing
  `~/.claude/state/build-loop/armed.json` (`cwd_prefix`, `marker`, `max`,
  `exclude_sessions`); the seat halts on purpose by writing
  `~/.claude/state/build-loop/stop`; arming expires after `MAX_AGE_H` (72 h).
  Arming is the user's action, as gate 2 of the factory is.
- **The monitor seat.** A second session started with `build-monitor`, beside
  the build seat for the life of the build: it approves each lane before merge,
  rules within the delegation, shapes the next wave's queue, runs staging and
  its falsifiers, and reads `loop-status.sh` for liveness. §Seats in the
  conventions doc is its contract.
- **The host kept awake.** On macOS, `caffeinate -dimsu -t 21600` in the
  background before lanes or a barrier, and `pmset -g assertions` showing
  `PreventSystemSleep 1`. Agents that die "[Request interrupted]" are checked
  against `pmset -g log` first: at wave 109 five died in a row because the Mac
  was entering maintenance sleep.

## Adapting an existing loop

When the user already has a loop prompt, do not regenerate it. Read it, run the
interview only for what it lacks, and propose additions as a diff. The common
gaps, in the order they cause damage:

1. No shared-resource law, or one that assumes row-level isolation covers
   whole-resource operations.
2. No rule that contention is not refutation — the loop retires sound tests when
   the machine is merely busy.
3. Builders permitted to record their own verdicts.
4. An open-ended blocked list.
5. No stop condition for "two waves, no change".
