---
name: software-factory
description: Prime a project so an autonomous, unattended software build can finish: review the requirements register and definition of done for falsifiability and reachability, define and approve the interface (design system, mockups, design rows) before the register freezes, then close thirteen gates (rig memory and sleep, standing permissions, a ruling policy, test-data lifecycle, lane provisioning, per-lane databases, reachable done conditions, generated state, a guarded deploy, named seats, a pre-flight for login, usage, disk and reboots, and a ratchet so tests and checks only get stricter), then run environment-check and hand off to build-loop. Use this first for any new autonomous or wave-based build, when someone wants a "software factory" set up, or wants acceptance criteria checked before an agent builds against them. Also use when a running loop stalls because of its environment: the machine swaps or sleeps, commands are refused, questions queue for a person, or state is maintained by hand. Not for missing secrets, blocked hosts, hosted migrations or logins (environment-check), writing or editing the loop prompt itself (build-loop), or watching a build in progress (build-monitor).
---

# Software factory

The loop is the easy part. What decides whether an autonomous build finishes is
the factory around it: an oracle worth building against, a rig that does not
swap, authority the loop already holds, a harness that cleans up after itself,
state nobody maintains by hand, limits the build sees coming, and checks that
only get stricter.

This skill primes those. **[references/evidence.md](references/evidence.md)**
records what each gate cost when it was missing, measured on one real build and
cited to its artefacts; read it when a user wants to skip one.

`build-loop` writes the loop prompt, the conventions doc, the status readout and
the scoreboard. This runs first and invokes `environment-check`, then
`build-loop`, at step 8.

## The fourteen gates

Work them in order. Each is a yes/no with a named artefact and a stated exit
condition. **Gate 0 decides whether the build is worth running at all**, and
**gate 0b decides whether it will look like anything** once it does; gates 1
to 5 are the ones that cost calendar time once it is running.

| # | Gate | Artefact | Who closes it |
| --- | --- | --- | --- |
| 0 | The oracle is worth building against | `<register>-review.md` beside the register | the product owner, with the agent |
| 0b | The interface is defined and approved before the register freezes | `docs/design/design-system.md`, approved mockups, design rows in the register | the agent drafts; **the owner approves the mockups** |
| 1 | The rig has a memory budget and a resident-process cap | `docs/engineering/the-rig.md` | the agent measures, the user acts |
| 2 | The loop holds standing authority for its own maintenance | project `.claude/settings.json` | **the user, by hand** |
| 3 | Judgement calls are delegated with a written policy | `decisions/ruling-policy.md` | the user delegates, the agent writes |
| 4 | Every spec removes what it creates; the rest is reaped by age | spec teardown, `scripts/estate-maintain.sh`, a residue census | the agent |
| 5 | The orchestrator provisions every lane in one step | `scripts/lane-cut.sh` | the agent |
| 6 | Lanes prove their integration tests before the barrier | `scripts/lane-db.sh` | the agent |
| 7 | Every done condition is reachable, and gates are selectable as work | the loop prompt's §Definition of done | the agent |
| 8 | State the loop reads is generated, and the record is capped | a regeneration path per derived file | the agent |
| 9 | Deploy is one guarded script, or there is no deploy | `scripts/deploy-<env>.sh` | the agent writes, the user confirms each run |
| 10 | Every seat is named, and one owns the trunk | the conventions doc's §Seats, added at step 8 | the agent |
| 11 | The build sees its limits coming: login, usage, disk, reboots | `scripts/preflight.sh`; the rig doc's §Disk and reboots and §Login and usage | the agent writes; **the user records the login time** |
| 12 | Tests and checks only get stricter | `.claude/test-freeze.json`, the checks and never-together ledgers, `scripts/guards.py` | the agent drafts; **the user places and commits the freeze config** |

**Waivers.** Gate 0b is waived only for a product with no user interface,
with the reason in the handover. Gates 4 and 6 assume a shared stateful service (a database, a
broker). A project with none waives them **with the reason written into the
handover**, not silently. A project with several such services runs gate 6 once
per service. Gate 9 is waived when there is genuinely no deploy target.

