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
FULL = "a" * 40
SLOT = re.compile(r"<[A-Z][A-Z0-9_]*(?::[^>]*|\s[^>]*)?>")


class FactoryFixtures(unittest.TestCase):
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
        rendered = self.render("pre-barrier", {
            "TRUNK_BRANCH": "trunk", "INTEGRATION_BRANCH": "w1/integration",
            "LANE_BRANCH_GLOB": "w1/*", "TYPECHECK_COMMAND": "mock typecheck",
            "REGISTRY_DUP_CHECK": 'mock dupcheck; [ "${DUP_FAIL:-0}" = 0 ]',
            "SHARED_ONLY_SUITES": "mock suites"})
        path = repo / "scripts" / "pre-barrier.sh"
        shutil.copy2(rendered, path)

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
        git("checkout", "-b", "w1/ab")
        commit("ab.txt")
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
                         ["head", "ancestry", "artefacts", "typecheck", "registry", "shared"])
        self.assertNotIn("FAIL", result.stdout)

        # A lane not merged is a stale merge; every later check still runs.
        git("branch", "w1/cd", "trunk")
        git("checkout", "w1/cd")
        commit("cd.txt")
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
        git("checkout", "trunk")
        self.assertIn("FAIL head", self.run_script(path, "--squashed", "cd").stdout)

    def test_prompt_contracts_and_drills(self):
        loop = (LOOP / "assets/build-loop.template.md").read_text()
        for clause in ["bootstrap_complete", "retryable `WIP`", "Empty frontier is not completion",
                       "journal.jsonl", "checkpoint.json", "budget-exhausted", "<WAVE_SPEND_LIMIT>",
                       "original deadline", "migration ID/checksum", "<LANE_CUT_COMMAND>",
                       "<PRE_BARRIER_COMMAND>", "attempt 3 is a reduction", "Multi-stage lanes",
                       "never `git revert -m 1`", "<DEPLOY_BRANCH>", '"type": "phase"', "review_wait", "owner_wait"]:
            self.assertIn(clause, " ".join(loop.split()))
        conventions = (LOOP / "assets/build-conventions.template.md").read_text()
        for clause in ["## Seats", "`build-monitor`", "isolation: 'worktree'"]:
            self.assertIn(clause, conventions)
        for name in ["interview.md", "loop-anatomy.md"]:
            self.assertIn("Empty frontier is not done", " ".join((LOOP / "references" / name).read_text().split()))
        drills = (SKILL / "references/recovery.md").read_text()
        for clause in ["Builder dies", "Migration applied", "Commit succeeds", "Deploy accepted",
                       "exhausted spend/deadline", "Seeded scoreboard", "restore into a disposable",
                       "Red barrier after an excluded lane", "Residual excluded schema"]:
            self.assertIn(clause, drills)


class KeepAliveHook(unittest.TestCase):
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


class PhaseTimings(unittest.TestCase):
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
