#!/usr/bin/env bash
# One command provisions a lane: its worktree cut from the trunk's CURRENT tip,
# the dependency links the tree needs, the proof that it is the right tree, the
# identifier range the lane may write in, and a copy of the range ledger inside
# the lane so its own checks can read it.
#
#   bash scripts/lane-cut.sh <lane> [--range-start <RANGE_START>]
#   bash scripts/lane-cut.sh --dry-run <lane>       # print it all, run none
#   bash scripts/lane-cut.sh status                 # cut lanes and ranges
#
# WHY ONE SCRIPT AND NOT TWO CONVENTIONS. The source build had both conventions
# written down: prove your base; take your migration number from the brief:
# and both recurred: 119 of 188 worktrees cut at a commit from a DIFFERENT
# PROJECT (twelve of twelve lanes in one wave affected), and four of eleven
# lanes choosing the same migration number in one wave, then two pairs again
# the next. The ruling: a lane does not cut its own worktree or choose its own
# number; the orchestrator provisions both, in one step, because the instant a
# lane comes into existence is the only instant at which both facts are known
# and cheap.
#
# THE TRUNK IS NOT IN THIS FILE. It is in scripts/lane-cut.conf (TRUNK_BRANCH,
# WAVE, LANE_ROOT), which the orchestrator moves each wave. A script naming one
# trunk in its own source is the original defect with a longer fuse. With no
# conf and no --trunk/--wave, this REFUSES rather than defaulting.
#
# IDEMPOTENT PER LANE: a lane that already holds a range keeps it; an existing
# tree on the right branch is re-proved, not re-cut.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/scripts/lane-cut.conf"
DRY=0; LANE=""; RANGE_START=""; TRUNK=""; WAVE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --range-start) RANGE_START="${2:?}"; shift ;;
    --trunk) TRUNK="${2:?}"; shift ;;
    --wave) WAVE="${2:?}"; shift ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) [ -z "$LANE" ] || { echo "expected one lane" >&2; exit 2; }; LANE="$1" ;;
  esac; shift
done
[ -f "$CONF" ] && . "$CONF"
TRUNK="${TRUNK:-${TRUNK_BRANCH:-}}"; WAVE="${WAVE:-${WAVE:-}}"
LANE_ROOT="${LANE_ROOT:-<LANE_ROOT_DEFAULT>}"
[ -n "$TRUNK" ] && [ -n "$WAVE" ] || { echo "REFUSE: no trunk/wave: write scripts/lane-cut.conf or pass --trunk and --wave" >&2; exit 2; }
[[ "$WAVE" =~ ^[1-9][0-9]*$ ]] || { echo "invalid wave" >&2; exit 2; }
[[ "$LANE" =~ ^[a-z][a-z0-9_]{0,47}$ ]] || { echo "invalid lane: use [a-z][a-z0-9_]{0,47}" >&2; exit 2; }
[ -z "$RANGE_START" ] || [[ "$RANGE_START" =~ ^[1-9][0-9]*$ ]] || { echo "invalid range start" >&2; exit 2; }

EVID="$ROOT/<EVIDENCE_DIR>/wave$WAVE"
LEDGER="$EVID/lane-ranges.json"
do_() { if [ "$DRY" -eq 1 ]; then printf '  would run:'; printf ' %q' "$@"; printf '\n'; else "$@"; fi; }

if [ "$LANE" = "status" ]; then
  [ -f "$LEDGER" ] && cat "$LEDGER" || echo "no lanes cut for wave $WAVE"
  git -C "$ROOT" worktree list | grep "w$WAVE/" || true
  exit 0
fi
[ -n "$LANE" ] || { echo "usage: lane-cut.sh <lane> | status" >&2; exit 2; }

BRANCH="w$WAVE/$LANE"; WT="$LANE_ROOT/wave$WAVE/$LANE"
TIP="$(git -C "$ROOT" rev-parse "$TRUNK")"
echo "lane $LANE · trunk $TRUNK @ ${TIP:0:8} · wave $WAVE"