## Workflow

### 0. Review the oracle before anything else

**[references/oracle-review.md](references/oracle-review.md)**: seven tests
over every requirement row, five over the definition of done.

This is the cheapest hour in the build and the most expensive to skip. A loop
satisfies its register exactly, for weeks, without asking whether that produces
the product; the reference records a build that reached 89 passing rows with an
application whose navigation offered nine destinations that did not work,
because no row said "through the interface".

The loop may not edit a requirement row, so every defect left here costs an
escalation, a ruling and a wave later. Repairs are made now, by the product
owner. Two of the seven tests (achievable evidence, and coverage) can only be
answered by them; do not rule on those.

**Exit condition:** the review file exists and the count of rows needing
human judgement is written down. The register is not frozen yet: gate 0b adds
rows to it first.

### 0b. Define the interface, then freeze

**[references/design-definition.md](references/design-definition.md)**: a
design brief, a design system of tokens and rules, approved mockups of the
four to six screens people spend their day on, and design rows in the register
(tokens enforced by a static check, shared components, each key screen
matching its mockup by side-by-side screenshot, contrast by token pair).

A loop never invents a look. With no design rows it ships whatever the first
lane wrote, every row passes, and nobody sees it until a person signs in to a
deployed build. Accessibility and responsive rows are not a design. Fill
`assets/design-system.template.md`, build the mockups as something the owner
can open, and put them in front of the owner. The owner may delegate taste
("you decide"), but not approval: they see the screens before the build does.

**Exit condition:** the design system file exists with no unreplaced slot,
the owner's approval of the mockups is quoted with its date, the design rows
are in the register and in wave 1's build order, and only then is the
register frozen. Waived, with the reason in the handover, for a product with
no user interface.

### 1. Measure the rig

Do not ask what the machine is. Measure it, and say the numbers back.

    sysctl hw.memsize vm.swapusage        # or /proc/meminfo, free -g
    docker info --format '{{.MemTotal}} {{.NCPU}}'
    ps -Ao rss,command | sort -rn | head -12
    pgrep -fl 'claude|next|node .*server' | wc -l

Four findings decide gate 1, and `assets/the-rig.template.md` has a slot for
each. **Total memory** against what one full check needs at its peak. **The
container runtime's allowance**: it competes with the check rather than
helping it, so it wants the smallest figure the database is happy with. **What
else is resident**, including desktop applications. **How many agent seats and
app servers are up at once**: the build's own barrier record names concurrent
agent sessions and an orphaned app server as the largest single costs, not the
desktop.

**Exit condition:** the rig doc exists with measured numbers, a container
budget with its reason, a resident-seat cap, a do-not-run list, and the
pre-launch swap check the barrier will run. The user has acted on the
do-not-run list, or said when they will.

**The host must not sleep.** A sleeping host pauses timers and kills in-flight
agent requests; they die as "[Request interrupted]", which reads like a
person's interruption. The rig doc's §Host sleep has the check for macOS, Linux
and Windows; the source
build lost five build agents in a row to it at wave 109.

### 2. Install standing authority: a human action

**This step is the user's, not the agent's.** The build this skill is drawn from
measured the write of the permission file refused at every autonomous seat, and
the same maintenance command refused at a background seat and permitted when
the user asked for it in the live session. Do not try to write the file from
here, and do not treat a foreground success as proof of anything.

Do this instead, from
**[references/standing-authority.md](references/standing-authority.md)** Part 1:

1. Fill `assets/settings.allowlist.template.json` (named scripts only, never
   bare `docker`, `psql`, `sh` or `git reset`) and write it to a path the user
   can paste from.
2. Tell the user exactly where it goes and that it is per-machine.
3. **Exit condition:** the user confirms it is in place, **and** step 9's
   background-seat check passes.

