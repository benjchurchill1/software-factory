# Review checklist, per lane

Read in this order: the verify panel's record, the evidence directory, then
the product itself. The builder's self-report is never evidence.

## Every lane

- [ ] The criterion quoted verbatim. Does what shipped meet the words, not a
      paraphrase of them?
- [ ] The panel ran the **caller-deletion** lens: the shipped caller was
      deleted and the row's own evidence went red. A green under deletion
      means the row is proved somewhere nobody reaches.
- [ ] The panel **broke the claim** on every axis that applies (wrong tenant,
      missing permission, direct write around the UI, concurrent write,
      replay, forged claim), with a positive control proving the refusal came
      from the control, not a fixture accident.
- [ ] The lane's database partition ran green on its own database, not first
      at the barrier.
- [ ] No credential-bearing artefacts in the diff (`trace.zip`, `.har`,
      `.env*`). If one exists, the merge is squashed without it.
- [ ] Test data the lane's specs create is removed by the specs themselves,
      identified by a marker the spec wrote. Residue on shared demo data was
      the most frequent barrier red in the source build.
- [ ] A spec that is correct and red because the product is wrong does **not**
      merge alone. It lands with its fix, and the row flips in the same commit.

## UI lanes

Screenshots at **390 px and 1440 px** for every changed screen, from the
panel's evidence or taken yourself against a served build.

- [ ] Page length is proportionate. The source build caught an AML page at
      12,496 px, filled by an unbounded history list.
- [ ] No truncated values at 390 px (`scrollWidth > clientWidth`).
- [ ] No raw identifiers in user copy: table names, enum keys, ISO dates.
- [ ] The page's one primary action is present for a seat that may take it,
      or its absence is explained.
- [ ] A seat that cannot see a section gets no section. "Nothing outstanding"
      shown to a seat that cannot see the data is a false statement.
- [ ] Lists show an honest count and page. A silent cap is a defect.
- [ ] Drawers and overlays don't reflow content; focus is trapped and returns;
      Esc closes; axe AA is clean open and closed.
- [ ] Past-due and state pills match the register's vocabulary.

## Data and concurrency lanes

- [ ] Locks are taken in one order on every writer path (advisory lock first).
      Any retry is bounded and jittered.
- [ ] Capacity is proven at the size a real customer reaches, not the fixture.
- [ ] Anything that fails, fails closed.

## Answer format

One line the build seat can quote in the merge commit:

- `APPROVED`
- `APPROVED with <excluded leg> → wave N+1 <lane>`
- `stage <k>: <change> — falsifier: <measurement that would prove it wrong>`
- `HOLD: <reason>`
