# Gates 4, 5, 6, 11 and 12: test data, lanes, lane databases, pre-flight, the ratchet

Gates 4 to 6 assume a shared stateful service (a database, a broker); gates 11
and 12 apply to every build. The SKILL.md step for each says what to do and
when it is closed. This file says
why, and holds the exact contract each script must meet, which is also what
`scripts/verify-factory.py` tests.

## Gate 4: every spec removes what it creates

### The failure

Residue was the most frequent red cause across the source build's waves 101 to
113, and each time it was data a spec had made on the shared practice and left.
An age-based reaper existed throughout. It was a backstop that ran too late to
stop the red.

### The rule

- **Teardown is the spec's, from wave 1.** Every spec removes what it creates,
  found by a **positive marker the spec itself writes**: a reference prefix, a
  fixture seat, a note token. Never by inference from what looks like test
  data.
- Where records are audited, the spec closes them through the product's own
  paths, as a user would, rather than deleting underneath the audit trail.
- Every population a test mints is **declared**. Anything undeclared is
  **reaped by age** at the barrier.
- The reaper's floor (rows a constraint will refuse to delete) is reported,
  never forced.
- `estate-maintain.sh` reaps orphans of **both** kinds: stranded database
  connections and stranded app servers.
- A **residue census** (a count, per minted population, of rows no live run
  owns) is measured at every barrier and ratcheted like any other gate.

### Script contract: `estate-maintain.sh`

- `--dry-run <evidence-dir>` plans and prints. It drops nothing, creates no
  evidence directory or log, and runs no database, process or analysis
  command.
- The evidence log path is declared, and its nearest existing parent is
  checked for writability without creating anything.
- The evidence path is created only on a real run.
- Any failing step fails the run with a non-zero exit.

## Gate 5: the orchestrator provisions every lane in one step

### The failure

Two conventions in the source build (prove your base; take your migration range
from the brief) were both written down, both read, and both recurred. 119 of
188 worktrees were cut at a commit from a different project, and four of eleven
lanes chose the same migration number. The ruling was that a lane does not cut
its own worktree or choose its own number. The instant a lane comes into
existence is the only instant at which both facts are known and cheap, so the
orchestrator provisions both there, with a script.

Never let a generic tool infer the base. The Workflow tool's
`isolation: 'worktree'` cuts from `main`. On the source build the trunk was not
`main`, and reaching past the script for it was E-14's fourth recurrence.

Paths with spaces are a second, quieter failure. The source build's wave 112
lane was green in its worktree and red in the main checkout, whose path held
spaces: `URL.pathname` keeps `%20`, so use `fileURLToPath`.

### Script contract: `lane-cut.sh`

- Cuts from the trunk's current tip. The trunk and the wave come from
  `lane-cut.conf`, which the orchestrator moves, never from the script's
  source.
- Links dependencies, then runs the **base proof**: the tip is an ancestor of
  the new tree, the expected directories exist, and the typecheck and the test
  harness both load.
- Runs one path-sensitive test from a path containing a space, once at this
  gate, unless the repo path is guaranteed free of them.
- Allocates the lane's identifier range and writes the range ledger.
- Lane names match `[a-z][a-z0-9_]{0,47}`. `status` is reserved. Invalid
  input is rejected, not normalised into something valid.
- `--dry-run <n>` prints every command it would run. It cuts nothing, creates
  no proof log and invokes no range allocator.
- `status` lists live lanes.
- The trunk owner provisions serially and uses names unique across active
  waves, retiring old lane databases before a name is reused.

### Script contract: `pre-barrier.sh`

Runs after the serial merge. One PASS or FAIL line per check:

- every lane branch is an ancestor of the integration branch (or declared
  squashed with `--squashed`);
- no lane diff adds `trace.zip`, `*.har` or `.env*`;
- the ratchet (gate 12): no committed test edited, both ledgers append-only,
  clean panel rounds at every lane tip, the ledger's checks green;
- the typecheck, the registry duplicate check, and the suites lanes cannot run.

The trunk, the integration branch and the lane glob come from `lane-cut.conf`.
`--dry-run` prints every check and runs none.

## Gate 6: lanes prove their integration tests before the barrier

### The failure

If parallel builders exist and integration tests need a shared service, those
tests otherwise first execute at the barrier, and the first barrier attempt is
red almost every wave.

### The shape

`lane-db.sh` stands up a second container, replays the schema into a template
once, and clones per lane in about a second.

Two classes of test cannot move there and must be named in the conventions
doc: those that talk to the shared service over HTTP, and those that build an
expensive fixture.

### Script contract: `lane-db.sh`

- `up` reports the replay time and a conformant template.
- `clone <lane>`, one small test, and `drop <lane>` all succeed, and the
  shared service is unchanged afterwards.
- Each lane's command runs in its own process group, recorded, so `stop` ends
  exactly that tree. That guard exists because a `pkill -f` once left an
  orphaned test process running against a database its lane had dropped and
  re-cloned.
- A second run on a live lane is refused.
- Lane names follow the same rule as `lane-cut.sh`, and unknown or reused
  identities are refused.

