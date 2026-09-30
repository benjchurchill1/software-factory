# What the monitor seat caught: the source build, waves 101–113

The source build is a UK accountancy practice-management product built by this
loop over 113 waves (August–September 2026). Source: its 2026-09-26
retrospective and the merge commits on its trunk, where the build seat quotes the monitor's ruling
("the reviewing seat …").

## Throughput with the seat in place

| Stretch | Green waves | Calendar | First-attempt greens |
| --- | --- | --- | --- |
| 84–99 | 15 | 2026-09-17 → 09-22 | at most 3 |
| 101–112 | 12 | ~74 h, 2026-09-23 → 09-26 | 7 |

PASS went from 109/150 (09-20) to 132/152 (09-26). The screens:strict ceiling
went 6 → 0 and the e2e census 10 → 2. Several changes landed between waves 99
and 101, so the seat is one cause among several, not the only one.

## Findings the gates and panels passed

- **ui-aml** (wave 112): the page was 12,496 px (18,811 before). The summary
  read "Version 130" because demo-residue versions filled an unbounded history.
  "public.aml risk factor" appeared in user copy. No Approve was visible while
  the page said "not yet approved". → wave 113 `ui-aml-2`, three stages.
- **settings-area-2** (wave 112): the rail reflowed content at 390 px when
  open. Approved with that leg excluded → wave 113 `phone-rail-overlay`.
- **doc-templates-paging** (after barrier 112-1): a silent 200-row cap on the
  template list. Ruled a real defect, not a fixture problem → wave 113 lane
  with honest counts, search, and an audit of every other `_LIMIT`.
- **portal-digest-2** (wave 112): a CDD filing failed with deadlock 40P01 in
  10/10 races, and 53,200 rows died at 13,000 → wave 113 `portal-digest-3`.
  Lock-first merged; chunking deferred to wave 114 rather than holding it.
- **str-residue** (wave 113): shaped the barrier-repair brief. Close flagged
  reports through the product's own withdrawal path, identify spec-created
  reports by a positive marker, and keep a decoy as the control.

## Mistakes the seat made, and the rule each became

- Wrote decision files into the checkout during barriers 84 and 104-1 →
  rule 1 (never write during a barrier).
- Read an empty `Set-Cookie` sweep as decisive when the probe looked at the
  wrong response; read "no file writes" as a stalled lane → rule 5.
- Re-derived a mechanism already recorded in design doc 0008 (~40 minutes) →
  rule 6.
- Checked a nested, empty stop-file path and reported "no stop marker" when
  one existed. The keep-alive hook reads a stop file in the repo's state directory (`hooks/arm.py status` shows where).
