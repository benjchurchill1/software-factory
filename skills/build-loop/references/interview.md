# The interview

Ask in this order. Later sections depend on earlier answers.

Do not ask what the repo already answers: confirm it instead ("I see
`bun run check` runs typecheck, lint, tests and a smoke; is that green?").
Batch two or three related questions per message; a twenty-question form gets
answered carelessly.

Three sections are marked **CHALLENGE**. In those, a weak answer is pushed back
on once, with the reason, before being accepted. Everywhere else, take what is
given.

---

## 1. The project

- What is being built, in one sentence?
- Which branch does the loop work on? (never `main`; default `autobuild/v1`)
- Is there existing work, or is this greenfield? If existing, what state is it in?

## 2. The oracle: CHALLENGE

The single most important answer. Everything else is downstream.

- **Which file decides whether a requirement is met?** Path.
- How is a row identified? (`PM-BIL-02`-style IDs, or something else)
- What does a row carry: a pass criterion, a verify method, a release/scope tag?
- **Who may change it?**

**Reject and re-ask if:**

- *"The tests."* Tests are written by the loop. An oracle the loop can edit is
  not an oracle: it is the loop marking its own homework with extra steps.
- *"The loop decides when a feature is done."* Same defect, stated plainly.
- *"The design docs."* Prose is not a criterion. Ask what a passing row looks
  like when executed. If the answer is "you'd have to read it and judge", the
  register does not exist yet and writing it is wave zero: say so.
- **Rows carry no pass criterion.** The loop cannot test an aspiration. Either
  criteria get written first, or the first wave writes them and a human approves
  them before any building starts.

**Also establish:** what happens when a row turns out to be wrong. There must be
a verdict for "this requirement is itself defective" that does not involve
editing the register: otherwise the loop's only route past a bad row is to
quietly change the contract.

## 3. Green: CHALLENGE

- **What single command means green?**
- What does it cover: types, lint, unit tests, integration tests against the
  shared resource, a runtime check that actually starts the thing?
- How long does it take? Which parts need the shared resource?

**Reject and re-ask if:**

- *"There isn't one yet."* Fine, but it becomes wave zero's first deliverable
  and nothing else starts until it exists and passes. Say so explicitly.
- *"Several commands."* Ask for one that runs them all. A loop that must
  remember four commands will drop one.
- **Nothing in it starts the product.** Name the blind spot in the generated
  conventions doc. Types, lint and unit tests start no server: a module that
  exports the wrong shape, a call site passing credentials the runtime cannot
  read, a route that 200s with an empty body: none are reachable by a test over
  a pure function, because the defect is in the composition rather than in any
  function. A loop with no runtime check will accumulate these behind a green
  barrier and find them all at once, late.

## 4. The shared singleton

The question that decides whether the loop's parallelism is real.

- **What one mutable resource do all lanes share?** A local database, a staging
  environment, a device, a rate-limited API, a build cache.
- **Who owns it?** Exactly one role: the orchestrator. Builders never mutate it.
- **What makes concurrent work on it safe?** Per-test tenancy, namespacing,
  separate schemas, per-worker accounts.
- **What operations are NOT covered by that isolation?**

That last question is the one that gets skipped, and it is the expensive one.
Namespacing separates *records*; it rarely separates *the resource itself*. Draw
the answer out with examples in the project's own terms:

| Isolation | What it does not scope |
| --- | --- |
| a tenant/row key in a database | `ALTER TABLE`, `TRUNCATE`, migrations, `VACUUM FULL`: whole-table locks no key narrows |
| a per-worker account on an API | the shared rate limit, global config, account-wide state |
| a namespace in a cluster | CRDs, admission webhooks, node capacity |
| a directory per worker | the package registry, a global lockfile, the port range |

Whatever comes back becomes the shared-state law in the generated prompt, *with
its limits stated*. A law that says "parallel work is safe here" without saying
where it stops is worse than no law: it is an invitation to run four of
everything.

Then ask the operational half:

- **How is a run of the check identified?** If the answer is "it isn't", the
  generated conventions doc gets the tagging rule: every connection, session or
  job carries the run's name, so a leftover can be found and reaped by name
  rather than by forensics.
- **Does killing a run release the resource?** Usually not. Long-running work
  frequently outlives the process that started it: a database backend does not
  notice a dead client while it is waiting on a lock; a queued job survives its
  submitter. The generated doc says so and gives the reap command.

## 5. Frozen ground

- What may the loop never edit? (typically: the register, the design docs,
  existing tests, `.env*`)
- Is any of that enforced by a hook, or is it prose?
- **What is the sanctioned route when a frozen thing is genuinely wrong?**

That last one matters more than it looks. A rule with no escape hatch gets
circumvented rather than obeyed. The usual shape: write a successor, name the
predecessor, record why, and let a privileged step do the deletion, so what is
no longer running is visible in one place rather than silently dropped.

## 6. Verdicts and the blocked list: CHALLENGE

- What verdicts may a row end in? Default: `PASS`, `BLOCKED(<dependency>)`,
  `DISPUTED(<reason>)`.
- What counts as evidence for a PASS? (must be executed: a test run, a script
  output, an artefact path, never "it should work")
- **Enumerate every legitimate reason a row cannot be finished locally.**

**Reject and re-ask if the list is open-ended.** "Some things will need
credentials" is not a list. Demand the actual set: each with what a human must
supply, and what the loop builds in the meantime (an interface, a fake, a
mock-based test). Anything not on the closed list is not blocked, it is `stuck`,
and `stuck` has an anti-spin rule. Without that distinction a loop parks its
hard rows under a respectable-sounding label and reports progress.

Also: **may a builder record its own PASS?** The answer must be no. If the same
context that wrote the code also writes the verdict, the verdict is worth
nothing. Verification is a separate pass with fresh context, told to refute.

## 7. Wave shape

- How many lanes can run at once?
- Do builders get isolated worktrees?
- How many verifier lenses per row, and which rows get a panel? (security,
  money, data-integrity rows usually get three: correctness,
  permissions, isolation-and-concurrency)
- What is the build order: which subsystems must exist before which?
- How many clean panel rounds in a row, at the same lane commit, finish a lane?
  Default two. Push back on one: a single panel's blind spot then decides.
  More than three mostly adds time.

## 8. The record

- Where does the scoreboard live?
- Where do assessments and evidence go?
- Commit message format; is pushing allowed; is deploying allowed? (default: no
  to both)
- If pushing is allowed, it is a standing instruction in the owner's words,
  bounded: after every green barrier's record, fast-forward only, the loop's
  branch only, never `--force`. **Which branch does the platform deploy from?**
  That branch is never the trunk and never pushed by the loop.
- Who reads the output? The tone rule follows from this: a file read by someone
  who was not watching needs plain verdicts and real paths, not cheerleading.

## 9. Stop conditions

Confirm or adjust the defaults:

- A row failing verification twice becomes `stuck`; retry once after two further
  waves; a second failure marks it disputed with the attempt history.
- Empty frontier is not done: completion requires bootstrap evidence and every
  in-scope row terminal. Retry ownerless WIP; diagnose cycles, missing IDs,
  cooldowns and non-PASS dependencies. If none can advance, hand off as
  dependency-stalled without inventing verdicts or empty waves.
- Two consecutive waves with no scoreboard change → stop, write the handoff,
  flag it stalled. Never idle-loop.
- Shared resource down → one restart attempt, then write the handoff and stop.
  Do not fight the machine.

- The login expires → stop cleanly before the step it would interrupt, with an
  `auth-expiring` handoff. How long does a login last here, and can anything
  report the time left? If nothing can, the owner records the login time.
- A usage limit → pause until the window resets, then resume. What reports the
  window, and what wakes the seat at the reset time (`/loop`'s next firing, a
  scheduled resume of the session, or a line on the owner's list)?

Also settle the durable run-state directory, total spend ceiling and accounting
unit, elapsed-time ceiling, per-operation bounds and handoff reserve. Budgets
include retries, reviewers and recovery and persist across restarts. Require a
usage source and the factory's crash-drill evidence before unattended operation.

---

## Before writing anything

Play the answers back as a short summary and get a yes. The interview is cheap;
a loop built on a misheard oracle is not.

---

## Answer → slot

Which answer fills which template slot. Slots appear as `<NAME>` or
`<NAME: what goes here>`; both must be replaced.

| Interview answer | Fills |
| --- | --- |
| project, one sentence | `<PROJECT>`, `<STACK_SUMMARY>` |
| branch | `<BRANCH>`, `<BASE_BRANCH>`, `<COMMIT_FORMAT>` |
| the oracle's path | `<REGISTER_PATH>`, `<N>`, `<SCOPE_RULE>` |
| the spec and architecture docs | `<SPEC_PATH>`, `<ARCHITECTURE_PATH>`, `<EXPLICIT_EXCLUSIONS>`, `<FIXED_DECISIONS>` |
| the green command | `<CHECK_COMMAND>`, `<BUILDER_GREEN_COMMAND>`, `<WHAT_IT_COVERS>` |
| what green covers, and what it doesn't start | `<RUNTIME_CHECK>`, `<RUNTIME_CHECK_RATIONALE>` |
| the shared resource | `<SINGLETON>`, `<SINGLETON_UP_CHECK>`, `<RESTART_COMMAND>` |
| what makes concurrency safe on it | `<ISOLATION_CONVENTION>`, `<ISOLATION_UNIT>`, `<ISOLATION_RULES>`, `<FORBIDDEN_MUTATIONS>` |
| what that isolation does **not** cover | `<UNSCOPED_OPERATIONS>`, `<UNSCOPED_RESOURCE>`, and one `<FILE>` / `<OPERATION>` table row per place it happens |
| bounded-wait mechanism | `<BOUNDED_WAIT_MECHANISM>`, `<TIMEOUT_SIGNAL>` |
| how a run is identified | `<RUN_TAG_UNIT>`, `<RUN_TAG_FORMAT>`, `<RUN_TAG_MECHANISM>`, `<REAP_COMMAND>`, `<ORPHANED_WORK_QUERY>` |
| default timeout vs observed contention | `<TIMEOUT_FACTS>`, `<CONTENTION_CHECK>`, `<CONTENTION_QUERY>`, `<CONTENTION_CHAIN_QUERY>` |
| the expensive setup, and whether it is rebuilt | `<SETUP_COST_SECTION_TITLE>`, `<SETUP_COST_RATIONALE>` |
| frozen paths and hooks | `<FROZEN_PATHS>`, `<HOOK_NOTE>`, `<SECRETS_RULE>` |
| the supersede route | `<SUPERSEDE_MECHANISM>` |
| verdicts and evidence | (the defaults in the template usually stand) |
| the closed blocked list | `<BLOCKED_LIST>` |
| wave shape | `<HIGH_STAKES_ROWS>`, `<LENSES>`, `<ATTACK_VECTORS>` |
| build order | `<BUILD_ORDER>` |
| the record | `<PROGRESS_PATH>`, `<ASSESSMENT_PATH>`, `<HANDOFF_PATH>`, `<MEMORY_APPEND_RULE>`, `<VERDICT_PATTERN>` |
| persistent accounting and recovery, total and per-wave ceilings | `<RUN_STATE_DIR>`, `<SPEND_LIMIT>`, `<WAVE_SPEND_LIMIT>`, `<TIME_LIMIT_MINUTES>`, `<WAVE_TIME_LIMIT_MINUTES>`, `<HANDOFF_RESERVE>` |
| deploy and push policy; the branch the platform deploys from | `<DEPLOY_SCOPE>`, `<PUSH_RULE>`, `<DEPLOY_BRANCH>` |
| clean rounds per lane | `<CLEAN_ROUNDS>` |
| what wakes the seat after a usage pause | `<RESUME_MECHANISM>` |
| **settled by `software-factory`, if it ran first**: do not re-ask | |
| the rig doc: do-not-run list, seat cap, pre-launch swap check | `<DO_NOT_RUN>` |
| the permission allowlist's path | `<ALLOWLIST_PATH>` |
| the ruling policy's path (the ladder's autonomous terminal) | `<RULING_POLICY_PATH>` |
| the estate maintenance step, run at the barrier before the check | `<MAINTENANCE_COMMAND>` |
| the lane provisioning script and its evidence root | `<LANE_CUT_COMMAND>`, `<EVIDENCE_DIR>` |
| the pre-barrier check script | `<PRE_BARRIER_COMMAND>` |
| the pre-flight script (login, usage, disk, reboots, config) | `<PREFLIGHT_COMMAND>` |
| the environment check and the owner's standing decisions (`environment-check`) | `<ENV_CHECK_COMMAND>`, `<STANDING_DECISIONS_PATH>` |
| the ratchet: the checks ledger, the never-together ledger, the supersessions register | `<CHECKS_LEDGER>`, `<NEVER_TOGETHER_PATH>`, `<SUPERSESSIONS_PATH>` |
| the lane database script and the two test classes that stay at the barrier | `<LANE_DB_COMMAND>`, `<SHARED_RESOURCE_SUITES>` |
| the derived files and their regeneration paths; the record caps | `<REGENERATED_FILES>`, `<RECORD_CAPS>` |
| the seats: the owner, and the trunk's owning seat | `<OWNER>`, `<TRUNK_OWNER>` |
| paths of the generated files | `<THIS_FILE>`, `<CONVENTIONS_PATH>`, `<STATUS_SCRIPT_PATH>`, `<STATUS_COMMAND>`, `<AGENT_INSTRUCTIONS_PATH>` |
| derived from the above | `<STATE_SOURCES>`, `<WAVE_ZERO_DELIVERABLES>`, `<MUTATIONS>`, `<MUTATION_ARTEFACT>`, `<SHARED_RESOURCE_SUITES>`, `<UNIT_SUITE_PATTERN>`, `<SHARED_SUITE_PATTERN>`, `<TEST_PROCESS_PATTERN>`, `<OTHER_COMMANDS>`, `<ENVIRONMENT_NON_NEGOTIABLES>` |

If an answer does not exist for a slot, do not invent one and do not leave the
slot. Either drop the sentence, or state the gap in the generated file as
something wave zero must establish: a loop told "this is not decided yet" behaves
better than one handed a plausible guess.
