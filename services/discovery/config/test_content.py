"""Public projections must never bypass unpublished-event visibility."""
from datetime import timedelta
from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from discovery import services
from discovery.models import DJProfile, GenreListeningReference


class ContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('curator', password='test-only')
        cls.category = services.save_category(actor=cls.admin, data={
            'name': 'House', 'color': '#aa3311', 'description': 'House music'})
        cls.venue = services.save_venue(actor=cls.admin, review_status='approved', data={
            'name': 'Madrid club', 'latitude': '40.400000', 'longitude': '-3.700000', 'timezone': 'Europe/Madrid'})
        start = timezone.now() + timedelta(days=2)
        cls.event = services.save_event(actor=cls.admin, category_ids=[cls.category.pk], data={
            'venue': cls.venue, 'title': 'A <special> night', 'description': 'Original description',
            'starts_at': start, 'ends_at': start + timedelta(hours=3)})
        cls.artist = DJProfile.objects.create(name='Artist', description='Biography', photo='djs/test.webp')
        cls.artist.categories.add(cls.category)
        cls.event.performers.add(cls.artist)
        ref = GenreListeningReference.objects.create(title='Sample', artist_credit='Artist',
            url='https://soundcloud.com/example/track', kind='track')
        ref.categories.add(cls.category)

    def test_search_filter_detail_and_no_private_fields(self):
        result = self.client.get('/api/browse/', {'q': 'Madrid'}).json()
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['events'][0]['title'], 'A <special> night')
        self.assertEqual(self.client.get('/api/browse/', {'q': 'absent'}).json()['events'], [])
        self.assertEqual(self.client.get('/api/browse/', {'category': 'bad'}).status_code, 400)
        detail = self.client.get(f'/api/events/{self.event.pk}/content/').json()
        self.assertEqual(detail['samples'][0]['title'], 'Sample')
        self.assertEqual(detail['performers'][0]['id'], self.artist.pk)
        for private in ('creator', 'email', 'review_note', 'poster'):
            self.assertNotIn(private, detail)
        self.assertEqual(self.client.get(f'/api/events/{self.event.pk}/poster/').status_code, 404)

    def test_browse_filters_by_day_window_and_subgenre(self):
        day = self.event.starts_at.date()
        window = lambda **query: self.client.get('/api/browse/', query)
        self.assertEqual(len(window(**{'from': day.isoformat(), 'to': day.isoformat()}).json()['events']), 1)
        self.assertEqual(window(**{'from': (day + timedelta(days=1)).isoformat()}).json()['events'], [])
        self.assertEqual(window(**{'to': (day - timedelta(days=1)).isoformat()}).json()['events'], [])
        for bad in ({'from': '2026-13-40'}, {'to': 'tomorrow'}, {'from': '2026-12-02', 'to': '2026-12-01'}, {'tag': 'x'}):
            self.assertEqual(window(**bad).status_code, 400, bad)
        tag = services.save_tag(actor=self.admin, data={'category': self.category, 'name': 'Deep', 'description': 'Deeper'})
        self.assertEqual(window(tag=tag.pk).json()['events'], [])
        self.event.tags.add(tag)
        self.assertEqual(len(window(tag=tag.pk).json()['events']), 1)

    def test_genre_is_reachable_by_stable_slug(self):
        self.assertEqual(self.category.slug, 'house')
        by_id = self.client.get(f'/api/genres/{self.category.pk}/').json()
        by_slug = self.client.get('/api/genres/slug/house/').json()
        self.assertEqual(by_slug, by_id)
        self.assertEqual(by_slug['slug'], 'house')
        self.assertEqual(self.client.get('/api/genres/slug/absent/').status_code, 404)
        listed = [c['slug'] for c in self.client.get('/api/genres/').json()['categories']]
        self.assertIn('house', listed)
        card = self.client.get('/api/browse/').json()['events'][0]['categories'][0]
        self.assertEqual(card['slug'], 'house')

    def test_new_categories_get_unique_slugs_and_keep_them_when_renamed(self):
        other = services.save_category(actor=self.admin, data={'name': 'house!', 'color': '#112233', 'description': 'x'})
        self.assertEqual(other.slug, 'house-2')
        other.name = 'Deep House'
        other.save()
        other.refresh_from_db()
        self.assertEqual(other.slug, 'house-2')

    def test_unpublished_event_is_absent_everywhere(self):
        self.event.moderation_hidden = True
        self.event.save()
        self.assertEqual(self.client.get('/api/browse/').json()['events'], [])
        self.assertEqual(self.client.get(f'/api/events/{self.event.pk}/content/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/events/{self.event.pk}/poster/').status_code, 404)
        artist = self.client.get(f'/api/artists/{self.artist.pk}/').json()
        self.assertEqual(artist['events'], [])

    def test_artist_and_genre_contracts_and_missing_records(self):
        self.assertEqual(self.client.get('/api/artists/').json()['artists'][0]['photo'], 'djs/test.webp')
        genre = self.client.get(f'/api/genres/{self.category.pk}/').json()
        self.assertEqual(genre['samples'][0]['tag_ids'], [])
        self.assertEqual(genre['artists'][0]['name'], 'Artist')
        self.assertEqual(self.client.get('/api/artists/999999/').status_code, 404)
        self.assertEqual(self.client.post('/api/browse/').status_code, 405)

    def test_curated_content_seed_is_repeatable(self):
        call_command('seed_discovery', stdout=StringIO())
        counts = (DJProfile.objects.count(), GenreListeningReference.objects.count())
        self.assertGreater(counts[0], 1)
        self.assertGreater(counts[1], 100)
        call_command('seed_discovery', stdout=StringIO())
        self.assertEqual(counts, (DJProfile.objects.count(), GenreListeningReference.objects.count()))
