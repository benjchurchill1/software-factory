---
name: software-factory
description: Prime a project to run an autonomous build unattended, end to end — quality-test the register/PRD and the definition of done first, then the rig's memory budget, standing permissions, a ruling policy, the test-data lifecycle, lane provisioning, per-lane databases, generated state and a guarded deploy — then invoke build-loop to write the loop prompt itself. Use when someone is about to start an autonomous or unattended build, wants a "software factory" set up, wants a new project primed for a wave-based build agent, wants acceptance criteria or a definition of done reviewed for falsifiability and reachability before an agent builds against them, or when a running loop keeps stalling on the machine, on permissions, on questions queued for a person, or on state a human maintains by hand.
---

# Software factory

The loop is the easy part. What decides whether an autonomous build finishes is
the factory around it: an oracle worth building against, a rig that does not
swap, authority the loop already holds, a harness that cleans up after itself,
and state nobody maintains by hand.

This skill primes those. **[references/evidence.md](references/evidence.md)**
records what each gate cost when it was missing, measured on one real build and
cited to its artefacts; read it when a user wants to skip one.

`build-loop` writes the loop prompt, the conventions doc, the status readout and
the scoreboard. This runs first and invokes it at step 7.

## The eleven gates

Work them in order. Each is a yes/no with a named artefact and a stated exit
condition. **Gate 0 decides whether the build is worth running at all**; gates
1 to 5 are the ones that cost calendar time once it is.

| # | Gate | Artefact | Who closes it |
| --- | --- | --- | --- |
| 0 | The oracle is worth building against | `<register>-review.md` beside the register | the product owner, with the agent |
| 1 | The rig has a memory budget and a resident-process cap | `docs/engineering/the-rig.md` | the agent measures, the user acts |
| 2 | The loop holds standing authority for its own maintenance | project `.claude/settings.json` | **the user, by hand** |
| 3 | Judgement calls are delegated with a written policy | `decisions/ruling-policy.md` | the user delegates, the agent writes |
| 4 | Every spec removes what it creates; the rest is reaped by age | spec teardown, `scripts/estate-maintain.sh`, a residue census | the agent |
| 5 | The orchestrator provisions every lane in one step | `scripts/lane-cut.sh` | the agent |
| 6 | Lanes prove their integration tests before the barrier | `scripts/lane-db.sh` | the agent |
| 7 | Every done condition is reachable, and gates are selectable as work | the loop prompt's §Definition of done | the agent |
| 8 | State the loop reads is generated, and the record is capped | a regeneration path per derived file | the agent |
| 9 | Deploy is one guarded script, or there is no deploy | `scripts/deploy-<env>.sh` | the agent writes, the user confirms each run |
| 10 | Every seat is named, and one owns the trunk | the conventions doc's §Seats, added at step 7 | the agent |

**Waivers.** Gates 4 and 6 assume a shared stateful service (a database, a
broker). A project with none waives them **with the reason written into the
handover**, not silently. A project with several such services runs gate 6 once
per service. Gate 9 is waived when there is genuinely no deploy target.

## Workflow

### 0. Review the oracle before anything else

**[references/oracle-review.md](references/oracle-review.md)** — seven tests
over every requirement row, five over the definition of done.

This is the cheapest hour in the build and the most expensive to skip. A loop
satisfies its register exactly, for weeks, without asking whether that produces
the product; the reference records a build that reached 89 passing rows with an
application whose navigation offered nine destinations that did not work,
because no row said "through the interface".

The loop may not edit a requirement row, so every defect left here costs an
escalation, a ruling and a wave later. Repairs are made now, by the product
owner. Two of the seven tests — achievable evidence, and coverage — can only be
answered by them; do not rule on those.

**Exit condition:** the review file exists, the register is frozen, and the
count of rows needing human judgement is written down.

### 1. Measure the rig

Do not ask what the machine is. Measure it, and say the numbers back.

    sysctl hw.memsize vm.swapusage        # or /proc/meminfo, free -g
    docker info --format '{{.MemTotal}} {{.NCPU}}'
    ps -Ao rss,command | sort -rn | head -12
    pgrep -fl 'claude|next|node .*server' | wc -l

Four findings decide gate 1, and `assets/the-rig.template.md` has a slot for
each. **Total memory** against what one full check needs at its peak. **The
container runtime's allowance** — it competes with the check rather than
helping it, so it wants the smallest figure the database is happy with. **What
else is resident**, including desktop applications. **How many agent seats and
app servers are up at once** — the build's own barrier record names concurrent
agent sessions and an orphaned app server as the largest single costs, not the
desktop.

**Exit condition:** the rig doc exists with measured numbers, a container
budget with its reason, a resident-seat cap, a do-not-run list, and the
pre-launch swap check the barrier will run. The user has acted on the
do-not-run list, or said when they will.

**The host must not sleep.** A sleeping host pauses timers and kills in-flight
agent requests; they die as "[Request interrupted]", which reads like a
person's interruption. The rig doc's §Host sleep has the check; the source
build lost five build agents in a row to it at wave 109.

### 2. Install standing authority — a human action

