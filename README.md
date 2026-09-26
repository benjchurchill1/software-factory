# software-factory

Three Claude Code skills for running an autonomous software build: requirements
in, working product out, with verification you can trust and no one watching
the terminal.

The loop itself is the easy part. Whether an unattended build finishes depends
on the factory around it (an oracle worth building against, a machine that
doesn't swap or sleep, permissions the loop already holds, tests that clean up
after themselves) and on a second pair of eyes that reviews what the gates
can't see.

| Skill | When | What it does |
| --- | --- | --- |
| `software-factory` | Once, before the build | Quality-tests the requirements register and the definition of done, then primes eleven gates: rig memory and sleep, standing permissions, a ruling policy, test-data lifecycle, lane provisioning, per-lane databases, reachable done conditions, generated state, a guarded deploy, and named seats. Then invokes `build-loop`. |
| `build-loop` | Once, at the end of priming | Interviews you and writes the loop prompt, the shared-resource conventions, a status readout and the scoreboard. Waves run parallel lanes in worktrees, each built and then attacked by an adversarial verify panel (up to three stages inside the wave), and then one serial barrier. Five gate counts ratchet: none may rise. |
| `build-monitor` | For the life of the build, in a second session | Reviews every lane before merge (screenshots at phone and desktop width), rules within your delegation, shapes the next wave's queue, runs staging checks, keeps your to-do list short, and publishes a generated **progress checklist**: road to done, the current wave lane by lane, the next queue, what waits on you, and history. |

The plugin also registers a **keep-alive Stop hook** for the build seat. It
does nothing until you arm it (see below).

## Where this came from

All three skills were extracted from one real build: a UK accountancy
practice-management product, built by this loop over 113 waves between
August and September 2026. Every rule cites what it cost when it was missing
(`skills/*/references/evidence.md`). The cited artefacts live in the private
source repository and are not published. A few figures:

- In the early waves, two thirds of the calendar was stall on the machine,
  permissions and questions queued for a person. The factory's gates exist to
  remove that.
- Most rows passed in the first ~30 waves could be proved with nothing rendered.
  Gate 0, the oracle review, exists to catch that before building starts.
- With the monitor seat and multi-stage lanes in place, 12 waves went green in
  about 74 hours, 7 of them at the first barrier attempt. By wave 113, 132 of
  152 requirement rows were PASS (the rest out of scope, or derived at the end);
  the build had not yet run its done sequence.

## Install

```
/plugin marketplace add benjchurchill1/software-factory
/plugin install software-factory@software-factory
```

## Use

1. In the project, run `/software-factory`. It works through the gates in
   order and tells you which ones need your hands. Two always do: pasting the
   permission allowlist, and granting the ruling delegation.
2. It finishes by running `build-loop`, which writes the loop prompt. Start the
   build seat with that prompt.
3. In a second session, run `/build-monitor`. It finds the build seat, writes a
   progress config beside the repo, and publishes the checklist page. It
   updates the page after every wave.

### The keep-alive hook

A loop seat ends its turn after each wave and nothing re-invokes it. The hook
blocks that stop, within bounds:

- **Arm it** by writing `~/.claude/state/build-loop/armed.json`:
  ```json
  { "cwd_prefix": "/path/to/repo", "marker": "a phrase from your loop prompt", "max": 60, "exclude_sessions": [] }
  ```
- **Holds** only the session whose transcript contains `marker`, inside
  `cwd_prefix`.
- **Stops holding** when the seat writes `~/.claude/state/build-loop/stop`,
  when `max` continuations are used, or when the arming is over 72 hours old.
- **Disarm** it by deleting `armed.json`. To re-arm after a deliberate stop,
  delete `stop` too: a stop file stays in force until removed.
- **Pick the marker carefully**: a unique nonce that appears only in the prompt
  you paste to start the build seat, not in the prompt file on disk (the
  monitor seat reads that). Put the monitor's session id in
  `exclude_sessions`. With no marker the hook holds nothing.

## Requirements

- Claude Code, with the Workflow tool or subagents for parallel lanes.
- `git`, `bash` and `python3`. The progress page generator and the factory's
  self-test use the standard library only.
- A requirements register (one row per requirement, with a pass criterion) and
  a single command that means "green". `software-factory` helps you get both
  into shape.

The templates assume a database-backed web app (per-lane databases, a
Playwright e2e suite). Gates that don't apply, such as lane databases for a
project with no shared service, are waived with the reason written down.

## Checking the plugin

```
python3 skills/software-factory/scripts/verify-factory.py
```

This renders the factory's shell templates into temporary git repos, including
one at a path with a space, and exercises them.

## Licence

MIT
