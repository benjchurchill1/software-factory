#!/usr/bin/env bash
# What must be true before the loop starts a wave or a barrier, as ONE command.
#
#   bash scripts/preflight.sh --queue <next queue file>   # at wave open, before any cut
#   bash scripts/preflight.sh --barrier                   # before every barrier attempt
#   bash scripts/preflight.sh --ack-reboot ...            # after recovery ran for a reboot
#   bash scripts/preflight.sh --dry-run                   # print it all, run none
#
# WHY. An unattended build meets four things no lane can fix: a login that
# expires, a usage window that runs out, a disk that fills and a host that
# reboots. The first needs a person, so the build must see it coming and stop at
# a clean point, never in the middle of a barrier. The second fixes itself when
# the window resets, so the build pauses rather than stops. The last two turn
# into timeouts and missing files that read like product regressions. Checking
# them costs seconds; finding them from a red barrier costs a wave.
#
# WHAT IT RUNS, in order, one line each:
#   1. config:   no unreplaced slot in the generated files the loop reads.
#   2. disk:     at least <DISK_FREE_GB> GB free on every path in DISK_PATHS.
#   3. boot:     the host has not rebooted since the last pre-flight.
#   4. reboot:   no reboot is pending (WARN only: it goes on the owner's list).
#   5. auth:     the login outlives the step about to start, plus the reserve.
#   6. usage:    the usage window and the total budget can fund the step
#                (guards.py pace, from the journal's usage events).
#   7. together: the queue holds no pair from the never-together ledger
#                (wave open only).
#
# EXIT: 0 go · 1 FAIL (fix it, then run again) · 10 PAUSE (prints resume_at)
#       20 STOP (a person is needed: login, budget) · 30 RECOVER (run the
#       recovery protocol, then --ack-reboot). When several fire, the order of
#       precedence is STOP, RECOVER, FAIL, PAUSE. Nothing launches on non-zero.
#
# READ-ONLY except one file: the boot id in the run-state directory, written the
# first time and on --ack-reboot.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/scripts/lane-cut.conf"
GUARDS="$ROOT/scripts/guards.py"
DRY=0; MODE=wave; QUEUE=""; ACK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --barrier) MODE=barrier ;;
    --queue) QUEUE="${2:?}"; shift ;;
    --ack-reboot) ACK=1 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac; shift
