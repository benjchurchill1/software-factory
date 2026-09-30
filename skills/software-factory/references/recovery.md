# Budgets, crash recovery and release readiness

An unattended build will be interrupted: a session dies, the host reboots, a
deploy's response is lost. This file says how the loop picks up without doing
anything twice, how it stays inside its budget, and what must be true before it
may deploy. It backs gate 9 and the budget slots `build-loop` fills.

## What is enforced and what is only asked

Be clear with the owner about which is which. A rule the loop is asked to follow
is only as good as the loop's attention on the day.

| Enforced by a script or the hook | Asked of the loop by its prompt |
| --- | --- |
| The deploy refuses the wrong target, a dirty tree, a commit outside the lineage, or a failing release check (`deploy-<env>.sh`) | Reserving budget before each operation and reconciling after |
| The served revision must equal the commit deployed (`deploy-<env>.sh` §5) | Writing an intent to the journal before each side effect and its outcome after |
| Lane names and identities are validated; a live lane is not run twice (`lane-cut.sh`, `lane-db.sh`) | Checking the previous owner is gone before resuming |
| The keep-alive hook stops holding at its caps and after 72 hours | Not re-merging, re-migrating or re-deploying when an outcome is unknown |
| | Stopping when the remaining budget cannot fund the next step plus the handoff |

Nothing in Claude Code stops a session at a spend ceiling. The budget works only
if the loop can read what it has spent, so settle the **usage source** at
priming: for example the session's own cost readout, or a figure the owner reads
from the provider's usage console and writes into the journal at each barrier.
Pick one that exists in your setup. The generated loop treats missing usage as a
reason to stop dispatching, so a build with no usage source will stop at its
first operation. That is deliberate: it is cheaper to find out at priming.

## Terms

- **Journal**: `journal.jsonl` in `<RUN_STATE_DIR>`, append-only, one JSON line
  per intent and per outcome. Only the trunk owner writes it.
- **Checkpoint**: `checkpoint.json` beside it, replaced atomically (write a
  sibling temporary file, then rename). It holds the last completed journal
  sequence, `bootstrap_complete`, the wave phase, accepted lane commits, row
  owners, failure counts and budget totals.
- **Reservation**: the maximum spend and time an operation may use, recorded
  before it starts and reconciled against actual use when it ends. An operation
  whose actual use is unknown keeps its full reservation.
- **`FULL`**: in `deploy-<env>.sh`, the full 40-character hash of the commit
  being deployed. Every check and every piece of evidence is keyed to it.
- **`FACTORY_DEPLOY_COMMIT`**: the environment variable the deploy script sets
  to `FULL` before building, so the build can embed it. The app serves it
  verbatim at a revision endpoint (`<ARTEFACT_PATH>`), which is how the script
  proves the new code is what is being served.
- **`<VERIFY_COMMIT_COMMAND>`**: the project's full release check, run inside
  the clean deploy worktree for `FULL`, writing its evidence under a path that
  names `FULL`. It must never be a no-op, and evidence from another commit does
  not count.
- **Known-good release**: the last deployment whose revision and HTTP checks all
  passed, recorded with its platform deployment id, commit and artefact.

## Budgets

Record before the first dispatch: the run id; the total spend ceiling and its
unit (`<SPEND_LIMIT>`); the elapsed-time ceiling (`<TIME_LIMIT_MINUTES>`); the
per-wave ceilings (`<WAVE_SPEND_LIMIT>`, `<WAVE_TIME_LIMIT_MINUTES>`); the
handoff reserve (`<HANDOFF_RESERVE>`); the start time and deadline in UTC; and
the usage source.

The rules the loop follows:

- Both the wave budget and the total budget must cover the next operation plus
  the handoff reserve, or dispatch stops.
- A restart keeps the same wave id, the cumulative totals, outstanding
  reservations and the original deadline. Downtime counts. Only a completed
  wave starts a new wave budget, and a failed wave is never renamed to escape
  its ceiling.
- When the budget runs out, the loop drains the work it owns, checkpoints, and
  writes a `budget-exhausted` handoff using the reserve.
- Only the owner raises a ceiling, by an instruction recorded in the journal.

## Crash drills

