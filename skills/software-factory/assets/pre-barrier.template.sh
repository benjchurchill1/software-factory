#!/usr/bin/env bash
# The checks that run after the serial merge and BEFORE the barrier's full check,
# as ONE command with a one-line verdict per check.
#
#   bash scripts/pre-barrier.sh [--squashed <lane>]... [--trunk <b>] [--integration <b>]
#   bash scripts/pre-barrier.sh --dry-run              # print it all, run none
#
# WHY ONE SCRIPT AND NOT FIVE MEMORY NOTES. On the source build every check below
# was learnt from a red barrier or a leak, then written down as a note, and the
# notes were run by memory: a lane merged before its handback put a stale tree
# under the barrier (waves 94 and 96); a Playwright trace.zip holding a local test token
# reached origin (wave 111); JSON registries auto-merged into duplicates with no
# conflict marker (wave 87); UI lanes passed their panels and reddened the
# db-partition nav guards that lanes cannot run (barrier 111-1). A check skipped
# by not invoking it is not a check.
#
# WHAT IT RUNS, in order, each printed as PASS or FAIL:
#   1. head       — the working tree is the integration branch; the later checks
#                   run against the working tree, so on any other branch they
#                   mean nothing.
#   2. ancestry   — every lane branch matching <LANE_BRANCH_GLOB> is an ancestor
#                   of the integration branch. A MISSING is a stale merge: merge
#                   only after the lane's handback. A lane squash-merged on
#                   purpose (e.g. to leave a trace out) is declared with
#                   --squashed <lane> and printed as such, never silently skipped.
#   3. artefacts  — no trace.zip, *.har or .env* in any lane's diff against the
#                   trunk, nor in the integration branch's. A tracked .env.example
#                   is flagged too; a scan that whitelists is the next hole.
#   4. typecheck  — <TYPECHECK_COMMAND>; catches a keep-both conflict resolution
#                   that left an entry unclosed, on the NEXT entry.
#   5. registry   — <REGISTRY_DUP_CHECK>; every shared-registry entry appears
#                   exactly once.
#   6. shared     — <SHARED_ONLY_SUITES>; the suites lanes cannot run (guard
#                   tests on the shared resource's own partition), run here on the
#                   shared resource before the barrier launches.
#
# READ-ONLY except for running the named commands. It merges, resets and deletes
# nothing, and writes no file: the orchestrator tees its output into the wave's
# verification record.
#
# EVERY CHECK RUNS; the exit is non-zero if any failed, so one run names every
# failure (the estate-maintain shape, not lane-cut's stop-at-first).
#
# THE TRUNK AND WAVE COME FROM scripts/lane-cut.conf, as for lane-cut.sh. Fill
# <TRUNK_BRANCH> as "$TRUNK_BRANCH" and the other two in terms of $WAVE (e.g.
# "w$WAVE/integration", "w$WAVE/*"), so nothing here names a wave.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/scripts/lane-cut.conf"
DRY=0; TRUNK=""; INTEGRATION=""; SQUASHED=" "
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --trunk) TRUNK="${2:?}"; shift ;;
    --integration) INTEGRATION="${2:?}"; shift ;;
    --squashed) SQUASHED="$SQUASHED${2:?} "; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac; shift
done
[ -f "$CONF" ] && . "$CONF"
TRUNK="${TRUNK:-<TRUNK_BRANCH>}"
INTEGRATION="${INTEGRATION:-<INTEGRATION_BRANCH>}"
LANE_GLOB="<LANE_BRANCH_GLOB>"
[ -n "$TRUNK" ] && [ -n "$INTEGRATION" ] && [ -n "$LANE_GLOB" ] || { echo "REFUSE: no trunk/integration/lane glob — write scripts/lane-cut.conf or pass --trunk and --integration" >&2; exit 2; }
ARTEFACTS='(^|/)(trace\.zip|[^/]*\.har|\.env[^/]*)$'

if [ "$DRY" -eq 1 ]; then
  printf '%s\n' "would check HEAD is $INTEGRATION" \
    "would list lanes: git for-each-ref refs/heads/$LANE_GLOB (excluding $INTEGRATION)" \
    "would run per lane: git merge-base --is-ancestor <lane> $INTEGRATION (declared squashed:${SQUASHED% })" \
    "would scan per lane and $INTEGRATION: git diff --name-only $TRUNK...<branch> for $ARTEFACTS" \
    'would run <TYPECHECK_COMMAND>' \
    'would run <REGISTRY_DUP_CHECK>' \
    'would run <SHARED_ONLY_SUITES>'
  exit 0
fi
cd "$ROOT" || exit 1
FAILED=0
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; FAILED=1; }

# ------------------------------------------------------------------ 1. head
HEAD_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
[ "$HEAD_BRANCH" = "$INTEGRATION" ] && pass "head: $INTEGRATION" || fail "head: on '$HEAD_BRANCH', expected $INTEGRATION"

LANES=()
while IFS= read -r ref; do
  [ -n "$ref" ] && [ "$ref" != "$INTEGRATION" ] && LANES+=("$ref")
done < <(git for-each-ref --format='%(refname:short)' "refs/heads/$LANE_GLOB")

# -------------------------------------------------------------- 2. ancestry
if [ "${#LANES[@]}" -eq 0 ]; then
  fail "ancestry: no lane branch matches $LANE_GLOB"
else
  missing=""; declared=""
  for lane in "${LANES[@]}"; do
    case "$SQUASHED" in *" ${lane##*/} "*|*" $lane "*) declared="$declared $lane"; continue ;; esac
    git merge-base --is-ancestor "$lane" "$INTEGRATION" 2>/dev/null || missing="$missing $lane"
  done
  [ -z "$missing" ] && pass "ancestry: ${#LANES[@]} lanes${declared:+ (declared squashed:$declared)}" \
    || fail "ancestry: MISSING$missing"
fi

# ------------------------------------------------------------- 3. artefacts
found=""
for branch in ${LANES[@]+"${LANES[@]}"} "$INTEGRATION"; do
  names="$(git diff --name-only "$TRUNK...$branch")" || { found="$found $branch: (diff failed)"; continue; }
  hits="$(printf '%s\n' "$names" | grep -E "$ARTEFACTS" | tr '\n' ' ')"
  [ -z "$hits" ] || found="$found $branch: $hits"
done
[ -z "$found" ] && pass "artefacts: none in $(( ${#LANES[@]} + 1 )) diffs" || fail "artefacts:$found"

# -------------------------------------------------- 4-6. the named commands
# Their own output goes to stderr, so stdout stays one line per check.
( <TYPECHECK_COMMAND> ) 1>&2 && pass "typecheck" || fail "typecheck"
( <REGISTRY_DUP_CHECK> ) 1>&2 && pass "registry" || fail "registry"
( <SHARED_ONLY_SUITES> ) 1>&2 && pass "shared" || fail "shared"

exit "$FAILED"