Two more standing instructions are settled here, in the user's words in the
transcript, not on the allowlist (Part 1, *Push after green*): **push after
every green barrier**, bounded to fast-forward on the trunk only, and **which
branch the platform deploys from**: that branch is never the trunk and never
pushed by the loop. The source build's trunk was a named wave branch while `main`
auto-deployed; say which is which on day one.

### 3. Write the ruling policy

The second half of standing authority, Part 2 of the same reference. Fill
`assets/ruling-policy.template.md`: who may rule, the ordered policies, the
floor (a row is ruled once), and the rule that a lane measuring a ruling wrong
is believed. The user grants the delegation **in the transcript**; quote it in
the file.

**Exit condition:** the policy file exists and names the delegate.

### 4. Design the test-data lifecycle

Ask one question: **what does a test leave behind, and who removes it?** If the
answer is "nothing, tests clean up", verify it on the largest suite.

Otherwise, teardown is the spec's from wave 1: every spec removes what it
creates, found by a marker the spec itself writes. An age-based reaper and a
residue census are backstops for a spec that died mid-run, not the mechanism.
**[references/harness-gates.md](references/harness-gates.md)** §Gate 4 has the
rules and the evidence behind them.

Fill `assets/estate-maintain.template.sh` to that file's contract, including
orphan reaps for both stranded database connections and stranded app servers.

**Exit condition:** the script's dry run plans and drops nothing, creates
nothing, and names its evidence path; the residue census is on the gate list.

### 5. Provision lanes from one script

A lane never cuts its own worktree or chooses its own identifier range. The
orchestrator does both in one step with `scripts/lane-cut.sh`, because that
instant is the only one at which both facts are known and cheap. On the source
build, the written conventions for both were read and still broken in most
lanes. Never let a generic tool infer the base: the Workflow tool's
`isolation: 'worktree'` cuts from `main`, which may not be the trunk.

Fill `assets/lane-cut.template.sh` and `assets/pre-barrier.template.sh` to
their contracts in **[references/harness-gates.md](references/harness-gates.md)**
§Gate 5. Lane-cut runs a base proof, including one test from a path with a
space; pre-barrier is the one command after the serial merge that checks
ancestry, stray artefacts and the suites lanes cannot run.

**Exit condition:** `lane-cut.sh --dry-run <n>` prints every command it would
run and creates nothing; `status` lists no lanes; `pre-barrier.sh --dry-run`
prints its checks.

### 6. Give lanes their own database

If parallel builders exist and integration tests need a shared service, give
each lane its own clone, or those tests first run at the barrier and the first
attempt goes red almost every wave. Fill `assets/lane-db.template.sh` to its
contract in **[references/harness-gates.md](references/harness-gates.md)**
§Gate 6, and name in the conventions doc the two classes of test that stay at
the barrier.

**Exit condition:** `up` reports the replay time and a conformant template;
`clone`, one small test, and `drop` all succeed; the shared service is
unchanged afterwards.

### 7. Pre-flight and the ratchet (gates 11 and 12)

**[references/harness-gates.md](references/harness-gates.md)** §Gates 11 and
12 has the contracts. Both gates are new in 0.3.0 and were not measured on the
source build; the reference says what they defend against and why.

**Gate 11.** Copy `assets/guards.py` to `scripts/guards.py` and commit it on
the trunk (pre-barrier runs the trunk's copy). Fill
`assets/preflight.template.sh`: the generated files it scans for slots
(`<GENERATED_FILES>`), the disk paths and floor (`<DISK_PATHS>`,
`<DISK_FREE_GB>`), the boot-id and reboot-pending commands, the login check and
lifetime (`<AUTH_CHECK_COMMAND>`, `<AUTH_LIFETIME_HOURS>`), the usage-window
command, the minutes a wave and a barrier may take plus the handoff reserve
(`<WAVE_TIME_LIMIT_MINUTES>`, `<BARRIER_MAX_MINUTES>`,
`<HANDOFF_RESERVE_MINUTES>`), and the spend figures as plain numbers in the
usage events' unit (`<SPEND_LIMIT_NUMBER>`, `<WAVE_SPEND_LIMIT_NUMBER>`,
`<BARRIER_SPEND_ESTIMATE>`, `<HANDOFF_RESERVE_NUMBER>`). Fill the rig doc's §Disk and reboots and
§Login and usage while measuring. Settle how the seat is woken after a usage
pause (`<RESUME_MECHANISM>`). Where nothing reports the login's time left, the
user records the login time after each login; say so plainly, it is theirs to
do.

