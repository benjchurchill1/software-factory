#!/usr/bin/env bash
# deploy-<ENV>.sh <commit> — deploy one commit of this repo to <ENV>.
#
# WHY A SCRIPT AND NOT A COMMAND. Three failures this shape prevents, all
# measured on one build:
#   * THE WRONG TARGET. Two services existed; one was a live application on a
#     different lineage. The deploy CLI pushes to whichever service is LINKED,
#     and nothing but this guard stood between them.
#   * A DEPLOY THAT DID NOTHING. The script lived in a temp directory, a reboot
#     removed it, and the next "deploy" reported success having done nothing.
#     The discrepancy surfaced only because a second agent contradicted the
#     first. KEEP THIS FILE IN THE REPO, or in a durable state directory —
#     never in a scratch or temp path.
#   * A DEPLOY NOBODY VERIFIED. Reporting the platform's SUCCESS is not
#     evidence that the new code is being served. §4 checks the artefact.
#
# AUTHORITY. This is NOT on the permission allowlist. A person confirms each
# deploy. Where a person has given a standing instruction to deploy on green,
# the loop still reports each one with the platform's own deployment id.
set -euo pipefail

[ $# -eq 1 ] && [[ "$1" =~ ^[0-9a-fA-F]{7,40}$ ]] || { echo "usage: deploy-<ENV>.sh <commit hash>" >&2; exit 2; }
C="$1"
ROOT="<REPO_ROOT>"
URL="<ENV_URL>"
SERVICE="<TARGET_SERVICE_NAME>"
FORBIDDEN="<THE_SERVICE_THIS_MUST_NEVER_TOUCH>"
# A commit that must be an ancestor of anything deployable: the point after
# which the deployed lineage is correct. Prevents deploying a stale or
# divergent tree that happens to build.
FLOOR="<FLOOR_COMMIT>"

FULL=$(git -C "$ROOT" rev-parse --verify "$C^{commit}"); SHORT="${FULL:0:12}"
WT="<DURABLE_WORKTREE_DIR>/wt-$FULL"

# ---------------------------------------------------------------- 1. lineage
git -C "$ROOT" merge-base --is-ancestor "$FLOOR" "$FULL" \
  || { echo "REFUSE: $SHORT does not descend from $FLOOR"; exit 3; }
echo "commit $SHORT descends from the floor"

# ------------------------------------------------------------- 2. a clean tree
git -C "$ROOT" worktree prune
[ -d "$WT" ] || git -C "$ROOT" worktree add --detach "$WT" "$FULL" >/dev/null
cd "$WT"
assert_tree() {
  local tree_status
  tree_status=$(git status --porcelain --untracked-files=all) || { echo "REFUSE: cannot inspect worktree" >&2; exit 3; }
  [ "$(git rev-parse --show-toplevel)" = "$(pwd -P)" ] && \
  [ "$(git rev-parse HEAD)" = "$FULL" ] && \
  [ -z "$tree_status" ] || {
    echo "REFUSE: deploy worktree is dirty or does not match $FULL" >&2; exit 3;
  }
}
assert_tree
# The build must embed FULL as its immutable revision endpoint, not a static
# string shared by several builds. DEPLOY_COMMAND must build from this tree.
export FACTORY_DEPLOY_COMMIT="$FULL"
# Run the full local release check here, binding its evidence to FULL. A prior
# green result for another commit is not sufficient. Refuse before linking.
<VERIFY_COMMIT_COMMAND> || { echo "REFUSE: verification failed for $FULL" >&2; exit 3; }
assert_tree

# ------------------------------------------------------------------ 3. guard
<LINK_TARGET_COMMAND> >/dev/null 2>&1 || true
ok=$(<LIST_SERVICES_COMMAND> | grep -c "$SERVICE <LINKED_MARKER>" || true)
bad=$(<LIST_SERVICES_COMMAND> | grep -c "$FORBIDDEN <LINKED_MARKER>" || true)
if [ "$ok" != "1" ] || [ "$bad" != "0" ]; then
  echo "GUARD FAILED target_linked=$ok forbidden_linked=$bad — NOT deploying"; exit 4
fi
echo "GUARD OK: $SERVICE is linked, $FORBIDDEN is not"
assert_tree

# ----------------------------------------------------------------- 4. deploy
out=$(<DEPLOY_COMMAND> 2>&1); echo "$out"
id=$(echo "$out" | grep -oE '<DEPLOY_ID_PATTERN>' | head -1) || true
[ -n "$id" ] || { echo "no deployment id parsed"; exit 5; }
echo "DEPLOY_ID=$id"

st=""
for _ in $(seq 1 30); do
  st=$(<DEPLOYMENT_STATUS_COMMAND>)
  echo "$(date +%H:%M:%S) $id $st"
  case "$st" in <TERMINAL_STATUSES>) break ;; esac
  sleep 20
done
[ "$st" = "<SUCCESS_STATUS>" ] || { echo "DEPLOY_NOT_SUCCESS status=$st"; exit 6; }

# ----------------------------------------------------------------- 5. verify
# The platform saying SUCCESS is not evidence the new code is served. Fetch the
# immutable revision endpoint: its entire body must be FULL, embedded by the
# build from FACTORY_DEPLOY_COMMIT. A fixed probe string or shared asset hash
# cannot bind a response to the requested commit. HTTP status is asserted too.
sleep 15
assert_http() {
  local path="$1" expected="$2" actual
  actual=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "$URL$path")
  [ "$actual" = "$expected" ] || { echo "VERIFY FAIL: $path HTTP $actual expected $expected"; exit 7; }
}
assert_http '<ENTRY_PATH>' '<ENTRY_EXPECTED_HTTP>'
assert_http '<ARTEFACT_PATH>' '200'
served=$(curl --fail -sS --max-time 30 "$URL<ARTEFACT_PATH>")
[ "$served" = "$FULL" ] || { echo "VERIFY FAIL: served revision $served expected $FULL"; exit 7; }
assert_http '<PROTECTED_PATH>' '<PROTECTED_EXPECTED_HTTP>'
echo "VERIFY OK"
