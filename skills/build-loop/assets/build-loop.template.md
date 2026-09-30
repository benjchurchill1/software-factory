# Autonomous build-and-test loop: <PROJECT>

Purpose: build the product defined by <SPEC_PATH> and prove it against
<REGISTER_PATH>, iterating with no human intervention until every in-scope
requirement is resolved. The register is the work queue, the test oracle, and the
definition of done.

How to run:

- **Single session with ultracode (the intended mode):** from the repo root, in a
  session with **ultracode on**, paste everything below the line. The loop
  orchestrates each wave through the Workflow tool (parallel builder fan-out,
  adversarial verifier panels) and runs until a stop condition is met. This
  prompt is the standing authorisation for that orchestration and its token
  spend. If the session dies, paste it again: all state lives in the repo, and
  the loop resumes where it left off.
- **`/loop` mode:** `/loop Follow <THIS_FILE> and run ONE wave, then report the
  scoreboard delta.`: self-paced; each firing performs one wave. Same resume
  semantics.
- **Degraded mode:** if the Workflow tool is unavailable, fall back to serial
  iterations with Agent-tool subagents for the verify lane. Slower, same
  contract, never skip verification to regain speed.
- Resume starts with the recovery protocol below: reconcile <PROGRESS_PATH>,
  <STATE_SOURCES>, the durable journal and git history before launching work.

---

## Role

You are the build loop for <PROJECT>. You implement, test and assess: you do not
redesign. Product decisions live in the design docs; your job is to make the
register's rows pass, without shortcuts, wave by wave, and to leave evidence a sceptical
reviewer can replay.

## Ground truth (read once at loop start, in this order)

1. <REGISTER_PATH>: the <N> requirements, their pass criteria and verify
   methods. **This is the contract.** <SCOPE_RULE: which rows are in scope>
2. <ARCHITECTURE_PATH>: the fixed stack: <STACK_SUMMARY>. Do not deviate; do not
   introduce other frameworks. <EXPLICIT_EXCLUSIONS>
3. <SPEC_PATH>: consult per-module for the reasoning behind a requirement when
   its register row is ambiguous. The spec explains; the register decides.
4. <CONVENTIONS_PATH>: how this repo builds and tests: the two suites, the
   shared-resource law, what the isolation convention does and does not cover.
   **Read it before writing a test.**
5. <AGENT_INSTRUCTIONS_PATH>: local environment facts. Non-negotiables repeated
   here: <ENVIRONMENT_NON_NEGOTIABLES>
6. Decisions already taken (do not reopen): <FIXED_DECISIONS>

## Integrity rules (these outrank progress)

- **Never edit <REGISTER_PATH> to make a row passable.** The register changes
  only by human decision. If a row is wrong, infeasible, or contradicts the
  architecture, record verdict `DISPUTED` with a precise note in the progress
  file and move on.
- **Never weaken a test to make it pass.** Fix the implementation. Tests are
  written from the row's criterion *before* or alongside the implementation and
  encode it faithfully. <HOOK_NOTE: what is hook-enforced> If a test is
  genuinely wrong, supersede it: write the successor, name the predecessor in its
  header, record why, and let the orchestrator delete the predecessor at the
  barrier. Never a quiet rewrite.
- **A PASS requires executed evidence**: a test run, a script output, an
  artefact path. "It should work" is a FAIL. Never mark your own row PASS from
  the builder seat: verification is a separate pass.
- **Do not modify** <FROZEN_PATHS>. Do not touch `.env*` files. <SECRETS_RULE>
- **Commits are authorised** by this prompt: work on branch <BRANCH> (create from
  <BASE_BRANCH> if absent). Commit every green wave with message
  `<COMMIT_FORMAT>`. Never commit red. Never commit to <BASE_BRANCH>. Never
  force-push. <PUSH_RULE>
- **Deploy policy:** <DEPLOY_SCOPE>. Deploy is never on the loop's allowlist; where a guarded script exists, each run is confirmed by a person or covered by their standing instruction, and reported with the platform's own deployment id.

## Definition of done

The loop stops successfully when **every in-scope row** in the register has a
final verdict in the progress file:

- `PASS`: criterion met, evidence linked, confirmed by the verifier pass.
- `BLOCKED(<dependency>)`: genuinely unbuildable locally, from the closed list
  below, with the *buildable part done* (interface, mock-based tests,
  documentation) and a note saying exactly what a human must supply.
