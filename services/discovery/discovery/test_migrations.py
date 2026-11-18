"""Prove the SQL-safe URL migration preserves populated rows."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UrlMigrationTests(TransactionTestCase):
    def test_populated_link_survives_digest_backfill(self):
        previous = [('discovery', '0011_eventcard')]
        executor = MigrationExecutor(connection)
        current = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            old = executor.loader.project_state(previous).apps
            dj = old.get_model('discovery', 'DJProfile').objects.create(name='Archive DJ', description='Test')
            link = old.get_model('discovery', 'DJMediaLink').objects.create(
                dj=dj, title='Recording', url='https://example.org/old', kind='track', platform='youtube')
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            new = executor.loader.project_state(current).apps
            saved = new.get_model('discovery', 'DJMediaLink').objects.get(pk=link.pk)
            self.assertEqual((saved.title, saved.url, saved.dj_id), ('Recording', 'https://example.org/old', dj.pk))
            self.assertEqual(len(saved.url_digest), 64)
        finally:
            MigrationExecutor(connection).migrate(current)
        from discovery.models import DJMediaLink
        long_url = 'https://example.org/'+'a'*1800
        added = DJMediaLink.objects.create(dj_id=dj.pk, title='Long URL', url=long_url, kind='track', platform='youtube')
        self.assertEqual(DJMediaLink.objects.get(pk=added.pk).url, long_url)
