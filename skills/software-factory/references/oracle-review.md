# Gate 0: is the oracle worth building against?

The register (or PRD, or acceptance criteria) is the work queue, the test oracle
and the definition of done. An autonomous loop will satisfy it **exactly**, for
weeks, without ever asking whether satisfying it produces the product. This
review is the cheapest hour in the whole build and the most expensive one to
skip.

Run it before wave one. Run it again at the halfway point, because a register
that was fine at row 40 is often wrong by row 90.

**The loop may not edit a requirement row.** That is why the review happens
before the loop starts: afterwards, every defect found here costs an escalation,
a ruling and a wave.

---

## The seven tests

Apply each to every row. A row that fails one is repaired **now**, by the
person who owns the product, not ruled on later by an agent.

### 1. Falsifiability: what makes this row RED?

Name the assertion that fails. If you cannot, the row will pass vacuously.

> **Measured.** A criterion said an obligation "recomputes". Its only assertion
> counted queued items greater than zero, against a queue that a fixture
> restore filled before every run and nothing ever drained. It could not fail.
> It sat PASS for six waves and was caught by an adversarial verifier, not by
> the suite.

> **Measured.** Two legs of another row were satisfied from the second run
> onward by the *previous* run's rows, because nothing cleared the table
> between runs.

**The test:** for each row, write the one sentence that describes the world in
which it is red. If that sentence is "the code was deleted", the row is
vacuous.

### 2. Reachability: is the capability reachable by a person?

A row provable against the database alone will be proved against the database
alone.

> **Measured, and it cost thirty waves.** A build reached 89 rows passing, 7,583
> tests and zero conformance violations, with an application whose navigation
> offered nine destinations that did not work and whose screens were, in the
> main, read-only registers over a database nobody could write to through the
> product. Seventy-two of the 89 passing rows were provable with nothing
> rendered. The register never said "through the interface", so the loop
> optimised exactly what it was asked to. (`docs/prompts/build-loop.md` §What
> changed from v1, in the source repo.)

**The test:** for each row, name the route, the control and the verb a person
uses. If the answer is "none, it is a database property", the row must say so
explicitly and carry a reason, and the count of such rows is a number you
should be uncomfortable with.

### 3. Non-contradiction: do any two rows conflict?

> **Measured.** One row required cold login to land on the client register,
> unqualified. Another required a configurable per-role dashboard. One predicate
> governed both "renders" and "is the landing screen", so satisfying the second
> made the first false in every practice. It took an escalation, a ruling and a
> deferred feature to resolve, mid-build.

**The test:** group rows by the surface they touch. Within each group, ask
whether all of them can be true at once. Pay attention to defaults, landing
states, and anything phrased as "always" or "never".

### 4. Achievable evidence: can this be proved where the build runs?

> **Measured.** Ten rows were tagged for the first release and asked for
> evidence no amount of building can create: a partner demonstrating live, a
> reconciliation against a practice's own manual list, an import from a real
> legacy backup, an audit over a thirty-day period. Holding the release behind
> them made it unreachable by construction: a category error, not a schedule
> problem. The repair was a release tag meaning "provable only by running the
> built system at a real site".

**The test:** for each row, name the artefact that proves it and ask whether
this machine can produce it. Rows that need a real customer, real elapsed time
or real third-party credentials get their own release tag and leave the
loop's scope, with their evidence package prepared for the day they can run.

### 5. Non-empty population: does the criterion quantify over something?

> **Measured.** A criterion quantified over a population the demo data never
> contained, so both its positive clauses were vacuously true. Another named
> fixtures the seed had never built, so its specs were red for want of data
> rather than for want of a product.

**The test:** for each row containing "every", "all", "any" or "no", name the
rows in the fixture that make the quantifier meaningful, and say who creates
them: the seed, or the spec through the shipped interface.

### 6. Mechanical pass condition: who decides, and how?

Each row needs a verify method, and the honest set is small: scriptable check,
deterministic against named fixtures, observable from a recorded walkthrough,
a named artefact exists, or professional judgement.

**Anything in the last category cannot be closed by an autonomous loop.** Count
them before you start. If any are in scope for the unattended run, the run
cannot finish; either they move out of scope or a person is in the loop by
design, on a schedule.

> **Measured.** Zero rows in the last category were in scope, which is the fact
> that made an unattended run possible at all. That was luck, discovered
> afterwards, not design.

### 7. Coverage: what does a user do that no row mentions?

The six tests above check the rows you have. This one checks for the rows you
do not.

**The test:** walk the product's main jobs end to end on paper: the daily
task, the weekly task, the onboarding of a new customer, the thing that happens
when something goes wrong. At each step, name the row. A step with no row is a
gap, and the loop will never find it, because the register is its whole world.

---

## The definition of done, tested the same way

The done conditions are rows too, and they fail the same ways.

1. **Each condition must fall by something the wave loop selects.** Read it
   aloud and name the step that moves it. See `harness-invariants.md` gate 7:
   one build's done condition fell by one over twelve waves because nothing
   ever selected it.
2. **Each must be enumerable, not a feeling.** "Every row has a terminal
   verdict" is enumerable. "The product is ready" is not.
3. **The terminal verdicts must be a closed list**, and every one of them must
   be reachable without a person: passed, blocked on a named dependency from a
   closed list, out of scope by release tag, or parked by a ruling that cannot
   be re-ruled. An open-ended "some rows will need discussion" is how a run
   stops while looking busy.
4. **Aggregate rows are derived, never built.** A row that says "the MVP is
   complete" is computed from its components at the end; it is never in a
   frontier.
5. **The last condition should be an artefact, not a state.** "This assessment
   file exists, one line per row with evidence" is checkable. "We are done" is
   not.

---

## What to produce

A short review document beside the register: the rows repaired and why, the
rows retagged out of scope, the contradictions resolved, the gaps found in test
7, and the count of rows needing human judgement. Then the register is frozen
as the contract and the loop may not touch it.

**Where a row is wrong and the owner is unavailable**, the loop's ladder can
rule on interpretation, but only within a row, never to add or delete one.
The gaps from test 7 in particular can only be closed by the person who knows
what the product is for.
