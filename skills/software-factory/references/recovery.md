# Budgets, crash recovery and release readiness

These are prompt-driven operating rules, not an automatic recovery engine.
Fill the build-loop's persistent state and budget slots before dispatch. Keep
the journal/checkpoint on durable storage with one owner; no secrets in either.
The accounting unit and usage source must be explicit. Bound each operation's
spend and time, reserve handoff capacity, and carry reservations and the original
deadline across restarts. Missing accounting is a stop condition, not unlimited
authority. A budget extension requires the user's instruction in the journal.
Track total and per-wave spend/time ceilings separately; resumed work retains
its wave ID, spent amounts, reservations and original wave deadline.

## Crash drills

Run these in a disposable local fixture, never by killing a production service.
For each drill retain initial checkpoint, journal intent/outcome tail, observed
git/resource state, resumed action, assertion result and evidence path. A human
or separate verifier walks the generated prompt from those records. Static
contract checks alone do not prove that a running agent followed the protocol.

| Interruption | Required resumed behavior and assertion |
| --- | --- |
| Seeded scoreboard, before wave zero finishes | `bootstrap_complete` remains false; inspect deliverables and run green before fan-out. No scoreboard-exists shortcut. |
| Builder dies with dirty lane | Preserve files; establish owner/process identity; retain reservation; return ownerless row to WIP and retry without another worktree or database collision. |
| Merge recorded as intent, no outcome | Inspect candidate HEAD/tree and accepted lane commits; do not merge twice. Keep a dirty failed candidate; rebuild separately from recorded base if necessary. |
| Red barrier after an excluded lane mutated the database | Retain failed resource/ledger. Compare the recorded base commit, resource identity, snapshot/fixture baseline and migration IDs/checksums with the accepted candidate. Rebuild a fresh isolated test database from that baseline and accepted migrations only where safe, assert ledger and schema/data postconditions before recheck. Residual excluded schema must fail this drill. Ambiguous/nonreversible changes stop with recovery handoff; no automatic destructive rollback. |
| Migration applied, outcome missing | Query ledger/checksum and actual postconditions. Already applied means reconcile, not rerun; partial or ambiguous state stops for handoff. |
| Verification finishes, before scoreboard write | Require retained evidence bound to candidate; an incomplete verifier gives no PASS. Re-run the first unproven phase. |
| Commit succeeds, before checkpoint | Find matching commit/tree and recorded evidence in history; reconcile its hash rather than duplicate the commit. |
| Deploy accepted, response or verification lost | Query platform by target, commit and recorded deployment ID; inspect served revision. Do not submit again while outcome is unknown. |
| Restart at exhausted spend/deadline | Original cumulative spend, unresolved reservations and elapsed downtime remain counted; no new dispatch; budget-exhausted handoff uses reserve. |
| Empty frontier with WIP, cooldown or dependency cycle | Retry eligible ownerless WIP; otherwise report dependency-stalled with IDs/chain. No done assessment and no empty waves. |

## Known-good release and restore readiness

Gate 9 requires a release record on durable storage before any authorized deploy:
target/environment identity, requested full commit, exact-tree local check command
and evidence, current known-good deployment ID/commit, immutable artifact identity,
and the previously verified entry/protected-route status plus revision endpoint.
`VERIFY_COMMIT_COMMAND` runs inside the clean exact worktree before link/deploy;
it must run the project's full release check and persist evidence keyed by FULL.
Never render it as a no-op or reuse evidence from a different tree. Deployment
must build/upload this worktree and embed FACTORY_DEPLOY_COMMIT in the served
revision endpoint; ignore-file rules must exclude all non-source build residue.

Record the supported rollback command targeting that known-good artifact, its
authority, and post-rollback HTTP/revision checks. A rollback is a deployment
and still requires explicit authorization. If schema/data changes are involved,
record compatibility with the old binary, backup ID/time/scope, restore command,
owner and measured recovery time. Rehearse restore into a disposable database,
assert schema and representative row/integrity checks, and retain the evidence.
A backup existing is not restore evidence. Irreversible or incompatible changes
need a forward-recovery plan before release; do not assume binary rollback fixes
data. Unknown rollback/restore readiness blocks deployment, not local building.

Before the actual deploy, journal intent and approval reference. Record platform
ID immediately on receipt, then status and exact revision/HTTP assertions. Only
after all checks pass promote it to known-good. On failure retain the prior
known-good record, stop further releases, and hand off recovery options; never
automatically deploy or restore because verification failed.

Rehearse a failed release with mock platform responses, an old revision response,
and a failing health status. Assert that none promotes known-good. Then rehearse
the approved rollback/restore procedure in isolation and assert the old revision
and data invariants. Attach these results and any unexecuted platform-specific
steps to the readiness handoff.
