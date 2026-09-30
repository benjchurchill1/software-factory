# Standing authority: what the loop may do, and what it may decide

Two delegations. Without the first, the loop stops at every barrier waiting for
a person to run a command. Without the second, it stops at every judgement call
waiting for a person to answer a question. Both are written once, before the
first wave.

---

## Part 1: the permission allowlist

### What it is for

An autonomous build has standing duties that look privileged to a permission
classifier: pruning its own test data, applying its own schema migrations,
restarting a wedged service, regenerating types. Measured across one build,
every one of these was refused at every autonomous seat, and the same command
was permitted when a person asked for it in their own words in a live session.
The loop cannot tell the difference and should not try.

### The shape

**Name scripts, never verbs.** An allowlist entry for a named script is a
delegation. An entry for `docker`, `psql`, `git reset` or a shell is a standing
grant to do anything, and it is the thing the classifier exists to refuse.

    "Bash(bash scripts/estate-maintain.sh:*)"     yes: one named duty
    "Bash(docker exec:*)"                         no : unbounded
    "Bash(supabase migration up:*)"               yes: a bounded CLI verb
    "Bash(psql:*)"                                no : unbounded

Everything the loop is ordered to do routinely belongs on the list. Everything
else stays off it, and the loop's own rule is: **try once, record the refusal
verbatim, put it on the person's list, and never route around it**, not by
splitting the command, not through another tool, and never by asking a peer
session to run it. A peer running a denied command is the user's decision
being laundered.

### What must never be allowlisted

- Anything that deploys, publishes or pushes to a remote.
- Anything that rewrites history (`reset --hard`, `push --force`).
- Anything that touches secrets or the permission file itself.
- Destructive database operations that are not behind a named, logged script.

### Push after green, and the deploy branch

A push stays off the allowlist. It is a **standing instruction** the user gives
in their own words in the transcript, quoted into the loop prompt's push rule,
and bounded: after every green barrier's committed record, fast-forward only,
the trunk only, never `--force`. A refused push is recorded and goes on the
person's list, like any other refusal.

Settle on day one **which branch the platform deploys from**. That branch is
never the trunk and never pushed by the loop. On the source build the trunk
was a named wave branch while `main`, a divergent lineage, auto-deployed; every
push was a guarded act, and every tool that assumed `main` was the trunk cut
from the wrong tree.

### The script contract

A duty on the allowlist is a script, and the script:

1. takes an evidence directory as its argument and appends a log there, so
   `git log -p` on that path is the whole history of every time the duty ran;
2. prints a before and after census of whatever it changed;
3. refuses its most destructive mode unless explicitly asked (`--all` and its
   kind are never the default);
4. exits non-zero if any step failed, having still run the others, so the log
   says which.

`assets/estate-maintain.template.sh` is that shape.

### Where it goes

The project's own settings file, gitignored. It is per-machine, and the loop
records in its handoff that a fresh machine needs it again.

---

## Part 2: the ruling policy

The policy itself is `assets/ruling-policy.template.md`: who may rule, the
ordered policies, the form of a ruling, the floor. Fill it; do not restate it
here. Two things about it that belong to the person setting up the factory
rather than to the file:

**Why it exists.** Forty-six questions accumulated on one build because each
individually needed a person; three lanes sat blocked on questions already
decided. The policy converts "ask a person" into "decide by these rules and
record it", and the delegated middle tier (a reviewing seat the owner has
explicitly authorised in the transcript) is what keeps the queue at zero.

**The rule that makes it safe.** A lane that measures a ruling to be wrong is
believed; the ruling is amended and cites the measurement. On the source build
this happened twice and the lane was right both times: once a ruling named a
relation that, read literally, would have refused every ordinary case. A
delegation without this rule produces confident nonsense that lanes then
implement.
