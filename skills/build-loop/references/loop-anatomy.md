# What each part of the loop is defending against

Read while filling the templates. Every section below exists because a loop
without it fails in a specific, observed way. Knowing the failure is what decides
whether a section can be trimmed for a given project — trim the defence only when
the project cannot suffer the failure.

## Contents

- [Role](#role) · [Ground truth](#ground-truth) · [Integrity rules](#integrity-rules)
- [Definition of done](#definition-of-done) · [The closed blocked list](#the-closed-blocked-list)
- [The wave](#the-wave) · [The barrier](#the-barrier) · [Adversarial verify](#adversarial-verify)
- [Shared-state law](#shared-state-law) · [Contention is not refutation](#contention-is-not-refutation)
- [Anti-spin](#anti-spin) · [Tone of the record](#tone-of-the-record)

---

## Role

**Defends against:** the loop redesigning the product when a requirement is
inconvenient.

"You implement, test and assess — you do not redesign." Autonomous agents faced
with a hard row will reliably find an easier row nearby and build that instead,
reporting progress the whole way. The separation of powers — design decided
elsewhere, the loop only satisfying it — is what makes the progress number mean
anything.

## Ground truth

**Defends against:** drift between waves, and state derived from conversation.

An ordered read list, executed at the start of every wave. The order matters: the
contract first, the fixed architecture second, explanatory docs third. State must
be derivable from the repo alone — the scoreboard, the migrations directory, git
history — never from what the loop remembers. This is what makes a killed session
resumable by pasting the prompt again, and it is worth protecting: any rule that
requires the loop to remember something across waves is a rule that will break.

## Integrity rules

**Defends against:** every cheap route to a green build.

These outrank progress, and say so. The set that matters:

- **Never edit the oracle to make a row passable.** With a verdict for "this row
  is itself defective" as the honest alternative.
- **Never weaken a test to make it pass.** Plus the sanctioned route for a test
  that is genuinely wrong: a successor that names its predecessor, recorded, with
  the deletion done by a privileged step. Without an escape hatch this rule gets
  circumvented instead of obeyed.
- **A PASS requires executed evidence.** A path, an output, a run. "It should
  work" is a FAIL.
- **The builder never writes its own verdict.**
- **Frozen paths**, listed explicitly, with hooks where they exist.
- **Commit protocol**: which branch, what message, never to the main branch,
  never force, never deploy.

## Definition of done

**Defends against:** a loop that runs forever, and one that stops early on a
feeling.

Done is an artefact set that either exists or does not: every in-scope row
carrying a final verdict, a fresh full assessment, a handoff naming what the
human must supply or decide. State it as "done means these files exist", because
a loop asked to judge its own completeness will judge generously.

## The closed blocked list

**Defends against:** the most respectable way for a loop to stop working.

`BLOCKED` is the label a stalled loop reaches for, because it sounds like
diligence. Enumerate the legitimate blockers — each with what a human must
supply, and what gets built in the meantime (an interface, a fake, a mock-based
test proving the contract). Then: *anything not on this list is not blocked, it
is stuck* — and stuck has an anti-spin rule that blocked does not.

The buildable-part rule is what stops the list becoming a dumping ground. A
blocked row still ships its interface and its fake-backed tests; only the residue
that genuinely needs the missing thing is blocked.

## The wave

**Defends against:** one-row-at-a-time serialisation, and unbounded fan-out.

`derive state → frontier → parallel build → serial barrier → parallel verify →
record → commit`. The frontier is *all* eligible rows, not the next one: wall
clock should track the slowest row in the wave, not the sum of the rows. Cap it
at the concurrency limit, batch tightly-coupled rows as one item, and isolate
builders in worktrees so they cannot collide on files.

A lane's own panel runs before merge, and a refuted lane gets a second and at
most a third build→panel stage inside the same wave. Sent back to wait a wave,
a refutation costs a wave; kept in the lane, it costs about an hour. (Source
build: wave 99 ran six stages on one worktree; wave 113's ui-aml-2 ran three.)

## The barrier

**Defends against:** concurrent mutation of the one thing that cannot take it.

Exactly one point per wave where shared state changes: merge in dependency order,
apply migrations once, regenerate anything derived, run the full check on the
merged tree. Everything either side fans out.

Guard it against silent success. A migration tool that records a zero-byte file
as applied, a deploy that returns 200 having done nothing — assert the artefact
is non-empty before applying and that its objects exist afterwards. "The command
exited zero" is not evidence the thing happened.

Red at the barrier means fix forward if trivial, otherwise drop the item back to
in-progress and re-merge without it. Never commit red.

Bound it: three attempts, and the third is a reduction — drop the lanes carrying
the failures and re-merge the rest — never a repair. A repair at attempt 3 can
fix the cause it was cut for and go red on a new one, stranding every good lane
in the merge. (Source build: wave 109 did exactly that and took six attempts.)
Run the mechanical pre-barrier checks before attempt 1, so the barrier is never
the first place a stale merge, a duplicated registry entry or a leaked trace is
found.

## Adversarial verify

**Defends against:** the builder's own account of its work.

Fresh context, told to refute rather than confirm: run the row's checks from
scratch, then attack — wrong tenant, missing permission, direct write bypassing
the interface, concurrent submission, replayed request. High-stakes rows get a
panel of distinct lenses rather than three identical sceptics, because redundancy
catches less than diversity does.

Two verifier failures on a row make it stuck. One makes it in-progress again.

## Shared-state law

**Defends against:** parallelism that is real for records and imaginary for the
resource.

State the isolation *and its limits*. Per-record namespacing separates records;
it almost never separates the resource itself. Whole-resource operations — schema
changes, truncations, global config, rate limits — are scoped by nothing, and
where they queue, everything behind them queues too.

Three rules follow, and they are cheap to write and expensive to omit:

- **One full check at a time.** A second run is not extra throughput. Where
  whole-resource operations queue, two runs deadlock each other's progress while
  both appear to be working.
- **Whole-resource operations declare a bounded wait**, and retry. An unbounded
  wait is indistinguishable from a hang, and a loop cannot escalate what it
  cannot name.
- **Killing a run does not release the resource.** Long-running work outlives the
  process that submitted it. Every run tags its sessions/connections/jobs with
  its own name, so leftovers are reaped by name instead of reconstructed by
  forensics.

## Contention is not refutation

**Defends against:** the one failure mode a loop cannot correct on its own.

A loop that treats red as evidence, and that is empowered to supersede tests on
evidence, will retire sound tests when the machine is merely busy. It does this
carefully, with a written rationale, and the record afterwards looks like
diligence — which is why nothing downstream catches it.

Two defences, both required:

- **Default timeouts sized above the shared resource's contention**, not above
  its best case. A five-second default against a resource that can queue for
  minutes converts every busy moment into a false refutation.
- **A verdict rule**: before returning a failure from a suite that touches the
  shared resource, check for contention, re-run the row alone, and record that
  the check happened.

## Anti-spin

**Defends against:** an infinite loop that looks like work.

A row failing twice becomes stuck and leaves the frontier, with what was tried
recorded; retry once after two further waves, since fresh context often unblocks
what persistence cannot. Ownerless WIP is eligible again; persist failure counts
and retry history so a restart cannot reset the ladder. Empty frontier is not
done: require explicit bootstrap completion and all in-scope rows terminal.
Cycles, missing dependencies, terminal non-PASS prerequisites or stranded
cooldowns require a dependency-stalled handoff if no productive work remains.
Never manufacture empty waves or silently mark descendants resolved. Two waves with no
scoreboard change → stop and write the handoff, flagged as stalled. Environment
down → one restart attempt, then stop. Never idle-loop; never fight the machine.

## Bootstrap, budgets and recovery

A seeded scoreboard is not bootstrap evidence. Record bootstrap completion
separately only after its deliverables and green command pass. A killed bootstrap
resumes from inspected deliverables; it does not skip ahead because a file exists.

The durable journal records intent before side effects and outcomes afterwards;
the atomic checkpoint captures the last proven phase and sequence. Reconcile
uncertain commits, migrations and deployments against external evidence before
replaying anything. Preserve dirty lanes; unknown ownership or external state
requires a handoff. Budget totals, deadline, reservations and retry counts survive
restarts. Unknown usage keeps its reservation; insufficient budget stops dispatch
while reserving enough for a handoff. Factory crash drills exercise these prompt
contracts; they are not claims of automatic crash safety.

## Tone of the record

**Defends against:** a scoreboard that reads well and means nothing.

The progress file is read by someone who was not watching. Plain verdicts, real
evidence paths, no cheerleading. A row that limps is a row that fails. The loop's
entire value is that its PASS means something — every sentence of encouragement
in the record is a small withdrawal from that.
