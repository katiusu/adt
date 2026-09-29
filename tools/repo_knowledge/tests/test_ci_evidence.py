import unittest

from tools.repo_knowledge.ci_evidence import derive, normalize_run_conclusion


class CIEvidenceTests(unittest.TestCase):
    def run_fixture(self,conclusion='failure'):
        return {'id':123,'run_attempt':2,'head_sha':'a'*40,'updated_at':'2026-09-27T00:00:00Z','conclusion':conclusion,'name':'Fixture CI'}
    def test_packaging_failure_is_not_hidden_by_passing_test(self):
        r=derive(self.run_fixture(),[{'steps':[{'name':'Tests','conclusion':'success','completed_at':'2026-09-26T23:59:00Z'}]}],'Tests')
        self.assertEqual(r['build_status'],'failed');self.assertEqual(r['test_status'],'passed')
        self.assertEqual(r['run_id'],'123');self.assertEqual(r['run_attempt'],'2')
        self.assertEqual(r['build_conclusion'],'failure');self.assertEqual(r['test_conclusion'],'success')
    def test_skipped_check_is_unknown_not_failed(self):
        r=derive(self.run_fixture(),[{'steps':[{'name':'Tests','conclusion':'skipped'}]}],'Tests')
        self.assertEqual(r['test_status'],'unknown')
        self.assertEqual(r['test_conclusion'],'skipped')
    def test_setup_only_does_not_create_test_success(self):
        r=derive(self.run_fixture('success'),[{'steps':[{'name':'Setup','conclusion':'success'}]}],'Tests')
        self.assertEqual(r['test_status'],'unknown')
    def test_ambiguous_test_step_rejected(self):
        with self.assertRaises(ValueError):derive(self.run_fixture(),[{'steps':[{'name':'Tests'}]},{'steps':[{'name':'Tests'}]}],'Tests')
    def test_normalize_run_conclusion_preserves_distinct_outcomes(self):
        self.assertEqual(normalize_run_conclusion('success'), 'passed')
        self.assertEqual(normalize_run_conclusion('failure'), 'failed')
        self.assertEqual(normalize_run_conclusion('cancelled'), 'cancelled')
        self.assertEqual(normalize_run_conclusion('skipped'), 'skipped')
        self.assertEqual(normalize_run_conclusion('timed_out'), 'timed_out')
        self.assertEqual(normalize_run_conclusion(None), 'unknown')
