#!/usr/bin/env python3
"""Isolated rendered-template checks; no network, Docker or third-party modules.

Run: python3 skills/software-factory/scripts/verify-factory.py
Mocks log all external side effects. Recovery drills remain prompt-driven and
must additionally be executed for each instantiated factory (recovery.md).
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import json
import sys

SKILL = Path(__file__).resolve().parents[1]
LOOP = SKILL.parent / "build-loop"
HOOKS = SKILL.parents[1] / "hooks"
GUARDS = SKILL / "assets" / "guards.py"
FULL = "a" * 40
SLOT = re.compile(r"<[A-Z][A-Z0-9_]*(?::[^>]*|\s[^>]*)?>")


class ScriptFixture(unittest.TestCase):
    """Rendered templates in a temp dir, with every external command mocked."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        self.wt = self.root / ("wt-" + FULL)
        self.wt.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        CALLS=str(self.log), FIXTURE_WT=str(self.wt), TMPDIR=str(self.root))
        self.command("mock", 'printf "%s\\n" "$*" >> "$CALLS"\n')
        self.command("sleep", "exit 0\n")
        self.command("ps", "exit 0\n")
        self.command("git", '''
case "$*" in
  *status*) [ "${STATUS_FAIL:-0}" = 0 ] || exit 1; printf '%s' "${DIRTY:-}" ;;
  *--show-toplevel*) printf '%s\\n' "$FIXTURE_WT" ;;
  *"rev-parse HEAD"*) printf '%s\\n' "${HEAD_OVERRIDE:-''' + FULL + '''}" ;;
  *rev-parse*) printf '%s\\n' "''' + FULL + '''" ;;
  *merge-base*|*worktree*) exit 0 ;;
esac
''')
        self.command("curl", '''
case "$*" in
  *http_code*) printf '%s' "${HTTP_STATUS:-200}" ;;
  *) printf '%s' "${SERVED:-''' + FULL + '''}" ;;
esac
''')
        self.command("query", '''
printf 'query %s\\n' "$*" >> "$CALLS"
case "$*" in
  *"${QUERY_FAIL:-never-match}"*) exit 1 ;;
  *orphans*) printf '123|missing-process|idle|9\\n' ;;
  *) printf '1\\n' ;;
esac
''')

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)

    def render(self, name, values=None):
        source = (SKILL / "assets" / (name + ".template.sh")).read_text()
        values = values or {}
        source = SLOT.sub(lambda m: values.get(m.group()[1:-1], ":"), source)
        path = self.scripts / (name + ".sh")
        path.write_text(source)
        shutil.copy2(GUARDS, self.scripts / "guards.py")
        syntax = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        return path

    def run_script(self, path, *args, **env):
        return subprocess.run(["bash", str(path), *args], env=dict(self.env, **env),
                              capture_output=True, text=True, timeout=10)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def maintenance(self):
        return self.render("estate-maintain", {
            "QUERY_RUNNER": "query", "COUNT_1_SQL": "count1", "COUNT_2_SQL": "count2",
            "SIZE_SQL": "size", "ORPHAN_CENSUS_SQL": "orphans",
            "TERMINATE_SQL_FOR_CONN": "terminate", "REAPER_COMMAND": "mock reap",
            "ANALYZE_COMMAND": "mock analyze", "APP_SERVER_PROCESS_PATTERN": "fixture-server"})



