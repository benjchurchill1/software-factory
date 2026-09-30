# Ruling policy: <PROJECT>

Standing delegation for questions the build raises and may not answer itself.
Written once, before the first wave. Amended only by <OWNER>.

## Who may rule

| Tier | May decide | Records where |
| --- | --- | --- |
| <OWNER> | anything, including reversing the tiers below | `docs/requirements/decisions/YYYY-MM-DD-title-slug.md` |
| The delegated reviewing seat | interpretation, scope, order, domain calls | the same, first line naming the delegation, "written to be vetoed" |
| The loop, at ladder rung 4 | only a row that has failed twice | `docs/requirements/decisions/auto/`, listed first in the handoff |

The delegation to the reviewing seat is granted by <OWNER> in the session
transcript and is quoted in every ruling made under it.

## The ordered policies

Apply the most specific that fits. Say which was used.

1. **Never rule that a requirement is satisfied.** Rulings resolve scope, order
   and interpretation. If the honest answer is that the row passes, that is a
   verdict with evidence, not a ruling.
2. **Never weaken a test, a gate or a budget** to fit a measurement.
3. **Prefer the reading that makes the product usable** over the one that is
   cheaper to build.
4. **Domain questions are decided on domain norms**, cited in one line.
   <DOMAIN_AUTHORITIES>
5. **Prefer the smaller certain claim**, and the reversible option when the
   call is genuinely balanced and money, safety or statute is involved. Say
   when it was balanced.
6. **Local answer now, hosted answer at launch**, where the two differ.
7. **Never take a bare revoke** of a working capability: build the replacement,
   move the consumers, revoke last.
8. **Mechanical beats prose.** If the rule could be a check, make it a check.

## The form of a ruling

Thirty to seventy lines. No essays.

    # <RULING_SENTENCE>
    <DATE>. **Decided under <OWNER>'s delegation of <DATE>**, by the reviewing
    seat; written to be vetoed. Answers **<ID>: "<TITLE_VERBATIM>"**.
    ## The question        (2-5 lines, in the escalation's own framing)
    ## The ruling          (imperative, numbered if several parts)
    ## Why                 (measured facts + which policy + the norm cited)
    ## What it costs, and what the other answer would have cost
    ## What this does not do
    ## What a person should check
    ## Confidence: high | medium | balanced

## The floor

A row may be ruled **once**. A failure after its ruling is terminal: parked,
never re-ruled, listed first in the handoff. That floor is what stops the
ladder becoming the spin it exists to prevent.

## The rule that makes this safe

**A lane that measures a ruling to be wrong is believed.** The measurement is
the authority; the ruling is amended and cites it. A delegation without this
produces confident nonsense that lanes then implement.