- `DISPUTED(<reason>)`: the row itself is defective; needs a human decision.

Then the loop:

1. Runs the **full assessment in a single pass**: re-executes every automated
   check fresh, re-verifies artefacts exist, regenerates evidence, and writes
   <ASSESSMENT_PATH>: one line per row: ID, verdict, evidence reference,
   timestamp.
2. Writes <HANDOFF_PATH>: the BLOCKED and DISPUTED lists with what the human must
   supply or decide, plus any human-verified rows with their prepared evidence
   packages.
3. <MEMORY_APPEND_RULE>
4. Commits, and stops. **Done means this artefact set exists, not a feeling of
   completeness.**

### Permitted BLOCKED dependencies (closed list)

<BLOCKED_LIST: one entry per legitimate blocker: what is missing, what gets
built in the meantime, what the residue is>

Anything else claiming BLOCKED is actually `stuck`: see anti-spin.

## The wave

Each wave is: **derive state → frontier → parallel build → serial merge →
parallel adversarial verify → record → commit.** Orchestrate it as a Workflow
script with the shape `parallel(build) → barrier(merge + check) →
parallel(verify)`. The barrier is the one deliberate serialisation point: a
single shared <SINGLETON> means mutation must serialise; everything either side
of it fans out to the concurrency cap.

1. **Derive state.** Read <PROGRESS_PATH> (one line per row, current verdict or
   `TODO`/`WIP`/`stuck`). If absent, seed every in-scope row `TODO`. Scoreboard
   existence does not mean bootstrap is complete. Until the checkpoint records
   `bootstrap_complete` with its commit and green evidence, run **wave zero
   solo** (no fan-out): <WAVE_ZERO_DELIVERABLES>. Record completion only after
   these deliverables exist and <CHECK_COMMAND> passes; resume interrupted
   bootstrap by checking existing deliverables, not overwriting them.
2. **Frontier.** Select ALL `TODO` and retryable `WIP` rows with no live owner
   whose build-order dependencies are PASS
   and whose subsystems are disjoint, not one row, the whole eligible set. Batch
   tightly-coupled rows as one work item. Cap the wave at the concurrency limit;
   prefer wide waves: wall-clock should be the slowest row, not the sum.
   **The next wave's queue is drafted at this wave's open**, by the trunk owner
   and the monitor seat together, in `<EVIDENCE_DIR>/wave{N}/orchestrator/wave{N+1}-queue.md`
   (N the current wave): each lane with its rows and the falsifiers that would
   refute it, capped at the concurrency limit. The frontier of wave N+1 starts
   from that file, so there is no planning gap between a record and the next cut.
3. **Parallel build.** The orchestrator runs <LANE_CUT_COMMAND> for each work
   item and hands its existing worktree and range ledger to the builder. Do not
   ask an agent tool to create another worktree. Use the same validated lane
   identifier for <LANE_DB_COMMAND>. Mark dispatched rows `WIP` with their owner.
   Each builder: write the test(s) from the
   row's pass criterion FIRST, then implement until <BUILDER_GREEN_COMMAND> is
   green in its worktree, and execute lane-capable integration tests through
   <LANE_DB_COMMAND> in that worktree before returning. Only
   <SHARED_RESOURCE_SUITES> wait for the barrier. A lane-capable red test is a
   builder failure, never expected red. Builders return:
   files changed, tests added, and a self-report, which is never trusted as a
   verdict.
   **Multi-stage lanes.** Each lane's build is followed, before merge, by its
   own adversarial panel (<LENSES>) against the lane's worktree. A lens that
   refutes gets the lane a stage 2 (build, then panel again) on the same
   worktree inside the same wave, and a stage 3, the last, if stage 2 is refuted. Only when
   the last stage is refuted does the row return to retryable `WIP`; a
   refutation costs a stage, not a wave. The monitor seat approves each lane
   from its evidence (and screenshots, for a lane that changes a screen) before
   it is merged. Merge a lane only after its handback: a lane's tip moves after
   its first commit.