class FactoryFixtures(ScriptFixture):
    def test_maintenance_dry_run_and_arguments(self):
        path = self.maintenance()
        evidence = str(self.root / "new-evidence")
        for args in [("--dry-run", evidence), (evidence, "--stale", "24", "--dry-run")]:
            result = self.run_script(path, *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("would send TERM", result.stdout)
        for args in [("--dry-run",), (evidence, "--stale", "0"),
                     (evidence, "--stale", "-1"), (evidence, "--wat"), (evidence, "extra")]:
            self.assertNotEqual(self.run_script(path, *args).returncode, 0)
        self.assertFalse(Path(evidence).exists())
        self.assertEqual(self.calls(), "")

    def test_maintenance_failure_propagation(self):
        path = self.maintenance()
        for failure in ["count1", "orphans", "terminate"]:
            result = self.run_script(path, str(self.root / "evidence"), QUERY_FAIL=failure)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("analyze", self.calls())

    def test_lane_names_and_dry_run(self):
        cut = self.render("lane-cut", {"LANE_ROOT_DEFAULT": str(self.root / "lanes"),
                                     "EVIDENCE_DIR": "evidence", "DEPENDENCY_LINK_DIRS": "packages",
                                     "NEXT_FREE_RANGE_COMMAND": "mock allocate"})
        db = self.render("lane-db", {"CREATE_DB_FROM_TEMPLATE": 'mock "clone lane_$lane"'})
        for name in ["a-b", "ab!", "A", "../ab", "a" * 49, ""]:
            self.assertNotEqual(self.run_script(cut, "--dry-run", name, "--trunk", "main", "--wave", "1").returncode, 0)
            self.assertNotEqual(self.run_script(db, "clone", name).returncode, 0)
        for name in ["ab", "a_b"]:
            result = self.run_script(cut, "--dry-run", name, "--trunk", "main", "--wave", "1")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), "")
        self.assertFalse((self.root / "evidence").exists())
        for name in ["ab", "a_b"]:
            self.assertEqual(self.run_script(db, "clone", name).returncode, 0)
            self.assertIn("clone lane_" + name, self.calls())

    def deploy(self, verify='mock "verify $FULL"', **overrides):
        values = {
            "REPO_ROOT": str(self.root), "DURABLE_WORKTREE_DIR": str(self.root),
            "FLOOR_COMMIT": FULL, "VERIFY_COMMIT_COMMAND": verify,
            "LINK_TARGET_COMMAND": "mock link", "LIST_SERVICES_COMMAND": "printf 'target linked\\n'",
            "TARGET_SERVICE_NAME": "target", "THE_SERVICE_THIS_MUST_NEVER_TOUCH": "forbidden",
            "LINKED_MARKER": "linked", "DEPLOY_COMMAND": "mock deploy; echo deploy-123",
            "DEPLOY_ID_PATTERN": "deploy-[0-9]+", "DEPLOYMENT_STATUS_COMMAND": "echo SUCCESS",
            "TERMINAL_STATUSES": "SUCCESS|FAILED", "SUCCESS_STATUS": "SUCCESS",
            "ENTRY_EXPECTED_HTTP": "200", "PROTECTED_EXPECTED_HTTP": "200"}
        values.update(overrides)
        return self.render("deploy-env", values)

    def test_deploy_real_git_worktree(self):
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "real Git is required for this fixture")
        platform_bin = self.root / "platform-bin"
        platform_bin.mkdir()
        for name in ["mock", "curl", "sleep"]:
            shutil.copy2(self.bin / name, platform_bin / name)
        self.env.update(PATH=str(platform_bin) + os.pathsep + os.environ["PATH"],
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        repo = self.root / "real-repo"
        repo.mkdir()

        def git(directory, *args):
            result = subprocess.run(
                [real_git, "-c", "user.name=Factory Fixture", "-c",
                 "user.email=factory@example.invalid", "-c", "commit.gpgsign=false",
                 "-C", str(directory), *args], env=self.env,
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()

        git(repo, "init")
        (repo / "app.txt").write_text("first\n")
        git(repo, "add", "app.txt")
        git(repo, "commit", "-m", "fixture first")
        first = git(repo, "rev-parse", "HEAD")
        (repo / "app.txt").write_text("second\n")
        git(repo, "add", "app.txt")
        git(repo, "commit", "-m", "fixture second")
        second = git(repo, "rev-parse", "HEAD")
        path = self.deploy(
            verify='[ "$(git rev-parse HEAD)" = "$FULL" ] && [ "$(cat app.txt)" = second ]',
            REPO_ROOT=str(repo), FLOOR_COMMIT=first)
        wt = self.root / ("wt-" + second)
        self.assertFalse(wt.exists())
        result = self.run_script(path, second, SERVED=second)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(git(wt, "rev-parse", "HEAD"), second)
        self.assertEqual(Path(git(wt, "rev-parse", "--show-toplevel")), wt)
        initial_calls = self.calls()

        (wt / "app.txt").write_text("dirty\n")
        result = self.run_script(path, second, SERVED=second)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty or does not match", result.stderr)
        self.assertEqual(self.calls(), initial_calls)
        (wt / "app.txt").write_text("second\n")
        git(wt, "checkout", "--detach", first)
        result = self.run_script(path, second, SERVED=second)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty or does not match", result.stderr)
        self.assertEqual(self.calls(), initial_calls)
        git(wt, "checkout", "--detach", second)
        result = self.run_script(path, second, SERVED=second)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls().count("deploy\n"), 2)

    def test_deploy_refuses_before_link(self):
        path = self.deploy()
        for env in [dict(DIRTY=" M app"), dict(DIRTY="?? new"),
                    dict(HEAD_OVERRIDE="b" * 40), dict(STATUS_FAIL="1")]:
            self.assertNotEqual(self.run_script(path, FULL, **env).returncode, 0)
            self.assertNotIn("link", self.calls())
        result = self.run_script(self.deploy("false"), FULL)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("link", self.calls())

    def test_deploy_commit_and_http_binding(self):
        path = self.deploy()
        result = self.run_script(path, FULL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verify " + FULL, self.calls())
        for env in [dict(SERVED="b" * 40), dict(HTTP_STATUS="500")]:
            result = self.run_script(path, FULL, **env)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("VERIFY OK", result.stdout)

    def test_lane_failed_run_preserves_surviving_group(self):
        path = self.render("lane-db", {"PROJECT": "fixture"})
        self.command("ps", '''
case "$*" in
  *pgid=*) printf '%s\\n' "$2" ;;
  *lstart=*) printf '%s\\n' 'Mon Sep 7 12:00:00 2026' ;;
esac
''')
        shell_env = self.root / "shell-env"
        shell_env.write_text('kill() { return "${KILL_RC:-1}"; }\n')
        result = self.run_script(path, "exec", "ab", "--", "false",
                                 BASH_ENV=str(shell_env), KILL_RC="0")
        self.assertNotEqual(result.returncode, 0)
        records = list(self.root.rglob("ab.run"))
        self.assertEqual(len(records), 1)
        self.assertIn("still alive", result.stderr)
        # A second exec must refuse before touching its database.
        self.assertIn("already live", self.run_script(
            path, "exec", "ab", "--", "true", BASH_ENV=str(shell_env), KILL_RC="0").stderr)
        # Explicit fixture cleanup represents an operator reconciling the group.
        records[0].unlink()
        result = self.run_script(path, "exec", "ab", "--", "false",
                                 BASH_ENV=str(shell_env), KILL_RC="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(list(self.root.rglob("ab.run")))

    def test_lane_refuses_unknown_or_reused_identity(self):
        path = self.render("lane-db", {"PROJECT": "fixture"})
        self.command("ps", '''
[ "${LEADER_GONE:-0}" = 0 ] || exit 1
case "$*" in
  *pgid=*) printf '%s\\n' "$2" ;;
  *lstart=*) printf '%s\\n' 'Mon Sep 7 12:00:00 2026' ;;
esac
''')
        shell_env = self.root / "shell-env"
        shell_env.write_text('kill() { printf "signal %s\\n" "$*" >> "$CALLS"; return 0; }\n')
        directory = self.root / "fixture-lane-db/fixture-lane-cluster"
        directory.mkdir(parents=True)
        record = directory / "ab.run"
        for identity, gone in [("", "0"), ("old start time", "0"),
                               ("Mon Sep 7 12:00:00 2026", "1")]:
            content = "pgid=12345\nleader_started=" + identity + "\n"
            record.write_text(content)
            for args in [("stop", "ab"), ("exec", "ab", "--", "true")]:
                result = self.run_script(path, *args, BASH_ENV=str(shell_env), LEADER_GONE=gone)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("REFUSE:", result.stderr)
                self.assertEqual(record.read_text(), content)
                self.assertEqual(self.calls(), "")

    def test_lane_real_fast_commands(self):
        path = self.render("lane-db", {"PROJECT": "fixture"})
        # Use the real ps and Bash kill builtin; short commands can exit before
        # leader_identity captures their start time.
        for command, expected in [("true", 0), ("false", 1)]:
            for _ in range(3):
                result = self.run_script(path, "exec", "ab", "--", command,
                                         PATH=os.environ["PATH"], BASH_ENV=os.devnull)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertFalse(list(self.root.rglob("ab.run")))

    def test_pre_barrier_real_git_spaced_path(self):
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "real Git is required for this fixture")
        # A spaced repo path, because the source build's lane went green in its
        # worktree and red in a checkout whose path held a space (wave 112).
        repo = self.root / "spaced repo"
        (repo / "scripts").mkdir(parents=True)
        platform_bin = self.root / "platform-bin"
        platform_bin.mkdir()
        shutil.copy2(self.bin / "mock", platform_bin / "mock")
        self.env.update(PATH=str(platform_bin) + os.pathsep + os.environ["PATH"],
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        state = self.root / "run state"
        rendered = self.render("pre-barrier", {
            "TRUNK_BRANCH": "trunk", "INTEGRATION_BRANCH": "w1/integration",
            "LANE_BRANCH_GLOB": "w1/*", "TYPECHECK_COMMAND": "mock typecheck",
            "REGISTRY_DUP_CHECK": 'mock dupcheck; [ "${DUP_FAIL:-0}" = 0 ]',
            "SHARED_ONLY_SUITES": "mock suites", "CHECKS_LEDGER": "docs/build/checks.jsonl",
            "NEVER_TOGETHER_PATH": "docs/build/never-together.jsonl", "CLEAN_ROUNDS": "2",
            "RUN_STATE_DIR": str(state)})
        path = repo / "scripts" / "pre-barrier.sh"
        shutil.copy2(rendered, path)
        shutil.copy2(GUARDS, repo / "scripts" / "guards.py")
        (repo / "scripts" / "lane-cut.conf").write_text("WAVE=1\n")
        state.mkdir()
        journal = state / "journal.jsonl"
        journal.write_text("")

        def clean(lane, rounds=2):
            tip = git("rev-parse", "w1/" + lane)
            with open(journal, "a") as fh:
                for r in range(1, rounds + 1):
                    fh.write(json.dumps({"type": "panel", "wave": 1, "lane": lane, "stage": 1,
                                         "round": r, "commit": tip, "verdict": "clean"}) + "\n")

        def git(*args):
            result = subprocess.run(
                [real_git, "-c", "user.name=Factory Fixture", "-c",
                 "user.email=factory@example.invalid", "-c", "commit.gpgsign=false",
                 "-C", str(repo), *args], env=self.env,
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()

        def commit(name, text="x\n"):
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
            git("add", name)
            git("commit", "-m", "fixture " + name)

        git("init", "-b", "trunk")
        commit("app.txt")
        commit(".claude/test-freeze.json", json.dumps({"tests": ["tests/**"], "base": "trunk"}))
        commit("scripts/guards.py", GUARDS.read_text())
        git("checkout", "-b", "w1/ab")
        commit("ab.txt")
        clean("ab")
        git("checkout", "-b", "w1/integration", "trunk")
        git("merge", "--no-ff", "-m", "merge ab", "w1/ab")

        result = self.run_script(path, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would run mock typecheck", result.stdout)
        self.assertEqual(self.calls(), "")
        self.assertNotEqual(self.run_script(path, "--wat").returncode, 0)

        result = self.run_script(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([l.split()[1].rstrip(":") for l in result.stdout.splitlines()],
                         ["head", "ancestry", "artefacts", "tests", "checks-ledger", "together-ledger",
                          "panels", "checks", "typecheck", "registry", "shared"])
        self.assertNotIn("FAIL", result.stdout)

        # A lane not merged is a stale merge; every later check still runs.
        git("branch", "w1/cd", "trunk")
        git("checkout", "w1/cd")
        commit("cd.txt")
        clean("cd")
        git("checkout", "w1/integration")
        open(self.log, "w").close()
        result = self.run_script(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL ancestry: MISSING w1/cd", result.stdout)
        self.assertIn("typecheck", self.calls())
        result = self.run_script(path, "--squashed", "cd")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("declared squashed: w1/cd", result.stdout)

        # A trace in a merged lane, a failing registry check, and the wrong HEAD.
        git("checkout", "-b", "w1/ef", "trunk")
        commit("test-results/run 1/trace.zip")
        git("checkout", "w1/integration")
        git("merge", "--no-ff", "-m", "merge ef", "w1/ef")
        result = self.run_script(path, "--squashed", "cd", DUP_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL artefacts: w1/ef: test-results/run 1/trace.zip", result.stdout)
        self.assertIn("FAIL registry", result.stdout)
        self.assertIn("FAIL panels: ef: no panel rounds", result.stdout)
        clean("ef", rounds=1)
        self.assertIn("ef: 1 clean in a row", self.run_script(path, "--squashed", "cd").stdout)

        # The ratchet: a committed test edited on the integration branch.
        git("checkout", "trunk")
        commit("tests/a.test", "assert strict\n")
        git("checkout", "w1/integration")
        git("merge", "--no-ff", "-m", "take trunk", "trunk")
        clean("ef")
        self.assertIn("PASS tests", self.run_script(path, "--squashed", "cd").stdout)
        commit("tests/a.test", "assert loose\n")
        self.assertIn("FAIL tests: committed tests edited: tests/a.test",
                      self.run_script(path, "--squashed", "cd").stdout)

        # A merge that edits guards.py to pass everything is judged by the
        # trunk's guards.py, which fails it.
        commit("scripts/guards.py", "print('PASS tests: tampered'); print('PASS panels: tampered')\n")
        result = self.run_script(path, "--squashed", "cd")
        self.assertIn("frozen files changed: scripts/guards.py", result.stdout)
        self.assertNotIn("tampered", result.stdout)
        git("checkout", "trunk")
        self.assertIn("FAIL head", self.run_script(path, "--squashed", "cd").stdout)

    def test_prompt_contracts_and_drills(self):
        loop = (LOOP / "assets/build-loop.template.md").read_text()
        for clause in ["bootstrap_complete", "retryable `WIP`", "Empty frontier is not completion",
                       "journal.jsonl", "checkpoint.json", "budget-exhausted", "<WAVE_SPEND_LIMIT>",
                       "original deadline", "migration ID/checksum", "<LANE_CUT_COMMAND>",
                       "<PRE_BARRIER_COMMAND>", "attempt 3 is a reduction", "Multi-stage lanes",
                       "never `git revert -m 1`", "<DEPLOY_BRANCH>", '"type": "phase"', "review_wait", "owner_wait",
                       "<PREFLIGHT_COMMAND> --barrier", "<CLEAN_ROUNDS> panel rounds in a row",
                       "## Prediction", "## Lessons become checks", "### Pausing on a usage limit",
                       '"type": "usage"', '"type": "rate_limit"', "auth-expiring", "<SUPERSESSIONS_PATH>",
                       "<NEVER_TOGETHER_PATH>", "A contention red never becomes a check",
                       "the loop never rules on its own checks", "`paused`",
                       "<ENV_CHECK_COMMAND>", "environment-blocked", "<STANDING_DECISIONS_PATH>"]:
            self.assertIn(clause, " ".join(loop.split()))
        conventions = (LOOP / "assets/build-conventions.template.md").read_text()
        for clause in ["## Seats", "`build-monitor`", "isolation: 'worktree'"]:
            self.assertIn(clause, conventions)
        for name in ["interview.md", "loop-anatomy.md"]:
            self.assertIn("Empty frontier is not done", " ".join((LOOP / "references" / name).read_text().split()))
        drills = (SKILL / "references/recovery.md").read_text()
        for clause in ["Builder dies", "Migration applied", "Commit succeeds", "Deploy accepted",
                       "exhausted spend/deadline", "Seeded scoreboard", "restore into a disposable",
                       "Red barrier after an excluded lane", "Residual excluded schema",
                       "Host reboots", "Usage limit", "Login expires"]:
            self.assertIn(clause, drills)
        policy = (SKILL / "assets/ruling-policy.template.md").read_text()
        self.assertIn("## Retiring a check", policy)
        allow = json.loads((SKILL / "assets/settings.allowlist.template.json").read_text())
        self.assertIn("Edit(.claude/test-freeze.json)", allow["permissions"]["deny"])
        self.assertIn("Edit(.claude/settings*.json)", allow["permissions"]["deny"])
        hooks = json.loads((HOOKS / "hooks.json").read_text())["hooks"]
        for event in hooks.values():
            for group in event:
                for hook in group["hooks"]:
                    script = re.search(r"hooks/([\w-]+\.py)", hook["command"]).group(1)
                    self.assertTrue((HOOKS / script).is_file(), script)


    def test_factory_live_settings_entry_is_scoped_and_grants_nothing(self):
        """Gate 11's draft enables the mod for one project and widens no permission."""
        entry = json.loads((SKILL / "assets/settings.factory-live.template.json").read_text())
        self.assertEqual(entry["enabledPlugins"], {"factory-live@software-factory": True})
        self.assertEqual(entry["extraKnownMarketplaces"]["software-factory"]["source"],
                         {"source": "github", "repo": "benjchurchill1/software-factory"})
        self.assertNotIn("permissions", entry)
        self.assertNotIn("hooks", entry)
        market = json.loads((HOOKS.parent / ".claude-plugin/marketplace.json").read_text())
        names = {p["name"]: p["source"] for p in market["plugins"]}
        self.assertEqual(names.get("factory-live"), "./mods/factory-live")
        self.assertTrue((HOOKS.parent / "mods/factory-live/.claude-plugin/plugin.json").is_file())


class KeepAliveBase(unittest.TestCase):
    """The Stop hook and its arming helper, against real git in temp repos."""

    MARKER = "build-loop-test-nonce-0001"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="keepalive fixture ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / "state"
        self.env = dict(os.environ, BUILD_LOOP_STATE_ROOT=str(self.state),
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                        GIT_COMMITTER_EMAIL="t@t")
        self.assertIsNotNone(shutil.which("git"), "real Git is required for this fixture")
        self.repo_a = self.repo("repo a")
        self.repo_b = self.repo("repo-b")
        self.transcript = self.root / "transcript.jsonl"
        self.transcript.write_text(json.dumps({"text": "start the loop " + self.MARKER}) + "\n")

    def repo(self, name):
        path = self.root / name
        path.mkdir()
        self.git(path, "init", "-q", "-b", "trunk")
        self.commit(path)
        return path

    def git(self, path, *args):
        subprocess.run(["git", "-C", str(path), *args], check=True, env=self.env,
                       capture_output=True)

    def commit(self, path):
        self.git(path, "commit", "-q", "--allow-empty", "-m", "c")

    def arm(self, repo, *extra):
        out = subprocess.run([sys.executable, str(HOOKS / "arm.py"), "arm", str(repo),
                              "--marker", self.MARKER, *extra], env=self.env,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return Path(re.search(r"stop\s+(.+)", out.stdout).group(1).strip())

    def stop(self, cwd, session="s1", transcript=None):
        payload = {"session_id": session, "cwd": str(cwd),
                   "transcript_path": str(transcript or self.transcript)}
        out = subprocess.run([sys.executable, str(HOOKS / "build-loop-continue.py")],
                             input=json.dumps(payload), env=self.env, capture_output=True,
                             text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None



class KeepAliveHook(KeepAliveBase):
    def test_unarmed_allows(self):
        self.assertIsNone(self.stop(self.repo_a))

    def test_holds_only_the_marked_session_inside_the_repo(self):
        self.arm(self.repo_a, "--exclude", "monitor")
        self.assertEqual(self.stop(self.repo_a / "sub")["decision"], "block")
        self.assertIsNone(self.stop(self.repo_b))
        self.assertIsNone(self.stop(self.repo_a, session="monitor"))
        other = self.root / "other.jsonl"
        other.write_text("no nonce here\n")
        self.assertIsNone(self.stop(self.repo_a, transcript=other))

    def test_progress_resets_the_consecutive_count(self):
        self.arm(self.repo_a, "--max", "2")
        self.assertIn("(1 of 2", self.stop(self.repo_a)["reason"])
        self.assertIn("(2 of 2", self.stop(self.repo_a)["reason"])
        self.commit(self.repo_a)  # a lane or barrier commit is progress
        self.assertIn("(1 of 2", self.stop(self.repo_a)["reason"])
        self.stop(self.repo_a)
        spent = self.stop(self.repo_a)
        self.assertIn("SPENT", spent["reason"])
        self.assertIsNone(self.stop(self.repo_a), "a spent hook disarms itself")

    def test_total_cap_holds_even_with_progress(self):
        self.arm(self.repo_a, "--max", "5", "--max-total", "2")
        self.stop(self.repo_a)
        self.commit(self.repo_a)
        self.stop(self.repo_a)
        self.commit(self.repo_a)
        self.assertIn("in this arming", self.stop(self.repo_a)["reason"])

    def test_state_is_per_repo(self):
        stop_a = self.arm(self.repo_a)
        stop_b = self.arm(self.repo_b)
        self.assertNotEqual(stop_a, stop_b)
        stop_a.write_text("done\n")
        self.assertIsNone(self.stop(self.repo_a))
        self.assertEqual(self.stop(self.repo_b)["decision"], "block")
        self.assertIn(str(stop_b), self.stop(self.repo_b)["reason"])

    def test_prompt_path_is_named_in_the_reason(self):
        self.arm(self.repo_a, "--prompt-path", "prompts/loop.md")
        self.assertIn("Re-read prompts/loop.md", self.stop(self.repo_a)["reason"])

    def test_rearming_clears_stop_and_resets(self):
        stop = self.arm(self.repo_a, "--max", "1")
        self.stop(self.repo_a)
        stop.write_text("stalled\n")
        self.assertIsNone(self.stop(self.repo_a))
        self.arm(self.repo_a, "--max", "1")
        self.assertIn("(1 of 1", self.stop(self.repo_a)["reason"])

    def test_legacy_arming_still_honoured(self):
        self.state.mkdir()
        (self.state / "armed.json").write_text(json.dumps(
            {"cwd_prefix": str(self.repo_a), "marker": self.MARKER, "max": 3}))
        self.assertEqual(self.stop(self.repo_a)["decision"], "block")
        (self.state / "stop").write_text("done\n")
        self.assertIsNone(self.stop(self.repo_a))

    def test_stale_arming_and_bad_input_allow(self):
        self.arm(self.repo_a)
        armed = next(self.state.glob("*/armed.json"))
        old = armed.stat().st_mtime - 73 * 3600
        os.utime(armed, (old, old))
        self.assertIsNone(self.stop(self.repo_a))
        out = subprocess.run([sys.executable, str(HOOKS / "build-loop-continue.py")],
                             input="not json", env=self.env, capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout), (0, ""))


class TimingBase(unittest.TestCase):
    """progress.py's "where the time went": priority attribution over journal phases."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "progress", SKILL.parent / "build-monitor" / "scripts" / "progress.py")
        cls.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.p)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="timing fixture ")
        self.addCleanup(self.temp.cleanup)
        self.journal = Path(self.temp.name) / "journal.jsonl"
        self.cfg = {"timing": {"journal": str(self.journal)}, "history": {"max": 30}}

    def write(self, *events, junk=False):
        lines = [json.dumps({"type": "phase", "wave": w, "phase": ph, "lane": lane,
                             "event": ev, "at": "2026-09-30T" + at + ":00Z"})
                 for w, ph, lane, ev, at in events]
        if junk:
            lines += ["not json", json.dumps({"type": "intent", "op": "merge"}),
                      json.dumps({"type": "phase", "wave": 1, "phase": "lunch", "event": "start",
                                  "at": "2026-09-30T10:00:00Z"}),
                      json.dumps({"type": "phase", "wave": 1, "phase": "build", "lane": "zz",
                                  "event": "end", "at": "2026-09-30T10:05:00Z"})]
        self.journal.write_text("\n".join(lines) + "\n")

    def at(self, hhmm):
        import datetime as dt
        return dt.datetime.fromisoformat("2026-09-30T" + hhmm + ":00+00:00")

    def wave(self, n, current=None, now="12:00"):
        data = self.p.timings("/", self.cfg, current, now=self.at(now))
        return next(w for w in data["waves"] if w["wave"] == n)



class PhaseTimings(TimingBase):
    def test_work_outranks_waiting_and_gaps_are_unaccounted(self):
        self.write((1, "build", "a", "start", "10:00"), (1, "build", "b", "start", "10:10"),
                   (1, "build", "b", "end", "10:30"), (1, "verify", "b", "start", "10:30"),
                   (1, "build", "a", "end", "10:40"), (1, "review_wait", "a", "start", "10:40"),
                   (1, "verify", "b", "end", "10:50"), (1, "review_wait", "a", "end", "11:00"),
                   (1, "barrier", "", "start", "11:20"), (1, "barrier", "", "end", "11:50"),
                   (1, "record", "", "start", "11:50"), (1, "record", "", "end", "11:55"),
                   junk=True)
        w = self.wave(1)
        self.assertEqual(w["phases"], {"build": 40, "verify": 10, "review_wait": 10,
                                       "unaccounted": 20, "barrier": 30, "record": 5})
        self.assertEqual(w["span_min"], 115)
        self.assertEqual(sum(w["phases"].values()), w["span_min"])
        self.assertEqual(w["top"], "build")
        self.assertEqual(w["slowest_build"], {"lane": "a", "min": 40})
        self.assertEqual(w["open"], [])

    def test_open_phase_runs_to_now_only_in_the_current_wave(self):
        self.write((1, "build", "a", "start", "09:00"), (1, "build", "b", "start", "09:00"),
                   (1, "build", "b", "end", "09:30"),            # lane a crashed, never ended
                   (2, "owner_wait", "", "start", "11:00"))
        self.assertEqual(self.wave(1, current=2)["span_min"], 30)
        self.assertEqual(self.wave(1, current=2)["open"], ["build/a"])
        current = self.wave(2, current=2, now="11:45")
        self.assertEqual(current["phases"], {"owner_wait": 45})
        self.assertTrue(current["current"])

    def test_barrier_attempts_are_separate_intervals(self):
        self.cfg["timing"]["journal"] = str(self.journal)
        lines = [json.dumps({"type": "phase", "wave": 3, "phase": "barrier", "attempt": a,
                             "event": ev, "at": "2026-09-30T" + t + ":00Z"})
                 for a, ev, t in [(1, "start", "10:00"), (1, "end", "10:40"),
                                  (2, "start", "11:00"), (2, "end", "11:30")]]
        self.journal.write_text("\n".join(lines) + "\n")
        self.assertEqual(self.wave(3)["phases"], {"barrier": 70, "unaccounted": 20})

    def test_absent_config_and_unreadable_journal(self):
        self.assertIsNone(self.p.timings("/", {}, 1))
        self.assertIn("error", self.p.timings("/", self.cfg, 1))


class RealRepo(unittest.TestCase):
    """A temp git repo on branch `trunk`, with helpers."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guards fixture ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                        GIT_COMMITTER_EMAIL="t@t")
        self.assertIsNotNone(shutil.which("git"), "real Git is required for this fixture")
        self.git("init", "-q", "-b", "trunk")

    def git(self, *args, cwd=None):
        out = subprocess.run(["git", "-C", str(cwd or self.repo), "-c", "commit.gpgsign=false", *args],
                             env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def put(self, name, text, commit=True):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if commit:
            self.git("add", "-A")
            self.git("commit", "-q", "-m", "put " + name)
        return path

    def jl(self, *entries):
        return "".join(json.dumps(e) + "\n" for e in entries)

    def guard(self, *args):
        out = subprocess.run([sys.executable, str(GUARDS), "--root", str(self.repo), *args],
                             env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(len(out.stdout.splitlines()) in (1, 2), True, out.stdout + out.stderr)
        return out.returncode, out.stdout


class Guards(RealRepo):
    """guards.py: the ratchet (ledgers, test freeze, clean rounds) and the pace and auth checks."""

    LEDGER = "docs/build/checks.jsonl"

    def test_ledger_is_append_only_and_retired_only_by_a_ruling(self):
        c1 = {"op": "add", "id": "C-1", "class": "lists filter by tenant", "lens": "permissions",
              "source": "evidence/w3/panel.md", "run": "scripts/checks/c1.sh"}
        self.put("scripts/checks/c1.sh", "exit 0\n", commit=False)
        self.put(self.LEDGER, self.jl(c1))
        self.git("checkout", "-q", "-b", "work")
        ledger = lambda: self.guard("ledger", self.LEDGER, "--kind", "checks", "--trunk", "trunk")
        self.assertEqual(ledger()[0], 0)
        c2 = {"op": "add", "id": "C-2", "class": "totals reconcile", "source": "e2"}
        self.put(self.LEDGER, self.jl(c1, c2), commit=False)
        rc, out = ledger()
        self.assertEqual(rc, 0, out)
        self.assertIn("2 active, 1 new lines", out)
        # Editing an earlier line, or deleting the file, is not appending.
        self.put(self.LEDGER, self.jl(dict(c1, lens="all"), c2), commit=False)
        self.assertIn("edited, not appended", ledger()[1])
        (self.repo / self.LEDGER).unlink()
        self.assertIn("deleted", ledger()[1])
        # A retirement needs a ruling that exists and names the check.
        retire = {"op": "retire", "id": "C-1", "ruling": "decisions/r1.md"}
        self.put(self.LEDGER, self.jl(c1, retire), commit=False)
        self.assertIn("does not exist", ledger()[1])
        self.put("decisions/r1.md", "# Retire C-10\n", commit=False)
        self.assertIn("does not name it", ledger()[1])
        self.put("decisions/r1.md", "# Retire C-1: measured wrong\n", commit=False)
        rc, out = ledger()
        self.assertEqual(rc, 0, out)
        self.assertIn("0 active", out)
        # The shape of an entry.
        for bad, why in [({"op": "add", "id": "C-3", "class": "x"}, "no source"),
                         ({"op": "add", "id": "C-3", "source": "s"}, "no class"),
                         ({"op": "add", "id": "C-3", "class": "x", "source": "s", "run": "rm -rf /"},
                          "under scripts/checks/"),
                         ({"op": "add", "id": "C-1", "class": "x", "source": "s"}, "added twice"),
                         ({"op": "retire", "id": "C-9", "ruling": "decisions/r1.md"}, "before it was added")]:
            self.put(self.LEDGER, self.jl(c1, bad), commit=False)
            rc, out = ledger()
            self.assertEqual(rc, 1, out)
            self.assertIn(why, out)
        self.put("together.jsonl", self.jl({"op": "add", "id": "T-1", "rows": ["A-1"], "source": "s"}),
                 commit=False)
        self.assertIn("two row IDs", self.guard("ledger", "together.jsonl", "--kind", "together",
                                                "--trunk", "trunk")[1])

    def test_checks_run_and_a_recurrence_fails(self):
        self.put("scripts/checks/ok.sh", "exit 0\n", commit=False)
        self.put("scripts/checks/bad.sh", "echo recurred >&2; exit 1\n", commit=False)
        entries = [{"op": "add", "id": "C-1", "class": "a", "source": "s", "run": "scripts/checks/ok.sh"},
                   {"op": "add", "id": "C-2", "class": "b", "source": "s", "run": "scripts/checks/bad.sh"},
                   {"op": "add", "id": "C-3", "class": "c", "source": "s"}]
        self.put(self.LEDGER, self.jl(*entries), commit=False)
        rc, out = self.guard("checks", self.LEDGER)
        self.assertEqual(rc, 1)
        self.assertIn("recurred: C-2", out)
        self.put("decisions/r.md", "C-2 is subsumed by C-1\n", commit=False)
        self.put(self.LEDGER, self.jl(*entries, {"op": "retire", "id": "C-2", "ruling": "decisions/r.md"}),
                 commit=False)
        rc, out = self.guard("checks", self.LEDGER)
        self.assertEqual(rc, 0, out)
        self.assertIn("1 run, 1 by lens only", out)

    def test_committed_tests_are_superseded_never_edited(self):
        self.put(".claude/test-freeze.json", json.dumps(
            {"tests": ["tests/**", "**/*.spec.ts"], "base": "trunk"}), commit=False)
        self.put("tests/a.test", "assert strict\n", commit=False)
        self.put("web/x.spec.ts", "expect(1)\n")
        self.git("checkout", "-q", "-b", "work")
        tests = lambda: self.guard("tests", "--trunk", "trunk")
        self.put("tests/new.test", "fresh\n")
        self.assertEqual(tests()[0], 0, "a new test is not frozen")
        self.put("web/x.spec.ts", "expect(true)\n")
        rc, out = tests()
        self.assertEqual(rc, 1)
        self.assertIn("committed tests edited: web/x.spec.ts", out)
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.git("rm", "-q", "tests/a.test")
        self.git("commit", "-q", "-m", "drop a")
        self.assertIn("no supersession record", tests()[1])
        reg = "docs/build/supersessions.jsonl"
        self.put(reg, self.jl({"predecessor": "tests/a.test", "successor": "tests/new.test",
                               "why": "encoded the defect", "wave": 4}))
        self.assertIn("does not name its predecessor", tests()[1])
        self.put("tests/new.test", "# supersedes a.test\nfresh\n")
        rc, out = tests()
        self.assertEqual(rc, 0, out)
        self.assertIn("1 superseded", out)
        self.put(".claude/test-freeze.json", json.dumps({"tests": [], "base": "trunk"}))
        self.assertIn(".claude/test-freeze.json changed", tests()[1])
        self.git("checkout", "-q", "trunk")
        self.assertIn("PASS", tests()[1])

    def test_check_scripts_and_the_ratchet_itself_are_frozen(self):
        self.put(".claude/test-freeze.json", json.dumps(
            {"tests": ["tests/**", "scripts/checks/**"], "base": "trunk"}), commit=False)
        self.put("scripts/checks/c1.sh", "grep -rq tenant_id src || exit 1\n", commit=False)
        self.put("scripts/guards.py", "# the real one\n")
        self.git("checkout", "-q", "-b", "work")
        self.put("scripts/checks/c2.sh", "exit 0\n")
        self.assertEqual(self.guard("tests", "--trunk", "trunk")[0], 0, "a new check is not frozen")
        self.put("scripts/checks/c1.sh", "exit 0\n")
        self.assertIn("committed tests edited: scripts/checks/c1.sh", self.guard("tests", "--trunk", "trunk")[1])
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.put("scripts/guards.py", "# weakened\n")
        self.assertIn("frozen files changed: scripts/guards.py", self.guard("tests", "--trunk", "trunk")[1])
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.git("rm", "-q", "scripts/guards.py")
        self.git("commit", "-q", "-m", "drop it")
        self.assertIn("frozen files changed: scripts/guards.py", self.guard("tests", "--trunk", "trunk")[1])

    def test_supersessions_register_is_append_only(self):
        self.put(".claude/test-freeze.json", json.dumps({"tests": ["tests/**"], "base": "trunk"}),
                 commit=False)
        reg = "docs/build/supersessions.jsonl"
        self.put(reg, self.jl({"predecessor": "tests/a", "successor": "tests/b"}))
        self.git("checkout", "-q", "-b", "work")
        self.put(reg, "")
        self.assertIn("edited, not appended", self.guard("tests", "--trunk", "trunk")[1])

    def test_panels_need_clean_rounds_in_a_row_at_the_tip(self):
        journal = self.root / "journal.jsonl"
        tip, old = "b" * 40, "c" * 40

        def rounds(*events):
            journal.write_text(self.jl(*[{"type": "panel", "wave": 5, "lane": "ab", "stage": st,
                                          "round": i, "commit": c, "verdict": v}
                                         for i, (st, c, v) in enumerate(events, 1)]))
            return self.guard("panels", "--journal", str(journal), "--wave", "5", "--rounds", "2",
                              "ab=" + tip)

        self.assertEqual(rounds((1, old, "refuted"), (2, tip, "clean"), (2, tip, "clean"))[0], 0)
        self.assertIn("1 clean in a row", rounds((1, tip, "clean"), (1, tip, "refuted"), (2, tip, "clean"))[1])
        self.assertIn("1 clean in a row", rounds((1, old, "clean"), (2, tip, "clean"))[1])
        self.assertIn("tip moved", rounds((1, old, "clean"), (1, old, "clean"))[1])
        self.assertIn("stage 4", rounds((4, tip, "clean"), (4, tip, "clean"))[1])
        self.assertIn("no panel rounds", self.guard("panels", "--journal", str(journal), "--wave", "6",
                                                    "--rounds", "2", "ab=" + tip)[1])
        self.assertEqual(self.guard("panels", "--journal", str(self.root / "none"), "--wave", "5",
                                    "--rounds", "2", "ab=" + tip)[0], 1)

    def test_never_together_reads_the_queue(self):
        ledger = self.put("together.jsonl", self.jl(
            {"op": "add", "id": "T-1", "rows": ["INV-01", "PAY-02"], "source": "barrier 12-1"}), commit=False)
        queue = self.put("queue.md", "- lane ab: INV-01, PAY-02\n", commit=False)
        together = lambda: self.guard("together", "together.jsonl", "--queue", str(queue))
        rc, out = together()
        self.assertEqual(rc, 1)
        self.assertIn("T-1 (INV-01 + PAY-02)", out)
        queue.write_text("- lane ab: INV-01, PAY-021\n")
        self.assertEqual(together()[0], 0, "a longer row ID is a different row")
        queue.write_text("- lane ab: INV-01\n- lane cd: PAY-02\n")
        self.put("decisions/r.md", "T-1: the shared table was split in wave 14\n", commit=False)
        ledger.write_text(ledger.read_text() + self.jl({"op": "retire", "id": "T-1", "ruling": "decisions/r.md"}))
        self.assertEqual(together()[0], 0)

    def test_pace_pauses_on_the_window_and_stops_on_the_budget(self):
        journal = self.root / "journal.jsonl"
        use = lambda w, ph, x: {"type": "usage", "wave": w, "phase": ph, "amount": x}
        journal.write_text(self.jl(use(1, "build", 10), use(2, "build", 22), use(2, "barrier", 8),
                                   use(3, "build", 15), use(3, "barrier", 5), use(4, "build", 3)))
        now = "2099-01-01T00:00:00Z"
        pace = lambda *extra: self.guard("pace", "--journal", str(journal), "--wave", "4", "--now", now,
                                         "--reserve", "5", *extra)
        rc, out = pace("--mode", "wave", "--limit", "200")
        self.assertEqual(rc, 0, out)
        self.assertIn("next wave about 30 (largest of last 3), spent 63", out)
        self.assertIn("about 8", pace("--mode", "barrier")[1])
        rc, out = pace("--mode", "wave", "--limit", "90")
        self.assertEqual(rc, 20)
        self.assertIn("budget-exhausted", out)
        rc, out = pace("--mode", "wave", "--remaining", "20", "--resets-at", "2099-01-01T05:00:00Z")
        self.assertEqual(rc, 10)
        self.assertIn("resume_at 2099-01-01T05:00:00Z", out)
        self.assertEqual(pace("--mode", "wave", "--remaining", "40")[0], 0)
        self.assertEqual(pace("--mode", "wave", "--remaining", "20")[0], 20, "short, with no reset time")
        journal.write_text(journal.read_text() + self.jl(
            {"type": "rate_limit", "at": "2098-12-31T23:00:00Z", "resets_at": "2099-01-01T02:00:00Z"}))
        rc, out = pace("--mode", "barrier")
        self.assertEqual(rc, 10)
        self.assertIn("resume_at 2099-01-01T02:00:00Z", out)
        now = "2099-01-01T03:00:00Z"
        self.assertEqual(pace("--mode", "barrier")[0], 0, "a limit that has reset")
        journal.write_text("")
        self.assertEqual(pace("--mode", "wave")[0], 20, "no history and no default estimate")
        self.assertEqual(pace("--mode", "wave", "--default-estimate", "12")[0], 0)

    def test_auth_stops_before_the_login_expires(self):
        auth = lambda *a: self.guard("auth", "--now", "2099-01-01T12:00:00Z", *a)
        self.assertEqual(auth("--need-minutes", "60", "--remaining-seconds", "7200")[0], 0)
        rc, out = auth("--need-minutes", "60", "--remaining-seconds", "1800")
        self.assertEqual(rc, 20)
        self.assertIn("auth-expiring", out)
        self.assertIn("cannot tell", auth("--need-minutes", "60", "--remaining-seconds", "unknown")[1])
        since = self.root / "auth-at"
        since.write_text("2099-01-01T11:00:00Z\n")
        counted = ("--remaining-seconds", "unknown", "--since", str(since), "--lifetime-hours", "8")
        self.assertEqual(auth("--need-minutes", "60", *counted)[0], 0)
        since.write_text("2099-01-01T04:30:00Z\n")
        self.assertEqual(auth("--need-minutes", "60", *counted)[0], 20)


class Preflight(ScriptFixture):
    """preflight.sh, rendered, with the machine's answers mocked."""

    def preflight(self):
        path = self.render("preflight", {
            "RUN_STATE_DIR": str(self.root / "state"), "GENERATED_FILES": '"gen.md" "scripts/lane-cut.conf"',
            "DISK_PATHS": '"." "$ROOT/scripts"', "DISK_FREE_GB": "${DISK_GB:-0}",
            "BOOT_ID_COMMAND": 'echo "${BOOT:-boot-1}"', "REBOOT_PENDING_COMMAND": '[ "${PENDING:-0}" = 1 ]',
            "AUTH_CHECK_COMMAND": 'echo "${AUTH_SECS:-99999}"', "AUTH_LIFETIME_HOURS": "8",
            "USAGE_WINDOW_COMMAND": 'echo "${WINDOW:-}"', "NEVER_TOGETHER_PATH": "together.jsonl",
            "BARRIER_MAX_MINUTES": "60", "HANDOFF_RESERVE_MINUTES": "10", "WAVE_TIME_LIMIT_MINUTES": "240",
            "BARRIER_SPEND_ESTIMATE": "5", "WAVE_SPEND_LIMIT_NUMBER": "20", "SPEND_LIMIT_NUMBER": "1000",
            "HANDOFF_RESERVE_NUMBER": "5"})
        (self.scripts / "lane-cut.conf").write_text("WAVE=2\n")
        (self.root / "gen.md").write_text("# the loop prompt, filled\n")
        (self.root / "state").mkdir(exist_ok=True)
        (self.root / "state" / "journal.jsonl").write_text("")
        (self.root / "queue.md").write_text("- lane ab: INV-01\n- lane cd: PAY-02\n")
        return path

    def run_pf(self, path, *args, **env):
        result = self.run_script(path, *args, **env)
        return result.returncode, result.stdout + result.stderr

    def test_preflight_go_and_dry_run(self):
        path = self.preflight()
        (self.root / "state" / "journal.jsonl").unlink()
        (self.root / "state").rmdir()
        rc, out = self.run_pf(path, "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("would compare", out)
        self.assertFalse((self.root / "state").exists(), "a dry run writes nothing")
        self.assertEqual(self.run_pf(path)[0], 2, "wave open needs its queue")
        path = self.preflight()
        rc, out = self.run_pf(path, "--queue", str(self.root / "queue.md"))
        self.assertEqual(rc, 0, out)
        self.assertEqual([l.split()[1].rstrip(":") for l in out.splitlines()],
                         ["config", "disk", "boot", "reboot", "auth", "usage", "together"])
        rc, out = self.run_pf(path, "--barrier")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("together", out)
        rc, out = self.run_pf(path, "--barrier", PENDING="1")
        self.assertEqual(rc, 0, out)
        self.assertIn("WARN reboot", out)

    def test_preflight_fail_recover_stop_pause(self):
        path = self.preflight()
        q = ("--queue", str(self.root / "queue.md"))
        self.assertEqual(self.run_pf(path, *q)[0], 0)
        (self.root / "gen.md").write_text("owner: <OWNER>\n")
        rc, out = self.run_pf(path, *q)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL config: unreplaced slots in gen.md(1)", out)
        (self.root / "gen.md").write_text("filled\n")
        rc, out = self.run_pf(path, *q, DISK_GB="100000000")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL disk: low on", out)
        rc, out = self.run_pf(path, *q, BOOT="boot-2")
        self.assertEqual(rc, 30)
        self.assertIn("RECOVER boot", out)
        self.assertEqual(self.run_pf(path, *q, BOOT="boot-2")[0], 30, "until acknowledged")
        self.assertEqual(self.run_pf(path, *q, "--ack-reboot", BOOT="boot-2")[0], 0)
        self.assertEqual(self.run_pf(path, *q, BOOT="boot-2")[0], 0)
        # The login must outlast the step: 250 minutes at wave open, 70 before a barrier.
        rc, out = self.run_pf(path, *q, BOOT="boot-2", AUTH_SECS="6000")
        self.assertEqual(rc, 20)
        self.assertIn("STOP auth: auth-expiring", out)
        self.assertEqual(self.run_pf(path, "--barrier", BOOT="boot-2", AUTH_SECS="6000")[0], 0)
        window = "3 2099-01-01T05:00:00Z"
        rc, out = self.run_pf(path, "--barrier", BOOT="boot-2", WINDOW=window)
        self.assertEqual(rc, 10)
        self.assertIn("resume_at 2099-01-01T05:00:00Z", out)
        self.assertEqual(self.run_pf(path, "--barrier", BOOT="boot-2", WINDOW=window, AUTH_SECS="60")[0], 20,
                         "a stop outranks a pause")
        (self.root / "together.jsonl").write_text(json.dumps(
            {"op": "add", "id": "T-1", "rows": ["INV-01", "PAY-02"], "source": "barrier 1-2"}) + "\n")
        rc, out = self.run_pf(path, *q, BOOT="boot-2")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL together", out)


class TestFreezeHook(RealRepo):
    """The PreToolUse hook: committed tests are refused, everything else allowed."""

    def setUp(self):
        super().setUp()
        self.put(".claude/test-freeze.json", json.dumps(
            {"tests": ["tests/**"], "base": "trunk", "supersessions": "docs/build/supersessions.jsonl"}),
            commit=False)
        self.put("tests/a.test", "assert strict\n")

    def hook(self, tool, file_path, cwd=None):
        payload = {"tool_name": tool, "tool_input": {"file_path": str(file_path)},
                   "cwd": str(cwd or self.repo)}
        out = subprocess.run([sys.executable, str(HOOKS / "test-freeze.py")], input=json.dumps(payload),
                             env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        if not out.stdout.strip():
            return None
        decision = json.loads(out.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        return decision["permissionDecisionReason"]

    def test_committed_tests_and_the_config_are_refused(self):
        reason = self.hook("Edit", self.repo / "tests/a.test")
        self.assertIn("committed test", reason)
        self.assertIn("docs/build/supersessions.jsonl", reason)
        self.assertIsNotNone(self.hook("Write", "tests/a.test"), "a relative path resolves from cwd")
        self.assertIsNotNone(self.hook("MultiEdit", self.repo / "tests/a.test"))
        self.assertIn("defines the test freeze", self.hook("Edit", self.repo / ".claude/test-freeze.json"))

    def test_the_ratchet_scripts_are_frozen_by_default(self):
        self.put("scripts/guards.py", "# the real one\n")
        self.assertIn("part of the ratchet", self.hook("Edit", self.repo / "scripts/guards.py"))
        self.assertIsNone(self.hook("Edit", self.repo / "scripts/other.sh"))

    def test_new_tests_other_files_and_other_tools_are_allowed(self):
        self.assertIsNone(self.hook("Write", self.repo / "tests/new/b.test"))
        self.assertIsNone(self.hook("Edit", self.repo / "src/app.js"))
        self.assertIsNone(self.hook("Bash", self.repo / "tests/a.test"))
        elsewhere = self.root / "other"
        elsewhere.mkdir()
        self.assertIsNone(self.hook("Edit", elsewhere / "tests/a.test"), "no config, no effect")
        out = subprocess.run([sys.executable, str(HOOKS / "test-freeze.py")], input="not json",
                             env=self.env, capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout), (0, ""))

    def test_a_lane_worktree_is_frozen_too(self):
        lane = self.root / "lanes" / "w1 ab"
        self.git("worktree", "add", "-q", "-b", "w1/ab", str(lane))
        self.assertIsNotNone(self.hook("Edit", lane / "tests/a.test", cwd=lane))
        self.assertIsNone(self.hook("Write", lane / "tests/lane-own.test", cwd=lane))


class KeepAlivePause(KeepAliveBase):
    """A usage pause lets the seat stop, uncounted, until its reset time."""

    def test_a_pause_in_the_future_allows_the_stop(self):
        self.arm(self.repo_a, "--max", "2")
        pause = next(self.state.glob("*/armed.json")).parent / "pause"
        self.assertIn(str(pause), self.stop(self.repo_a)["reason"])
        pause.write_text(json.dumps({"until": "2099-01-01T00:00:00Z", "reason": "usage"}))
        for _ in range(4):
            self.assertIsNone(self.stop(self.repo_a), "paused: allowed, and not counted")
        status = subprocess.run([sys.executable, str(HOOKS / "arm.py"), "status", str(self.repo_a)],
                                env=self.env, capture_output=True, text=True).stdout
        self.assertIn("paused until 2099-01-01T00:00:00Z", status)
        pause.write_text(json.dumps({"until": "2000-01-01T00:00:00Z", "reason": "usage"}))
        self.assertIn("(2 of 2", self.stop(self.repo_a)["reason"], "a past pause is ignored")
        self.arm(self.repo_a)
        self.assertFalse(pause.exists(), "re-arming clears a pause")


class PausedPhase(TimingBase):
    def test_paused_ranks_last(self):
        self.write((1, "paused", "", "start", "10:00"), (1, "build", "a", "start", "10:30"),
                   (1, "build", "a", "end", "10:45"), (1, "paused", "", "end", "11:00"))
        self.assertEqual(self.wave(1)["phases"], {"paused": 45, "build": 15})
        self.assertEqual(self.p.PHASES[-1], "paused")


class KanbanBoard(TimingBase):
    """progress.py's kanban view: row ids in queues, column placement, the run."""

    def git(self, *args, at="2026-09-30T03:00:00Z"):
        env = {**os.environ, "GIT_COMMITTER_DATE": at, "GIT_AUTHOR_DATE": at}
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, env=env)

    def put(self, rel_path, text):
        path = self.repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def checkpoint(self, wave, phase, spent, wave_spent, msg):
        self.put("run/checkpoint.json", json.dumps({"wave_phase": phase, "budget": {
            "unit": "tokens", "spent": spent, "total_limit": 100, "started_at": "2026-09-30T00:00:00Z",
            "deadline": "2026-10-02T00:00:00Z",
            "wave": {"id": wave, "spent": wave_spent, "started_at": f"2026-09-30T0{wave}:00:00Z"}}}))
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def setUp(self):
        super().setUp()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-qb", "trunk")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.board = ("| ID | Tag | Verdict | Note |\n| --- | --- | --- | --- |\n"
                      "| SES-01 | R1 | PASS | done |\n| SES-02 | R1 | TODO | |\n| SES-03 | R1 | TODO | |\n"
                      "| SES-04 | R1 | TODO | |\n| TRI-01 | R1 | WIP | failed verify |\n"
                      "| TRI-02 | SITE | TODO | |\n| TRI-03 | R1 | TODO | stuck: twice |\n| TRI-04 | R1 | TODO | |\n")
        self.put("progress.md", self.board.replace("| SES-01 | R1 | PASS", "| SES-01 | R1 | TODO"))
        self.put("conf", "WAVE=2\n")
        self.put("ev/wave1/orchestrator/wave2-queue.md",
                 "# Wave 2\n\n- **ses_core**: SES-02..03, and TRI-04 later\n- **tri_fix**: Rows: TRI-01\n")
        self.put("ev/wave2/orchestrator/wave3-queue.md", "| Lane | Rows |\n| --- | --- |\n| ses_more | SES-04 |\n")
        self.checkpoint(1, "building", 10, 10, "wave 1 open")
        self.put("progress.md", self.board)
        self.checkpoint(1, "recorded", 20, 20, "wave 1 record")
        self.git("branch", "carry/w2-tri_fix")
        self.cfg = {"repo": str(self.repo), "trunk": "trunk", "view": "kanban",
                    "scoreboard": {"path": "progress.md", "id_regex": r"^[A-Z]+-\d+$", "verdict_column": 3},
                    "board": {"columns": {"tag": 2, "note": 4}, "parked_tags": ["SITE"],
                              "carry_branch": "carry/w{N}-{lane}", "areas": {"SES": "Sessions"}},
                    "wave": {"conf": "conf", "evidence_dir": "ev/wave{N}", "integration_branch": "w{N}/int",
                             "lane_branch": "w{N}/{lane}", "verification_glob": "ev/wave{N}/v-*.txt"},
                    "history": {"record_regex": "^wave {N} record"},
                    "run": {"checkpoint": "run/checkpoint.json"}}

    def test_ids_in_prose_expand_and_only_known_ids_count(self):
        known = {"SES-05", "SES-06", "SES-07", "TRI-01", "TRI-02", "TRI-03", "TRI-04", "DEC-07", "SES-03"}
        self.assertEqual(self.p.expand_ids("SES-05, 06, 07 and TRI-01..04", known),
                         ["SES-05", "SES-06", "SES-07", "TRI-01", "TRI-02", "TRI-03", "TRI-04"])
        self.assertEqual(self.p.expand_ids("DEC-07, SES-03; wave 2, 10 lanes; XYZ-01", known), ["DEC-07", "SES-03"])

    def test_every_row_lands_in_one_column(self):
        data = self.p.build(self.cfg, self.temp.name, "kanban")
        col = {r["id"]: r["column"] for r in data["board"]["rows"]}
        self.assertEqual(col, {"SES-01": "done", "SES-02": "wave", "SES-03": "wave", "TRI-04": "wave",
                               "TRI-01": "wave", "SES-04": "next", "TRI-02": "parked",
                               "TRI-03": "rework"})
        lanes = {l["lane"]: l for l in data["board"]["lanes"]}
        self.assertTrue(lanes["tri_fix"]["carried"])
        self.assertEqual(lanes["ses_core"]["rows"], ["SES-02", "SES-03", "TRI-04"])
        self.assertEqual(data["board"]["areas"][0], {"code": "SES", "name": "Sessions", "total": 4, "done": 1})

    def test_the_run_reads_each_recorded_wave_from_checkpoint_history(self):
        import datetime as dt
        r = self.p.run_block(str(self.repo), self.cfg, 8, 1, now=dt.datetime(2026, 9, 30, 10, tzinfo=dt.timezone.utc))
        self.assertEqual([(w["wave"], w["spent"], w["done"]) for w in r["waves"]], [(1, 20.0, 1)])
        self.assertEqual((r["spent"], r["limit"], r["elapsed_hours"]), (20.0, 100.0, 10.0))
        self.assertEqual(r["projection"]["bound_by"], "budget")
        self.assertEqual(r["projection"]["done"], 5)          # 80 left / 20 a wave = 4 more waves, +1 row each
        self.assertEqual(r["to_finish"]["waves"], 7.0)
        self.cfg["run"].update(no_time_limit=True, limit_override=300)
        r = self.p.run_block(str(self.repo), self.cfg, 8, 1)
        self.assertEqual((r["limit"], r["deadline"], r["projection"]["done"]), (300.0, "", 8))

    def test_the_page_is_written_with_the_data_embedded(self):
        cfg_path = Path(self.temp.name) / "monitor.json"
        cfg_path.write_text(json.dumps({**self.cfg, "out": "board.html"}))
        out = subprocess.run([sys.executable, str(SKILL.parent / "build-monitor" / "scripts" / "progress.py"),
                              "--config", str(cfg_path)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        page = (Path(self.temp.name) / "board.html").read_text()
        self.assertNotIn("/*__DATA__*/null", page)
        self.assertIn('"column": "parked"', page)
        self.assertIn("<title>repo build board</title>", page)


class EnvironmentCheck(unittest.TestCase):
    """env-check.py against a temp repo, with no network and a scrubbed environment."""

    SCRIPT = SKILL.parent / "environment-check" / "scripts" / "env-check.py"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="env-check-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "db").mkdir()
        for n in range(3):
            (self.root / "db" / f"{n:03}_init.sql").write_text("select 1;\n")
        (self.root / "deploy.sh").write_text("#!/bin/bash\nsupabase db push\nnetlify deploy\n")
        (self.root / "decisions.md").write_text(
            "- budget: 150M total, 12M a wave (owner, 2026-10-01)\n"
            "- deploy-on-green: yes (owner, 2026-10-01)\n")
        self.manifest = {
            "project": "fixture", "where_the_build_runs": "cloud", "cloud_environment": "Fixture Build",
            "secrets": [{"name": "HOST_AUTH_TOKEN", "for": "deploy"},
                        {"name": "OPTIONAL_KEY", "for": "nice to have", "optional": True}],
            "tools": [{"name": "python3", "version_command": "python3 --version"},
                      {"name": "no-such-cli-xyz", "install": "npm i -g no-such-cli-xyz"}],
            "probes": [{"name": "token sees the site", "command": "echo site-123 $HOST_AUTH_TOKEN",
                        "expect_stdout": "site-123", "needs": ["HOST_AUTH_TOKEN"]}],
            "migrations": {"dir": "db", "deploy_script": "deploy.sh", "apply_command": "supabase db push"},
            "logins": {"how": "owner-creates", "accounts": [{"email": "owner@example.com", "role": "admin"}],
                       "owner_confirmed": False},
            "concurrency": {"planned_lanes": 999},
            "decisions_file": "decisions.md",
            "decisions_required": ["budget", "deploy-on-green", "migrations-on-deploy"],
        }

    def run_check(self, *args, **env):
        (self.root / "environment.json").write_text(json.dumps(self.manifest))
        base = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "SYSTEMROOT"}}
        return subprocess.run([sys.executable, str(self.SCRIPT), "--repo", str(self.root),
                               "--manifest", "environment.json", "--skip-network", *args],
                              env=dict(base, **env), capture_output=True, text=True, timeout=60)

    def test_blocked_report_names_every_owner_action(self):
        r = self.run_check(HOST_AUT_TOKEN="s3cret-value-1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        out = r.stdout
        self.assertIn("**BLOCKED**", out)
        self.assertIn("Rename HOST_AUT_TOKEN to HOST_AUTH_TOKEN", out)
        self.assertIn("fresh session", out)
        self.assertIn("Install no-such-cli-xyz", out)
        self.assertIn("never invents passwords", out)
        self.assertIn("migrations-on-deploy", out)
        self.assertIn("planned 999", out)
        self.assertNotIn("s3cret-value-1", out)
        self.assertRegex(out, r"\| secrets \| OPTIONAL_KEY \| WARN")

    def test_ready_when_everything_is_in_place_and_values_are_redacted(self):
        self.manifest["tools"] = self.manifest["tools"][:1]
        self.manifest["logins"]["owner_confirmed"] = True
        self.manifest["concurrency"]["planned_lanes"] = 1
        (self.root / "decisions.md").write_text(
            "- budget: 150M (owner, 2026-10-01)\n- deploy-on-green: yes\n- migrations-on-deploy: yes\n")
        report = self.root / "out" / "env.md"
        r = self.run_check("--report", str(report), HOST_AUTH_TOKEN="s3cret-value-2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("**READY**", report.read_text())
        self.assertIn("Lanes at once", r.stdout)
        self.assertNotIn("s3cret-value-2", r.stdout + report.read_text())

    def test_deploy_without_migrations_and_failed_probe(self):
        (self.root / "deploy.sh").write_text("#!/bin/bash\nnetlify deploy\n")
        self.manifest["probes"][0]["expect_stdout"] = "other-site"
        r = self.run_check(HOST_AUTH_TOKEN="tok-abcdef")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not run `supabase db push`", r.stdout)
        self.assertRegex(r.stdout, r"token sees the site \| FAIL")
        self.assertNotIn("tok-abcdef", r.stdout)

    def test_dry_run_runs_nothing_and_slots_are_refused(self):
        marker = self.root / "ran"
        self.manifest["probes"][0]["command"] = f"touch {marker}"
        r = self.run_check("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PLAN  probes: token sees the site", r.stdout)
        self.assertFalse(marker.exists())
        self.manifest["project"] = "<PROJECT>"
        self.assertEqual(self.run_check().returncode, 2)
        template = SKILL.parent / "environment-check" / "assets" / "environment.template.json"
        self.assertRegex(template.read_text(), r"<PLANNED_LANES>")


class HouseStyle(unittest.TestCase):
    """Prose in the plugin uses UK spelling and no em dashes.

    The only em dashes allowed are in progress.py, which still parses them in
    queue, owner-list and merge-subject lines written by older builds.
    """

    REPO = SKILL.parents[1]
    US = re.compile(r"\b(behavior\w*|normaliz\w*|serializ\w*|organiz\w*|recogniz\w*|"
                    r"prioritiz\w*|summariz\w*|optimiz\w*|authoriz\w*|initializ\w*|"
                    r"minimiz\w*|maximiz\w*|categoriz\w*|standardiz\w*|utiliz\w*|"
                    r"artifacts?\b(?!_url)|judgment|canceled|labeled|modeling|honestly)", re.I)

    def texts(self):
        for path in sorted(self.REPO.rglob("*")):
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts \
                    and path.suffix in {".md", ".sh", ".json", ".html", ".py"}:
                yield path, path.read_text(errors="replace")

    def test_no_em_dashes(self):
        for path, text in self.texts():
            if path.name in {"progress.py", "verify-factory.py"}:
                continue
            with self.subTest(path=str(path.relative_to(self.REPO))):
                self.assertNotIn("\u2014", text)

    def test_uk_spelling(self):
        for path, text in self.texts():
            if path.suffix != ".md":
                continue
            # The Artifact tool is a product name; the rule is about prose.
            prose = re.sub(r"`[^`]*`|Artifact tool|an artifact\b", "", text)
            with self.subTest(path=str(path.relative_to(self.REPO))):
                self.assertEqual(self.US.findall(prose), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