**Gate 12.** Draft `.claude/test-freeze.json` with the project's test globs
plus `scripts/checks/**`, the `frozen` list (by default `scripts/guards.py`,
`scripts/pre-barrier.sh` and `scripts/preflight.sh`), the trunk as `base`, and
the supersessions register's path, for the user to place and commit: once gate 2's allowlist is in, it denies agent edits to that
file, as it does to the settings. Seed the checks ledger and the
never-together ledger as empty files on the trunk, and create
`scripts/checks/`. Add the ruling policy's §Retiring a check. Fill
`pre-barrier.sh`'s ratchet slots.

**Exit condition:** `preflight.sh --dry-run` prints every check; one real run
exits 0 (or its non-zero line is reported and understood); a hand edit of a
committed test in a scratch branch is refused by the hook and failed by
`pre-barrier.sh`'s `tests` line.

### 8. Close gates 7, 8 and 10, then build the loop

Gates **7**, **8** and **10** are in
**[references/harness-invariants.md](references/harness-invariants.md)** with
the failure behind each and the test to apply. In short: read each done
condition aloud and name the wave-loop step that makes it fall; list the files
the loop reads to derive state and give each a regeneration path, and cap the
record so it stops growing faster than the product; and name every seat
(the owner, the build seat that owns the trunk, and the monitor seat that runs
`build-monitor` beside it), with what each owns, writes and never does.

For **9**, `assets/deploy-env.template.sh` is one script that refuses the wrong
target, verifies the served artefact rather than trusting the platform's
success line, and lives somewhere a reboot does not clear. Deploy is never on
the allowlist.

**Recovery and budgets.** Write the readiness record described in
**[references/recovery.md](references/recovery.md)**: where the journal and
checkpoint live, the spend and time limits and where usage is read from, and
for gate 9 the known-good release, rollback and restore steps. That file says
which parts a script enforces and which are rules the loop is asked to follow.
Gate 9 can close with deploy **waived** for a local-only build; it cannot close
as **met** until rollback and restore have been rehearsed on the real target.

**Then run `environment-check`. Not optional.** Gates 1 to 12 prime the
machine and the repo; they do not prove the outside world is ready. The
environment check lists every secret, CLI, host, hosted migration path, login
and standing decision the build needs, sends the owner one list of what is
missing, and passes only from the session the build will run in. On the source
build for that skill, 23 of 26 migrations never reached the hosted database
because the cloud environment had no database token, and three approvals were
refused by the build seat because they were relayed. Do not start the loop on
a BLOCKED report.

**Then invoke `build-loop`. Not optional.** A primed factory with no loop is
half a delivery. It writes the loop prompt, the conventions doc, the status
readout and the scoreboard. Hand it what the factory settled so its interview
does not re-ask, in the terms its slot table uses:

