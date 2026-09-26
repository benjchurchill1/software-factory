#!/usr/bin/env bash
# Per-lane databases: every parallel builder gets a migrated, empty database of
# its own, so it proves its integration tests BEFORE the barrier.
#
# WHY. Under a shared-singleton law, integration tests first execute at the
# merge barrier. Measured on one build: the first barrier attempt was red and
# the second green at four consecutive waves, each costing a full extra check.
#
# WHY A SEPARATE CLUSTER. Roles are cluster-global, so a partial replay into a
# second database on the SHARED cluster mutates the shared one. Its own
# container, its own port.
#
#   bash scripts/lane-db.sh up | clone <lane> | exec <lane> -- <cmd> | stop <lane> | drop <lane> | status | down
#
# WHAT STAYS AT THE BARRIER, named in the conventions doc: (a) tests that talk
# to the shared service over HTTP; (b) tests that build an expensive fixture.
#
# WHY `exec` OWNS A PROCESS GROUP AND `stop` EXISTS. A `pkill -f` against a lane
# run once matched the parent, killed it, and left the test child at PPID 1 —
# still connected — which then reconnected to a re-created lane database and
# ran beside the next run. So `exec` runs the command in its own process group,
# records the group in a run file, refuses a second run while one is live, and
# `stop` ends exactly that group (TERM, then KILL) and any tagged backend it
# left behind.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${LANE_CONTAINER:-<PROJECT>-lane-cluster}"
IMAGE="${LANE_IMAGE:-<SAME_IMAGE_TAG_AS_THE_SHARED_SERVICE>}"
PORT="<LANE_PORT>"          # one port, not overridable: the test runner's guard hardcodes it
TEMPLATE="<PROJECT>_template"
META="<PROJECT>_lane_meta"
RUN_DIR="${TMPDIR:-/tmp}/<PROJECT>-lane-db/$CONTAINER"

die() { echo "$*" >&2; exit 1; }
# Same injective identifier in lane-cut, database names and run-file paths.
validate_lane() { [[ "${1:-}" =~ ^[a-z][a-z0-9_]{0,47}$ ]] && [ "$1" != status ] || die "invalid lane: use [a-z][a-z0-9_]{0,47}, except status"; }
fingerprint() { cat $(ls "$ROOT"/<MIGRATIONS_GLOB> | sort) | shasum -a 256 | cut -c1-16; }
apply_migration() {  # one migration is one change or none
  <APPLY_ONE_MIGRATION_SINGLE_TRANSACTION>
}

cmd_up() {
  if lsof -ti ":$PORT" >/dev/null 2>&1 && ! docker ps --filter "name=$CONTAINER" --format '{{.Names}}' | grep -q .; then
    die "port $PORT is held by something that is not our container"
  fi
  if ! docker ps --filter "name=$CONTAINER" --format '{{.Names}}' | grep -q .; then
    docker run -d --name "$CONTAINER" -p "$PORT:<SERVICE_PORT>" <RUNTIME_ENV_FLAGS> "$IMAGE" >/dev/null
    printf 'waiting'; for _ in $(seq 1 60); do <READY_PROBE> >/dev/null 2>&1 && break; printf '.'; sleep 1; done; echo
  fi
  want="$(fingerprint)"; have="$(<QUERY_TEMPLATE_COMMENT> 2>/dev/null || true)"
  if [ "$have" = "lane-template $want" ]; then echo "$TEMPLATE already matches the migration chain ($want); nothing to do"; return 0; fi
  live="$(<LIST_LANE_DBS_WITH_CONNECTIONS> || true)"
  [ -z "$live" ] || die "lane databases in use, cannot rebuild the template: $live"

  # THE BASELINE a bare container lacks and the shared service has: default
  # privileges, schemas, extensions. Measure against the shared service.
  <BASELINE_STATEMENTS>

  echo "replaying $(ls "$ROOT"/<MIGRATIONS_GLOB> | wc -l | tr -d ' ') migrations..."; t0=$(date +%s)
  for m in $(ls "$ROOT"/<MIGRATIONS_GLOB> | sort); do
    apply_migration "$m" || die "replay stopped at $(basename "$m")"
    # <BUILD_STEP_MID_CHAIN: any step the chain needs between two migrations —
    #  derive its position from the migrations' own text, never hardcode it>
  done
  echo "replayed in $(( $(date +%s) - t0 ))s"
  <CONFORMANCE_CHECK> || die "replayed database is not conformant; template not built"
  <SNAPSHOT_TO_TEMPLATE>; <SET_TEMPLATE_COMMENT>; <RECORD_MANIFEST>
  echo "template $TEMPLATE built, fingerprint $want"
}

cmd_clone() {
  lane="$1"
  <CREATE_DB_FROM_TEMPLATE>
  for m in $(<PENDING_MIGRATIONS_VS_MANIFEST>); do echo "  + $(basename "$m")"; apply_migration "$m"; done
  echo "export DATABASE_URL=<LANE_URL>"; echo "export LANE_DB=lane_$lane"
}