**This step is the user's, not the agent's.** The build this skill is drawn from
measured the write of the permission file refused at every autonomous seat, and
the same maintenance command refused at a background seat and permitted when
the user asked for it in the live session. Do not try to write the file from
here, and do not treat a foreground success as proof of anything.

Do this instead, from
**[references/standing-authority.md](references/standing-authority.md)** Part 1:

1. Fill `assets/settings.allowlist.template.json` — named scripts only, never
   bare `docker`, `psql`, `sh` or `git reset` — and write it to a path the user
   can paste from.
2. Tell the user exactly where it goes and that it is per-machine.
3. **Exit condition:** the user confirms it is in place, **and** step 8's
   background-seat check passes.

Two more standing instructions are settled here, in the user's words in the
transcript, not on the allowlist (Part 1, *Push after green*): **push after
every green barrier**, bounded to fast-forward on the trunk only, and **which
branch the platform deploys from** — that branch is never the trunk and never
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

Ask one question: **what does a test leave behind, and who removes it?**

If "nothing, tests clean up", verify it on the largest suite. Otherwise: every
population a test mints is **declared**; anything undeclared is **reaped by
age** at the barrier; and the reaper's floor — rows a constraint will refuse to
delete — is reported, never forced.

**Teardown is the spec's, from wave 1.** Every spec removes what it creates,
found by a **positive marker the spec itself writes** — a reference prefix, a
fixture seat, a note token — never by inference from what looks like test
data. Where records are audited, it closes them through the product's own
paths, as a user would. The age-based reaper and any barrier precondition are
backstops for a spec that died mid-run, not the mechanism. Residue was the most
frequent red cause across the source build's waves 101 to 113, and each time
it was data a spec had made on the shared practice and left.

Fill `assets/estate-maintain.template.sh`, including its orphan reaps for
**both** stranded database connections **and** stranded app servers.

**Exit condition:** the script's dry run plans and drops nothing; its evidence
log path is declared and its nearest existing parent is verified writable
without creating files.
The dry run creates no evidence directory or log and executes no database,
process or analysis command. Create the evidence path only on a real run.
A **residue census** — a count, per minted population, of rows no live run
owns — is measured every barrier and ratcheted like any other gate.

### 5. Provision lanes from one script

Two conventions in the source build — prove your base, take your migration
range from the brief — were both written down, both read, and both recurred:
119 of 188 worktrees cut at a commit from a different project; four of eleven
lanes choosing the same migration number. The ruling was that a lane does not
cut its own worktree or choose its own number: **the orchestrator provisions
both in one step, with a script**, because the instant a lane comes into
existence is the only instant at which both facts are known and cheap.

Fill `assets/lane-cut.template.sh`: cut from the trunk's current tip, link
dependencies, run the base proof (the tip is an ancestor of the new tree; the
expected directories exist; the typecheck and the test harness both load),
allocate the lane's identifier range, write the range ledger. The trunk and wave
come from a conf file the orchestrator moves, never from the script's source.

Never let a generic tool infer the base. The Workflow tool's
`isolation: 'worktree'` cuts from `main`; on the source build the trunk was not
`main`, and reaching past the script for it was E-14's fourth recurrence.

The base proof also runs **one path-sensitive test from a path containing a
space**, once at this gate, unless the repo path is guaranteed free of them. The
source build's wave 112 lane was green in its worktree and red in the main
checkout, whose path held spaces: `URL.pathname` keeps `%20`, so use
`fileURLToPath`.

`assets/pre-barrier.template.sh` is this gate's other half: after the serial
merge, one command asserts every lane branch is an ancestor of the integration
branch, scans each lane's diff for `trace.zip`, `*.har` and `.env*`, and runs
the typecheck, the registry duplicate check and the suites lanes cannot run,
one PASS or FAIL line each. Its header says what fills each slot; the trunk,
integration branch and lane glob come from `lane-cut.conf`, as lane-cut's do.

**Exit condition:** `lane-cut.sh --dry-run <name>` prints every command it would
run; `status` lists no lanes; `pre-barrier.sh --dry-run` prints its checks.
Use `[a-z][a-z0-9_]{0,47}` in both lane scripts, reserving `status`;
reject invalid input instead of normalizing it. The trunk owner provisions
serially and uses unique names across active waves, retiring old databases
before reuse. Dry run must not create proof logs or invoke range allocators.

### 6. Give lanes their own database

If parallel builders exist and integration tests need a shared service, they
otherwise first execute at the barrier, and the first barrier attempt is red
almost every wave. `assets/lane-db.template.sh` stands up a second container,
replays the schema into a template once, and clones per lane in about a second.
It runs each lane's command in its own process group and records it, so `stop`
ends exactly that tree and a second run on a live lane is refused; that guard
exists because a `pkill -f` once left an orphaned test process running against
a database its lane had dropped and re-cloned.

Two classes of test cannot move there and must be named in the conventions doc:
those that talk to the shared service over HTTP, and those that build an
expensive fixture.

**Exit condition:** `up` reports the replay time and a conformant template;
`clone`, one small test, and `drop` all succeed; the shared service is
unchanged afterwards.

