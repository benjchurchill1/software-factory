# Gates 4, 5 and 6: test data, lane provisioning, lane databases

These three gates assume a shared stateful service (a database, a broker). The
SKILL.md step for each says what to do and when it is closed. This file says
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