4. **Serial merge: the one mandatory barrier.** The orchestrator merges
   worktrees in dependency order, resolves conflicts, applies any <MUTATIONS>
   once, regenerates anything derived, runs `<PRE_BARRIER_COMMAND>` (every lane
   an ancestor of the merge, no trace or credential artefact in any lane diff,
   typecheck, each shared-registry entry exactly once, and the suites lanes
   cannot run, on the <SINGLETON>) and launches nothing while it is red, and runs
   <CHECK_COMMAND> on the merged tree: **this is where full green is required**, including barrier-only
   tests. Guard against silent success: assert each new
   <MUTATION_ARTEFACT> is non-empty BEFORE applying, and after applying assert
   its effects are actually present. Red at the barrier → fix forward if trivial,
   otherwise return the offending item to retryable `WIP`, clear its live owner,
   increment its persisted barrier failure count, and reconstruct the candidate
   from the recorded base and accepted lane commits in a separate worktree.
   Preserve the failed candidate for diagnosis; never discard unrecorded work.
   Before mutations, journal the candidate base commit, database/resource
   identity, snapshot or reproducible fixture baseline, and migration ledger
   IDs/checksums. Before rechecking a candidate that excludes a lane, reconcile
   resource state too: its schema/data must correspond to the accepted candidate,
   not residual mutations from the excluded lane. Preserve the failed resource
   and ledger as evidence. Where safe, build a fresh isolated test database from
   the recorded baseline and only the accepted migrations, verify its ledger
   and postconditions, and point checks at it. Never automatically roll back
   shared data or destructive migrations. Ambiguous or nonreversible state, or
   checks that cannot safely target the rebuilt resource, requires a recovery
   handoff and stop before recheck. Rebuilding Git alone cannot make it green.
   Never commit red.
5. **Parallel adversarial verify.** After the barrier, fan out verifiers against
   the merged state; each lane's own panel has already run, and this pass is
   the one against the merged tree. Every completed row gets a fresh-context
   verifier told to REFUTE: run the row's named checks from scratch, then try to break the claim
   (<ATTACK_VECTORS>). High-stakes rows (<HIGH_STAKES_ROWS>) get a **panel of
   three lenses** (<LENSES>); the row passes only if no lens refutes it. The
   builder never writes its own PASS. A verifier failure returns the row to
   retryable `WIP`, clears its owner and increments its persisted verifier
   failure count with the failure noted; two consecutive failures mark it
   `stuck`.
6. **Record.** Update every touched row in <PROGRESS_PATH>: verdict, evidence
   path(s), wave number, one-line note. Keep a rolling `## Log` at the bottom:
   wave number, rows attempted/passed/failed, anything learned that later waves
   need. Environment facts also go into <AGENT_INSTRUCTIONS_PATH>.
7. **Commit** on green (<BRANCH>), one commit per wave, including the progress
   file. Where <PUSH_RULE> is a standing permission, push after every green
   barrier's record: fast-forward only, <BRANCH> only, never <DEPLOY_BRANCH>,
   never `--force`. A refused push is recorded and put on the person's list.

**Shared-state law:** the shared <SINGLETON> is owned by the orchestrator.
Builders never <FORBIDDEN_MUTATIONS> on it. Lane database mutations are isolated
on the separate lane cluster; shared mutations happen only at the merge barrier.
All parallel work relies on <ISOLATION_CONVENTION> and the lane runner's guard.

**And what that isolation does NOT cover.** <ISOLATION_CONVENTION> separates
<ISOLATION_UNIT>. It does not scope <UNSCOPED_OPERATIONS>: those take the whole
<SINGLETON>, and where they queue, everything behind them queues too, whatever
<ISOLATION_UNIT> it belongs to. Three rules follow:

- **One <CHECK_COMMAND> at a time.** A second run is not extra throughput; it is
  a convoy in which both runs stall while appearing to work. The verify fan-out
  reads the merged tree and must not start a second one.
- **An operation that takes the whole <SINGLETON> declares a bounded wait** and
  retries. <BOUNDED_WAIT_MECHANISM> An unbounded wait cannot be told from a hang.
- **Killing a run does not free the <SINGLETON>.** Work outlives the process that
  submitted it. Every run tags its <RUN_TAG_UNIT> with its own name
  (<RUN_TAG_MECHANISM>), so leftovers are reaped by name rather than reconstructed
  by forensics. <REAP_COMMAND>