### 7. Close gates 7, 8 and 10, then build the loop

Gates **7**, **8** and **10** are in
**[references/harness-invariants.md](references/harness-invariants.md)** with
the failure behind each and the test to apply. In short: read each done
condition aloud and name the wave-loop step that makes it fall; list the files
the loop reads to derive state and give each a regeneration path, and cap the
record so it stops growing faster than the product; and name every seat —
the owner, the build seat that owns the trunk, and the monitor seat that runs
`build-monitor` beside it — with what each owns, writes and never does.

For **9**, `assets/deploy-env.template.sh` is one script that refuses the wrong
target, verifies the served artefact rather than trusting the platform's
success line, and lives somewhere a reboot does not clear. Deploy is never on
the allowlist.

**Required operational artifact:** follow
[references/recovery.md](references/recovery.md) and write a durable readiness
record naming budget limits/usage source, journal/checkpoint paths, crash-drill
evidence, known-good release, rollback and restore evidence or explicit service
waivers. Gate 9 stays blocked until target-specific recovery steps are
instantiated and rehearsed; mock fixtures do not close platform readiness.

**Then invoke `build-loop`. Not optional.** A primed factory with no loop is
half a delivery. It writes the loop prompt, the conventions doc, the status
readout and the scoreboard. Hand it what the factory settled so its interview
does not re-ask, in the terms its slot table uses:

| Factory gate | `build-loop` slot |
| --- | --- |
| 1 — the rig | `<TIMEOUT_FACTS>`, `<DO_NOT_RUN>` (do-not-run list, seat cap, pre-launch check) |
| 2 — allowlist; push after green | `<ALLOWLIST_PATH>`, `<PUSH_RULE>` |
| 3 — ruling policy | `<RULING_POLICY_PATH>` (the ladder's autonomous terminal) |
| 4 — maintenance | `<MAINTENANCE_COMMAND>` (a barrier build step, before the check) |
| 5 — lane provisioning; pre-barrier checks | `<LANE_CUT_COMMAND>`, `<EVIDENCE_DIR>`, `<PRE_BARRIER_COMMAND>` |
| 6 — lane databases | `<SINGLETON>`, `<LANE_DB_COMMAND>`, `<SHARED_RESOURCE_SUITES>` (the two classes that stay at the barrier) |
| 8 — generated state | `<REGENERATED_FILES>`, `<RECORD_CAPS>` |
| 9 — deploy | `<DEPLOY_SCOPE>` (the guarded script and its confirmation rule), `<DEPLOY_BRANCH>` |
| 10 — seats | `<OWNER>`, `<TRUNK_OWNER>` (the monitor seat is `build-monitor`, not a slot) |
| budgets and recovery | `<RUN_STATE_DIR>`, `<SPEND_LIMIT>`, `<WAVE_SPEND_LIMIT>`, `<TIME_LIMIT_MINUTES>`, `<WAVE_TIME_LIMIT_MINUTES>`, `<HANDOFF_RESERVE>` |

Let it interview for what the factory did not settle: the oracle's path, the
green command, the blocked list, wave shape, stop conditions.

### 8. Verify, then hand over

Do not hand over an unprimed factory or an unrun loop.

**The factory:**

- `estate-maintain.sh --dry-run <evidence-dir>`: plans, creates nothing.
- `lane-cut.sh --dry-run <name>`: prints every command, cuts nothing.
- `pre-barrier.sh --dry-run`: prints every check, runs none.
- `lane-db.sh up`, `clone`, one small test, `drop`: report the replay time.
- The deploy script with its guard tripped: refuses.
- Run `python3 <this skill's base directory>/scripts/verify-factory.py`: rendered shell fixtures must pass. Repeat against project-filled
  commands in isolation before claiming project readiness.
- Execute and record the crash drills in `references/recovery.md` with a
  separate verifier; check budgets survive restart and unknown operations stop.
  Name any unexecuted platform rollback/restore drill as blocked, not passed.
- **The allowlist, from a background seat.** Spawn a subagent or a
  `run_in_background` command that runs one allowlisted script with its dry-run
  flag, and quote its result verbatim. A foreground run proves nothing; the
  source build measured the same command permitted foreground and refused
  background.

**The loop** — `build-loop`'s own checks, repeated because they are the half a
person runs first:

- The status readout executes and prints.
- The check command exists and terminates; if red, say so.
- The scoreboard's row count matches the register's in-scope count.
- No unreplaced slot in any generated file: `grep -nE '<[A-Z][A-Z0-9_]*(:[^>]*)?>'`
  over everything written. Every slot in this skill's assets is that shape.

Then report each of the eleven gates as **met**, **waived with a reason**, or
**blocked on the user**, and state how to start the loop, how to watch it —
start the monitor seat with `build-monitor` in a second session, beside
`loop-status.sh` — and what it will produce when it finishes.

## Priming an existing build

Do not regenerate anything. Run gate 0 against the register as it stands — a
build in flight has usually found several of its defects the expensive way and
is still carrying the rest. Then measure the rig, read the loop's own barrier
records for what has stalled it, and propose the missing gates as a diff. The
order the gates cause damage in is the order in the table.
