"""Recovery/scope tests with fake Azure only; never exercise production in CI."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import live_release as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            'RUNNER_TEMP': self.temp.name, 'GITHUB_ACTIONS': 'true',
            'GITHUB_REF': 'refs/heads/main', 'GITHUB_REPOSITORY': 'xanman04/devops_assignment',
            'GITHUB_RUN_ID': '123', 'GITHUB_SHA': 'a'*40, 'PREFIX': 'student',
            'RESOURCE_GROUP': 'rg-student', 'ARM_SUBSCRIPTION_ID': '00000000-0000-0000-0000-000000000001'})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_scope_refuses_feature_branch_and_other_group_or_service(self):
        for key, value in [('GITHUB_REF', 'refs/heads/feature'), ('RESOURCE_GROUP', 'other-group')]:
            with patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                release.context()
        with self.assertRaises(ValueError): release.endpoint('other-students-app')

    @patch('live_release.lifecycle', side_effect=RuntimeError('ambiguous remote response'))
    def test_stop_records_recovery_before_request_and_refuses_second_stop(self, lifecycle):
        release.write('restore-required.json', [])
        with self.assertRaises(RuntimeError): release.stop('groups')
        self.assertEqual(release.read('restore-required.json'), ['groups'])
        with self.assertRaises(ValueError): release.stop('discovery')
        self.assertEqual(lifecycle.call_count, 1)

    @patch('live_release.lifecycle')
    @patch('live_release.running', return_value='Stopped')
    def test_restore_restarts_owned_service_without_querying_new_main_head(self, running, lifecycle):
        release.write('restore-required.json', ['discovery'])
        release.restore()
        lifecycle.assert_called_once_with('discovery', 'start')
        self.assertEqual(release.read('restore-required.json'), [])

    @patch('live_release.lifecycle', side_effect=RuntimeError('start failed'))
    @patch('live_release.running', return_value='Stopped')
    def test_failed_recovery_retains_obligation(self, running, lifecycle):
        release.write('restore-required.json', ['groups'])
        with self.assertRaises(RuntimeError): release.restore()
        self.assertEqual(release.read('restore-required.json'), ['groups'])

    @patch('live_release.time.sleep')
    @patch('live_release.lifecycle')
    @patch('live_release.running', side_effect=['Stopping', 'Stopped'])
    def test_recovery_waits_for_inflight_stop_before_start(self, running, lifecycle, sleep):
        release.ensure_running('groups')
        sleep.assert_called_once_with(5)
        lifecycle.assert_called_once_with('groups', 'start')

    @patch('live_release.az')
    def test_firewall_recovery_refuses_unexpected_marker(self, azure):
        release.write('firewall.json', {'rule': 'someone-elses-rule'})
        with self.assertRaises(ValueError): release.cleanup_firewall()
        azure.assert_not_called()

    @patch('live_release.az', return_value=[])
    def test_firewall_cleanup_is_idempotent_after_failed_create(self, azure):
        release.write('firewall.json', {'rule': 'student-verify-123'})
        release.cleanup_firewall()
        self.assertFalse((release.directory()/'firewall.json').exists())
        self.assertEqual(azure.call_count, 1)

    def migration_fixture(self):
        baseline = json.loads((release.ROOT/'evidence/azure/2026-11-23-before-slug-migration.json').read_text(encoding='utf-8'))
        release.write('configuration.json', {'sha': 'a'*40, 'urls': {'discovery': 'https://example.invalid'}})
        release.write('fixture.json', {'migrations': [
            {'name': name, 'applied_at': '2026-11-23T12:00:00+00:00'}
            for name in ('0014_genrecategory_slug', '0015_genrecategory_slug_unique')]})
        return [{'id': x['id'], 'name': x['name'], 'slug': 'genre-'+str(x['id'])} for x in baseline['genre_categories']]

    def test_migration_audit_requires_retained_rows_unique_slugs_and_applied_records(self):
        rows = self.migration_fixture()
        with patch('live_release.urlopen', return_value=io.BytesIO(json.dumps({'categories': rows}).encode())):
            release.audit_migration()
        self.assertEqual(len(release.read('migration-audit.json')['preserved_categories']), len(rows))
        for changed in (rows[1:], [dict(x, slug='duplicate') for x in rows]):
            with patch('live_release.urlopen', return_value=io.BytesIO(json.dumps({'categories': changed}).encode())):
                with self.assertRaises(ValueError): release.audit_migration()
        release.write('fixture.json', {'migrations': []})
        with patch('live_release.urlopen', return_value=io.BytesIO(json.dumps({'categories': rows}).encode())):
            with self.assertRaises(ValueError): release.audit_migration()


if __name__ == '__main__': unittest.main()
