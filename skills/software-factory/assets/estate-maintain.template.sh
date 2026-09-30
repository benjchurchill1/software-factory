#!/usr/bin/env bash
# The test estate's maintenance, as ONE named build step with its evidence file.
#
# WHY THIS EXISTS. A suite that mints data per test and never cleans up grows a
# shared database until the build's own performance gates fail on it. Measured
# on one build: 33 million permission rows across 34,559 test tenants, roughly a
# third of a million rows added per full check, six waves reddened by it.
#
# WHY IT IS A SCRIPT AND NOT A GRANT. A loop that can vacuum its own database
# whenever a number disappoints it is a loop that can make any performance gate
# green. This is one named duty, on the permission allowlist by name, appending
# to an evidence log: so `git log -p` on that log is the complete history of
# every time the estate was touched.
#
# WHEN IT RUNS. Once per barrier attempt, BEFORE the check, from the repo root.
# NEVER between a red cell and a re-run of that same cell.
#
# WHAT IT DOES NOT DO. It never passes the reaper's `--all`-class flag. It does
# not reindex. It does not reclaim disk (a DELETE returns space to the free-space
# map, not the OS): run it for row counts, never for bytes.
#
#   bash scripts/estate-maintain.sh [--dry-run] <evidence-dir> [--stale <hours>]
#
# Steps, each recorded in <evidence-dir>/estate-maintain.log:
#   1. Reap orphaned connections whose owning OS process is gone.
#   2. <REAPER_COMMAND>: the default keep rules only.
#   3. --stale <hours>: additionally reap test fixtures BELOW the reaper's floor
#      whose age exceeds the cutoff. Destructive; a shorter cutoff is a person's
#      call at the time, never a standing default.
#   4. <ANALYZE_COMMAND>.
#   5. Before/after census.
set -uo pipefail

EVID=""; STALE=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --stale)
      [ -z "$STALE" ] && [[ "${2:-}" =~ ^[1-9][0-9]*$ ]] || { echo "--stale requires positive integer hours, once" >&2; exit 2; }
      STALE="$2"; shift 2 ;;
    -*) echo "unknown argument: $1" >&2; exit 2 ;;
    *) [ -z "$EVID" ] && [ -n "$1" ] || { echo "expected one evidence directory" >&2; exit 2; }; EVID="$1"; shift ;;
  esac
done
[ -n "$EVID" ] || { echo "usage: estate-maintain.sh [--dry-run] <evidence-dir> [--stale <hours>]" >&2; exit 2; }
# Exit before queries, process discovery, signals, directory creation or logs.
# This is a static plan: even census commands are not run in dry-run mode.
if [ "$DRY" -eq 1 ]; then
  printf '%s\n' "would log before/after census to $EVID/estate-maintain.log" \
    'would terminate orphaned database connections (<TERMINATE_SQL_FOR_CONN>)' \
    'would send TERM to orphaned app servers (<APP_SERVER_PROCESS_PATTERN>)' \
    'would run <REAPER_COMMAND> (default keep rules)' \
    'would run <ANALYZE_COMMAND>'
  [ -z "$STALE" ] || printf '%s\n' "would run <REAPER_COMMAND> --stale $STALE"
  exit 0
fi
cd "$(dirname "$0")/.." || exit 1
mkdir -p "$EVID" || exit 1
LOG="$EVID/estate-maintain.log"

Q="<QUERY_RUNNER>"   # the read-only query runner for this project's database

say() { printf '%s\n' "$*" | tee -a "$LOG"; }
q() { $Q -c "$1" 2>&1; }
snapshot() {
  # the two or three counts that characterise this project's estate
  local first second size
  first=$(q '<COUNT_1_SQL>') || return 1
  second=$(q '<COUNT_2_SQL>') || return 1
  size=$(q '<SIZE_SQL>') || return 1
  echo "<ENTITY_1>=$first <ENTITY_2>=$second size=$size"
}

orphan_rc=0; census_rc=0
say "== estate-maintain $(date -u +%FT%TZ) · $(git rev-parse --short HEAD) · $(git branch --show-current) =="
before=$(snapshot) || census_rc=1
say "BEFORE $before"