leader_identity() {
  # lstart is stable across invocations; also require that this PID leads its group.
  local pid="$1" group started
  group=$(LC_ALL=C ps -p "$pid" -o pgid=) || return 1
  group=$(printf '%s' "$group" | tr -d '[:space:]')
  [ "$group" = "$pid" ] || return 1
  started=$(LC_ALL=C ps -p "$pid" -o lstart=) || return 1
  started=$(printf '%s' "$started" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  [ -n "$started" ] || return 1
  printf '%s' "$started"
}

live_pgid() {
  local f="$1" pgid recorded current; [ -f "$f" ] || return 0
  pgid="$(sed -n 's/^pgid=//p' "$f" | head -1)"
  recorded="$(sed -n 's/^leader_started=//p' "$f" | head -1)"
  [[ "$pgid" =~ ^[1-9][0-9]*$ ]] && [ -n "$recorded" ] || {
    echo "REFUSE: missing process identity; retaining $f" >&2; return 1;
  }
  current=$(leader_identity "$pgid") && [ "$current" = "$recorded" ] || {
    echo "REFUSE: unknown or mismatched process identity (leader may be gone); retaining $f" >&2; return 1;
  }
  printf '%s' "$pgid"
}

signal_owned() {
  local owned
  owned=$(live_pgid "$1") || return 1
  [ -n "$owned" ] || return 1
  kill "-$2" -- "-$owned"
}

cmd_exec() {
  lane="$1"; shift 2
  mkdir -p "$RUN_DIR"; run_file="$RUN_DIR/$lane.run"
  live="$(live_pgid "$run_file")"
  [ -z "$live" ] || die "a run is already live on lane_$lane (process group $live). Stop it first: lane-db.sh stop $lane"
  <DB_EXISTS_OR_CLONE>
  echo "exec in lane_$lane: $*"
  set -m
  DATABASE_URL="<LANE_URL>" LANE_DB="lane_$lane" "$@" < /dev/null &
  child=$!; set +m
  identity=$(leader_identity "$child") || identity=""
  printf 'pgid=%s\nleader_started=%s\nstarted=%s\ncmd=%s\n' "$child" "$identity" "$(date -u +%FT%TZ)" "$*" > "$run_file"
  trap 'signal_owned "$run_file" TERM || true' INT TERM HUP
  rc=0; wait "$child" || rc=$?
  if kill -0 -- "-$child" 2>/dev/null; then
    echo "process group $child still alive or identity unknown; retaining $run_file; inspect before stop" >&2
    [ "$rc" -ne 0 ] || rc=1
  else
    rm -f "$run_file"
  fi
  exit "$rc"
}

cmd_stop() {
  lane="$1"; run_file="$RUN_DIR/$lane.run"
  pgid="$(live_pgid "$run_file")"
  if [ -n "$pgid" ]; then
    echo "stopping process group $pgid on lane_$lane"; signal_owned "$run_file" TERM || die "stop refused; retaining $run_file"
    for _ in $(seq 1 10); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 1; done
    if kill -0 -- "-$pgid" 2>/dev/null; then
      echo "  still alive; revalidate before SIGKILL"
      signal_owned "$run_file" KILL || die "stop refused; retaining $run_file"
      sleep 1
    fi
    kill -0 -- "-$pgid" 2>/dev/null && die "process group $pgid is STILL alive"
    rm -f "$run_file"; echo "  gone"
  else echo "no live run recorded for lane_$lane"; fi
  # A backend whose tag names a process that is gone is a suite that outlived
  # its parent and still holds locks. End it by name.
  <TERMINATE_TAGGED_BACKENDS_ON_LANE_DB>
}

cmd_drop()   { lane="$1"; cmd_stop "$lane"; <TERMINATE_CONNECTIONS>; <DROP_DB>; echo "dropped lane_$lane"; }
cmd_status() { docker ps --filter "name=$CONTAINER" --format '{{.Names}} {{.Status}}'; <LIST_LANE_DBS_WITH_SIZES>; ls "$RUN_DIR" 2>/dev/null | sed 's/^/  live run: /' || true; }
cmd_down()   { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$RUN_DIR"; echo "removed $CONTAINER"; }

case "${1:-}" in
  clone|stop|drop) [ $# -eq 2 ] || die "expected command and lane"; validate_lane "$2" ;;
  exec) [ $# -ge 4 ] && [ "$3" = -- ] || die "usage: exec <lane> -- <cmd>"; validate_lane "$2" ;;
  up|status|down) [ $# -eq 1 ] || die "unexpected arguments" ;;
  *) die "usage: up | clone | exec | stop | drop | status | down" ;;
esac
case "$1" in
  up) cmd_up ;; clone) shift; cmd_clone "$@" ;; exec) shift; cmd_exec "$@" ;;
  stop) shift; cmd_stop "$@" ;; drop) shift; cmd_drop "$@" ;; status) cmd_status ;; down) cmd_down ;;
  *) die "unknown command: $1" ;;
esac

# THE TEST RUNNER'S HALF: a `lane` mode that REFUSES unless LANE_DB is set and
# the connection names this port, and that excludes the two barrier-only
# classes by a predicate measured on this repository — a naive transitive
# import scan over shared helpers collapsed one selection from 308 files to 24.
