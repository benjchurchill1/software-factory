# Build conventions: <PROJECT>

What builders and verifiers must know before writing a line. The loop prompt
points here at wave start; this file is where the rules that would otherwise be
re-learned the hard way are written down.

## Commands

| Command | What it does | Who runs it |
| --- | --- | --- |
| `<BUILDER_GREEN_COMMAND>` | <WHAT_IT_COVERS: no shared resource> | builders, in their worktree: must be green before returning |
| `<CHECK_COMMAND>` | everything above **plus** <SHARED_RESOURCE_SUITES> **plus** <RUNTIME_CHECK> | the orchestrator at the merge barrier: must be green before any commit |
| `<STATUS_COMMAND>` | read-only: live runs, contention, orphans, scoreboard | anyone, at any point in a wave |
| `<LANE_CUT_COMMAND>` | provision worktree, base proof and range ledger | orchestrator before dispatch |
| `<LANE_DB_COMMAND>` | clone/exec/stop/drop isolated lane database | lane integration checks before returning |
| <OTHER_COMMANDS> | | the orchestrator only |
| `<PRE_BARRIER_COMMAND>` | after the serial merge: lane ancestry, no trace or credential artefacts, the ratchet (no committed test edited, both ledgers append-only, <CLEAN_ROUNDS> clean panel rounds at each lane tip, the ledger's checks), typecheck, registry duplicates, the suites lanes cannot run | the orchestrator, before every barrier attempt |
| `<PREFLIGHT_COMMAND>` | at wave open and before every barrier attempt: generated files free of slots, disk, reboot, login, usage and budget, the never-together ledger | the orchestrator; nothing launches on a non-zero exit |
| `python3 scripts/guards.py checks <CHECKS_LEDGER>` | runs every active check with a script | each lane's panel, in the lane's worktree |

## Seats

Three parties, each with one job. On the source build the second agent seat
carried the quality layer of its best stretch and was written down nowhere but
commit messages and memory; this section is where it is written down.

| | Owns | Writes | Never |
| --- | --- | --- | --- |
| **Owner**: <OWNER> | rulings the policy cannot make; register changes; permission-gated commands; deploy consent | the register, by hand; the rulings they make | (none) |
| **Build seat**: <TRUNK_OWNER> | <BRANCH>, the shared <SINGLETON>, lane provisioning, the barrier, the record, the push | code, via lanes; wave records; rulings under the written policy | merges a lane before its handback; spends barrier attempt 3 on a repair; pushes <DEPLOY_BRANCH> |
| **Monitor seat**: a second session running `build-monitor` | approval of each lane before merge; rulings within the delegation; the next wave's queue, with the build seat; staging and its falsifiers | drafts in its own scratchpad, handed over by message (`SendMessage`, or the file channel in the orchestrator directory's `inbox/` where that tool is absent); the build seat commits them with attribution | writes into the shared checkout while a barrier runs |

Rules between seats:

- **Never message a running workflow agent.** A message resumes it as a second
  writer in the same worktree, and a stand-down reply forks it again. Act, or
  say nothing; the lane's own default resolves it.
- **Never use the Workflow tool's `isolation: 'worktree'` while <BRANCH> is not
  `main`.** It cuts from `main`, not from the session's branch; a tool that
  infers its base is no substitute for one told it. Provision every lane with `<LANE_CUT_COMMAND>`,
  then run the workflow with isolation omitted and each agent handed its
  worktree path.
- A seat that disagrees with another about whether something happened settles
  it from the external record (the reflog, the platform's deployment list, the
  log file), not from either seat's memory.

## Test placement

- **<UNIT_SUITE_PATTERN>**: pure logic, no <SINGLETON>. Runs anywhere, including
  a worktree with no access to it.
- **<SHARED_SUITE_PATTERN>**: lane-capable integration tests must pass through
  `<LANE_DB_COMMAND>` in the provisioned worktree before return. The runner
  refuses a missing LANE_DB or a connection to the shared service.
- **<SHARED_RESOURCE_SUITES>**: only these named HTTP/shared-service or
  expensive-fixture suites first execute at the barrier. Never weaken a test
  to make a worktree green. Record an explicit waiver if no stateful service exists.

Use the exact same lane name in both scripts: `[a-z][a-z0-9_]{0,47}`, with
`status` reserved. Reject other names rather than stripping characters; the
48-character cap leaves room for database prefixes within PostgreSQL's limit.
Provisioning is serial under the trunk owner. Names are unique among active
lanes across waves; stop/drop the previous database before reusing a name.

## The runtime check, and the class of defect it exists for