# ---------------------------------------------------------------- 1. cut
if [ -d "$WT" ]; then
  echo "tree exists; re-proving rather than re-cutting"
  [ "$(git -C "$WT" branch --show-current)" = "$BRANCH" ] || { echo "wrong lane branch" >&2; exit 1; }
else
  do_ git -C "$ROOT" worktree add -b "$BRANCH" "$WT" "$TIP"
fi

# ------------------------------------------------------- 2. dependency links
# The links or installs a fresh tree needs: e.g. node_modules symlinks per
# workspace package, a vendored toolchain. Never a network install per lane.
for d in <DEPENDENCY_LINK_DIRS>; do
  do_ ln -sfn "$ROOT/$d/node_modules" "$WT/$d/node_modules"
done

# --------------------------------------------------------------- 3. base proof
# Any failure here is fatal. Order matters: ancestry first (the cheap, decisive
# test), then presence, then the two that need the links to be right.
do_ mkdir -p "$EVID/lane-cut"
PROOF="$EVID/lane-cut/$LANE-base-proof.log"
if [ "$DRY" -eq 1 ]; then
  printf '%s\n' "would prove ancestry of $TIP and expected directories at $WT" \
    'would run <TYPECHECK_COMMAND> and <HARNESS_LOADS_COMMAND>' \
    'would allocate range using <NEXT_FREE_RANGE_COMMAND> and <RANGE_END_COMMAND>' \
    "would append range to $LEDGER and copy it to $WT/<EVIDENCE_DIR>/wave$WAVE/lane-ranges.json"
  exit 0
fi
{
  echo "== base proof $LANE $(date -u +%FT%TZ) =="
  if [ "$DRY" -eq 0 ]; then
    git -C "$WT" merge-base --is-ancestor "$TIP" HEAD && echo "ancestry OK" || { echo "ANCESTRY FAILED: $TIP is not an ancestor of the new tree"; exit 1; }
    for d in <EXPECTED_DIRS>; do [ -d "$WT/$d" ] && echo "present $d" || { echo "MISSING $d: wrong tree"; exit 1; }; done
    (cd "$WT" && <TYPECHECK_COMMAND>) && echo "typecheck OK" || { echo "TYPECHECK FAILED: a broken install, most likely"; exit 1; }
    (cd "$WT" && <HARNESS_LOADS_COMMAND>) && echo "harness loads" || { echo "HARNESS DID NOT LOAD"; exit 1; }
  else
    echo "(dry run: proof not executed)"
  fi
} | tee "$PROOF"

# ------------------------------------------------------ 4. identifier range
# How this project allocates ranges: migration numbers, escalation ids, port
# blocks. The ledger is the single source; a lane's own check refuses a file
# outside its range.
if [ -f "$LEDGER" ] && grep -q "\"lane\": *\"$LANE\"" "$LEDGER"; then
  echo "range already allocated for $LANE (idempotent)"
else
  START="${RANGE_START:-$(<NEXT_FREE_RANGE_COMMAND>)}"
  END="$(<RANGE_END_COMMAND>)"
  entry="{\"lane\":\"$LANE\",\"range\":[\"$START\",\"$END\"],\"cut\":\"${TIP:0:8}\",\"at\":\"$(date -u +%FT%TZ)\"}"
  if [ "$DRY" -eq 1 ]; then echo "  would append to $LEDGER: $entry"; else
    mkdir -p "$EVID"; [ -f "$LEDGER" ] || echo "[]" > "$LEDGER"
    python3 - "$LEDGER" "$entry" <<'EOF'
import json,sys; p,e=sys.argv[1],json.loads(sys.argv[2]); d=json.load(open(p)); d.append(e); json.dump(d,open(p,"w"),indent=2)
EOF
    echo "range $START..$END -> $LEDGER"
  fi
fi

# ---------------------------------------- 5. the ledger, readable in the lane
# Copied, UNCOMMITTED: the orchestrator's ledger arrives by the orchestrator's
# commit; a lane committing a partial copy of the same path is a conflict at
# the merge.
do_ mkdir -p "$WT/<EVIDENCE_DIR>/wave$WAVE"
do_ cp "$LEDGER" "$WT/<EVIDENCE_DIR>/wave$WAVE/lane-ranges.json"
echo "lane $LANE provisioned at $WT"
