---
name: build-loop
description: Write, or adapt, the loop prompt for a register-driven autonomous build in Claude Code, with its conventions doc, status readout and seeded scoreboard. Waves run parallel builders in worktrees, adversarial verify panels, and one serial barrier. Use when software-factory hands off at the end of priming, when someone asks for a "run until every requirement passes" prompt, or when an existing loop prompt has a logic flaw: builders mark their own work PASS, the loop retires sound tests when the machine is merely busy, the blocked list is open-ended, or there is no stop condition or closed definition of done. For a brand-new build, start with software-factory instead. For a loop stalling on the machine, permissions or queued questions, use software-factory.
---

# Build loop

Produce a loop that a competent stranger could run unattended, against a
project it has never seen, and trust the result of.

The loop being generated is a **register-driven product build**: a file of
requirement rows is the work queue, the test oracle and the definition of done.
Work proceeds in waves: parallel builders in worktrees, one serial barrier
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
skill primes the other half: the rig's memory budget, the permission allowlist
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

Follow **[references/interview.md](references/interview.md)**: the full question
set in order, with the specific answers that must be pushed back on.

Three answers are load-bearing and get challenged rather than recorded:

- **The oracle.** If the user names the tests, or the loop's own judgement, the
  loop has no oracle. Tests are written by the loop; an oracle the loop can edit
  is not one. Ask again for something the loop may never change.
- **Green.** If no single command means green, or the named command does not yet
  exist, that is wave zero's first job, not something to discover mid-build.
- **The blocked list.** It must be closed and enumerated. An open-ended "some
  rows can't be done locally" is how a loop stops working while looking busy.

Everything else is taken at face value.

### 3. Emit

Fill the templates in `assets/`. Every `<SLOT>` must be replaced or deliberately
removed: a slot left in a generated file is a defect, so grep for `<` before
finishing.

Read **[references/loop-anatomy.md](references/loop-anatomy.md)** while filling
them: it says what each section of the loop prompt is defending against, which
is what decides whether a section can be trimmed for a given project.

Seed two files before the first wave:

- **The scoreboard**, from the register: one line per in-scope row, verdict
  `TODO`, plus an empty `## Log` section. The loop derives its state from it.
- **The checkpoint**, with `bootstrap_complete: false`. Wave zero sets it. The
  scoreboard existing is never evidence that wave zero ran, so a resumed loop
  checks the checkpoint, not the scoreboard.

Fill the budget and recovery slots from the factory handover, or the interview
if there was none. When adapting a running loop, keep the values it already
has.

### 4. Verify before handing over

Do not hand over an unrun loop.

- Run the generated `loop-status.sh`. It must execute and print, with the shared
  resource up and down.
- Run the project's check command. It must exist and terminate. If it is red,
  say so: the loop's first wave will inherit that.
- Confirm the scoreboard's row count matches the register's in-scope row count.
- Grep the generated files for unreplaced slots.
- Read the generated prompt's §Persistent budgets and recovery against three cases: a `WIP` row whose
  owner is gone is retried; an empty frontier with rows still open is reported
  as a dependency stall, not done; a restart before `bootstrap_complete` reruns
  wave zero. Restart safety is only shown by running the drills in
  `software-factory/references/recovery.md`; say which were run.

Report what was verified and what was not.

### 5. Hand over

State how to start it (paste the prompt in an ultracode session, or `/loop` for
one wave per firing), how to watch it (`loop-status.sh`, and the four signals in
the conventions doc), and what it will produce when it finishes.

Four things start with it. The first three each cost the source build at
least one lane or barrier when missing; the fourth is new in 0.3.0:

- **The keep-alive Stop hook.** A loop seat ends its turn after a wave or a
  barrier and nothing re-invokes it. This plugin registers a Stop hook
  (`hooks/build-loop-continue.py`) that blocks that stop, within bounds. It
  does nothing until the owner arms it for this repo:
  `python3 hooks/arm.py arm <repo> --marker <nonce> --exclude <monitor session>`,
  with the nonce from `arm.py nonce` placed in the prompt the owner pastes (not
  in the prompt file, which the monitor reads). Pass `--prompt-path` if the
  loop prompt is not at the default path. The hook holds only the marked
  session; caps consecutive continuations without a new commit (`--max`,
  default 60) and continuations per arming (`--max-total`, default 500);
  expires after 72 hours; and tells the seat the stop-file path to write, with
  one line, when it halts on purpose. Arming is the owner's action, as gate 2
  of the factory is.
- **The monitor seat.** A second session started with `build-monitor`, beside
  the build seat for the life of the build: it approves each lane before merge,
  rules within the delegation, shapes the next wave's queue, runs staging and
  its falsifiers, and reads `loop-status.sh` for liveness. §Seats in the
  conventions doc is its contract.
- **The host kept awake.** Before lanes or a barrier, run the hold from the
  rig doc's §Host sleep for this OS (`caffeinate` on macOS, `systemd-inhibit`
  on Linux) and confirm it. Agents that die "[Request interrupted]" are checked
  against the sleep log first: at wave 109 five died in a row because the Mac
  was entering maintenance sleep.
- **The test-freeze hook.** The plugin's PreToolUse hook
  (`hooks/test-freeze.py`) refuses an edit to a test file that exists on the
  trunk, and tells the seat how to supersede it instead. It is inert until the
  repo commits `.claude/test-freeze.json` (software-factory gate 12). The
  pre-barrier `tests` line is the guarantee; the hook saves the lane a stage.

Before the first wave, the owner records the login time
(`date -u +%FT%TZ > <run state dir>/auth-at`) unless the rig has a command that
reports the time left, and the pre-flight runs once by hand.

## Adapting an existing loop

When the user already has a loop prompt, do not regenerate it. Read it, run the
interview only for what it lacks, and propose additions as a diff. The common
gaps, in the order they cause damage:

1. No shared-resource law, or one that assumes row-level isolation covers
   whole-resource operations.
2. No rule that contention is not refutation: the loop retires sound tests when
   the machine is merely busy.
3. Builders permitted to record their own verdicts.
4. An open-ended blocked list.
5. No stop condition for "two waves, no change".
6. Refutations that are fixed but never become checks, so later waves repeat
   them; or a checks list the loop can quietly shorten.
7. One clean panel finishing a lane, with the verifier reading the builder's
   claim before forming its own view.
8. No pre-flight: a login that expires or a usage window that runs out is
   found mid-barrier.
