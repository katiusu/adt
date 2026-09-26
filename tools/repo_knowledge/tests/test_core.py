#!/usr/bin/env python3
"""Self-tests for tools/repo_knowledge/core.py.

Runnable from the repository root:

    python3 -m unittest discover -s tools/repo_knowledge/tests -p 'test_*.py' -v

All fixtures are throwaway git repositories under a temp directory; nothing here touches the
real SKB repository's own .repo/.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1]  # tools/repo_knowledge
REPO_ROOT = TOOL_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.repo_knowledge import core


def make_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    run = lambda *args: subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True)
    run("init", "-q", "-b", "main")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-q", "-m", "initial commit")


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_git_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_get_head_returns_real_commit(self) -> None:
        head = core.get_head(self.root)
        self.assertIsNotNone(head["commit"])
        self.assertEqual(len(head["commit"]), 40)
        self.assertEqual(head["branch"], "main")
        self.assertIsNotNone(head["committed_at"])
        self.assertTrue(head["committed_at"].endswith("Z"))

    def test_get_head_on_non_git_dir_is_none(self) -> None:
        # Must be outside self.root: git walks up to a parent .git, so a subdirectory of a
        # real repo is still "in" that repo and would (correctly) return its HEAD.
        with tempfile.TemporaryDirectory() as outside:
            head = core.get_head(Path(outside))
            self.assertIsNone(head["commit"])

    def test_build_project_state_promotes_on_pass(self) -> None:
        state = core.build_project_state(
            self.root, "demo", "owner/demo", "test", "local", existing=None,
            build_status="passed", build_run_id="run-1",
        )
        self.assertEqual(state["build"]["status"], "passed")
        self.assertIsNotNone(state["last_successful_build"])
        self.assertIsNone(state["last_failed_build"])
        self.assertEqual(state["schema_version"], 1)

    def test_failed_build_preserves_prior_success(self) -> None:
        first = core.build_project_state(
            self.root, "demo", "owner/demo", "test", "local", existing=None,
            build_status="passed", build_run_id="run-1",
        )
        second = core.build_project_state(
            self.root, "demo", "owner/demo", "test", "local", existing=first,
            build_status="failed", build_run_id="run-2",
        )
        self.assertEqual(second["build"]["status"], "failed")
        self.assertIsNotNone(second["last_successful_build"])
        self.assertEqual(second["last_successful_build"], first["last_successful_build"])
        self.assertIsNotNone(second["last_failed_build"])
        self.assertEqual(second["last_failed_build"]["run_id"], "run-2")

    def test_unreported_status_keeps_previous_block(self) -> None:
        first = core.build_project_state(
            self.root, "demo", "owner/demo", "test", "local", existing=None,
            build_status="passed", build_run_id="run-1",
        )
        second = core.build_project_state(
            self.root, "demo", "owner/demo", "test", "local", existing=first,
        )
        self.assertEqual(second["build"], first["build"])

    def test_compute_phases_not_configured_by_default(self) -> None:
        phases = core.compute_phases(self.root)
        self.assertEqual(phases["source"], "not_configured")
        self.assertEqual(phases["completed"], [])
        self.assertIsNone(phases["active"])

    def test_compute_phases_from_declared_file_and_tags(self) -> None:
        core.dump_yaml(self.root / ".repo" / "phases.yaml", {
            "phases": [
                {"name": "Foundation", "complete_tag": "phase-foundation-done"},
                {"name": "Device Validation", "complete_tag": "phase-device-done"},
            ]
        })
        phases = core.compute_phases(self.root)
        self.assertEqual(phases["source"], ".repo/phases.yaml")
        self.assertEqual(phases["completed"], [])
        self.assertEqual(phases["active"], "Foundation")
        self.assertEqual(phases["next"], "Device Validation")

        subprocess.run(["git", "tag", "phase-foundation-done"], cwd=self.root, check=True)
        phases = core.compute_phases(self.root)
        self.assertEqual(phases["completed"], ["Foundation"])
        self.assertEqual(phases["active"], "Device Validation")
        self.assertIsNone(phases["next"])

    def test_write_event_idempotent_same_content(self) -> None:
        event = core.make_event("owner/demo", "a" * 40, "build", status="passed", run_id="run-1")
        p1 = core.write_event(self.root, event)
        p2 = core.write_event(self.root, dict(event))
        self.assertEqual(p1, p2)
        self.assertTrue(p1.exists())

    def test_write_event_conflict_raises(self) -> None:
        event = core.make_event("owner/demo", "a" * 40, "build", status="passed", run_id="run-1")
        core.write_event(self.root, event)
        conflicting = dict(event)
        conflicting["status"] = "failed"
        with self.assertRaises(RuntimeError):
            core.write_event(self.root, conflicting)

    def test_render_status_markdown_is_marked_generated(self) -> None:
        state = core.build_project_state(
            self.root, "demo", "owner/demo", "test", "local", existing=None,
        )
        rendered = core.render_status_markdown(state)
        self.assertIn("GENERATED", rendered)
        self.assertIn("owner/demo", rendered)


if __name__ == "__main__":
    unittest.main()