<RUNTIME_CHECK_RATIONALE>

Types, lint and unit tests **start nothing**. A module exporting the wrong shape,
a call site passing credentials the runtime cannot read, a route that returns 200
with an empty body: none are reachable by a test over a pure function, because
the defect is in the composition rather than in any function. A check that starts
the product and exercises it is the only thing that sees them, and it has **no
skip-when-unavailable branch**: a check that quietly skips is how a blind spot is
built.

## <ISOLATION_CONVENTION>

The shared <SINGLETON> belongs to the orchestrator. Lane databases live in a
separate cluster and never mutate it. Parallel work is safe only because
<ISOLATION_RULES> and the lane runner's connection guard.

Builders **never** <FORBIDDEN_MUTATIONS>.

## …and what <ISOLATION_CONVENTION> does NOT buy you

<ISOLATION_CONVENTION> separates **<ISOLATION_UNIT>**. It does nothing about
**<UNSCOPED_RESOURCE>**, and conflating the two is the expensive mistake.

<UNSCOPED_OPERATIONS> take the whole <SINGLETON>. No <ISOLATION_UNIT> key
narrows them, and where such an operation queues (itself waiting behind
something unrelated), everything after it queues too.

The operations that do this, and there are few:

| Where | Operation |
| --- | --- |
| <FILE> | <OPERATION> |

Rules that follow:

- **Bound the wait.** <BOUNDED_WAIT_MECHANISM>, and retry. Note the cost of
  getting it wrong in the other direction: a bounded wait surfaces as
  <TIMEOUT_SIGNAL>, so a test asserting the real failure must retry rather than
  treat the timeout as its answer.
- **One `<CHECK_COMMAND>` at a time.** Two runs against the one <SINGLETON> do
  not halve the wall-clock; they build the convoy above.
- **Killing a run does not free the <SINGLETON>.** Work outlives the process that
  submitted it. Every run tags its <RUN_TAG_UNIT> as <RUN_TAG_FORMAT>
  (<RUN_TAG_MECHANISM>) so a leftover can be reaped by name:

      <REAP_COMMAND>

## <SETUP_COST_SECTION_TITLE>

<SETUP_COST_RATIONALE: the expensive fixture or environment build, how long it
takes, what it holds while it runs, and whether it is rebuilt every run. If a
cleanup step deletes what the next run rebuilds, say so plainly: those two are
paying for each other, and reuse-if-present is the fix.>

## Checks, and the lessons they come from

<CHECKS_LEDGER> holds a check for every refutation that stood: the failure
class, the lens it belongs to, and, where it can be mechanical, a script under
`scripts/checks/` that exits non-zero when the class recurs. A verifier reads
the entries for its lens **before** it reads the builder's claim, and runs the
scripts. <NEVER_TOGETHER_PATH> holds pairs of rows whose lanes collided at a
barrier; they never share a wave. Both files are append-only; an entry is
retired only by a line citing a ruling that names it.

## Contention is not refutation

<TIMEOUT_FACTS: the default timeout, and the observed contention it must sit
above.>

A verifier that reads a contention failure as a refuted row will supersede a
sound test on evidence that is purely queueing, and that is the one failure this
loop cannot correct on its own: the record afterwards looks like diligence.
Before returning a FAIL from a suite that touches the <SINGLETON>, check for
contention (<CONTENTION_CHECK>), re-run the row alone, and say in the finding
that you did.

## Superseding a test, and who deletes the old one

A committed test may not be edited. `.claude/test-freeze.json` names which
files are tests; the test-freeze hook refuses an edit to any of them that
exists on <BRANCH>, and `<PRE_BARRIER_COMMAND>`'s `tests` line fails a merge
that edits one anyway (a shell command gets past the hook, not past the
barrier). A test a lane created itself is not frozen until it is merged. When one is genuinely wrong (it encodes the
defect, or asserts as correct something a later wave refuted), write the
successor, name the predecessor in its header with an assertion map, and record
the predecessor for deletion by the orchestrator at the barrier: one line
appended to <SUPERSESSIONS_PATH>,
`{"predecessor": "<path>", "successor": "<path>", "why": "...", "wave": N}`.
The register is append-only.

Both files must not simply be left to run: two files asserting contradictory
things about the same behaviour keep the barrier permanently red and hide the
next real regression behind known noise. <SUPERSEDE_MECHANISM: where the list
of superseded files lives, and how the runner refuses when an entry is stale.>

This is **not** a way to silence a failing test. Each entry names both files, and
both are checked to exist: a predecessor already deleted, or a successor never
written, aborts the run rather than skipping quietly.
