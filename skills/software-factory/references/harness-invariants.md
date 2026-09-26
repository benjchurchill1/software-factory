# Gates 7, 8 and 10: the invariants that keep a long run honest

Three properties that cost nothing to establish before wave one and are
expensive to retrofit. Each has a measured failure behind it; see
`evidence.md`.

---

## Gate 7 — every done condition is reachable, and gates are selectable as work

### The failure

A build had four done conditions. One required a count of unreferenced exports
to reach zero. Over twelve consecutive green waves it fell by **one**, because
the wave loop's frontier only ever selected requirement rows and nothing in the
loop ever selected a gate violation as work. The condition was unreachable by
construction, and the run could only have ended by its own stall rule.

### The test to apply before the first wave

Read each done condition aloud and answer: **what, in the wave loop, makes this
fall?** Name the step. If the answer is "a lane might happen to", the condition
is decoration.

### The two repairs

1. **Demote what the loop cannot select.** A count that measures something real
   but that no lane owns stays a **ratchet** — measured every barrier, may only
   fall, recorded in the wave log — and comes out of the definition of done.
   That is not weakening the bar: the per-row precondition it was standing in
   for is still enforced on every row.
2. **Make the rest selectable.** Every build wave carries at least one lane
   whose subject is a gate count, until each is zero. Write it into the frontier
   step, not into prose someone must remember. A wave that closes rows and moves
   no gate is not finished.

### The shape of a good gate

- Reports a **count**, not a boolean.
- Ratchets: green when the count is at or below the previous barrier's, adopted
  mechanically, with a refusal to raise built into the adopter.
- Zero is a **done condition** for the ones a lane can own, never a commit
  condition — gating on zero on day one means the instruments wave cannot commit
  its own work, and the only way out is dishonest exemptions.
- A ceiling that genuinely must rise is raised **by a person editing the file**,
  with the reason in its note, so the file's history is the complete record of
  every number that moved and which way.

---

## Gate 8 — state the loop reads is generated, and the record is capped

### The failure

An index of open questions, maintained by hand alongside the archive it
summarised, listed **fourteen items as needing a person that had all been
decided four days earlier**. Three build lanes were blocked on that staleness,
two of them holding gate violations the build needed closed. Nobody had lied;
the rulings had been written and the index had simply not been updated.

### The rule

Any file the loop reads **to decide what to do next** is derived, and is
regenerated at the barrier from the underlying record. Not "should be kept up to
date". Generated.

### How to apply it

1. **List the derived files.** Typically: the index of open questions, the
   scoreboard's summary counts, a surface or coverage map, any "what remains"
   table.
2. **For each, name the source of truth** — the archive, the register, the
   decision files, the code itself — and write the regeneration path.
3. **Regenerate at the barrier**, in the same step that writes the wave record,
   and commit the result with the wave.
4. **Where regeneration is genuinely too expensive**, put a staleness stamp at
   the top (the commit it was derived at) and have the loop refuse to act on a
   file whose stamp is older than the current wave.

### The tell

If a person can edit a file and the loop will behave differently as a result,
and nothing regenerates it, that file will drift. The question is only which
wave.

### The record's size is part of this gate

Everything the loop writes, every lane reads at the start of the next wave.
Measured: eight waves added 148,002 lines under `docs/` against 8,243 of
product code, and the archive of open questions reached 700 KB before an index
replaced it as the thing lanes read. Cap it in the loop prompt, as numbers:

- a barrier artefact is at most **150 lines** — a phase table, each failure
  with one named cause, the gate counts, pointers to raw logs;
- a wave-log entry is at most **40 lines**;
- lanes read a **derived index** of open questions, never the archive;
- raw output goes to evidence files, never into the record.

A record that grows faster than the product is a token cost on every wave and
a reader cost on every handover.

---

## Gate 10 — every seat is named, and one owns the trunk

### The failures

Two agents on one branch, over one day, produced:

- **A duplicate commit** of the same lane's work, because one seat
  fast-forwarded onto a commit the other then amended.
- **An unattributed merge of 5,000 lines** onto a branch nobody had authorised,
  discovered later, whose provenance could not be established because every
  agent commits under the same identity.
- **A factual disagreement** about whether a deploy had happened, which took a
  query to the hosting platform's own API to settle.

None of these was a mistake of reasoning. They are what concurrent writers to
one branch produce.

### The protocol

- **One seat owns the trunk.** It merges, it records, it commits. Name it in the
  conventions doc.
- **Every other seat proposes**: it works on its own branch or worktree and
  messages the owner with a hash. It does not merge, reset or rewrite.
- **A seat that must change something the owner owns says so first** and waits
  for an acknowledgement.
- **Evidence beats assertion.** When two seats disagree about whether something
  happened, the answer is the external system's own record — the platform's
  deployment list, the reflog, the log file — not either seat's memory. Quote it.
- **Never route a denied action through a peer.** If a seat's permission
  classifier refused a command, another seat running it launders the user's
  decision. It goes on the person's list instead.

### The seats

Name all three in the conventions doc's §Seats, with what each owns, writes and
never does:

- **The owner** — rulings the policy cannot make, register changes,
  permission-gated commands, deploy consent.
- **The build seat** — owns the trunk, the shared resource, lane provisioning,
  the barrier, the record and the push.
- **The monitor seat** — a second session running `build-monitor` for the life
  of the build. It approves each lane before merge (screenshots at phone and
  desktop width for a lane that changes a screen), rules within the delegation,
  shapes the next wave's queue with the build seat, runs staging and its
  falsifiers, and keeps the owner's list short. It **never writes into the
  shared checkout while a barrier runs**: it drafts in its own scratchpad and
  hands over by message, and the build seat commits with attribution.

Two rules between seats, each learnt more than once: **never message a running
workflow agent** — it resumes as a second writer in the same worktree; and
**never let a generic tool pick a lane's base** — provision with the lane-cut
script.

### What it costs

Almost nothing, and it is the difference between two agents doubling throughput
and two agents producing work that has to be untangled.
