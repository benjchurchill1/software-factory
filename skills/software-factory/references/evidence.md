# What each gate cost when it was missing

Measured on one register-driven build: a multi-tenant practice-management
application (Postgres, Next.js, ~250 migrations, ~9,300 tests, a 200-spec
browser suite) on a dedicated 32 GB Mac mini. Every figure below names the
artefact it comes from, all under `docs/requirements/` in that repo, or the
2026-09-26 retrospective written beside it. Where a figure was measured at the
reviewing seat rather than recorded by the loop, it says so; where it comes
from a seat's note rather than a loop record, it says that too.

Quote these when a user wants to skip a gate. They are not arguments; they are
what happened.

## The headline

Over waves 31 to 52 (seven days), roughly **two thirds of the calendar was
stall**, and almost none of it was the model or the prompt.
(`decisions/2026-09-03-the-loop-goes-faster.md` §0.)

| Where the time went | Share |
| --- | --- |
| Machine stalls: container runtime wedged, host swapping, reboots | about a third |
| The serial barrier, 45 to 70 minutes per attempt, run two or three times per wave | about half of the working time |
| Waiting on a person for maintenance, permissions and rulings | most of the rest |
| Authoring lanes, already parallel | small |

## Gate 0: the oracle

The first thirty waves produced 89 rows passing, 7,583 tests and zero
conformance violations, over an application whose navigation offered nine
destinations that did not work and whose screens were mostly read-only
registers over a database nobody could write to through the product. 72 of the
89 were provable with nothing rendered. No row said "through the interface", so
the loop optimised exactly what it was asked to.
(`docs/prompts/build-loop.md` §What changed from v1, lines 16–45.)

A criterion whose only assertion counted queued items greater than zero,
against a queue a fixture restore filled before every run and nothing drained,
sat PASS for six waves; it could not fail. (`verification/wave55-verify.txt`,
PM-CMP-01.) Two legs of another row were satisfied from the second run onward
by the previous run's rows. (Escalation E-163.)

## Gate 1: the rig

The box was dedicated but not headless, and the barrier's own record names the
costs in this order:

- **Concurrent agent sessions and an orphaned app server**, not the desktop:
  *"Docker Desktop at 15.6 GB on a 32 GB machine with several Claude sessions,
  a Next build and Playwright left the host in swap; the orphaned server was
  the largest single cost."* (`verification/wave54-barrier-2.txt`, host note.)
  One orphaned Next server was measured at 4.4 GB; a single security fuzz
  test's own dev server reached 3.4 GB. (Reviewing seat, 2026-09-05.)
- **The container runtime's allowance competes with the check.** Set to 16 GB
  the host went to 22 GB of swap and two launches went red; set back to 10 GB
  (reported as 9.7) the next two barriers were green. The check's own work runs
  on the host. (`decisions/2026-09-03-the-loop-goes-faster.md` §8, corrected.)
- **Desktop applications were the next tier.** Measured at the reviewing seat
  on 2026-09-05: an IDE at 2.1 GB, a browser at 1.5 GB, a chat client and a
  meetings client at 0.6 GB each. After a reboot (swap 0.6 GB) the same tree
  went green; a later launch entered its heavy stage with 0.1 GB free until
  three of those applications were fully quit, which took free memory to
  2.9 GB in three minutes. (`verification/wave57-barrier-3.txt`; reviewing
  seat measurements.)
- The runtime wedged twice, three to ten hours each, both under memory
  pressure. (`assessments/2026-09-01-wave48-environment-handoff.md`.)