| Factory gate | `build-loop` slot |
| --- | --- |
| 1: the rig | `<TIMEOUT_FACTS>`, `<DO_NOT_RUN>` (do-not-run list, seat cap, pre-launch check) |
| 2: allowlist; push after green | `<ALLOWLIST_PATH>`, `<PUSH_RULE>` |
| 3: ruling policy | `<RULING_POLICY_PATH>` (the ladder's autonomous terminal) |
| 4: maintenance | `<MAINTENANCE_COMMAND>` (a barrier build step, before the check) |
| 5: lane provisioning; pre-barrier checks | `<LANE_CUT_COMMAND>`, `<EVIDENCE_DIR>`, `<PRE_BARRIER_COMMAND>` |
| 6: lane databases | `<SINGLETON>`, `<LANE_DB_COMMAND>`, `<SHARED_RESOURCE_SUITES>` (the two classes that stay at the barrier) |
| 8: generated state | `<REGENERATED_FILES>`, `<RECORD_CAPS>` |
| 9: deploy | `<DEPLOY_SCOPE>` (the guarded script and its confirmation rule), `<DEPLOY_BRANCH>` |
| 0b: the interface | `<DESIGN_SYSTEM_PATH>`, `<MOCKUPS_PATH>` (design rows first in `<BUILD_ORDER>`) |
| 10: seats | `<OWNER>`, `<TRUNK_OWNER>` (the monitor seat is `build-monitor`, not a slot) |
| 11: pre-flight | `<PREFLIGHT_COMMAND>`, `<RESUME_MECHANISM>` |
| the environment check | `<ENV_CHECK_COMMAND>`, `<STANDING_DECISIONS_PATH>`, and its lane count as the wave's width |
| 12: the ratchet | `<CHECKS_LEDGER>`, `<NEVER_TOGETHER_PATH>`, `<SUPERSESSIONS_PATH>`, `<CLEAN_ROUNDS>` |
| budgets and recovery | `<RUN_STATE_DIR>`, `<SPEND_LIMIT>`, `<WAVE_SPEND_LIMIT>`, `<TIME_LIMIT_MINUTES>`, `<WAVE_TIME_LIMIT_MINUTES>`, `<HANDOFF_RESERVE>` |

Let it interview for what the factory did not settle: the oracle's path, the
green command, the blocked list, wave shape, stop conditions.

### 9. Verify, then hand over

Do not hand over an unprimed factory or an unrun loop.

**The factory:**

- `estate-maintain.sh --dry-run <evidence-dir>`: plans, creates nothing.
- `lane-cut.sh --dry-run <name>`: prints every command, cuts nothing.
- `pre-barrier.sh --dry-run`: prints every check, runs none.
- `preflight.sh --dry-run`: prints every check; one real run is recorded.
- The test-freeze hook refuses an edit to a committed test, and allows a new
  one, in a scratch branch.
- `lane-db.sh up`, `clone`, one small test, `drop`: report the replay time.
- The deploy script with its guard tripped: refuses.
- `scripts/env-check.py` exits 0 from the build's own session, and its report
  is committed.
- The design system has no unreplaced slot, the mockups open, the owner's
  approval is quoted, and the register's design rows are in wave 1 (or gate
  0b's waiver is written down).
- `python3 <this skill's base directory>/scripts/verify-factory.py` passes.
  It tests the templates, not your filled copies: run each filled script's
  dry run as well.
- The crash drills in `references/recovery.md` have been run in a disposable
  fixture and recorded. Any drill not run is reported as **blocked**, not
  passed.
- **The allowlist, from a background seat.** Spawn a subagent or a
  `run_in_background` command that runs one allowlisted script with its dry-run
  flag, and quote its result verbatim. A foreground run proves nothing; the
  source build measured the same command permitted foreground and refused
  background.

**The loop**: `build-loop`'s own checks, repeated because they are the half a
person runs first:

- The status readout executes and prints.
- The check command exists and terminates; if red, say so.
- The scoreboard's row count matches the register's in-scope count.
- No unreplaced slot in any generated file: `grep -nE '<[A-Z][A-Z0-9_]*(:[^>]*)?>'`
  over everything written. Every slot in this skill's assets is that shape.

Then report each of the fourteen gates as **met**, **waived with a reason**, or
**blocked on the user**, and state how to start the loop, how to watch it
(start the monitor seat with `build-monitor` in a second session, beside
`loop-status.sh`), and what it will produce when it finishes.

## Priming an existing build

Do not regenerate anything. Run gate 0 against the register as it stands,
and gate 0b if no design rows exist (as new rows through the ruling policy,
plus one restyle wave; see the reference's last section): a
build in flight has usually found several of its defects the expensive way and
is still carrying the rest. Then measure the rig, read the loop's own barrier
records for what has stalled it, and propose the missing gates as a diff. The
order the gates cause damage in is the order in the table.
