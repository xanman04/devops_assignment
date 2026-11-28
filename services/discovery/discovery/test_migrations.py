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


class GenreSlugMigrationTests(TransactionTestCase):
    """0014/0015 add GenreCategory.slug to a populated table without losing or renumbering rows."""

    def test_populated_categories_keep_ids_and_gain_unique_slugs(self):
        previous = [('discovery', '0013_legacyadminaudit')]
        executor = MigrationExecutor(connection)
        current = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            Category = executor.loader.project_state(previous).apps.get_model('discovery', 'GenreCategory')
            names = ['Dubstep / 140', 'House', 'Drum & Bass', 'Drum + Bass', '///']
            before = {Category.objects.create(name=n, color='#112233', description=f'About {n}', display_order=i).pk: n
                      for i, n in enumerate(names)}
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            Migrated = executor.loader.project_state(current).apps.get_model('discovery', 'GenreCategory')
            after = {c.pk: c for c in Migrated.objects.all()}
            self.assertEqual({pk: c.name for pk, c in after.items()}, before)
            self.assertTrue(all(c.description == f'About {c.name}' and c.color == '#112233' for c in after.values()))
            slugs = {c.name: c.slug for c in after.values()}
            self.assertEqual(slugs['Dubstep / 140'], 'dubstep-140')
            self.assertEqual(slugs['House'], 'house')
            self.assertEqual(slugs['Drum & Bass'], 'drum-bass')
            self.assertEqual(slugs['Drum + Bass'], 'drum-bass-2')  # collision gets a numeric suffix
            self.assertEqual(slugs['///'], 'genre')  # nothing slug-safe falls back to a fixed word
            self.assertEqual(len(set(slugs.values())), len(names))
        finally:
            MigrationExecutor(connection).migrate(current)


class GenreTagSlugMigrationTests(TransactionTestCase):
    """0017/0018 add GenreTag.slug to a populated table without losing or renumbering rows."""

    def test_populated_subgenres_keep_their_rows_and_gain_unique_slugs(self):
        previous = [('discovery', '0016_report_hide_permission')]
        executor = MigrationExecutor(connection)
        current = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            old = executor.loader.project_state(previous).apps
            Category = old.get_model('discovery', 'GenreCategory')
            Tag = old.get_model('discovery', 'GenreTag')
            parents = [Category.objects.create(name=n, slug=n.lower(), color='#112233', description=n)
                       for n in ('House', 'Techno')]
            rows = [(parents[0], 'Deep House'), (parents[0], 'Minimal'), (parents[1], 'Minimal'), (parents[1], '///')]
            before = {Tag.objects.create(category=c, name=n, description=f'About {n}', bpm_min=100, bpm_max=130).pk:
                      (c.pk, n, f'About {n}', 100, 130) for c, n in rows}
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            Migrated = executor.loader.project_state(current).apps.get_model('discovery', 'GenreTag')
            after = list(Migrated.objects.order_by('pk'))
            self.assertEqual({t.pk: (t.category_id, t.name, t.description, t.bpm_min, t.bpm_max) for t in after}, before)
            # The same name under two genres gets a suffix; a name with nothing slug-safe uses the fallback.
            self.assertEqual([t.slug for t in after], ['deep-house', 'minimal', 'minimal-2', 'subgenre'])
        finally:
            MigrationExecutor(connection).migrate(current)