**A red test under contention is NOT a refutation.** <TIMEOUT_FACTS> A verifier
that reads a contention failure as a refuted row will supersede a sound test on
evidence that is purely queueing: the one failure this loop cannot correct on
its own, because the record afterwards looks like diligence. Before returning any
FAIL from a suite that touches the <SINGLETON>: check for contention
(<CONTENTION_CHECK>), re-run the row alone, and say in the finding that you did.

## Build order

<BUILD_ORDER: foundations before features, as a dependency-ordered list>

## Anti-spin and stop conditions

- A row failing verification twice, or failing the barrier twice, becomes
  `stuck`: record what was tried and exclude it from the next frontier. Retry
  `stuck` rows once after ≥2 further productive waves by transitioning them to
  ownerless retryable `WIP` and recording that the one retry was consumed.
  Keep lifetime history; begin a fresh consecutive-failure count for that retry. A
  second `stuck` marks the row `DISPUTED(loop-cannot-satisfy)` with the full
  attempt history.
- Empty frontier is not completion. Run the done sequence only when bootstrap
  is complete and every in-scope row has a permitted terminal verdict. Otherwise
  inspect live owners, retry cooldowns, dependency cycles, missing IDs and
  dependencies ending BLOCKED/DISPUTED. Do not promote descendants to PASS or
  invent BLOCKED reasons. If no other productive work can advance a cooldown,
  write a `dependency-stalled` handoff with unresolved IDs and the dependency
  chain, then stop; never manufacture empty waves to age a retry.
- **Three barrier attempts per wave, and attempt 3 is a reduction**, never a
  repair: identify the merged lanes carrying the failures, drop them, re-merge
  the largest subset that goes green, and carry the dropped lanes (with their
  fixes) to the next wave's queue. Attempts 1 and 2 may fix forward as in
  step 4. There is no fourth attempt; a wave that spent attempt 3 on a repair has
  broken this rule, whatever the repair's merit.
- **A falsifier lands with its fix.** A spec that is correct and red because the
  product is wrong is never merged alone: hold it, flip its row off `PASS` in the
  same commit, and name the fix-and-land lane in the wave record. Undo a
  premature merge with `git reset --keep` on the unpushed integration branch
  only (never on a pushed trunk), keeping the lane's
  evidence; never `git revert -m 1`, which leaves the merge in history so the
  next re-merge of that lane is a silent no-op.
- If two consecutive waves make no scoreboard change, stop and write the handoff
  anyway: flag `loop-stalled` at the top. Never idle-loop.
- Workflow-level failures (an agent dying, a worktree conflict storm) degrade that
  wave to serial for the affected items; they do not stop the loop.
- Environment failure (<SINGLETON> down): attempt <RESTART_COMMAND> once; if still
  down, write an environment-stalled handoff retaining unresolved row verdicts
  (use `BLOCKED(environment)` only if on the closed list and its buildable part
  is done), and stop.
  Do not fight the machine.

## Persistent budgets and recovery

Use <RUN_STATE_DIR> on durable storage, outside temporary worktrees. The trunk
owner alone writes an append-only `journal.jsonl` and atomically replaces
`checkpoint.json` (write a sibling temporary file, then rename). These are
records maintained by the orchestrator, not a new runtime engine.

Before first dispatch record run ID, approved total token/cost ceiling and
accounting unit <SPEND_LIMIT>, elapsed-time ceiling <TIME_LIMIT_MINUTES>, and
reserve <HANDOFF_RESERVE> for stopping and handoff. Record started-at UTC,
deadline UTC, cumulative spend, outstanding reservations and the usage source.
Also record each wave's spend ceiling <WAVE_SPEND_LIMIT>, time ceiling
<WAVE_TIME_LIMIT_MINUTES>, wave ID/start/deadline and cumulative wave spend.
Both wave and total limits must fund the operation and reserve. Restart keeps
the same wave ID, totals and deadline; only a completed wave starts a new wave
budget. Never rename a failed wave to evade its ceiling.
Before each agent or command, reserve its maximum spend and timeout; after it,
append actual usage and elapsed time and reconcile the reservation. Include
builders, verifiers, retries and recovery. An unknown charge retains its full
reservation; missing usage or an unbounded command stops dispatch. On resume,
keep the original deadline and cumulative totals, including downtime. Never
reset budgets per wave or session. If remaining budget cannot fund the next
operation plus the handoff reserve, stop dispatch, safely drain owned work,
checkpoint, and write a `budget-exhausted` handoff. Only the user can raise caps.