done
[ -f "$CONF" ] && . "$CONF"
WAVE="${WAVE:-}"
STATE="<RUN_STATE_DIR>"
case "$STATE" in /*) ;; *) STATE="$ROOT/$STATE" ;; esac
JOURNAL="$STATE/journal.jsonl"
GENERATED_FILES=(<GENERATED_FILES>)
DISK_PATHS=(<DISK_PATHS>)
TOGETHER="<NEVER_TOGETHER_PATH>"
if [ "$MODE" = barrier ]; then NEED_MIN=$(( <BARRIER_MAX_MINUTES> + <HANDOFF_RESERVE_MINUTES> ))
else NEED_MIN=$(( <WAVE_TIME_LIMIT_MINUTES> + <HANDOFF_RESERVE_MINUTES> )); fi
[[ "$WAVE" =~ ^[1-9][0-9]*$ ]] || { echo "REFUSE: no wave: write scripts/lane-cut.conf" >&2; exit 2; }
[ "$MODE" = barrier ] || [ -n "$QUEUE" ] || [ "$DRY" -eq 1 ] || { echo "REFUSE: at wave open pass --queue <file>" >&2; exit 2; }

if [ "$DRY" -eq 1 ]; then
  printf '%s\n' "would grep ${#GENERATED_FILES[@]} generated files for unreplaced slots" \
    "would check <DISK_FREE_GB> GB free on: ${DISK_PATHS[*]}" \
    "would compare <BOOT_ID_COMMAND> with $STATE/boot-id" \
    'would run <REBOOT_PENDING_COMMAND>' \
    "would run <AUTH_CHECK_COMMAND> and need $NEED_MIN min ($MODE)" \
    "would run <USAGE_WINDOW_COMMAND> and guards.py pace --mode $MODE on $JOURNAL" \
    "would run guards.py together $TOGETHER --queue ${QUEUE:-(barrier: skipped)}"
  exit 0
fi
cd "$ROOT" || exit 1
STOPPED=0; RECOVER=0; FAILED=0; PAUSED=0
line() {  # line <verdict> <text>
  echo "$1 $2"
  case "$1" in STOP) STOPPED=1 ;; RECOVER) RECOVER=1 ;; FAIL) FAILED=1 ;; PAUSE) PAUSED=1 ;; esac
}
guard() {  # run guards.py, print its verdict line, keep its resume_at
  local out rc; out="$(python3 "$GUARDS" --root "$ROOT" "$@" 2>/dev/null)"; rc=$?
  [ -n "$out" ] || { line FAIL "$1: guards.py printed nothing (exit $rc)"; return; }
  printf '%s\n' "$out" | while IFS= read -r l; do echo "$l"; done
  case "$rc" in 0) ;; 1) FAILED=1 ;; 10) PAUSED=1 ;; 20) STOPPED=1 ;; *) FAILED=1 ;; esac
}

# ---------------------------------------------------------------- 1. config
SLOT_RE='<[A-Z][A-Z0-9_]*(:[^>]*)?>'
left=""; missing=""
for f in "${GENERATED_FILES[@]}"; do
  [ -f "$f" ] || { missing="$missing $f"; continue; }
  hits="$(grep -cE "$SLOT_RE" "$f")"; [ "${hits:-0}" -eq 0 ] || left="$left $f($hits)"
done
if [ -n "$missing$left" ]; then
  line FAIL "config:${missing:+ missing$missing}${left:+ unreplaced slots in$left}"
else line PASS "config: ${#GENERATED_FILES[@]} generated files, no slot left"; fi

# ------------------------------------------------------------------ 2. disk
low=""
for p in "${DISK_PATHS[@]}"; do
  kb="$(df -Pk "$p" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [ -z "$kb" ]; then low="$low $p(unreadable)"
  elif [ "$kb" -lt $(( <DISK_FREE_GB> * 1024 * 1024 )) ]; then low="$low $p($(( kb / 1024 / 1024 )) GB)"; fi
done
[ -z "$low" ] && line PASS "disk: <DISK_FREE_GB> GB free on ${#DISK_PATHS[@]} paths" || line FAIL "disk: low on$low"

# ------------------------------------------------------------------ 3. boot
boot="$(<BOOT_ID_COMMAND> 2>/dev/null | tr -d '[:space:]')"
mkdir -p "$STATE"
if [ -z "$boot" ]; then line FAIL "boot: no boot id; the reboot check cannot run"
elif [ ! -s "$STATE/boot-id" ]; then printf '%s\n' "$boot" > "$STATE/boot-id"; line PASS "boot: recorded $boot"
elif [ "$(cat "$STATE/boot-id")" = "$boot" ]; then line PASS "boot: no reboot since the last pre-flight"
elif [ "$ACK" -eq 1 ]; then printf '%s\n' "$boot" > "$STATE/boot-id"; line PASS "boot: reboot acknowledged"
else line RECOVER "boot: the host rebooted since the last pre-flight; run the recovery protocol, then --ack-reboot"; fi

# ---------------------------------------------------------------- 4. reboot
if ( <REBOOT_PENDING_COMMAND> ) >/dev/null 2>&1; then line WARN "reboot: a reboot is pending; put it on the owner's list"
else line PASS "reboot: none pending"; fi

# ------------------------------------------------------------------ 5. auth
secs="$(<AUTH_CHECK_COMMAND> 2>/dev/null | tr -d '[:space:]')"
guard auth --need-minutes "$NEED_MIN" --remaining-seconds "${secs:-unknown}" \
  --since "$STATE/auth-at" --lifetime-hours "<AUTH_LIFETIME_HOURS>"

# ----------------------------------------------------------------- 6. usage
read -r remaining resets <<<"$(<USAGE_WINDOW_COMMAND> 2>/dev/null)"
window=()
[[ "${remaining:-}" =~ ^[0-9]+([.][0-9]+)?$ ]] && window=(--remaining "$remaining" ${resets:+--resets-at "$resets"})
if [ "$MODE" = barrier ]; then EST=<BARRIER_SPEND_ESTIMATE>; else EST=<WAVE_SPEND_LIMIT_NUMBER>; fi
guard pace --journal "$JOURNAL" --wave "$WAVE" --mode "$MODE" --limit "<SPEND_LIMIT_NUMBER>" \
  --reserve "<HANDOFF_RESERVE_NUMBER>" --default-estimate "$EST" ${window[@]+"${window[@]}"}

# -------------------------------------------------------------- 7. together
[ "$MODE" = barrier ] || guard together "$TOGETHER" --queue "$QUEUE"

[ "$STOPPED" -eq 1 ] && exit 20
[ "$RECOVER" -eq 1 ] && exit 30
[ "$FAILED" -eq 1 ] && exit 1
[ "$PAUSED" -eq 1 ] && exit 10
exit 0