- **The host slept.** At wave 109 five build agents in a row, all in one lane,
  died "[Request interrupted]". The cause was maintenance sleep on AC power:
  `pmset -g log` showed the sleep, and 100 seconds of `sleep` took over ten
  minutes of wall time. Each death cost the lane its build, 20 to 40 minutes.
  `caffeinate -dimsu -t 21600` before lanes and barriers ended it.
  (Build seat's note, 2026-09-25, not a loop record; retrospective §4.)

## Gate 2: standing authority

The permission classifier denied the loop, at every autonomous seat measured,
its own maintenance script, its schema migrations, the container restart, and
the write of the permission file itself. (`decisions/2026-09-03-the-loop-goes-faster.md`
§7; `verification/wave52-barrier-1.txt` §7.)

- Six barriers ran unmaintained because the loop could not prune its own test
  data. (Waves 46, 47, 48, 50, 52 recorded the refusal; `wave52-barrier-1.txt` §3.)
- One wave halted for ten hours because a migration could not be applied.
  (`2026-09-01-wave48-environment-handoff.md`.)
- **The identical command was refused at a background seat and permitted when
  the user asked for it in their own words in the live session.** Measured
  2026-09-04 and again 2026-09-06. This is why gate 2 is a human action and why
  its verification must run from a background seat.
- **Push after green, as a standing instruction.** Granted 2026-09-23 and
  relayed by the reviewing seat. Every green barrier since was pushed:
  fast-forward, a named wave branch only, never `main`. (Retrospective §1.)
  Before it, the trunk once went 688 commits unpushed. (Build seat's note.)
- **The trunk was not the deploy branch.** The trunk was a named wave branch;
  `main` was a divergent lineage about 2,350 commits behind that the platform
  auto-deployed. That made every push a guarded act and caused E-14 four
  times. (Retrospective §5; build seat's note, 2026-09-17.)

## Gate 3: the ruling policy

Forty-six open questions had accumulated before anyone noticed, because each
individually needed a person. Once a written policy existed, all forty-six were
decided in one pass (`decisions/2026-09-04-the-escalation-pass-index.md`), and
the queue stayed at zero afterwards with rulings issued the same hour lanes
raised them.

Two rulings were later measured wrong by the lanes implementing them, and both
times the lane was believed and the ruling amended.
(`decisions/2026-09-06-standing-wip-is-wip-component.md`; E-156's §3 reading.)

## Gate 4: the test-data lifecycle

Tenant-per-test with no cleanup. (Escalation E-141 and its addendum.)

| | |
| --- | --- |
| Permission-table rows at peak | 33.2 million |
| Test tenants at peak | 34,559 |
| Growth per full check | roughly a third of a million rows |
| Regrowth in one day at thirteen lanes a wave | 17,000 → 34,000 tenants |
| Waves whose performance gate reddened on it | six |

The reaper's floor mattered as much as the reaper: rows a ledger constraint
refused to delete left 18,550 tenants standing after the largest prune.
(`evidence/wave62/prune-stale.log`.) Design for the floor and report it.

The age-based reaper was not enough. **Residue left by specs on the shared demo
practice was the most frequent red cause across waves 101 to 113**
(retrospective §4):

| Red | Residue |
| --- | --- |
| 113-1 | flagged reports left by specs blocked a chase cycle across every demo client (`evidence/wave113/orchestrator/lane-str-residue.md`) |
| 112-1 | e2e template residue past a 200-row cap (`verification/wave112-barrier-1.txt`) |
| 97-1 | a spec asserting absolute sequence numbers on a demo row, after earlier runs' letters (PM-CLI-16 → -2) |
| wave 100 | 244 unrevalued FX lines against a console's `LIMIT 100`, one per run since 2026-08-30; the seventh red of seven launches |

A prediction at 113 went wrong because it reasoned about one spec when the
cycle spans every demo client. The repair that held was the spec's own: close
what it made, through the product path, found by a positive marker it wrote,
with a decoy as control and the barrier precondition as backstop.

## Gate 5: lane provisioning

Two conventions were written down, read, and both recurred: 119 of 188
worktrees were cut at a commit from a different project, affecting twelve of
twelve lanes in one wave; four of eleven lanes chose the same migration number
in one wave and two pairs collided again the next.
(`docs/engineering/build-conventions.md` §Cutting a lane; escalations E-14, E-15.)

A script does not stop a seat reaching past it. E-14's fourth recurrence, at
wave 84, was the orchestrator using the Workflow tool's `isolation: 'worktree'`,
which resolves `main`: all three lanes were cut from a lineage about 2,350
commits behind the trunk. (Build seat's note, 2026-09-17.)

The base proof did not cover the path. At wave 112 a lane was green in its
worktree and red in the main checkout, whose path holds spaces: `URL.pathname`
keeps `%20`; `fileURLToPath` does not. (Retrospective §4.)

The checks after the merge were memory notes run by memory, and each missed
once before it was written: a lane merged before its handback put a stale tree
under the barrier (waves 94 and 96); two JSON registries auto-merged into a
duplicate with no conflict marker (wave 87); UI lanes passed their panels and
reddened db-partition nav guards lanes cannot run (`verification/wave111-barrier-1.txt`);
a Playwright `trace.zip` holding an expired local test token reached origin at wave
111. A ratchet-file miss recurred five times before it was mechanised.
(Build seat's note `merge-traps-parallel-lanes`; retrospective §4, §5.)
`assets/pre-barrier.template.sh` is those notes as one command.

## Gate 6: lane databases

Before them, the first barrier attempt was red and the second green at four
consecutive waves (46, 47, 48, 50), structurally, each costing a full extra
check. (`build-conventions.md` §Lane databases.)

After them: schema replay into the template took 281 seconds once; a lane
clone took under a second; the lane selection settled at 304 of 392 integration
test files after the exclusion classes were measured rather than guessed.
(Escalation E-136 addendum 4.) A `pkill -f` once left an orphaned test process
running against a database its lane had dropped and re-cloned; `exec` now runs
each command in its own process group and `stop` ends exactly that tree.
(E-136 addendum 4; `build-conventions.md` §Lane databases.)

## Gate 7: reachable done conditions

One done condition required a count to reach zero. It fell by one in twelve
waves, because the wave loop only ever selected requirement rows and nothing
ever selected a gate violation. (`decisions/2026-09-03-the-loop-goes-faster.md`
§1–2.) After the repair, both remaining gates moved every wave.

## Gate 8: generated state, and the record's size

The hand-maintained index of open questions listed fourteen items as needing a
person that had all been decided four days earlier; three lanes sat blocked on
that. (`escalations-open.md` history, 2026-09-06.)

Waves 45 to 52 added 148,002 lines under `docs/` against 8,243 of product
code; the ruling capped barrier artefacts at 150 lines and log entries at 40.
(`decisions/2026-09-03-the-loop-goes-faster.md` §0, §5.)

## Gate 9: the guarded deploy

The deploy script lived in a temporary directory; a reboot removed it and the
next "deploy" reported success having done nothing. Two targets existed, one a
live application on a different lineage; the linked-service marker was the only
thing between them. (Reviewing seat, 2026-09-05.)

## Gate 10: every seat is named, and one owns the trunk

Two agents on one branch produced a duplicate commit of one lane's work, an
unattributed 5,000-line merge (escalation E-125 addendum), and a factual
disagreement about whether a deploy had happened that the platform's own
deployment list had to settle.

The build's best stretch ran three seats, and the second agent seat (the
reviewing seat, now `build-monitor`) was defined nowhere in the loop prompt or
the conventions doc; it existed only in commit messages, decisions and memory.
(Retrospective §2, grepped 2026-09-26.) Over waves 101 to 112, twelve waves
went green in about 74 hours, seven at the first attempt; over waves 84 to 99,
at most three of fifteen. Several changes landed together, so no single cause
is isolated. (Retrospective §3.) Its screenshot review caught what no gate sees: a
12,496 px page, internal names in user copy, a phone rail reflowing content.
(Retrospective §1–2.)

Two rules between seats were learnt the hard way. Messaging a running workflow
agent resumes it as a second writer in the same worktree, and a stand-down
reply forks it again: measured twice (E-385). And a monitor that writes into
the shared checkout during a barrier changes the tree under test: done twice,
2026-09-17 and 09-23. (Build seat's notes.)

## The wave: rules carried into `build-loop`

- **Multi-stage lanes.** Wave 99 ran six stages on one worktree
  (build→panel three times), the stage-D panel refuting the row on a third
  function (`evidence/wave99/cli10-export-envelope/`); wave 113's ui-aml-2 ran
  three (`evidence/wave113/orchestrator/stage3-ui-aml-2.md`). A refutation
  cost about an hour rather than a wave. At wave 100 the panels refuted three
  of four rows, each of which would have shipped silently. (Retrospective §3.)
- **The next queue is drafted at wave open.** `evidence/wave112/orchestrator/wave113-queue.md`
  existed before wave 112's record; there was no planning gap between a record
  and the next cut. (Retrospective §3.)
- **Attempt 3 reduces.** Wave 109 spent attempt 3 on a repair lane; it fixed
  109-2's cause and 109-3 went red on a new one (smoke visiting a sign-out that
  now revoked), stranding an approved lane off trunk. The wave took six
  attempts and a stall. (`verification/wave109-barrier-*.txt`; build seat's
  note.) Waves 101 to 112 took 22 attempts in all, six of them wave 109's.
  (Retrospective §1.)
- **A falsifier lands with its fix.** Wave 92 merged a correct red spec
  (PM-NFR-04) alone; `e2e:suite` ratchets at zero failures, so the barrier went
  red on a defect no attempt could repair and the wave reduced, losing the
  measurement. Wave 93 held it and flipped the row; wave 94's
  `nfr04-fix-and-land` landed both. A `git revert -m 1` would have made the
  next re-merge of that lane a silent no-op. (Build seat's note.)

## What worked, and should be kept

- **Ratcheting gates** rather than gating on zero.
- **Adversarial verify waves.** They found four real ledger defects the build's
  own tests could not see: a revaluation that posted twice (E-161), postings
  that reported success while leaving a draft (E-156, E-158, E-162), a bill
  picker that stopped showing new bills past a hundred, and a currency lookup
  that failed for any seat without rules access. (Waves 55, 59, 62.)
- **A per-export coverage instrument** found five of every six shipped server
  actions were exercised only by the browser suite. (E-143 addendum.)
- **A lane that measures a ruling wrong is believed.** Twice; right both times.