## Gate 11: the build sees its limits coming

### Why, and what it is not

New in 0.3.0; not measured on the source build, whose seats were attended
often enough that a person noticed an expired login. An unattended build has no
such person, and four things arrive from outside the product: a login that
expires, a usage window that runs out, a disk that fills, a host that reboots.
Each surfaces as a failure in whatever step was running. The barrier is the
worst place: it holds the shared resource, and an interrupted barrier leaves
the recovery protocol a merge, a migration or a check to reconcile.

The login is the one only a person can fix, so it **stops** the loop, early
enough to stop cleanly. The usage window comes back by itself, so it
**pauses** the loop until the reset. A reboot sends the loop to its recovery
protocol. Low disk is fixed before anything launches.

### Script contract: `preflight.sh`

- Runs at wave open (`--queue <file>`, required) and before every barrier
  attempt (`--barrier`). One line per check, in order: config, disk, boot,
  reboot, auth, usage, together.
- **config**: every generated file the loop reads exists and holds no
  unreplaced slot.
- **disk**: at least the floor free on every listed path (`df -Pk`, which reads
  the same on macOS and Linux).
- **boot**: the boot id matches the one recorded in the run-state directory;
  the first run records it; a mismatch is RECOVER until `--ack-reboot`.
- **reboot**: a pending reboot is WARN and does not block.
- **auth**: the login's time left (reported, or counted from `auth-at` and the
  lifetime) covers the step's time limit plus the handoff reserve, or STOP. When
  it cannot be told, STOP: an unknown login is not a live one.
- **usage**: `guards.py pace` over the journal's usage events. STOP when the
  total budget cannot fund the step plus the reserve; PAUSE, printing
  `resume_at`, when a recorded usage limit has not reset yet, or the window's
  remainder cannot fund the step.
- **together**: at wave open, no pair from the never-together ledger is in the
  queue.
- Exit 0 go, 1 FAIL, 10 PAUSE, 20 STOP, 30 RECOVER; precedence STOP, RECOVER,
  FAIL, PAUSE. `--dry-run` prints every check and runs none. It writes nothing
  but the boot id.

A pause is written to the keep-alive hook's `pause` file, which lets the seat
stop, uncounted, until the reset. What wakes it then is the rig's
`<RESUME_MECHANISM>`: `/loop`'s next firing, a scheduled resume of the session,
or, where there is nothing, a line on the owner's list with the reset time.

## Gate 12: tests and checks only get stricter

### Why

New in 0.3.0, and the direct extension of two source-build rules that held only
while someone watched: "never weaken a test" and "contention is not refutation"
(`evidence.md`). With nobody reviewing every wave, three things decide whether
the verification drifts:

1. **A weakened test is invisible.** The suite goes green and the record looks
   like diligence. The test freeze makes a committed test impossible to edit
   and possible only to supersede, on the record.
2. **A lesson that is only fixed is learnt once.** The checks ledger turns each
   refutation that stood into a check every later panel applies, and the
   never-together ledger does the same for lanes that collided.
3. **A list the loop can shorten is not a ratchet.** Both ledgers are
   append-only, and an entry leaves only by a ruling that names it, made by the
   owner or the reviewing seat, never by the loop.

Clean rounds belong here too: a lane is finished only when fresh panels, in a
row, find nothing at the same commit, and each forms its view before it reads
the builder's claim.

### Contract: `guards.py`

Standard library only; each subcommand prints one line and exits 0 PASS, 1
FAIL, 10 PAUSE or 20 STOP.

- `tests`: against the trunk, a committed test file (by the freeze config's
  `tests` globs, which include `scripts/checks/**`) that is modified is FAIL;
  one deleted needs a supersessions record whose successor exists and names
  it; any change at all to a `frozen` path (by default `guards.py`,
  `pre-barrier.sh`, `preflight.sh`) is FAIL; the freeze config itself
  unchanged; the supersessions register append-only.
- **Who judges.** `pre-barrier.sh` runs `guards.py` as committed on the trunk,
  never the merge candidate's copy, so a lane that edits the guards cannot
  pass its own merge. The trunk's copy starts as the owner's and can change only
  through a merge that this same check would fail.
- `ledger`: the file's trunk lines are a prefix of its current lines; every line
  is an `add` or a `retire`; an `add` has an id, a source and (checks) a class,
  and any `run` is a script under `scripts/checks/` that exists; a `retire`
  follows its `add` and cites a ruling file that exists and names the id.
- `checks`: every active check with a script runs green.
- `panels`: for each lane, the last N panel events in the journal are clean and
  at the lane's tip commit, and no stage passed the cap.
- `together`, `pace`, `auth`: the pre-flight checks above.

### The test-freeze hook

`hooks/test-freeze.py`, registered by the plugin as a PreToolUse hook on Edit,
Write, MultiEdit and NotebookEdit. Inert in a checkout without
`.claude/test-freeze.json`. Refuses an edit to a path matching the config's
globs, or the `frozen` list, that exists on the config's `base`, and to the
config itself; allows everything else, including tests a lane created. A shell command gets past it,
which is why the pre-barrier line is the guarantee and the hook is the warning.
