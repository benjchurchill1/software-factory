#!/usr/bin/env bash
# Stop hook: keep an autonomous build-loop seat running. Does nothing until armed.
#
# WHY THIS EXISTS. The loop seat ends its turn after a wave or a barrier and
# nothing re-invokes it, so an autonomous run stops whenever the model decides
# it has said enough. OMC ships `persistent-mode.mjs` for this class of problem
# but it is not registered in the Stop hook and it only fires for OMC modes
# (ralph/ultrawork/...). This is the same idea, scoped to one repo, bounded, and
# disarmed by deleting one file.
#
# CONTRACT
#   armed        state/armed.json exists, is under MAX_AGE_H old, and names a
#                cwd prefix the stopping session is inside.
#   identified   only a session whose transcript contains `marker` (a nonce from
#                the loop's opening prompt), inside `cwd_prefix`, and not listed
#                in `exclude_sessions`, is held. No marker, no hold.
#   bounded      at most `max` consecutive blocks (default 60). The counter
#                resets whenever armed.json is re-armed (its mtime moves).
#   released     the seat (or a person) creates state/stop, or the count is
#                spent, or the file is deleted. A released stop is a real stop.
#
# The loop seat is told, in the block reason, to create `stop` when it stops on
# purpose — done, stalled, or waiting on a person. That keeps a deliberate halt
# distinguishable from drifting to a halt, which is the whole point.
set -euo pipefail

STATE_DIR="${HOME}/.claude/state/build-loop"
ARMED="${STATE_DIR}/armed.json"
STOPFILE="${STATE_DIR}/stop"
COUNT="${STATE_DIR}/count"
MAX_AGE_H=72

allow() { exit 0; }   # exit 0 with no stdout = the session stops normally

[ -f "$ARMED" ] || allow
[ -f "$STOPFILE" ] && allow

payload="$(cat || true)"

jqv() { printf '%s' "$payload" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(sys.argv[1],"") or "")' "$1" 2>/dev/null || true; }
cfg() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); v=d.get(sys.argv[2],""); print(v if not isinstance(v,list) else " ".join(map(str,v)))' "$ARMED" "$1" 2>/dev/null || true; }

session="$(jqv session_id)"
cwd="$(jqv cwd)"

# Stale arming is not arming. A machine left overnight must not wake up holding
# a seat open against a prompt nobody remembers writing.
if [ -n "$(find "$ARMED" -mmin +$((MAX_AGE_H * 60)) 2>/dev/null)" ]; then allow; fi

prefix="$(cfg cwd_prefix)"
[ -n "$prefix" ] || allow
case "${cwd%/}/" in "${prefix%/}/"*) : ;; *) allow ;; esac

read -r -a excluded_ids <<< "$(cfg exclude_sessions)" || true
for excluded in "${excluded_ids[@]:-}"; do
  [ -n "$excluded" ] && [ "$session" = "$excluded" ] && allow
done

# THE SEAT IDENTIFIES ITSELF. `marker` is a phrase the loop's own opening
# prompt contains, so only the session actually running the loop is held
# open — an ordinary chat in the same workspace is not, and there is no
# first-to-stop race to lose. No marker, no hold: an arming without one is
# refused. Use a unique nonce that appears only in the pasted opening prompt
# (not in the prompt FILE, which a monitor seat reads), and list the monitor's
# session id in exclude_sessions.
marker="$(cfg marker)"
[ -n "$marker" ] || allow
transcript="$(jqv transcript_path)"
[ -n "$transcript" ] && [ -f "$transcript" ] || allow
grep -qF -- "$marker" "$transcript" 2>/dev/null || allow

max="$(cfg max)"; [[ "$max" =~ ^[1-9][0-9]{0,3}$ ]] || max=60

# The counter belongs to this arming, not to all time.
if [ ! -f "$COUNT" ] || [ "$ARMED" -nt "$COUNT" ]; then echo 0 > "$COUNT"; fi
n=$(( $(cat "$COUNT" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$COUNT"

if [ "$n" -gt "$max" ]; then
  rm -f "$ARMED"
  cat <<EOF
{"decision":"block","reason":"BUILD-LOOP KEEP-ALIVE SPENT: $max consecutive continuations without a deliberate stop. The hook has disarmed itself so this cannot run away. Write one paragraph for the owner saying where the wave got to and what it needs, then stop."}
EOF
  exit 0
fi

cat <<EOF
{"decision":"block","reason":"BUILD-LOOP CONTINUATION ($n of $max). You are the autonomous build-loop seat and the run is not finished. Do not summarise and stop: pick the loop back up where it is. Re-read docs/prompts/build-loop.md if you have lost the thread, work out from git log and the scoreboard and wave records the loop prompt names which wave and which step you are on, and take the NEXT step of that step list — a lane, a barrier attempt, the record, or opening the next wave. If you are genuinely finished or genuinely blocked — the definition of done is met, §Stop conditions has fired, or a decision only the owner can take is in the way — then create ${STOPFILE} with one line saying which of those it is, and stop. That file is how a deliberate halt is told apart from drifting to a halt."}
EOF
