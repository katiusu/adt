#!/usr/bin/env python3
"""Functional tests for the repo-knowledge CLI end to end.

Runnable from the repository root:

    python3 -m unittest discover -s tools/repo_knowledge/tests -p 'test_*.py' -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOL_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.repo_knowledge import cli, core
from tools.repo_knowledge.tests.test_core import make_git_repo


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_git_repo(self.root)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/example/demo.git"],
            cwd=self.root, check=True, capture_output=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_cli(self, *args: str) -> int:
        return cli.main(["--root", str(self.root), *args])

    def test_init_creates_skeleton(self) -> None:
        rc = self.run_cli("init")
        self.assertEqual(rc, 0)
        self.assertTrue((self.root / ".repo" / "project.yaml").exists())
        self.assertTrue((self.root / ".repo" / "events").is_dir())
        state = core.load_yaml(self.root / ".repo" / "project.yaml")
        self.assertEqual(state["repository"], "example/demo")
        self.assertEqual(state["project_id"], "demo")

    def test_init_is_idempotent(self) -> None:
        self.assertEqual(self.run_cli("init"), 0)
        before = (self.root / ".repo" / "project.yaml").read_text()
        self.assertEqual(self.run_cli("init"), 0)
        after = (self.root / ".repo" / "project.yaml").read_text()
        self.assertEqual(before, after)

    def test_collect_records_build_and_test_events(self) -> None:
        self.run_cli("init")
        rc = self.run_cli(
            "collect", "--build-status", "passed", "--build-run-id", "run-1",
            "--test-status", "passed", "--test-summary", "10/10 passed",
        )
        self.assertEqual(rc, 0)
        state = core.load_yaml(self.root / ".repo" / "project.yaml")
        self.assertEqual(state["build"]["status"], "passed")
        self.assertEqual(state["test"]["summary"], "10/10 passed")
        events = list((self.root / ".repo" / "events").glob("*.yaml"))
        kinds = {core.load_yaml(p)["kind"] for p in events}
        self.assertIn("build", kinds)
        self.assertIn("test", kinds)
        # No "commit" event: init() already captured this same HEAD, so collect() sees no
        # new commit since then (see test_collect_records_new_commit_event below).

    def test_collect_records_new_commit_event(self) -> None:
        self.run_cli("init")
        (self.root / "file2.txt").write_text("more\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "second commit"], cwd=self.root,
            check=True, capture_output=True,
        )
        self.run_cli("collect")
        events = list((self.root / ".repo" / "events").glob("*.yaml"))
        kinds = {core.load_yaml(p)["kind"] for p in events}
        self.assertIn("commit", kinds)

    def test_failed_build_does_not_erase_prior_success(self) -> None:
        self.run_cli("init")
        self.run_cli("collect", "--build-status", "passed", "--build-run-id", "run-1")
        self.run_cli("collect", "--build-status", "failed", "--build-run-id", "run-2")
        state = core.load_yaml(self.root / ".repo" / "project.yaml")
        self.assertEqual(state["build"]["status"], "failed")
        self.assertIsNotNone(state["last_successful_build"])
        self.assertEqual(state["last_successful_build"]["run_id"], "run-1")

    def test_sync_writes_status_markdown_and_sync_event(self) -> None:
        self.run_cli("init")
        rc = self.run_cli("sync", "--ci", "--build-status", "passed", "--test-status", "passed")
        self.assertEqual(rc, 0)
        status_md = self.root / ".repo" / "STATUS.md"
        self.assertTrue(status_md.exists())
        self.assertIn("GENERATED", status_md.read_text())
        state = core.load_yaml(self.root / ".repo" / "project.yaml")
        self.assertEqual(state["sync"]["source"], "ci")
        events = [core.load_yaml(p) for p in (self.root / ".repo" / "events").glob("*.yaml")]
        self.assertTrue(any(e["kind"] == "sync" for e in events))

    def test_sync_succeeds_even_when_build_failed(self) -> None:
        self.run_cli("init")
        rc = self.run_cli("sync", "--ci", "--build-status", "failed")
        self.assertEqual(rc, 0)
        state = core.load_yaml(self.root / ".repo" / "project.yaml")
        self.assertEqual(state["build"]["status"], "failed")
        self.assertEqual(state["sync"]["status"], "ok")

    def test_verify_passes_on_valid_state(self) -> None:
        # copy the real schemas in so verify (which reads <root>/schemas/...) has them
        schemas_src = REPO_ROOT / "schemas"
        schemas_dst = self.root / "schemas"
        schemas_dst.mkdir()
        for name in ("project-registry.schema.json", "project-event.schema.json"):
            (schemas_dst / name).write_text((schemas_src / name).read_text())
        self.run_cli("init")
        self.run_cli("collect", "--build-status", "passed", "--test-status", "passed")
        rc = self.run_cli("verify")
        self.assertEqual(rc, 0)

    def test_verify_fails_on_missing_project_yaml(self) -> None:
        (self.root / "schemas").mkdir()
        for name in ("project-registry.schema.json", "project-event.schema.json"):
            (self.root / "schemas" / name).write_text(
                (REPO_ROOT / "schemas" / name).read_text()
            )
        rc = self.run_cli("verify")
        self.assertEqual(rc, 1)

    def test_status_reports_missing_state(self) -> None:
        rc = self.run_cli("status")
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