Run each drill in a disposable local fixture, never by killing a real service.
For each, keep the checkpoint before, the journal tail, what git and the shared
resource looked like, what the resumed loop did, whether the assertion held, and
where the evidence is. Someone other than the build seat (a person, or a
separate verifier agent) walks the generated prompt against those records.
Reading the prompt is not the drill: a static check shows the rule is written,
not that a running agent follows it.

| Interruption | What the resumed loop must do |
| --- | --- |
| **Seeded scoreboard**, before wave zero finishes | See `bootstrap_complete: false`, check wave zero's deliverables and run green before any fan-out. The scoreboard existing proves nothing. |
| **Builder dies** with a dirty lane | Keep the files. Establish who owned the lane and whether its process is gone. Keep its reservation. Return the row to `WIP` and retry without cutting another worktree or colliding on a database. |
| Merge recorded as intent, no outcome | Inspect the candidate HEAD and tree and the accepted lane commits. Do not merge twice. Keep a dirty failed candidate; if needed, rebuild separately from the recorded base. |
| **Red barrier after an excluded lane** mutated the database | Keep the failed database and ledger. Compare base commit, resource identity, baseline and migration ids and checksums with the accepted candidate. Where safe, rebuild a fresh test database from that baseline and the accepted migrations only, and assert the ledger and schema before rechecking. **Residual excluded schema** fails this drill. Anything ambiguous or irreversible stops with a handoff; there is no automatic destructive rollback. |
| **Migration applied**, outcome missing | Query the ledger, checksum and actual postconditions. Already applied means reconcile, not rerun. Partial or ambiguous state stops with a handoff. |
| Verification finishes, before the scoreboard write | Require evidence bound to the candidate. An incomplete verifier gives no PASS. Rerun the first phase that is not proven. |
| **Commit succeeds**, before the checkpoint | Find the matching commit and evidence in history and record its hash. Do not commit again. |
| **Deploy accepted**, response or verification lost | Query the platform by target, commit and recorded deployment id, and check the served revision. Do not submit again while the outcome is unknown. |
| Restart at **exhausted spend/deadline** | The original totals, open reservations and downtime still count. No new dispatch. Write the `budget-exhausted` handoff from the reserve. |
| Empty frontier with rows in `WIP`, in cooldown or in a dependency cycle | Retry eligible ownerless `WIP`. Otherwise report a dependency stall with the row ids and the chain. Not done, and no empty waves. |

## Release readiness (gate 9)

Before any deploy the owner authorises, a release record exists on durable
storage with: the target and environment; `FULL`; the release check's evidence
for that exact tree; the current known-good deployment id and commit; the
artefact identity; and the status of the entry route, a protected route and the
revision endpoint on the known-good release.

**Rollback.** Record the platform's rollback command for the known-good
artefact, who may authorise it, and the HTTP and revision checks to run after
it. A rollback is a deployment and needs the same authorisation.

**Data.** Where a release changes schema or data, record whether the old build
still works against the new schema, the backup's id, time and scope, the restore
command, its owner and the measured time to restore. Rehearse the
restore into a disposable database and check the schema and representative rows. A backup
existing is not evidence it restores. A change that cannot be reversed needs a
forward-recovery plan before release; rolling back the binary does not repair
data.

**The deploy itself.** Journal the intent and the approval before deploying.
Record the platform's deployment id as soon as it is returned, then the status
and the revision and HTTP checks. Promote to known-good only when all of them
pass. On failure, keep the previous known-good record, stop further releases
and hand the options to the owner. Never deploy or restore automatically
because a check failed.

**Rehearsal.** With mocked platform responses, rehearse a failed release: an old
revision served, and a failing health status. Assert that neither is promoted
to known-good. Then rehearse the rollback and restore in isolation and assert
the old revision and the data invariants.

### How gate 9 closes

- **Met**: the release record exists, the mocked failed-release rehearsal
  passed, and rollback and restore have been rehearsed against the real target.
- **Waived**: there is no deploy target for this build (local only). Write the
  reason into the handover.
- **Blocked on the user**: a deploy target exists but the real-target rehearsal
  has not been run. Say so; do not report it as met on the strength of mocks.
  This blocks deploying, not building: the loop can start with gate 9 blocked
  and run locally until it closes.
