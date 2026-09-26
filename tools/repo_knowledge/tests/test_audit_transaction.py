"""Audit regressions for stable identities and all-or-nothing state publication."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.repo_knowledge import cli, core
from tools.repo_knowledge.tests.test_core import make_git_repo


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        make_git_repo(self.root)
        subprocess.run(['git','remote','add','origin','https://github.com/example/fixture.git'],cwd=self.root,check=True)
    def tearDown(self):self.tmp.cleanup()
    def call(self,*args):return cli.main(['--root',str(self.root),*args])
    def snapshot(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in (self.root/'.repo').rglob('*') if p.is_file()}
    def test_three_unchanged_runs_have_identical_bytes_and_events(self):
        snapshots=[]
        for i in range(3):
            with patch.object(core,'now_iso',return_value=f'2026-09-27T00:00:0{i}Z'):
                self.call('sync')
            snapshots.append(self.snapshot())
        self.assertEqual(snapshots[0],snapshots[1]);self.assertEqual(snapshots[1],snapshots[2])
    def test_same_ci_run_retry_is_identical(self):
        snapshots=[]
        for i in range(3):
            with patch.object(core,'now_iso',return_value=f'2026-09-27T00:00:0{i}Z'):
                self.call('sync','--ci','--build-status','passed','--build-run-id','fixture-run','--test-status','passed')
            snapshots.append(self.snapshot())
        self.assertEqual(snapshots[0],snapshots[1]);self.assertEqual(snapshots[1],snapshots[2])
    def test_different_attempt_is_distinct_observation(self):
        self.call('sync','--build-status','passed','--build-run-id','fixture-run','--run-attempt','1')
        self.call('sync','--build-status','failed','--build-run-id','fixture-run','--run-attempt','2')
        state=core.load_yaml(self.root/'.repo/project.yaml')
        self.assertEqual(state['build']['run_attempt'],'2')
        self.assertEqual(state['build']['status'],'failed')
        self.assertEqual(state['last_successful_build']['run_id'],'fixture-run')
    def test_conflicting_same_event_does_not_change_any_file(self):
        self.call('sync','--build-status','passed','--build-run-id','fixture-run')
        before=self.snapshot()
        with self.assertRaises(RuntimeError):
            self.call('sync','--build-status','failed','--build-run-id','fixture-run')
        self.assertEqual(before,self.snapshot())
    def test_event_write_exception_does_not_publish_partial_state(self):
        self.call('sync');before=self.snapshot()
        with patch.object(core,'write_event',side_effect=OSError('fixture disk failure')), self.assertRaises(OSError):
            self.call('sync','--build-status','passed')
        self.assertEqual(before,self.snapshot())
    def test_publication_failure_leaves_previous_directory_unchanged(self):
        self.call('sync');before=self.snapshot()
        with patch.object(cli,'_publish',side_effect=OSError('fixture unsupported exchange')), self.assertRaises(OSError):
            self.call('sync','--build-status','passed')
        self.assertEqual(before,self.snapshot())
    def test_invalid_timestamp_is_rejected_before_publication(self):
        self.call('sync');before=self.snapshot()
        with self.assertRaises(ValueError):
            self.call('sync','--build-status','passed','--build-at','not-a-time')
        self.assertEqual(before,self.snapshot())
    def test_explicit_ci_time_and_test_identity_are_preserved(self):
        self.call('sync','--build-status','passed','--build-run-id','run1','--build-at','2026-09-27T00:00:00Z',
                  '--test-status','passed','--test-at','2026-09-27T00:00:01Z')
        state=core.load_yaml(self.root/'.repo/project.yaml')
        self.assertEqual(state['test']['run_id'],'run1')
        self.assertEqual(state['test']['commit'],state['head']['commit'])
        self.assertEqual(state['build']['timestamp_source'],'ci')
    def test_custom_project_identity_survives_plain_sync(self):
        self.call('--project-id','custom-fixture','init');self.call('sync')
        self.assertEqual(core.load_yaml(self.root/'.repo/project.yaml')['project_id'],'custom-fixture')
    def test_identity_migration_is_not_silent(self):
        self.call('sync');before=self.snapshot()
        with self.assertRaises(ValueError):self.call('--repository','example/other','sync')
        self.assertEqual(before,self.snapshot())
    def test_human_phases_file_preserved(self):
        self.call('sync');p=self.root/'.repo/phases.yaml';p.write_text('phases:\n  - name: Human gate\n')
        before=p.read_bytes();self.call('sync');self.assertEqual(p.read_bytes(),before)
    def test_state_only_bot_commit_does_not_churn(self):
        self.call('sync');before=self.snapshot()
        subprocess.run(['git','add','.repo'],cwd=self.root,check=True)
        subprocess.run(['git','commit','-qm','chore(repo-knowledge): fixture publication'],cwd=self.root,check=True)
        self.call('sync');self.assertEqual(before,self.snapshot())
    def test_empty_repository_fails_before_writing_null_state(self):
        with tempfile.TemporaryDirectory() as t:
            subprocess.run(['git','init','-qb','main',t],check=True)
            with self.assertRaises(ValueError):cli.main(['--root',t,'--repository','example/empty','init'])
            self.assertFalse((Path(t)/'.repo').exists())
    def test_explicit_source_allows_only_generated_later_changes(self):
        self.call('sync');source=core.get_head(self.root)['commit']
        subprocess.run(['git','add','.repo'],cwd=self.root,check=True)
        subprocess.run(['git','commit','-qm','publish generated state'],cwd=self.root,check=True)
        self.call('sync','--source-commit',source,'--build-status','passed','--build-run-id','run')
        self.assertEqual(core.load_yaml(self.root/'.repo/project.yaml')['head']['commit'],source)
    def test_explicit_stale_ci_cannot_overwrite_new_source(self):
        source=core.get_head(self.root)['commit'];self.call('sync');before=self.snapshot()
        (self.root/'code.py').write_text('new source\n')
        subprocess.run(['git','add','code.py'],cwd=self.root,check=True)
        subprocess.run(['git','commit','-qm','new source'],cwd=self.root,check=True)
        with self.assertRaises(ValueError):self.call('sync','--source-commit',source)
        self.assertEqual(before,self.snapshot())