# ---------------------------------------------------------------- 1. orphans
# A killed test run does NOT end its database work: the server notices a dead
# client only when it next writes to the socket, and a statement waiting on a
# lock never does. Reap by the application_name every connection carries, and
# LEAVE ALONE any whose OS process is still alive: that is a live run.
say "-- 1. orphaned connections --"
reaped=0; left=0
connections=$($Q -c "<ORPHAN_CENSUS_SQL>" 2>&1) || orphan_rc=1
while IFS='|' read -r conn app state age; do
  case "${conn:-}" in ''|*[!0-9]*) continue ;; esac
  ospid="${app#<APP_NAME_PREFIX>}"
  if [ -n "$ospid" ] && [ "$ospid" != "$app" ] && kill -0 "$ospid" 2>/dev/null; then
    say "   LEFT   $app ($state, age $age): OS process $ospid alive"
    left=$((left + 1))
  else
    if result=$(q "<TERMINATE_SQL_FOR_CONN>"); then
      say "   REAPED $app ($state, age $age): $result"
      reaped=$((reaped + 1))
    else
      orphan_rc=1; say "   FAILED to reap $app: $result"
    fi
  fi
done <<< "$connections"
say "   orphans: reaped=$reaped left=$left"

# ------------------------------------------------- 1b. orphaned app servers
# The barrier's app server and a test's own dev server outlive a killed run and
# hold gigabytes on the HOST (one measured at 4.4 GB; a single test's server at
# 3.4 GB). They were the largest single memory cost in the source build's
# record. Reap those whose parent is gone; leave a live run's alone.
# <APP_SERVER_PROCESS_PATTERN> MUST include the repo's absolute path or a run
# tag: on macOS every launchd-started app has ppid 1, so a bare `node` or `next`
# would TERM unrelated processes.
say "-- 1b. orphaned app servers (<APP_SERVER_PROCESS_PATTERN>) --"
processes=$(ps -Ao pid,ppid,rss,command) || orphan_rc=1
while read -r pid ppid rss cmd; do
  [ -n "${pid:-}" ] || continue
  if [ "$ppid" = "1" ] || ! kill -0 "$ppid" 2>/dev/null; then
    say "   REAPED pid=$pid rss=$((rss/1024))MB (parent gone): ${cmd:0:80}"; kill -TERM "$pid" 2>/dev/null || orphan_rc=1
  else
    say "   LEFT   pid=$pid rss=$((rss/1024))MB (parent $ppid alive): ${cmd:0:80}"
  fi
done < <(printf '%s\n' "$processes" | grep -E '<APP_SERVER_PROCESS_PATTERN>' | grep -v grep || true)

# ---------------------------------------------------------------- 2. reap
say "-- 2. <REAPER_COMMAND> (default keep rules; never the --all class) --"
t0=$(date +%s)
<REAPER_COMMAND> > "$EVID/reap.log" 2>&1
reap_rc=$?
say "   exit=$reap_rc in $(( $(date +%s) - t0 ))s -> $EVID/reap.log"

# ------------------------------------------------------- 3. stale (optional)
stale_rc=0
if [ -n "$STALE" ]; then
  say "-- 3. <REAPER_COMMAND> --stale $STALE (below the floor, older than the cutoff) --"
  t0=$(date +%s)
  <REAPER_COMMAND> --stale "$STALE" > "$EVID/reap-stale.log" 2>&1
  stale_rc=$?
  say "   exit=$stale_rc in $(( $(date +%s) - t0 ))s -> $EVID/reap-stale.log"
  grep -E '<REAPER_STALE_SUMMARY_PATTERN>' "$EVID/reap-stale.log" | tail -3 | sed 's/^/   /' | tee -a "$LOG"
fi

# ---------------------------------------------------------------- 4. analyze
say "-- 4. <ANALYZE_COMMAND> --"
t0=$(date +%s)
<ANALYZE_COMMAND> > "$EVID/analyze.log" 2>&1
an_rc=$?
say "   exit=$an_rc in $(( $(date +%s) - t0 ))s -> $EVID/analyze.log"

after=$(snapshot) || census_rc=1
say "AFTER  $after"
say "== done $(date -u +%FT%TZ) · reap=$reap_rc stale=$stale_rc analyze=$an_rc orphan=$orphan_rc census=$census_rc =="

[ "$reap_rc" -eq 0 ] && [ "$stale_rc" -eq 0 ] && [ "$an_rc" -eq 0 ] && [ "$orphan_rc" -eq 0 ] && [ "$census_rc" -eq 0 ]

# ---------------------------------------------------------------------------
# THE FLOOR, AND WHY IT MUST BE REPORTED RATHER THAN FORCED.
#
# Some rows a constraint will refuse to delete: an append-only ledger, an audit
# chain, a foreign key with no cascade. Measured on one build: 18,550 tenants
# survived the largest prune for exactly that reason, and that residue IS the
# estate's resting size.
#
# Report it. Do not add a flag that deletes around the constraint: the constraint
# is a product invariant and the reaper is a convenience. If the floor genuinely
# becomes load-bearing, the answer is a lane that removes the rows the way the
# PRODUCT would (a reversal, an archival), never a harness that overrides it.
# ---------------------------------------------------------------------------
