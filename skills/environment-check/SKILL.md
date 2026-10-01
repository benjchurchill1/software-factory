---
name: environment-check
description: Before an autonomous build starts, list everything it needs from the outside world (secrets, CLIs, network hosts, hosted database and migrations, deploy target, logins, machine size, the owner's standing decisions) and prove each one works from the session the build will run in, so nothing is found missing mid-build. Produces an environment manifest, a standing-decisions file, one list of owner actions, and a READY or BLOCKED report. Use when priming a build reaches the environment, before starting a build seat, when someone asks "is everything set up for the build?", or when a running build hits a missing token, a blocked host, a migration it cannot apply or a login nobody created. Not for the machine's memory and sleep or the permission allowlist (software-factory), the loop prompt (build-loop) or watching a build (build-monitor).
---

# Environment check

A build loop only finds out what its environment lacks when a wave needs it,
and by then the fix needs the owner at a computer, a fresh session, and a wave
to redo. This skill moves every one of those discoveries to before wave 0.

**[references/evidence.md](references/evidence.md)** records what each check
cost when it was missing on the Keystone build: 23 of 26 migrations that could
not reach the hosted database, a token saved under a misspelt name, logins
nobody had made, a machine that lost its worker three times, and approvals the
build seat rightly refused because they were relayed. Read it when someone
wants to start first and fix the environment later.

`software-factory` runs this at step 8, before `build-loop`. It can also run on
its own, on a build already in flight.

## What gets written

| File | From | Purpose |
| --- | --- | --- |
| `docs/build/environment.json` | `assets/environment.template.json` | what the build needs from the world, and how each need is proved |
| `docs/build/standing-decisions.md` | `assets/standing-decisions.template.md` | the owner's standing word, recorded before the build seat starts |
| `docs/build/environment-check.md` | written by the script | the latest READY or BLOCKED report |

The script is `scripts/env-check.py` in this skill (standard library only).
Copy it to `scripts/env-check.py` in the target repo so the loop can run it.

## Workflow

### 1. Find every outside dependency

Read the spec, the architecture, the register and the repo, and list every
system the build will **write** to, not just read: the hosted database, the
hosting platform, email, file storage, payment or identity providers, package
registries, the git remote. For each, settle:

- the **secret** that authorises the write, by its exact variable name;
- the **CLI** that performs it, and how it is installed in a fresh session;
- the **host** it talks to;
- a **probe**: one command that proves the secret works for that target, such
  as listing the target site or reading the migration history. A probe that
  only proves the CLI is installed proves nothing.

Ask only what the repo cannot answer. Write it into `environment.json`.

### 2. Make migrations travel with every deploy

When there is a hosted database, the deploy script applies migrations with the
database's own CLI, from a token in the environment, before it ships the app.
Fill the `migrations` section: the directory, the deploy script, the exact
apply command the script must contain, a probe that reads the hosted history,
and a dry run of the push.

**Never plan to apply migrations through a connector or MCP tool.** On the
source build the session's safety checks refused every migration that drops or
replaces a function, even with the owner's yes, and 23 of 26 never applied.

### 3. Plan the logins

Name every account someone will sign in with on the hosted environment, and
how it comes to exist: `seed` (fictional people the build creates, no real
password), `invite` (the app emails the owner), or `owner-creates`. **Claude
never invents a password for a real person**, so anything other than `seed` is
the owner's action, and it goes on their list now rather than being found when
they first open the site.

### 4. Record the standing decisions

Fill `standing-decisions.md` with the owner's own words, dated: the budget and
per-wave limit, the time limit, push after green, the deploy branch, deploy on
green, migrations on deploy, and what data the hosted environment may hold.
Commit it on the trunk.

A build seat will not act on an approval relayed from another session or a
tapped card, and it is right not to. Decisions made here, in the owner's words,
are ones it never has to ask for. A later change is typed by the owner in the
build seat's own session, then appended to the file.

### 5. Size the build to the machine

The script measures cores and memory and works out the lanes that can run at
once (by default two cores and 3 GB per lane) and whether review lenses must
run one after another (under eight cores). Put the planned lane count in
`concurrency.planned_lanes`; the check fails if the plan is wider than the
machine. Hand the result to `build-loop` as the wave shape.

### 6. Give the owner one list, once

Run the check (`--report docs/build/environment-check.md`). Every failing line
carries one sentence the owner can act on: which secret to add or rename, which
host to allow, which login to create, which decision to state. Send the owner
that list **in one message**, with where each setting lives:

- **Cloud builds**: secrets, network access and the setup script belong to the
  cloud environment (claude.ai/code, the environment's settings), not the
  project's settings. A running session never sees a change, so after the owner
  changes anything the check is rerun from a **fresh session on that
  environment**.
- **Local builds**: the shell profile the build seat starts from; restart the
  seat after a change.

Never ask for a secret's value in chat, and never write one to the repo, a
report or memory. The script prints names and presence only, and redacts any
value that appears in a probe's output.

### 7. Prove it from the build's own session

**Exit condition:** `env-check.py` exits 0, run from the session the build will
run in (for a cloud build, a fresh session on the build's environment), and the
report is committed. A pass from a different session or machine proves nothing
about the build's.

Then:

- `--dry-run` prints every check and runs none; use it to show the owner what
  will be checked.
- The loop prompt runs the check as its first step and on every resume
  (`build-loop`'s `<ENV_CHECK_COMMAND>`). Exit 1 stops the loop before any wave
  with an `environment-blocked` handoff listing the owner's actions.

Report each area as **ready**, **waived with a reason** (for example, no hosted
database), or **blocked on the owner**, with the action.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | ready |
| 1 | blocked; the report lists the owner's actions |
| 2 | the manifest is unreadable or still has a slot |

## When a running build hits the environment

Do not patch around it inside the loop (a second spelling of a variable, a
connector instead of the CLI, a password made up for a test login). Add the
missing need to the manifest, run the check, give the owner the one list, and
let the build seat resume from a fresh session once the check is green.