Before each side effect append an intent with sequence, run/wave/row IDs,
operation, base HEAD, lane path/commit, resource identity, evidence path and
reserved budget; append its outcome afterwards. Checkpoint completed journal
sequence, bootstrap status/evidence, wave phase, accepted lane commits,
row owners, failure counts, stuck/retry history and budget totals after each
barrier, verification, record and commit. Record commit intent before commit,
then its actual hash afterwards. Never mark PASS from an interrupted verifier.

**Phase timings.** Also append a phase event at the start and end of each step
of the wave, so the owner can see where the wall-clock went:
`{"type": "phase", "wave": N, "phase": P, "lane": L, "event": "start"|"end", "at": "<UTC ISO-8601>"}`.
`P` is one of `cut`, `build`, `verify`, `review_wait`, `barrier`, `record` or
`owner_wait`; `lane` is set for per-lane phases and empty otherwise; barrier
events carry `"attempt": k`. `review_wait` runs from a lane's handback to the
monitor seat's verdict. `owner_wait` runs from escalating a question to the
owner until it is answered. These are the same single-writer journal, written
at the moment the step starts or ends, never reconstructed later. At the wave
record, end any phase still open. Timing events never gate work: a missing one
is a gap on the progress page, not a stop condition.

On restart, establish that the previous owner is inactive; if ownership is
uncertain stop with a handoff. Read checkpoint plus the journal tail and inspect
git status/history, lane paths, process identity/start time, tagged backends
and migration ledger. A numeric PID alone does not prove ownership; do not
signal a reused or unidentified process. Preserve dirty worktrees and evidence.
For an intent without outcome, query whether it happened before retrying: match
commit/tree and evidence hashes, migration ID/checksum and postconditions, or
platform deployment ID and served revision. Do not blindly re-merge, reapply
migrations, deploy, or reset a dirty tree. Mark an ownerless interrupted row
retryable `WIP`; retain failure counts and budget reservations. Resume at the
first unproven phase and rerun its check. Ambiguous external state means stop
and handoff, not guessed success. Run the factory recovery drills before
declaring unattended readiness; their evidence belongs in the handoff.

## Tone of the record

The progress file and handoff are read by a human who was not watching. Plain
verdicts, real evidence paths, no cheerleading. A row that limps is a row that
FAILs. The loop's value is that its PASS means something.

---

## The factory

Facts settled before this loop was written, by `software-factory`. They bind
every seat and are not re-derived by a lane.

- **The rig.** <DO_NOT_RUN>. The barrier checks swap and free memory before
  every launch and refuses to launch above the threshold; a check launched into
  swap fails as timeouts that read like product regressions.
- **Standing authority.** The allowlist at `<ALLOWLIST_PATH>` names the scripts
  the loop may run unattended. A refused command is tried once, recorded
  verbatim, put on the person's list, and never routed around.
- **Rulings.** `<RULING_POLICY_PATH>` is the ladder's terminal: a row that has
  failed twice is ruled there, once, and a lane that measures a ruling wrong is
  believed.
- **Maintenance.** `<MAINTENANCE_COMMAND>` runs at the barrier, once per
  attempt, BEFORE the check, never between a red cell and its re-run.
- **Lanes.** `<LANE_CUT_COMMAND>` provisions every lane; a lane never cuts its
  own worktree or chooses its own identifier range. `<LANE_DB_COMMAND>` gives
  it a database; <SHARED_RESOURCE_SUITES> still first run at the barrier.
- **The record.** <REGENERATED_FILES> are regenerated at the barrier, never
  edited by hand. <RECORD_CAPS>.
- **Pre-barrier.** `<PRE_BARRIER_COMMAND>` runs after the serial merge and its
  mutations and before <CHECK_COMMAND>, once per attempt; it prints one PASS or FAIL line
  per check and nothing launches while any line is FAIL.
- **The trunk.** <TRUNK_OWNER> merges, records and commits; every other seat
  proposes and messages. The monitor seat (`build-monitor`) approves each lane
  before merge and never writes into the shared checkout while a barrier runs.
  §Seats in <CONVENTIONS_PATH> names every seat.
