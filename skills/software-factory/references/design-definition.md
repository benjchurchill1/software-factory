# Gate 0b: is the interface defined before anyone builds it?

A loop builds what the register asks for and nothing else. If no row says what
the product looks like, the loop will not invent a look; it will produce
whatever the first lane happened to write, copied by every lane after it, and
every row will still pass. Nobody sees the result until a person signs in to a
deployed build, by which point the look is spread across every screen.

So the look is defined **before the register freezes**, by the same person who
owns the product, and it enters the register as rows the loop can fail
against. Taste can be delegated ("you decide, make it slick"); approval
cannot. The owner sees the screens before the build does.

Run this immediately after the oracle review (gate 0) and before the freeze.
Gate 0 asks whether the rows are worth building against; this gate asks
whether there are rows for the thing a person will actually look at.

---

## What it costs when it is missing

> **Measured, on a second build.** A staff case-management app was built
> to 56 of 98 register rows passing, deployed, with WCAG 2.2 AA, tablet and
> phone layouts and a branded PDF all in the register, and no row about how a
> screen looks. The interactive prototype the spec was written from reached the
> build only as a text summary. Styling was one hand-grown stylesheet with
> colour literals throughout. The owner signed in to the hosted site and called
> the UI appalling. A design system, five approved screens and five new rows
> were then written mid-build, and one whole wave was spent restyling with the
> logic untouched. See [evidence.md](evidence.md) §Gate 0b.

> **Measured, on a sister product.** After a session of closing gaps, every
> field was present and every test green, and the screens still did not look
> like the design: the person reviewing "still saw the old screens". Matching
> every field is necessary and not enough. Their fix was a written brief, a
> fixture-driven wireframe, and a side-by-side screenshot audit that a screen
> must pass before it ships.

Accessibility rows are not a design. An accessible, responsive, ugly product
satisfies every one of them.

---

## The four artefacts

All four exist, and the owner has approved the last two, before the register
is frozen. Fill `assets/design-system.template.md` for the first two.

### 1. A design brief

Half a page: who uses it, on what device, in what setting, and the character
the product should have in one sentence ("calm and precise, like a well-made
clinical notebook, not a dashboard"). Name what it must not look like, and any
product it must look distinct from. When the spec changes, the brief changes
in the same commit.

If the owner has no brand, say so in the brief and record who sets the visual
direction. A delegation in the owner's words is enough; quote it.

### 2. A design system

The tokens and the rules, written so a check can enforce them:

- **Tokens.** Every colour, type size, radius, shadow, space and duration as a
  named custom property (or the stack's equivalent). A literal value is legal
  only where a token is declared.
- **Status.** A closed set of status colours (three is enough), each as a
  text-on-tint pair that passes contrast, and each carrying a glyph as well as
  a colour so it survives greyscale and colour blindness. "No result yet" is
  neutral, never a warning colour.
- **Reserved colour.** If the product has one irreversible act (submit, sign,
  file, pay), it gets one colour nothing else uses.
- **Components.** The handful every screen uses (buttons, status chips, the
  card, the main list row, the form field, the product's one signature
  component), each defined once.
- **Rules.** How much of a screen is neutral, minimum text size, motion and
  its reduced-motion gate, print, dark mode in or out of scope. Out of scope is
  a fine answer; half-themed is not.

### 3. Approved mockups of the key screens

The screens a person spends their day on, not every screen: usually four to
six. Pick them from oracle test 7's walk through the main jobs: the landing
screen, the main list, the main record, the main action's form, and the
irreversible act. Each at the two widths the register names (for example 1280
and 390), with realistic fixture data, including an empty state and a long
value.

Build them as something the owner can open and react to: a published page, a
clickable prototype, design files. A text description of a prototype is not a
mockup; the build seat cannot see what the owner saw.

**Exit for this artefact:** the owner has looked at them and said yes, in
their own words, recorded with the date. "Looks good" counts. Silence does not.

### 4. Design rows in the register

The look enters the oracle as rows, so the loop can go red on it. These five
cover most products; adapt the IDs and widths, keep the verify methods
mechanical:

| ID | Requirement | Pass criterion | Verify method |
| --- | --- | --- | --- |
| DSN-01 | One token layer | The stylesheet declares exactly the design system's tokens; a static check fails on any colour, size or radius literal outside the token block | scripted check |
| DSN-02 | The shell matches | Top bar, navigation, page width and card treatment match the approved mockups at both widths | screenshot comparison |
| DSN-03 | Shared components | Each component in the design system exists once as a shared component and every screen uses it; no screen re-implements one | scripted check plus review |
| DSN-04 | Screens match the mockups | Each key screen, screenshotted at both widths with fixture data in the mockup's state, matches its approved mockup side by side; red when visibly different in layout, colour, type, spacing or overlay behaviour | screenshot comparison |
| DSN-05 | Contrast by token pair | A unit test asserts at least 4.5:1 for every text-on-ground token pair, including hover and status tints | unit test |

DSN-04 is the anti-drift row. It is judged by a person or a review lens
looking at two images side by side, so oracle test 6 counts it as review; put
it in the monitor seat's review (the `build-monitor` UI lane checklist does
this) rather than leaving it to the loop's own judgement, and say so in the
gate 0 review's count.

Every screen beyond the key ones inherits the system: DSN-01 and DSN-03 make
that mechanical.

---

## Order inside the build

The design rows are in **wave 1's frontier**, not the last wave's. Tokens and
the shared components go in before the first screen, so every later lane
builds on them. A restyle wave late in the build is the cost of skipping this
gate, not a plan.

`build-loop` takes the design system's path and the mockups' location as
`<DESIGN_SYSTEM_PATH>` and `<MOCKUPS_PATH>`, and the loop prompt tells every UI
lane to read them before writing a screen.

---

## Waiver

A product with no user interface (a library, an API, a batch job, a CLI with no
screens) waives this gate **with the reason written into the handover**. A
product whose only interface is generated by a framework the owner accepts as
is (an admin scaffold) may waive it the same way, naming that framework.

## Priming a build already in flight

Do not stop the build. Write the four artefacts in a separate session, get the
owner's approval on the mockups, then hand the rows to the build through its
ruling policy as **new** rows (the frozen register is never edited) and queue
one restyle wave with logic untouched. Then every later wave is held to them.
