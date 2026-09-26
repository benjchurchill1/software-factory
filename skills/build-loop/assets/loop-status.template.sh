#!/usr/bin/env bash
# A read-only readout of what the build loop is doing right now.
#
# It exists because the answer to "why is this wave taking an hour" is usually
# not visible from anything the loop prints: a second run started against the
# shared <SINGLETON>, an interrupted lane left work running with nothing waiting
# on it, or the live run is queued behind something a killed run still holds.
#
#   bash <STATUS_SCRIPT_PATH>        # or: <STATUS_COMMAND>
#
# It reads and never writes: no migration, no reset, no terminate. Where it finds
# something worth killing it prints the command and leaves the decision with you.
# Safe to run at any point in a wave.
#
# See <CONVENTIONS_PATH> for what each warning means.

# NO `set -e`. This script's whole job is to report a broken machine, and a
# machine with the <SINGLETON> down must still get past that section to print the
# scoreboard.
set -uo pipefail

cd "$(dirname "$0")/.."

warn=0

echo "── runs ────────────────────────────────────────────────────────────"
checks=$(ps -Ao command | grep -cE '^<CHECK_COMMAND>$')
echo "  <CHECK_COMMAND>: ${checks}"
if [ "$checks" -gt 1 ]; then
  echo "  WARN  more than one full run is live. They do not share the wall-clock,"
  echo "        they build a convoy — see the conventions doc. Leave ONE."
  warn=1
fi

# An orphan is a run whose parent is gone (PPID 1). It keeps going, keeps its
# claim on the <SINGLETON>, and nothing is waiting on its exit code.
orphans=$(ps -Ao pid,ppid,command | awk '$2 == 1 && /<TEST_PROCESS_PATTERN>/ { print $1 }')
if [ -n "$orphans" ]; then
  echo "  WARN  orphaned runs (parent gone, still running):"
  for p in $orphans; do
    echo "        pid $p — $(ps -o etime=,pcpu= -p "$p" 2>/dev/null | tr -s ' ')"
  done
  echo "        kill $(echo "$orphans" | tr '\n' ' ')"
  echo "        …then re-run this script: killing these does NOT free their work."
  warn=1
fi

echo "── <SINGLETON> ─────────────────────────────────────────────────────"
if ! <SINGLETON_UP_CHECK>; then
  echo "  WARN  <SINGLETON> is not available — the shared suites cannot pass."
  warn=1
else
  # <CONTENTION_QUERY> must report how many operations are waiting and the
  # longest wait. Anything past a minute is a convoy rather than ordinary load.
  echo "  contention:      $(<CONTENTION_QUERY>)"

  # Print the queue when it is real: the head of it is the only entry that
  # explains the rest.
  chain=$(<CONTENTION_CHAIN_QUERY>)
  if [ -n "$chain" ]; then
    echo "  WARN  waiting longer than a minute — head of the queue first:"
    echo "$chain" | sed 's/^/        /'
    warn=1
  fi

  # Work tagged for a process that no longer exists is a corpse: the <SINGLETON>
  # does not notice a dead client while it is waiting.
  dead=$(<ORPHANED_WORK_QUERY>)
  if [ -n "$dead" ]; then
    echo "  WARN  work whose run is gone:$dead"
    echo "        <REAP_COMMAND>"
    warn=1
  fi
fi

echo "── repository ──────────────────────────────────────────────────────"
echo "  branch:          $(git rev-parse --abbrev-ref HEAD)"
echo "  last commit:     $(git log --oneline -1)"
dirty=$(git status --porcelain | wc -l | tr -d ' ')
echo "  uncommitted:     ${dirty} file(s)"
if [ "$dirty" -gt 0 ]; then
  echo "  note  a wave in flight will sweep these into its own commit. If they are"
  echo "        yours rather than the loop's, move them to a branch."
fi

echo "── scoreboard ──────────────────────────────────────────────────────"
progress=<PROGRESS_PATH>
if [ -f "$progress" ]; then
  echo "  $(grep -oE '<VERDICT_PATTERN>' "$progress" | sort | uniq -c | tr -s ' \n' ' ')"
  echo "  last log entry:  $(grep -oE '^\- \*\*[^*]+\*\*' "$progress" | tail -1 | sed 's/^- \*\*//;s/\*\*$//')"
else
  echo "  (no scoreboard yet — the loop has not run wave zero)"
fi

echo "── machine ─────────────────────────────────────────────────────────"
echo "  load:            $(uptime | sed 's/.*averages: //')  on $(getconf _NPROCESSORS_ONLN) cores"

echo
if [ "$warn" -eq 0 ]; then
  echo "Nothing to act on."
else
  echo "Warnings above. Nothing has been changed — every fix is yours to run."
fi
