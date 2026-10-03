# factory-live

A Claude Code mod (a plugin of function hooks) for the build seat. It covers
three things the Python hooks can't do from outside the session.

**Early access.** Function hooks are an early-access Claude Code API that "may
change between releases without notice". This mod was written and tested
against Claude Code 2.1.288. Everything it does has a fallback that the
factory already describes, so a build never depends on it.

## What it does

All of it is scoped to a repo that `hooks/arm.py` has armed, and it does
nothing anywhere else. It writes only its own files, in the arming's state
directory (`~/.claude/state/build-loop/<repo-key>/`), and never touches the
build seat's single-writer `journal.jsonl`.

| | |
| --- | --- |
| **Wakes a paused seat** | When pre-flight pauses on a usage window, the seat writes the arming's `pause` file and stops. Once the pause's `until` is a minute past, the mod submits a resume prompt into the seat. The prompt follows the loop's §Pausing on a usage limit: delete the pause file, close the `paused` phase, run pre-flight again, and carry on from the checkpoint. It wakes once per pause and at most 24 times per arming. It never wakes after the `stop` file, past the arming's 72 hours, or in any session other than the seat. This fills the loop's `<RESUME_MECHANISM>`. |
| **Writes the windows** | On every measurement it writes `usage-window.json` (each rate-limit window's percent used and reset time, plus the session's cost) and `usage-window`, one line: `<percent left of the tightest window> <its reset time>`. |
| **Records the seat's turns** | Every turn of the seat goes into `turns.jsonl`, including its subagents' turns: duration, end reason, model, the four token counts, and the session's running cost in US dollars. It rotates to `turns.jsonl.1` at 2 MiB. |
| **Shows the state** | A band above the prompt: seat or watching, the keep-alive's counts (`held 3/60 · 41/500`), the pause and when it wakes, the tightest window, and the cost. `/factory` prints the same with the file paths. |

### Which session is the seat

It is the session whose prompt carried the arming's marker, the nonce you
paste to start the build seat, as the keep-alive hook requires. The mod
records that session in `seat.json` when the prompt is submitted, or when a
resumed session is found to hold it. A session in the arming's `--exclude`
list (the monitor) is never the seat.

## Install

```
/plugin install factory-live@software-factory
```

For a build, enable it for the project rather than everywhere. The factory's
gate 11 drafts the entry
(`skills/software-factory/assets/settings.factory-live.template.json`), and the
owner merges it into the project's gitignored settings file next to the
allowlist:

```json
"enabledPlugins": { "factory-live@software-factory": true }
```

Otherwise it has to load in the session the build seat runs in: an installed plugin, or
`claude --plugin-dir <this folder>` (or `CLAUDE_CODE_PLUGIN_DIRS` where no flag
can be given). Start the seat and run `/factory`. It should say
`this session  the build seat`.

## Wiring it into a build

- **`<RESUME_MECHANISM>`**: "factory-live wakes the seat a minute after the
  pause file's `until`". Test it once before the first wave, as the rig doc
  asks. Write a pause file with an `until` two minutes ahead, end the seat's
  turn, and watch for the resume prompt.
- **`<USAGE_WINDOW_COMMAND>`**: `cat "<state dir>/usage-window"`, but **only if
  the run's spend figures are in percent of the window**. `guards.py pace`
  compares what is left with the next step's estimate in the usage events'
  unit, so a percentage only means something against estimates also kept in
  percent. Otherwise leave the command empty. The loop still pauses on a
  refused request's reset time, and the monitor can read `usage-window.json`.
- **Spend**: `turns.jsonl` is a usage source the loop can cite in its `usage`
  events (`"source": "factory-live turns.jsonl"`), in place of an estimate.

## Checking it

```
claude plugin validate mods/factory-live
claude plugin test mods/factory-live
```

The tests run the module against the engine, with an in-memory filesystem and
a mocked clock. They cover:
- waking once a minute after the reset, and again for a later pause
- never waking a session that isn't the seat, a released seat, or a stale arming
- the marker claiming the seat, and the excluded monitor not claiming it
- the window line pre-flight reads
- the turn ledger
- the band on the terminal and desktop surfaces

## What has not been shown

The tests cover the module, not a real build. It has not yet woken a real
seat after a real usage limit. Nor has it been run in a cloud session, where
whether a plugin's timers keep running while the session sits idle depends on
the host keeping the session alive.
