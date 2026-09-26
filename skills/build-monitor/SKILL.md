---
name: build-monitor
description: Run the monitor seat for an autonomous wave-based build — a second Claude session beside the build seat that reviews every lane before merge (screenshots at phone and desktop width for UI lanes), makes product rulings within the owner's delegation, shapes the next wave's queue, deploys to staging and runs falsifiers there, keeps the owner's list short, watches liveness, and publishes a generated progress checklist page after each wave. Use when someone wants a build monitor, a reviewing seat, a second pair of eyes on an unattended build, a progress checklist or dashboard for a build loop, or asks "where is the build", "what's left", or "what's waiting on me" during a software-factory / build-loop build.
---

# Build monitor

The build seat builds. This seat decides whether what was built is the product,
and keeps everyone able to see where the build is.

It exists because gates and verify panels catch what the register says, and
miss what a person would see in ten seconds: a 12,000 px page, a raw table
name in user copy, a list that silently stops at 200. Over waves 101–112 of the
source build, with this seat in place, 12 waves went green in about
74 hours and 7 of 12 went green at the first barrier attempt. Several changes
landed at the same time, so the seat is one cause among several
(`references/evidence.md`).

Run it after `software-factory` has primed the project and `build-loop` has
written the loop. The factory's seats gate names this seat; the loop's
conventions doc gives it its rights.

## The seat's rules

These outrank everything else here.

1. **Never write into the shared checkout while a barrier runs.** A barrier's
   verdict describes the tree it measured. Check first (the status readout, or
   a barrier `launch.txt` with no exit line). If unsure, draft in your
   scratchpad and hand the path to the build seat by message. It places the
   file at the record, with your attribution. Done wrong twice in the source
   build; harmless both times by luck.
2. **Never message a running workflow agent.** It resumes as a second writer in
   the same worktree. Talk to the build seat; the build seat talks to lanes.
3. **Never route a refused command through another seat.** If the permission
   layer refuses something, put it on the owner's list with the exact command.
4. **You approve; you don't merge.** The build seat owns trunk, the shared
   resource, the barrier, the record and the push.
5. **An absence is evidence only if you said first what a presence looks
   like.** "No commits in ten minutes" is not a stalled lane: lanes batch
   commits and spend their last stretch in tests. Liveness is processes and
   database backends, not files.
6. **Search the build record before reasoning about a mechanism** (design docs,
   decisions, escalations), and say what the search returned.

## Setup (once per build)

1. Find the build seat. `ListAgents` shows sessions; agree the channel
   (`SendMessage`) and the orchestrator directory where briefs and queues live.
2. Write the progress config beside the repo, not in it (the build seat owns
   the checkout): copy `assets/monitor.example.json` to
   `<project folder>/build-monitor/monitor.json` and fill it from the repo.
   Every field is a path or a pattern the build already writes; see
   `references/progress-checklist.md`.
3. Seed `owner-list.md` from `assets/owner-list.template.md` with whatever is
   already waiting on the owner.
4. Generate and publish the page (below). Record its URL in `monitor.json`
   as `artifact_url` so any later session updates the same page.
5. Save a memory note naming the build seat, the config path and the page URL.

## The cycle

Each pass: **look → review → rule → shape → publish.** Most passes are only the
first step. Pace passes to what you are waiting for: a lane handback or a
barrier is 20–50 minutes, so a 20–30 minute cadence is right while nothing is
due, not a minute-by-minute poll.

### Look

- Run the project's status readout (`scripts/loop-status.sh`, or wherever build-loop wrote it). Read
  lane processes, barrier state, memory and swap, dirty files.
- If agents died with "[Request interrupted]", check host sleep first
  (`pmset -g log | grep -E 'Sleep|Wake'`), then tell the build seat to run
  `caffeinate`.
- If a barrier reds on a timeout in code no lane touched, suspect the host or
  the test estate before the tree. Ask for the one cell alone.

### Review every lane before merge

The build seat messages you at each lane's handback. Read the verify panel's
record, then the evidence, then look at the product yourself.
`references/review-checklist.md` has the full list; the core is:

- **The criterion, verbatim, against what shipped.** Not the self-report.
- **UI lanes: screenshots at 390 and 1440 px** for every changed screen. Look
  for page length, truncated values, raw identifiers or ISO dates in user copy,
  a missing primary action, reflow when a drawer opens, silent caps on lists.
- **Scope.** Merge now with a follow-up queued for the next wave, send it to
  stage 2 or 3, or hold it. A lane that is safe and better than trunk merges;
  its remaining gap becomes a named lane.

Answer with one of: **APPROVED**, **APPROVED with <exclusion> → wave N+1
<lane>**, **stage <k>: <what to change and the falsifier>**, or **HOLD:
<why>**. The build seat quotes it in the merge commit.

### Rule within the delegation

The ruling policy (`decisions/ruling-policy.md` from the factory) says what
you may decide. Rule fast, in writing, with the smaller claim that is certain.
If a question is the owner's (legal, commercial, a new register row), bring it
to them as a recommendation they can answer yes or no to, and put it on the
owner's list until they do.

### Shape the next wave

At the current wave's open, the next wave's queue is drafted
(`<orchestrator dir>/wave<N+1>-queue.md`). Add to it as reviews produce work:
each entry names the lane, why, and its falsifiers. Keep the queue within the
host's lane capacity. First in the queue is whatever a review found that is a
real defect.

### Staging

After a green record, if the owner has authorised it: deploy through the
project's guarded deploy script only, verify the served build, and run any
falsifiers that only staging can answer (HTTP, hosted auth). Commit the probe
as evidence by handing it to the build seat. Credentials come from the
environment and never go in a file.

### Publish the progress checklist

    python3 <this skill's base directory>/scripts/progress.py --config <project folder>/build-monitor/monitor.json

Then republish the page: Artifact `publish` with `file_path` set to the
generated HTML and `url` set to `artifact_url`. The page's `url` stays the
same. Do this after every wave record, and after any change to the owner's
list. The script is read-only against the repo and safe during a barrier.

The page shows:
- **Road to done**: each done condition with its live count.
- **The current wave**: lane by lane (cut, built, review stages with verdicts,
  approved, merged), barrier attempts, recorded, pushed.
- **The next queue.**
- **What waits on the owner.**
- **History**: PASS per green wave and barrier attempts per wave.

Everything except the owner's list is derived. Never hand-edit the page.

### Keep the owner's list short

`owner-list.md`: one line per item, `- [ ] what — why or where`. Only things
no seat may do: register writes, refused commands, legal and commercial calls,
deploy consent, history rewrites. Remove ticked items after one wave. When
reporting to the owner, lead with this list.

## When the owner asks

- **"Where are we?"** Regenerate and republish, then answer in three lines:
  done conditions met, current wave and barrier state, what waits on them.
- **"What's left?"** The unticked done conditions with counts, then the queue.
- **"Is it stuck?"** Apply the loop's stop conditions as written: three build
  waves with no terminal-row or gate movement, or three red barrier attempts
  with no gate falling. Measure; don't judge.

## References

- `references/review-checklist.md`: what to check on each lane type before
  approving.
- `references/progress-checklist.md`: the config fields, how each page section
  is derived, and adapting it to a build with different file names.
- `references/evidence.md`: what this seat caught in the source build, cited to
  its artefacts.
